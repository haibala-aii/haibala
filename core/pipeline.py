"""
haibala · M3 · core/pipeline.py
===============================
【这一课：状态机 + 断点续跑（agent 可靠性的核心）】
M1/M2 的闭环是"一口气跑完"。真实 agent 跑几十上百步，很可能中途崩/被打断。
M3 把任务拆成多个**阶段(state)**，每做完一阶段就把中间结果**写入断点**。
一旦中断，下一轮从断点继续，**不重做已经完成的昂贵步骤**（抽取/决策/派活）。

阶段：observe -> decide -> dispatch -> judge -> learn
每次推进存 checkpoint；stop_after 参数可模拟"在某个阶段故意中断"来演示 resume。

剩下仍是：observe -> decide -> 同场比试 -> judge -> 写入案例/画像 -> 安全审批。
"""
from core.features import extract_features
from core import store, config
from judge.base import DEFAULT_RUBRIC
from judge.mock import MockJudge
from learn import router
from workers import registry

STAGES = ["observe", "decide", "dispatch", "judge", "learn"]
SENSITIVE_WORDS = ["发邮件", "写库", "删除", "对外", "外发", "支付", "发布", "写文件到外部", "部署到生产"]

class Interrupt(Exception):
    """用于模拟"任务被打断/崩溃"，验证断点续跑。"""

def _make_judge():
    if config.JUDGE_PROVIDER == "api" and config.JUDGE_API_KEY:
        from judge.api import ApiJudge
        return ApiJudge()
    return MockJudge()

def _is_sensitive(text):
    return any(w in text for w in SENSITIVE_WORDS)

# ---------------- 各阶段（state 是断点 dict）----------------
def do_observe(state):
    state["features"] = extract_features(state.get("description") or state.get("title", ""))

def do_decide(state):
    state["decision"] = router.decide(state["features"], registry.worker_names())

def do_dispatch(state):
    # 昂贵步骤：真正调用每个 worker 干活（断点续跑会跳过它）
    jobs = []
    for name in registry.worker_names():
        worker = registry.get_worker(name)
        if worker is None:
            continue
        try:
            art = worker.submit(state.get("description") or state.get("title", ""))
        except Exception as ex:
            from workers.mock import MockWorker
            art = MockWorker(name, worker.capability).submit(
                state.get("description") or state.get("title", ""))
            art.detail = f"（真实命令不可用，回退 mock：{ex}）"
        jobs.append({"worker": name, "cost_usd": art.cost_usd,
                     "latency_ms": art.latency_ms, "detail": art.detail[:1500],
                     "capability": getattr(worker, "capability", [])})
    state["artifacts"] = jobs

def do_judge(state):
    judge = _make_judge()
    board = []
    for a in state.get("artifacts", []):
        proxy = _ArtifactProxy(name=a["worker"], detail=a.get("detail", ""),
                               cost=a.get("cost_usd", 0), latency=a.get("latency_ms", 0),
                               capability=a.get("capability", []))
        try:
            ev = judge.score(DEFAULT_RUBRIC, proxy, {"features": state["features"]})
        except Exception:
            ev = MockJudge().score(DEFAULT_RUBRIC, proxy, {"features": state["features"]})
        board.append({"worker": a["worker"], "weighted": round(ev.weighted, 2),
                      "scores": ev.scores, "rationale": ev.rationale,
                      "cost_usd": a.get("cost_usd"), "latency_ms": a.get("latency_ms")})
        # 持久化每次打分（供 Agent 画像/榜单聚合）
        store.add_evaluation(state["job_id"], a["worker"], ev.scores,
                             round(ev.weighted, 2), ev.rationale, ev.judge)
    state["leaderboard"] = board

