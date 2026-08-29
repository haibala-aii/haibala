"""
haibala · M4 · learn/policy.py
==============================
【这一课：L2 — 在线学习的路由策略（真正的"会用"）】
L1(案例检索)是"模仿以前遇到的场景"；L2 是"学一个规律，举一反三"。

做法（纯 Python，一个"在线线性策略"，也叫多臂老虎机/线性强化）：
  1. 把任务特征变成数值向量 features。  featurize()
  2. 每个 worker 有一组权重向量 W[worker]；预测分数 = W[worker] · features。
     分数最高的 worker = 预测的最佳人选。
  3. 任务跑完、judge 揭晓"实际最强 worker"后，更新：给那个赢家的权重
     加点 features（强化它的特征关联），其它 worker 轻微惩罚。
  这样系统会逐渐学到"什么样的特征→用谁"，并能推断没见过的组合。
"""
from core import store

TASK_TYPES = ["image", "frontend", "data", "text", "coding"]

def featurize(f: dict) -> list[float]:
    """把 features 映射成固定长度的数值向量（特征工程）。"""
    v = []
    v += [1.0 if f.get("task_type") == t else 0.0 for t in TASK_TYPES]     # 类型 one-hot
    v += [1.0 if f.get("complexity") == "high" else 0.0]                  # 复杂度高
    v += [1.0 if f.get("size") in ("medium", "large") else 0.0]           # 规模中/大
    v += [1.0 if f.get("size") == "large" else 0.0]                       # 规模大
    v += [1.0 if f.get("multimodal") else 0.0]                            # 多模态
    v += [min(f.get("n_subtasks", 1), 4) / 4.0]                           # 子任务数(归一)
    return v

class PolicyModel:
    """在线学习的线性路由策略。"""

    def __init__(self, workers: list[str], lr: float = 0.3):
        self.dim = len(featurize({}))
        self.workers = list(workers)
        self.lr = lr
        self.W = {w: [0.0] * self.dim for w in self.workers}
        self.history = 0            # 已学习次数（>0 才相信策略）

    def predict(self, features: dict) -> dict[str, float]:
        v = featurize(features)
        return {w: sum(a * b for a, b in zip(self.W[w], v)) for w in self.workers}

    def best_worker(self, features: dict) -> str:
        scores = self.predict(features)
        if not scores:
            return "mock"
        # 无历史时全部 0 分，用"能力匹配启发式"兜底（见 router）
        return max(scores, key=lambda w: scores[w])

    def update(self, features: dict, winner: str, actual_score: float):
        """judge 揭晓后：强化赢家，惩罚其它。"""
        v = featurize(features)
        for w in self.workers:
            sign = self.lr * actual_score if w == winner else -self.lr * 0.1
            self.W[w] = [a + sign * b for a, b in zip(self.W[w], v)]
        self.history += 1

    def to_weights(self):
        return {w: self.W[w] for w in self.workers}

    @classmethod
    def from_weights(cls, weights: dict, workers: list[str], history: int):
        p = cls(workers)
        for w in workers:
            p.W[w] = list(weights.get(w, [0.0] * p.dim))
        p.history = history
        return p

# ---------- 持久化 ----------
def load_policy(workers: list[str]) -> PolicyModel:
    w = store.get_policy()
    hist = store.get_policy_count()
    if w:
        return PolicyModel.from_weights(w, workers, hist)
    return PolicyModel(workers)

def save_policy(policy: PolicyModel):
    store.save_policy(policy.to_weights(), policy.history)

def policy_summary(workers: list[str]) -> dict:
    """给界面看：它现在学了什么（模型类型 + 该用谁）。"""
    import json
    from learn.model import SoftmaxRouter
    cases = store.list_cases()
    learned = set()
    for c in cases:
        try:
            learned.add(json.loads(c.get("features_json")).get("task_type"))
        except Exception:
            pass
    model = None
    mtype = "softmax"
    try:
        from learn.sklearn_model import SklearnRouter
        sk = SklearnRouter().fit(cases)
        if sk.trained:
            model, mtype = sk, "sklearn"
    except Exception:
        pass
    if model is None:
        sm = SoftmaxRouter().fit(cases)
        if sm.trained:
            model, mtype = sm, "softmax"
    if model is None:
        policy = load_policy(workers)
        predicts, mtype = [], ("linear" if policy.history else "none")
        if policy.history:
            for t in TASK_TYPES:
                if t in learned:
                    f = {"task_type": t, "complexity": "medium", "size": "small",
                         "multimodal": False, "n_subtasks": 1}
                    predicts.append({"task_type": t, "best_worker": policy.best_worker(f)})
        return {"model": mtype, "history": policy.history, "accuracy": None, "predicts": predicts}

    predicts = []
    for t in TASK_TYPES:
        if t in learned:
            f = {"task_type": t, "complexity": "medium", "size": "small",
                 "multimodal": False, "n_subtasks": 1}
            predicts.append({"task_type": t, "best_worker": model.predict(f)})
    return {"model": mtype, "history": len(cases),
            "accuracy": model.accuracy(), "predicts": predicts}
