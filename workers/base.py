"""
haibala · M1 · workers/base.py
==============================
【这一课：抽象接口 / 插件化】
为什么所有 agent 都实现一个 submit() 接口？
  因为 supervisor 不该知道"Codex 还是 DeepSeek 还是 Cursor"。
  它只需要：给我一个任务 -> 还我一个产物。这就叫「抽象/接口」，
  也是你在 DSH 看到的插件思想的本质：核心稳定，实现可插拔。

任何新 agent，只要写一个类继承 WorkerPlugin、实现 submit()，
就能被系统认出来使用 —— 这就是"加 agent 不改核心"。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class Artifact:
    """一次执行的结果（产物）。"""
    id: str
    status: str            # done / failed
    summary: str           # 干了什么的描述
    cost_usd: float        # 花费（美元）
    latency_ms: float      # 耗时
    detail: str = ""
    meta: dict = field(default_factory=dict)

class WorkerPlugin(ABC):
    """所有"工人 agent"的统一接口。"""

    # 子类必须定义这些类属性
    name: str = ""                       # 唯一标识，如 "codex"
    capability: list[str] = []           # 会什么，如 ["coding","image"]
    kind: str = "cli"                    # cli / api / mcp / manual

    @abstractmethod
    def submit(self, task: str, workspace: str = ".") -> Artifact:
        """执行任务并返回产物。子类必须实现。"""
        raise NotImplementedError