def do_learn(state):
    best = max(state["leaderboard"], key=lambda x: x["weighted"])
    decision = state["decision"]
    true_best = dict(decision); true_best["worker"] = best["worker"]
    true_best["reason"] = "实例评测：该 worker 得分最高"

    # 提取"经验/教训"（RAG 案例库存的不只是分数，还有踩坑）
    pitfalls = []
    for a in state.get("artifacts", []):
        if "回退 mock" in a.get("detail", ""):
            pitfalls.append(f"{a['worker']} 真实命令不可用→回退 mock")
    if best["cost_usd"] > config.APPROVAL_COST_THRESHOLD:
        pitfalls.append(f"该任务成本 ${best['cost_usd']} 偏高")
    if state["features"].get("multimodal"):
        pitfalls.append("多模态任务注意视觉质量与人工抽检")

    store.add_case(state["features"]["task_type"], state["features"], true_best,
                   best["weighted"], best["cost_usd"], pitfalls="；".join(pitfalls))

    # L2 学习：用"实际最强 worker + 得分"更新路由策略（举一反三）
    from learn.policy import load_policy, save_policy
    policy = load_policy(registry.worker_names())
    policy.update(state["features"], best["worker"], best["weighted"])
    save_policy(policy)
    store.add_audit("system", "learn", f"策略已学习：{best['worker']} 在 {state['features']['task_type']} 类得分 {best['weighted']}（累计 {policy.history} 次）", state["job_id"])

    approvals = []
    sens = _is_sensitive(state.get("description") or state.get("title", ""))
    if sens:
        approvals.append({"action": "敏感操作", "reason": "任务涉及敏感动作，需盖章"})
    if best["cost_usd"] > config.APPROVAL_COST_THRESHOLD:
        approvals.append({"action": "高成本", "reason": f"花费 ${best['cost_usd']} 超阈值"})
    status = "awaiting_approval" if approvals else "done"
    for a in approvals:
        a["job_id"] = state["job_id"]; a["worker"] = best["worker"]
        a["id"] = store.add_approval(state["job_id"], best["worker"], a["action"], a["reason"])
        store.add_audit("system", "approval", f"{a['action']} 待盖章：{a['reason']}", state["job_id"])
    state["best_worker"] = best["worker"]; state["best_weighted"] = best["weighted"]
    state["status"] = status; state["approvals"] = approvals
    store.update_job_status(state["job_id"], status)

_STAGE_FN = {"observe": do_observe, "decide": do_decide, "dispatch": do_dispatch,
             "judge": do_judge, "learn": do_learn}

def _advance(job_id, state, start_idx, stop_after):
    """从 start_idx 依次执行到结束；每阶段写断点；stop_after 处模拟中断。"""
    for i in range(start_idx, len(STAGES)):
        stage = STAGES[i]
        _STAGE_FN[stage](state)
        store.save_job_state(job_id, stage, state)
        store.add_audit("system", stage, f"完成阶段 {stage}", job_id)
        if stop_after == stage:
            store.update_job_status(job_id, "interrupted")
            raise Interrupt(f"在阶段 {stage} 被中断（演示断点续跑）")
    store.clear_job_state(job_id)
    store.update_job_status(job_id, state.get("status", "done"))

def run_task(title: str, description: str = "", stop_after=None) -> dict:
    """跑一个新任务；stop_after 用于教学演示"故意中断"。"""
    store.init_db()
    job_id = store.create_job(title, description, "", {}, {})
    state = {"job_id": job_id, "title": title, "description": description}
    do_observe(state); _apply_job_fields(job_id, state)
    do_decide(state); store.update_job_decision(job_id, state["decision"])
    store.save_job_state(job_id, "decide", state)
    _advance(job_id, state, 2, stop_after)   # 从 dispatch 阶段开始
    return _summary(state)

def resume_task(job_id: str) -> dict:
    """从断点恢复：不重做已完成阶段，接着跑。"""
    store.init_db()
    st = store.get_job_state(job_id)
    if not st:
        raise RuntimeError(f"没有可恢复的断点：{job_id}")
    state = st["checkpoint"]
    state["job_id"] = job_id
    state["_resumed_from"] = st["stage"]
    last = st["stage"]
    start_idx = STAGES.index(last) + 1 if last in STAGES else 0
    store.add_audit("user", "resume", f"从阶段 {last} 恢复，继续 {STAGES[start_idx:]}", job_id)
    _advance(job_id, state, start_idx, None)
    return _summary(state)

def _apply_job_fields(job_id, state):
    f = state["features"]
    store.update_job_meta(job_id, task_type=f["task_type"], features=f)

def _summary(state):
    return {
        "job_id": state["job_id"], "title": state.get("title"),
        "features": state.get("features"),
        "recommended_decision": state.get("decision"),
        "leaderboard": sorted(state.get("leaderboard", []), key=lambda x: -x["weighted"]),
        "best_worker": state.get("best_worker"),
        "best_weighted": state.get("best_weighted"),
        "approvals_needed": state.get("approvals", []),
        "status": state.get("status"),
        "resumed_from": state.get("_resumed_from"),
    }

class _ArtifactProxy:
    """给 judge 用的轻量产物（从断点恢复时，产物以 dict 形式存在 state 里）。"""
    def __init__(self, name, detail, cost, latency, capability=None):
        import uuid as _u
        self.id = f"art-{_u.uuid4().hex[:6]}"
        self.meta = {"name": name, "capability": capability or []}
        self.detail = detail
        self.cost_usd = cost
        self.latency_ms = latency
