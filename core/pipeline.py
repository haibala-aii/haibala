"""
haibala 闭环：先观察+决策并停住，你盖章后再派活。
阶段：observe -> decide -> (等人盖章) -> dispatch -> judge -> learn
"""
from pathlib import Path
from core.features import extract_features
from core import store, config
from judge.base import DEFAULT_RUBRIC
from judge.mock import MockJudge
from learn import router
from workers import registry

ROOT = Path(__file__).resolve().parent.parent
STAGES = ["observe", "decide", "dispatch", "judge", "learn"]
SENSITIVE_WORDS = ["发邮件", "写库", "删除", "对外", "外发", "支付", "发布", "写文件到外部", "部署到生产"]


class Interrupt(Exception):
    """演示断点续跑。"""


def _make_judge():
    if config.JUDGE_PROVIDER == "api" and config.JUDGE_API_KEY:
        from judge.api import ApiJudge
        return ApiJudge()
    return MockJudge()


def _is_sensitive(text):
    return any(w in (text or "") for w in SENSITIVE_WORDS)


def do_observe(state):
    state["features"] = extract_features(state.get("description") or state.get("title", ""))
    state["sensitive"] = _is_sensitive(state.get("description") or state.get("title", ""))


def do_decide(state):
    decision = router.decide(state["features"], registry.worker_names())
    if state.get("budget_usd") is not None:
        decision["budget_usd"] = float(state["budget_usd"])
    elif not decision.get("budget_usd"):
        decision["budget_usd"] = config.BUDGET_DEFAULT
    state["decision"] = decision


def _run_one_worker(state, name):
    worker = registry.get_worker(name)
    if worker is None:
        return None
    ws = ROOT / "runs" / state["job_id"] / name
    ws.mkdir(parents=True, exist_ok=True)
    task = state.get("description") or state.get("title", "")
    try:
        art = worker.submit(task, workspace=str(ws))
    except Exception as ex:
        from workers.mock import MockWorker
        cap = getattr(worker, "capability", [])
        art = MockWorker(name, cap).submit(task, workspace=str(ws))
        art.detail = f"（真实命令不可用，回退 mock：{ex}）\n" + (art.detail or "")
    return {
        "worker": name,
        "status": art.status,
        "cost_usd": art.cost_usd,
        "latency_ms": art.latency_ms,
        "detail": (art.detail or "")[:1500],
        "summary": art.summary,
        "capability": getattr(worker, "capability", []),
        "kind": getattr(worker, "kind", ""),
        "artifact_path": str(ws),
    }


def do_dispatch(state):
    mode = state.get("dispatch_mode") or "dispatch"
    chosen = (state.get("decision") or {}).get("worker") or "mock"
    names = list(registry.worker_names()) if mode == "benchmark" else [chosen]
    if chosen not in registry.worker_names() and mode != "benchmark":
        names = [registry.worker_names()[0]] if registry.worker_names() else []

    store.clear_subtasks(state["job_id"])
    jobs = []
    pending_manual = False

    if mode == "benchmark":
        auto_names = []
        for name in names:
            w = registry.get_worker(name)
            if w is None:
                continue
            if getattr(w, "kind", "") == "manual":
                store.add_subtask(state["job_id"], f"手动 · {name}", name, 90, "skipped")
                continue
            auto_names.append(name)
        for i, name in enumerate(auto_names):
            store.add_subtask(state["job_id"], f"比试 · {name}", name, i, "running")
            row = _run_one_worker(state, name)
            if row:
                jobs.append(row)
        store.set_subtasks_status(state["job_id"], "done")
    else:
        w = registry.get_worker(chosen)
        kind = getattr(w, "kind", "") if w else ""
        titles = (state.get("decision") or {}).get("priority_order") or ["main"]
        if not state.get("decision", {}).get("split"):
            titles = ["主任务"]
        for i, title in enumerate(titles):
            store.add_subtask(state["job_id"], str(title), chosen, i, "running")
        row = _run_one_worker(state, chosen)
        if row:
            jobs.append(row)
            if row.get("status") == "pending_manual" or kind == "manual":
                pending_manual = True
                store.set_subtasks_status(state["job_id"], "awaiting_manual", row.get("artifact_path"))
            else:
                store.set_subtasks_status(state["job_id"], "done", row.get("artifact_path"))

    state["artifacts"] = jobs
    if pending_manual:
        state["status"] = "awaiting_manual"


