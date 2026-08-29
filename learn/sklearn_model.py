"""
haibala · M5.5 · learn/sklearn_model.py
======================================
【这一课：用 sklearn 换更强的路由模型】
纯 Python softmax 能把梯度下降看清楚；样本一多、特征一交叉，线性一层就不够。
这里用 scikit-learn 的多项式逻辑回归（L2 正则）学「特征 → 该用哪个 worker」。
没装 sklearn 时自动回退 SoftmaxRouter，不崩。
"""
from learn.policy import featurize


def _xy(cases):
    import json
    X, y = [], []
    for c in cases:
        try:
            f = json.loads(c.get("features_json") or "{}")
            d = json.loads(c.get("decision_json") or "{}")
            w = d.get("worker")
            if w:
                X.append(featurize(f))
                y.append(w)
        except Exception:
            continue
    return X, y


class SklearnRouter:
    """sklearn 多项式逻辑回归。接口与 SoftmaxRouter 对齐：fit / predict / accuracy / trained。"""

    def __init__(self):
        self.clf = None
        self.trained = False
        self.class_names = []

    def fit(self, cases):
        try:
            from sklearn.linear_model import LogisticRegression
        except ImportError:
            return self
        X, y = _xy(cases)
        if len(X) < 4 or len(set(y)) < 2:
            return self
        # lbfgs 支持多分类；C 略小一点，样本少时少过拟合
        clf = LogisticRegression(max_iter=800, solver="lbfgs", C=0.8)
        clf.fit(X, y)
        self.clf = clf
        self.class_names = list(clf.classes_)
        self.trained = True
        return self

    def predict(self, features):
        if not self.trained:
            return None
        return str(self.clf.predict([featurize(features)])[0])

    def accuracy(self):
        from core import store
        X, y = _xy(store.list_cases())
        if not X or not self.trained:
            return 0.0
        return round(float(self.clf.score(X, y)), 3)
