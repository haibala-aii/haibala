"""
haibala · M4.5 · learn/model.py
===============================
【这一课：真正的监督学习 — softmax 逻辑回归（梯度下降）】
M4 的线性策略是"给赢家加点权重"。M4.5 把它升格为一个**真正的多分类模型**：
用所有历史案例（特征 -> 实际最强 worker）训练一个 softmax 回归，
再对任意新任务预测"该用谁"。这有概率输出、能泛化、能算准确率。

训练就是经典的"梯度下降 + 交叉熵"，全程纯 Python 实现，你能看清每一步。
"""
import math
from learn.policy import featurize, TASK_TYPES

class SoftmaxRouter:
    """多分类 softmax 逻辑回归（用梯度下降训练）。"""

    def __init__(self, lr=0.2, epochs=500):
        self.lr = lr
        self.epochs = epochs
        self.W = []               # W[c][d] = 类别c在第d个特征上的权重
        self.class_names = []
        self._idx = {}
        self.trained = False
        self.dim = len(featurize({}))

    def _build(self, cases):
        """从案例库构造训练集：X(特征向量), y(最佳 worker)。"""
        X, y = [], []
        for c in cases:
            try:
                import json
                f = json.loads(c.get("features_json"))
                d = json.loads(c.get("decision_json"))
                w = d.get("worker")
                if w:
                    X.append(featurize(f)); y.append(w)
            except Exception:
                continue
        return X, y

    def fit(self, cases):
        X, y = self._build(cases)
        if len(X) < 4:
            return self           # 样本太少，不训练（留给兜底）
        self.class_names = sorted(set(y))
        self._idx = {n: i for i, n in enumerate(self.class_names)}
        n_cls, dim, n = len(self.class_names), self.dim, len(X)
        W = [[0.0] * dim for _ in range(n_cls)]

        for _ in range(self.epochs):
            grad = [[0.0] * dim for _ in range(n_cls)]
            for x, label in zip(X, y):
                scores = [sum(W[c][d] * x[d] for d in range(dim)) for c in range(n_cls)]
                mx = max(scores)
                exps = [math.exp(s - mx) for s in scores]
                ssum = sum(exps)
                probs = [e / ssum for e in exps]
                true = self._idx[label]
                for c in range(n_cls):
                    delta = probs[c] - (1 if c == true else 0)
                    for d in range(dim):
                        grad[c][d] += delta * x[d]
            for c in range(n_cls):
                for d in range(dim):
                    W[c][d] -= self.lr * grad[c][d] / n
        self.W, self.trained = W, True
        return self

    def predict(self, features):
        if not self.trained:
            return None
        x = featurize(features)
        scores = [sum(self.W[c][d] * x[d] for d in range(self.dim)) for c in range(len(self.class_names))]
        mx = max(scores)
        probs = [math.exp(s - mx) for s in scores]
        return self.class_names[scores.index(max(scores))]

    def accuracy(self):
        """训练集上的准确率（教学用，便于看"学得怎么样"）。"""
        from core import store
        X, y = self._build(store.list_cases())
        if not X:
            return 0.0
        ok = sum(1 for x, lab in zip(X, y) if self.predict_from_vec(x) == lab)
        return round(ok / len(X), 3)

    def predict_from_vec(self, x):
        scores = [sum(self.W[c][d] * x[d] for d in range(self.dim)) for c in range(len(self.class_names))]
        return self.class_names[scores.index(max(scores))]