def do_judge(state):
    judge = _make_judge()
    board = []
    for a in state.get("artifacts", []):
        if a.get("status") == "pending_manual":
            continue
        proxy = _ArtifactProxy(
            name=a["worker"], detail=a.get("detail", ""),
            cost=a.get("cost_usd", 0), latency=a.get("latency_ms", 0),
            capability=a.get("capability", []),
        )
        try:
            ev = judge.score(DEFAULT_RUBRIC, proxy, {"features": state["features"]})
        except Exception:
            ev = MockJudge().score(DEFAULT_RUBRIC, proxy, {"features": state["features"]})
        board.append({
            "worker": a["worker"], "weighted": round(ev.weighted, 2),
            "scores": ev.scores, "rationale": ev.rationale,
            "cost_usd": a.get("cost_usd"), "latency_ms": a.get("latency_ms"),
        })
        store.add_evaluation(state["job_id"], a["worker"], ev.scores,
                             round(ev.weighted, 2), ev.rationale, ev.judge)
    state["leaderboard"] = board


def do_learn(state):
    board = state.get("leaderboard") or []
    if not board:
        state["status"] = state.get("status") or "done"
        store.update_job_status(state["job_id"], state["status"])
        return
    best = max(board, key=lambda x: x["weighted"])
    decision = dict(state["decision"])
    true_best = dict(decision)
    true_best["worker"] = best["worker"]
    true_best["reason"] = "实例评测：该 worker 得分最高"

    pitfalls = []
    for a in state.get("artifacts", []):
        if "回退 mock" in (a.get("detail") or ""):
            pitfalls.append(f"{a['worker']} 真实命令不可用→回退 mock")
    if (best.get("cost_usd") or 0) > config.APPROVAL_COST_THRESHOLD:
        pitfalls.append(f"该任务成本 ${best['cost_usd']} 偏高")
    if state["features"].get("multimodal"):
        pitfalls.append("多模态任务注意视觉质量与人工抽检")

    store.add_case(state["features"]["task_type"], state["features"], true_best,
                   best["weighted"], best.get("cost_usd") or 0, pitfalls="；".join(pitfalls))

    from learn.policy import load_policy, save_policy
    policy = load_policy(registry.worker_names())
    policy.update(state["features"], best["worker"], best["weighted"])
    save_policy(policy)
    store.add_audit("system", "learn",
                    f"策略已学习：{best['worker']} 在 {state['features']['task_type']} 类得分 {best['weighted']}（累计 {policy.history} 次）",
                    state["job_id"])

    approvals = []
    spent = sum((a.get("cost_usd") or 0) for a in state.get("artifacts", []))
    budget = float((state.get("decision") or {}).get("budget_usd") or config.BUDGET_DEFAULT)
    if spent > budget:
        approvals.append({"action": "超预算", "reason": f"实际 ${spent:.2f} 超过预算 ${budget:.2f}（活已干完，请确认记录）"})
    if (best.get("cost_usd") or 0) > config.APPROVAL_COST_THRESHOLD:
        approvals.append({"action": "高成本", "reason": f"花费 ${best['cost_usd']} 超阈值（活已干完，请确认记录）"})
    status = "awaiting_approval" if approvals else "done"
    for a in approvals:
        a["job_id"] = state["job_id"]
        a["worker"] = best["worker"]
        a["id"] = store.add_approval(state["job_id"], best["worker"], a["action"], a["reason"])
        store.add_audit("system", "approval", f"{a['action']} 待确认：{a['reason']}", state["job_id"])
    state["best_worker"] = best["worker"]
    state["best_weighted"] = best["weighted"]
    state["status"] = status
    state["approvals"] = approvals
    store.update_job_status(state["job_id"], status)


_STAGE_FN = {
    "observe": do_observe, "decide": do_decide, "dispatch": do_dispatch,
    "judge": do_judge, "learn": do_learn,
}


def _advance(job_id, state, start_idx, stop_after):
    for i in range(start_idx, len(STAGES)):
        stage = STAGES[i]
        _STAGE_FN[stage](state)
        store.save_job_state(job_id, stage, state)
        store.add_audit("system", stage, f"完成阶段 {stage}", job_id)
        if state.get("status") == "awaiting_manual" and stage == "dispatch":
            store.update_job_status(job_id, "awaiting_manual")
            return _summary(state)
        if stop_after == stage:
            store.update_job_status(job_id, "interrupted")
            raise Interrupt(f"在阶段 {stage} 被中断（演示断点续跑）")
    store.save_job_state(job_id, STAGES[-1], state)
    store.update_job_status(job_id, state.get("status", "done"))
    return _summary(state)


