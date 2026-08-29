"""
haibala · M1 · workers/mock.py
==============================
【这一课：一个"可配置"的假 worker，让闭环先跑起来】
M1 不真的调 Codex/DeepSeek，先写一个 MockWorker 假装干完活返回"产物"，
这样你能立刻跑通：任务 -> 决策 -> 派活 -> 收集 -> 打分 -> 学习。

关键点：同一个类，用不同 name/capability 就能造出"不同能力"的假 agent
（codex / dsh / minimax）。这样 judge 打分才有差异、router 才能比较出"谁适合这活"。
M2 再做真的 CLIWorker 去调真实命令，接口一模一样，上层不用改 —— 这就是接口的好处。
"""
from workers.base import WorkerPlugin, Artifact
import uuid, random

class MockWorker(WorkerPlugin):
    capability: list[str] = []

    def __init__(self, name: str, capability: list[str], kind: str = "mock"):
        self.name = name
        self.capability = capability
        self.kind = kind

    def submit(self, task: str, workspace: str = ".") -> Artifact:
        # 假装干活：返回一个"符合真实量级"的随机成本/耗时（避免误导审批演示）
        return Artifact(
            id=f"art-{uuid.uuid4().hex[:6]}",
            status="done",
            summary=f"[mock:{self.name}] 已完成：{task[:40]}",
            cost_usd=round(random.uniform(0.2, 1.2), 2),
            latency_ms=round(random.uniform(800, 4000)),
            detail="M1 mock 产物，仅用于先跑通闭环。",
            meta={"name": self.name, "capability": self.capability},
        )

    def capability_penalty(self) -> float:
        # 能力越广成本越高（粗略），只为了让数字有区分度
        return round(len(self.capability) * 0.05, 2)
