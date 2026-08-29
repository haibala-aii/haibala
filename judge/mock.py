"""
haibala · M1 · judge/mock.py
============================
【这一课：一个"假"裁判，先看打分流程】
MockJudge 不做真理解，而是根据"worker 能力是否匹配任务类型"给分数。
这样你能看到：不同 worker 对同一任务得分不同 -> 系统据此判断"谁适合"。

打分逻辑（教学用的简化版）：
  1. 把任务特征里的 task_type 映射到这个任务"需要的能力标签"。
  2. 看 worker.capability 里有没有这个标签，算一个 match_score(0-5)。
  3. 各维度分数大致跟随 match_score，再轻微加噪声。
  4. 用 rubric 权重算出加权总分。
"""
from judge.base import JudgePlugin, Evaluation, DEFAULT_RUBRIC

# task_type -> 该任务核心需要的能力标签
NEED = {
    "image":    "image",
    "frontend": "frontend",
    "data":     "data",
    "text":     "text",
    "coding":   "coding",
}

class MockJudge(JudgePlugin):
    name = "mock"

    def score(self, rubric: dict, artifact, context: dict) -> Evaluation:
        features = context.get("features", {})
        task_type = features.get("task_type", "coding")
        need = NEED.get(task_type, "coding")
        cap = artifact.meta.get("capability", [])

        # 能力匹配度 -> 基础分 0..5
        if need in cap:
            match = 5.0
        elif any(n in cap for n in ("coding", "frontend", "text", "image", "data")):
            match = 3.5
        else:
            match = 2.0

        # 各维度分数（跟随 match，轻微波动）——仅为了演示
        scores = {}
        for d in rubric["dimensions"]:
            base = round(max(1.0, min(5.0, match + (hash(artifact.id) % 3) / 6.0)), 1)
            scores[d["name"]] = base

        # 加权总分
        weighted = round(sum(scores[d["name"]] * d["weight"] for d in rubric["dimensions"]), 2)
        rationale = (f"对 {task_type} 类任务，能力匹配度 {match:.1f}/5，加权 {weighted}。"
                     "（盲评：未使用工人身份。）")
        return Evaluation(worker=artifact.meta.get("name", "?"), scores=scores,
                          weighted=weighted, rationale=rationale, judge="mock")