def propose_task(title: str, description: str = "", budget_usd=None) -> dict:
    """只做到决策，状态 awaiting_decision，等人盖章。"""
    store.init_db()
    job_id = store.create_job(title, description, "", {}, {}, status="awaiting_decision")
    state = {
        "job_id": job_id, "title": title, "description": description,
        "budget_usd": budget_usd,
    }
    do_observe(state)
    store.update_job_meta(job_id, task_type=state["features"]["task_type"], features=state["features"])
    do_decide(state)
    store.update_job_decision(job_id, state["decision"])
    store.save_job_state(job_id, "decide", state)
    store.update_job_status(job_id, "awaiting_decision")
    store.add_audit("user", "propose", f"待盖章：建议 {state['decision'].get('worker')}", job_id)
    state["status"] = "awaiting_decision"
    return _summary(state)


def confirm_task(job_id: str, action: str = "accept", worker=None, mode="dispatch",
                 budget_usd=None, split=None, stop_after=None) -> dict:
    """盖章后才派活。action: accept | modify | reject。mode: dispatch | benchmark。"""
    store.init_db()
    st = store.get_job_state(job_id)
    if not st:
        raise RuntimeError("没有待签发的决策，或任务已经结束")
    state = st["checkpoint"]
    state["job_id"] = job_id

    if action == "reject":
        store.update_job_status(job_id, "rejected")
        store.clear_job_state(job_id)
        store.add_audit("user", "reject", "拒绝该决策，未派活", job_id)
        state["status"] = "rejected"
        return _summary(state)

    dec = dict(state.get("decision") or {})
    if worker:
        dec["worker"] = worker
        dec["source"] = "用户改派"
        dec["reason"] = (dec.get("reason") or "") + f" 你改派为 {worker}。"
    if split is not None:
        dec["split"] = bool(split)
    if budget_usd is not None:
        dec["budget_usd"] = float(budget_usd)
    state["decision"] = dec
    state["dispatch_mode"] = "benchmark" if mode == "benchmark" else "dispatch"
    store.update_job_decision(job_id, dec)
    store.update_job_status(job_id, "running")
    store.save_job_state(job_id, "decide", state)
    store.add_audit("user", "seal", f"{action} · {state['dispatch_mode']} · {dec.get('worker')}", job_id)
    return _advance(job_id, state, 2, stop_after)


def complete_manual(job_id: str, detail: str) -> dict:
    """手动任务卡回填产物后，继续打分和学习。"""
    store.init_db()
    st = store.get_job_state(job_id)
    if not st:
        raise RuntimeError("没有待回填的任务卡")
    state = st["checkpoint"]
    state["job_id"] = job_id
    filled = False
    for a in state.get("artifacts", []):
        if a.get("status") == "pending_manual":
            a["status"] = "done"
            a["detail"] = detail or a.get("detail") or ""
            filled = True
    if not filled:
        raise RuntimeError("当前没有待回填的手动工人")
    store.set_subtasks_status(job_id, "done")
    store.update_job_status(job_id, "running")
    store.add_audit("user", "manual", "已回填手动产物", job_id)
    return _advance(job_id, state, STAGES.index("judge"), None)


def run_task(title: str, description: str = "", stop_after=None) -> dict:
    """命令行：自动盖章并同场比试（方便演示榜单）。"""
    result = propose_task(title, description)
    if stop_after == "decide":
        return result
    return confirm_task(result["job_id"], "accept", mode="benchmark", stop_after=stop_after)


def resume_task(job_id: str) -> dict:
    store.init_db()
    st = store.get_job_state(job_id)
    if not st:
        raise RuntimeError(f"没有可恢复的断点：{job_id}")
    state = st["checkpoint"]
    state["job_id"] = job_id
    state["_resumed_from"] = st["stage"]
    last = st["stage"]
    job = store.get_job(job_id)
    if job and job.get("status") == "awaiting_decision":
        raise RuntimeError("任务还在待盖章，请先签发，不要直接续跑")
    if job and job.get("status") in ("done", "rejected", "awaiting_approval"):
        raise RuntimeError("没有可恢复的断点")
    start_idx = STAGES.index(last) + 1 if last in STAGES else 0
    if start_idx >= len(STAGES):
        start_idx = 0
    store.add_audit("user", "resume", f"从阶段 {last} 恢复", job_id)
    return _advance(job_id, state, start_idx, None)


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
        "dispatch_mode": state.get("dispatch_mode"),
        "sensitive": state.get("sensitive"),
        "artifacts": state.get("artifacts", []),
    }


class _ArtifactProxy:
    def __init__(self, name, detail, cost, latency, capability=None):
        import uuid as _u
        self.id = f"art-{_u.uuid4().hex[:6]}"
        self.meta = {"name": name, "capability": capability or []}
        self.detail = detail
        self.cost_usd = cost
        self.latency_ms = latency
        self.summary = (detail or "")[:80]
