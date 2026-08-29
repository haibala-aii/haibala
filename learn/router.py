"""
haibala · M1 · learn/router.py
==============================
【这一课：决策 / 路由器，以及"学习"的最小形态】
supervisor 的核心决策 = 给一个任务定"配置"：
    {worker 用谁, split 拆不拆, priority 优先级, budget 预算}

M1 学习用的是最朴素的 L1（案例记忆/检索）：
   - 每次跑完，把「特征 -> 决策 -> 实际得分(judge) -> 成本」存成一条 case。
   - 下次接相似任务，先看历史 case 里"这个类型谁得分高、谁便宜"，据此建议。
这就是"越用越会"的最小闭环。M2 再升级成 L2（训一个路由小模型泛化）。
"""
from core import store

# 任务先设为通用默认，再被案例改写
def _fallback_decision(features, worker_names):
    task_type = features["task_type"]
    # M1 用"能力匹配"选一个默认 worker（真实系统里这里会查 AgentProfile）
    best = "dsh"
    if task_type == "text":
        best = "minimax"
    elif task_type == "image":
        best = "codex"
    elif task_type == "frontend":
        best = "cursor"
    elif task_type == "data":
        best = "mock"
    return best

def _similarity(features, case):
    """衡量一个 case 和当前任务的相似度（简单：同类型 + 标签重合）。"""
    cf = case.get("features_json", "{}")
    import json as _json
    try:
        cf = _json.loads(cf)
    except Exception:
        cf = {}
    score = 0
    if cf.get("task_type") == features.get("task_type"):
        score += 3
    # 技术栈重合
    score += len(set(cf.get("stack", [])) & set(features.get("stack", [])))
    if cf.get("complexity") == features.get("complexity"):
        score += 1
    return score

def decide(features, worker_names):
    """根据案例记忆（L1）给出决策。"""
    cases = store.list_cases()
    similar = []
    for c in cases:
        s = _similarity(features, c)
        if s > 0:
            similar.append((s, c))
    similar.sort(key=lambda x: -x[0])
    top = similar[:3]

    # 从相似案例里统计"哪个 worker 在这个类型上得分最高"
    from collections import defaultdict
    worker_score = defaultdict(list)
    for s, c in top:
        try:
            dec = _json_load(c.get("decision_json"))
            w = dec.get("worker")
            sc = c.get("actual_score") or 0
            worker_score[w].append(sc)
        except Exception:
            continue

    best_worker = _fallback_decision(features, worker_names)
    source = ""
    if worker_score:
        # 平均得分最高者胜出
        best_worker = max(worker_score,
                          key=lambda w: (sum(worker_score[w]) / len(worker_score[w]),
                                         -len(worker_score[w])))
        source = f"参考 {len(top)} 个相似案例"

    # 是否拆分：复杂度高或粗估子任务>1 就拆
    split = features.get("complexity") in ("high",) or features.get("n_subtasks", 1) > 1
    n_workers = features.get("n_subtasks", 1) if split else 1

    # 优先级（简化：拆出的子任务按一个顺序排）
    priority_order = ["data", "model", "frontend"] if split else ["main"]

    return {
        "worker": best_worker,
        "split": split,
        "n_workers": n_workers,
        "priority_order": priority_order,
        "budget_usd": 5.0,
        "reason": f"根据案例记忆，{features['task_type']} 类任务建议用 {best_worker}。" + ("；" + source if source else ""),
        "source": source or "默认规则（无历史案例）",
    }

def _json_load(s):
    import json as _json
    try:
        return _json.loads(s)
    except Exception:
        return {}
