"""
haibala · M2 · core/pipeline.py
===============================
【这一课：闭环 + 配置/回退 + 安全审批】
M1 是纯 mock 的闭环；M2 让它更"真实"：
  - judge 可配置：配了 API 用真 LLM-as-judge，没配自动回退 mock。
  - worker 可配置：config 里 enabled 的 CLI 用真命令，否则回退 mock。
  - 每个关键步骤写审计日志。
  - 成本超过阈值 / 任务涉及敏感动作 -> 标记"待盖章"，进入审批流（安全）。

循环仍是：observe -> decide -> 同场比试(benchmark) -> judge -> 写入案例与画像。
classify：
  judge = ApiJudge 如果配置了 key，否则 MockJudge（永远能跑）
"""
from core.features import extract_features
from core import store, config
from judge.base import DEFAULT_RUBRIC
from judge.mock import MockJudge
from learn import router
from workers import registry

SENSITIVE_WORDS = ["发邮件", "写库", "删除", "对外", "外发", "支付", "发布", "写文件到外部", "部署到生产"]

def _make_judge():
    # 配置了 API key + provider=api 才用真 judge，否则回退 mock（永远能跑）
    if config.JUDGE_PROVIDER == "api" and config.JUDGE_API_KEY:
        from judge.api import ApiJudge
        return ApiJudge()
    return MockJudge()

def _is_sensitive(text):
    return any(w in text for w in SENSITIVE_WORDS)

def run_task(title: str, description: str = "") -> dict:
    store.init_db()
    # 1) observe
    features = extract_features(description or title)
    worker_names = registry.worker_names()

    # 2) decide
    decision = router.decide(features, worker_names)
    job_id = store.create_job(title, description, features["task_type"], features, decision)
    store.add_audit("system", "decide",
                    f"决策：worker={decision['worker']} split={decision['split']} 预算${decision['budget_usd']}", job_id)

    judge = _make_judge()

    # 3) 同场比试：同一任务派给所有 worker，judge 打分
    leaderboard = []
    for name in worker_names:
        worker = registry.get_worker(name)
        if worker is None:
            continue
        try:
            art = worker.submit(description or title)
        except Exception as ex:                       # 真实 CLI worker 不可用 -> 回退 mock
            from workers.mock import MockWorker
            art = MockWorker(name, worker.capability).submit(description or title)
            art.detail = f"（真实命令不可用，回退 mock：{ex}）"
        try:
            ev = judge.score(DEFAULT_RUBRIC, art, {"features": features})
        except Exception:
            ev = MockJudge().score(DEFAULT_RUBRIC, art, {"features": features})
        leaderboard.append({"worker": name, "weighted": round(ev.weighted, 2),
                            "scores": ev.scores, "rationale": ev.rationale,
                            "cost_usd": art.cost_usd, "latency_ms": art.latency_ms})
        store.add_evaluation(job_id, name, ev.scores, ev.weighted, ev.rationale, ev.judge)

    # 4) 找出实际最强 worker，写入案例 + 画像（学习）
    best = max(leaderboard, key=lambda x: x["weighted"])
    true_best = dict(decision); true_best["worker"] = best["worker"]
    true_best["reason"] = "实例评测：该 worker 得分最高"
    store.add_case(features["task_type"], features, true_best, best["weighted"], best["cost_usd"])
    store.add_audit("system", "judge", f"最强 worker = {best['worker']}（{best['weighted']} 分），已写入案例", job_id)

    # 5) 安全审批：高成本 或 敏感动作 -> 待盖章
    subs = [{"title": f"子任务{i}", "worker": best["worker"], "status": "done", "score": best["weighted"]}
            for i in range(1, max(1, decision.get("n_workers", 1)) + 1)]
    approvals_needed = []
    sensitive = _is_sensitive(description or title)
    if sensitive:
        approvals_needed.append({"job_id": job_id, "worker": best["worker"],
                                 "action": "敏感操作", "reason": "任务涉及敏感动作，需盖章"})
    if best["cost_usd"] > config.APPROVAL_COST_THRESHOLD:
        approvals_needed.append({"job_id": job_id, "worker": best["worker"],
                                 "action": "高成本", "reason": f"花费 ${best['cost_usd']} 超阈值"})

    status = "awaiting_approval" if approvals_needed else "done"
    store.update_job_status(job_id, status)
    for a in approvals_needed:
        a["id"] = store.add_approval(job_id, a["worker"], a["action"], a["reason"])
        store.add_audit("system", "approval", f"{a['action']} 待盖章：{a['reason']}", job_id)

    return {
        "job_id": job_id, "title": title, "features": features,
        "recommended_decision": decision,
        "leaderboard": sorted(leaderboard, key=lambda x: -x["weighted"]),
        "best_worker": best["worker"], "best_weighted": best["weighted"],
        "subtasks": subs, "approvals_needed": approvals_needed,
        "status": status,
        "learning_note": f"已写入案例：{features['task_type']} 类任务最佳为 {best['worker']}。",
    }
