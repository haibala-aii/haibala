"""
手动工人：Cursor / 其它 GUI。控制台发任务卡，你干完再把产物贴回来。
"""
import uuid
from workers.base import WorkerPlugin, Artifact


class ManualWorker(WorkerPlugin):
    kind = "manual"

    def __init__(self, name, capability, note="在对应 GUI 里完成任务后，把产物贴回签发台。"):
        self.name = name
        self.capability = capability
        self.note = note

    def submit(self, task: str, workspace: str = ".") -> Artifact:
        return Artifact(
            id=f"art-{uuid.uuid4().hex[:6]}",
            status="pending_manual",
            summary=f"任务卡已开：{task[:40]}",
            cost_usd=0.0,
            latency_ms=0.0,
            detail=self.note + "\n\n任务：\n" + task,
            meta={"name": self.name, "capability": self.capability, "kind": "manual"},
        )
