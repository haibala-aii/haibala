"""
工人注册表。mock 保证开箱能跑；config.json 里 enabled 的 CLI / MCP 会覆盖同名 mock。
"""
import json
from pathlib import Path
from workers.base import WorkerPlugin
from workers.mock import MockWorker
from workers.cli import CLIWorker
from workers.manual import ManualWorker

_REGISTRY: dict[str, WorkerPlugin] = {}
_CFG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def register(worker: WorkerPlugin):
    _REGISTRY[worker.name] = worker


def get_worker(name: str) -> WorkerPlugin | None:
    return _REGISTRY.get(name)


def worker_names() -> list[str]:
    return list(_REGISTRY.keys())


def load_config() -> dict:
    if not _CFG_PATH.exists():
        return {}
    return json.loads(_CFG_PATH.read_text(encoding="utf-8"))


def reload():
    _REGISTRY.clear()
    _bootstrap()


def _bootstrap():
    register(MockWorker(name="codex", capability=["coding", "image", "frontend"], kind="cli"))
    register(MockWorker(name="dsh", capability=["coding", "agent", "frontend"], kind="cli"))
    register(MockWorker(name="minimax", capability=["text", "design"], kind="api"))
    register(ManualWorker(name="cursor", capability=["frontend", "design"]))
    register(MockWorker(name="mock", capability=["coding", "image", "text", "data"], kind="mock"))

    cfg = load_config()
    for name, conf in cfg.get("workers", {}).items():
        if not conf.get("enabled"):
            continue
        kind = conf.get("type", "cli")
        cap = conf.get("capability", ["coding"])
        try:
            if kind == "cli":
                register(CLIWorker(name=name, cmd=conf.get("cmd", name), capability=cap))
            elif kind == "manual":
                register(ManualWorker(name=name, capability=cap))
            elif kind == "api":
                register(MockWorker(name=name, capability=cap, kind="api"))
        except Exception:
            pass

    for name, conf in cfg.get("mcp_servers", {}).items():
        if not conf.get("enabled"):
            continue
        try:
            from workers.mcp import MCPWorker
            register(MCPWorker(
                name=name,
                command=conf.get("command", ["npx", "-y", "@modelcontextprotocol/server-everything"]),
                capability=conf.get("capability", ["coding", "text"]),
            ))
        except Exception:
            pass


_bootstrap()
