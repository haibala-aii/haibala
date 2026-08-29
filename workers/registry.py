"""
haibala · M2 · workers/registry.py
==================================
【这一课：注册表 + 配置驱动 + 回退（这是"可插拔"的关键）】
通过"名字 -> 实例"查到 worker。这里做了两件事：
  1. 先注册一组 mock worker（保证开箱能跑、能比较）。
  2. 读取 config.json 里 enabled 的 CLI worker（Codex/dsh 等），加进来。
     没 enabled / 命令不存在 -> 不注册，回退到 mock，绝不崩。
M3 会改成扫描 plugins/ 自动发现。
"""
import json
from pathlib import Path
from workers.base import WorkerPlugin
from workers.mock import MockWorker
from workers.cli import CLIWorker

_REGISTRY: dict[str, WorkerPlugin] = {}

def register(worker: WorkerPlugin):
    _REGISTRY[worker.name] = worker

def get_worker(name: str) -> WorkerPlugin | None:
    return _REGISTRY.get(name)

def worker_names() -> list[str]:
    return list(_REGISTRY.keys())

# 1) 内置 mock（用来做"同场比试"，也作为回退）
register(MockWorker(name="codex",   capability=["coding", "image", "frontend"], kind="cli"))
register(MockWorker(name="dsh",     capability=["coding", "agent", "frontend"], kind="cli"))
register(MockWorker(name="minimax", capability=["text", "design"], kind="api"))
register(MockWorker(name="cursor",  capability=["frontend", "design"], kind="manual"))
register(MockWorker(name="mock",    capability=["coding", "image", "text", "data"], kind="mock"))

# 2) 配置里的真实 CLI worker（enabled=true 才会注册）
_cfg = json.loads((Path(__file__).resolve().parent.parent / "config.json").read_text(encoding="utf-8"))
for name, conf in _cfg.get("workers", {}).items():
    if conf.get("enabled") and conf.get("type") == "cli":
        try:
            register(CLIWorker(name=name, cmd=conf.get("cmd", name),
                               capability=conf.get("capability", ["coding"])))
        except Exception:
            pass  # 配置错误就跳过，不影响核心
