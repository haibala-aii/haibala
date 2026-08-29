"""
haibala · M1 · judge/base.py
============================
【这一课：裁判 / LLM-as-judge 的抽象】
rubric = 一组"带权重的维度"，每个维度有 1-5 分和描述锚点。
judge 拿到"产物 + rubric" -> 逐维度打分 -> 加权总分 + 一句理由。

这是本系统最值钱、也最难的一环（评估）。M1 先用 MockJudge（假分数）让你
看清流程；M2 换成真的 LLM-as-judge（调 API），接口一样，上层不用改。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

# 默认评分标准（带锚点）。weight 之和 = 1.0
DEFAULT_RUBRIC = {
    "title": "编码/图像任务评价",
    "dimensions": [
        {"name": "功能正确性", "weight": 0.40, "scale": 5, "anchors": {"5": "完整可跑通", "1": "基本不可用"}},
        {"name": "代码质量",   "weight": 0.25, "scale": 5, "anchors": {"5": "清晰可维护", "1": "混乱无结构"}},
        {"name": "可复用性",   "weight": 0.20, "scale": 5, "anchors": {"5": "易扩展",     "1": "一次性"}},
        {"name": "成本/耗时",  "weight": 0.15, "scale": 5, "anchors": {"5": "省时省钱",   "1": "贵而慢"}},
    ],
}

@dataclass
class Evaluation:
    """一次打分结果。"""
    worker: str
    scores: dict[str, float]        # {维度: 分数}
    weighted: float                 # 加权总分
    rationale: str                  # 一句理由
    judge: str                      # 用的哪个 judge（如 mock / deepseek）

class JudgePlugin(ABC):
    """所有 judge 的统一接口。"""
    name: str = ""

    @abstractmethod
    def score(self, rubric: dict, artifact, context: dict) -> Evaluation:
        raise NotImplementedError
