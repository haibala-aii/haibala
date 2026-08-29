"""
haibala · M4 · learn/router.py
==============================
【这一课：决策 = L2 策略预测 + L1 案例记忆（RAG）结合】
M1 的 router 只靠案例检索（L1）。M4 把"在线学到的策略"（L2）加进来：
  - L2 `PolicyModel` 用学到的特征权重给出"预测最佳 worker"（能泛化到新组合）。
  - L1 案例检索提供"经验/教训/参考"（决策理由的来源），这就是"案例库 RAG"。
两者结合：worker 主要由 L2 预测决定，但理由和踩坑来自 L1 相似案例。
"""
from learn.policy import load_policy
from learn.model import SoftmaxRouter
from core import store

MIN_CASES = 4   # 案例够多条，才启用监督学习模型（否则冷启动兜底）

def _train_router():
    """优先 sklearn 逻辑回归；没装或样本不够则 softmax；再不够返回 None。"""
    cases = store.list_cases()
    if len(cases) < MIN_CASES:
        return None
    try:
        from learn.sklearn_model import SklearnRouter
        m = SklearnRouter().fit(cases)
        if m.trained:
            return m
    except Exception:
        pass
    m = SoftmaxRouter().fit(cases)
    if m.trained:
        return m
    return None

def _fallback_decision(features, worker_names):
    """冷启动：还没学到策略时的启发式。"""
    task_type = features["task_type"]
    if task_type == "text": return "minimax"
    if task_type == "image": return "codex"
    if task_type == "frontend": return "cursor"
    if task_type == "data": return "mock"
    return "dsh"

def _similarity(features, case):
    """衡量一个 case 和当前任务的相似度（简单：同类型 + 标签重合）。"""
    cf = _json_load(case.get("features_json"))
    score = 0
    if cf.get("task_type") == features.get("task_type"):
        score += 3
    score += len(set(cf.get("stack", [])) & set(features.get("stack", [])))
    if cf.get("complexity") == features.get("complexity"):
        score += 1
    return score

def decide(features, worker_names):
    cases = store.list_cases()
    # ---- L2/M4.5：先用训练好的 softmax 模型预测（能泛化）----
    model = _train_router()
    if model:
        predicted = model.predict(features) or _fallback_decision(features, worker_names)
        kind = "sklearn" if model.__class__.__name__ == "SklearnRouter" else "softmax"
        l2_note = f"{kind}模型(L2) · 训练集准确率{model.accuracy()}"
    else:
        policy = load_policy(worker_names)
        if policy.history > 0:
            predicted = policy.best_worker(features)
            l2_note = "在线线性策略(L2)"
        else:
            predicted = _fallback_decision(features, worker_names)
            l2_note = "默认规则(冷启动)"

    # ---- L1：检索相似案例，作为"理由/经验/RAG"----
    similar = sorted(((_similarity(features, c), c) for c in cases if _similarity(features, c) > 0),
                     key=lambda x: -x[0])[:3]
    pitfalls, ref = [], {}
    for _s, c in similar:
        if c.get("pitfalls"):
            pitfalls.append(c["pitfalls"])
        dec = _json_load(c.get("decision_json"))
        ref.setdefault(dec.get("worker"), []).append(c.get("actual_score") or 0)
    if ref:
        best_by_case = max(ref, key=lambda w: sum(ref[w]) / len(ref[w]))
        predicted = best_by_case
        l2_note += " + 案例记忆(L1)"

    pitfalls = list(dict.fromkeys(pitfalls))  # 去重
    source = f"参考 {len(similar)} 个相似案例" if similar else "默认规则(冷启动)"
    reason = (f"对 {features['task_type']} 类任务，{l2_note} 建议用 {predicted}。"
              + ("  经验：" + "；".join(pitfalls) if pitfalls else ""))

    split = features.get("complexity") in ("high",) or features.get("n_subtasks", 1) > 1
    n_workers = features.get("n_subtasks", 1) if split else 1
    order = ["data", "model", "frontend"] if split else ["main"]
    return {
        "worker": predicted, "split": split, "n_workers": n_workers,
        "priority_order": order, "budget_usd": 5.0,
        "reason": reason, "source": source, "l2": l2_note,
        "pitfalls": pitfalls[:3],
    }

def _json_load(s):
    import json
    try: return json.loads(s)
    except Exception: return {}
