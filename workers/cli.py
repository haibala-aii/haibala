"""
haibala · M2 · workers/cli.py
=============================
【这一课：真的 CLI worker（接 Codex / dsh 这类命令行 agent）】
把任务写成一个文件，调用配置里的命令去"干活"，命令把结果写出来，我们读文件。
两点很重要：
  1) 用"文件读写"而非"捕获 stdout 管道"——在受限环境里管道捕获会 EPERM，
     而且很多 agent 命令会交互，靠文件传结果最稳。
  2) 命令没配置/没安装 -> 抛错，由 pipeline 回退到 mock，永远不会崩。
"""
import subprocess, uuid
from pathlib import Path
from workers.base import WorkerPlugin, Artifact

class CLIWorker(WorkerPlugin):
    kind = "cli"

    def __init__(self, name, cmd, capability):
        self.name = name
        self.cmd = cmd            # 例如 "codex" / "dsh"，可带参数列表
        self.capability = capability

    def submit(self, task: str, workspace: str = ".") -> Artifact:
        ws = Path(workspace)
        ws.mkdir(parents=True, exist_ok=True)
        # 1) 把任务写成输入文件
        in_file = ws / f"task_{self.name}_{uuid.uuid4().hex[:6]}.md"
        out_file = ws / f"out_{self.name}_{uuid.uuid4().hex[:6]}.md"
        in_file.write_text(task, encoding="utf-8")

        # 2) 执行命令（stdout 写到文件，不用管道捕获）
        cmd = [self.cmd] if isinstance(self.cmd, str) else list(self.cmd)
        import time
        t0 = time.time()
        with open(out_file, "w", encoding="utf-8") as o, open(ws / "err.log", "w", encoding="utf-8") as e:
            try:
                subprocess.run(cmd + [str(in_file)], cwd=ws, stdout=o, stderr=e, timeout=600)
            except subprocess.TimeoutExpired:
                raise RuntimeError("CLI worker 超时")
            except FileNotFoundError:
                raise RuntimeError(f"没有找到命令 {self.cmd}")
        latency = round((time.time() - t0) * 1000)

        detail = out_file.read_text(encoding="utf-8") if out_file.exists() else "(无输出)"
        return Artifact(id=f"art-{uuid.uuid4().hex[:6]}", status="done",
                        summary=f"CLI 完成：{task[:40]}",
                        cost_usd=0.0, latency_ms=latency, detail=detail[:3000],
                        meta={"name": self.name, "capability": self.capability})
