"""
haibala · M5+ · workers/mcp.py
==============================
【这一课：MCP（Model Context Protocol）通用接入 —— 真正"零代码接新 agent"】
MCP 是"AI 工具的统一插口"：任何提供 MCP server 的工具，都能以**统一协议**接入。
我们只需连它的 server、列出工具、调用工具，就能让这个工具当"worker"干活。
=> 加一个新 agent = 在 config.json 里声明一个 MCP server（含命令/地址），**不用写核心代码**。
"""
import asyncio, uuid
from workers.base import WorkerPlugin, Artifact

class MCPWorker(WorkerPlugin):
    kind = "mcp"

    def __init__(self, name, command, capability=None):
        self.name = name
        self.command = command                 # 例如 ["npx","-y","@modelcontextprotocol/server-everything"]
        self.capability = capability or ["coding", "text", "data"]
        self._tools = None

    async def _call(self, task):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        params = StdioServerParameters(command=self.command[0], args=self.command[1:])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                if not tools:
                    raise RuntimeError("该 MCP server 没有可调用工具")
                # 简单选一个最匹配"任务"的工具，否则取第一个
                tool = tools[0]
                for t in tools:
                    if t.name.lower() in task.lower() or task and t.name:
                        tool = t
                        break
                res = await session.call_tool(tool.name, {"task": task})
                # 取结构化结果的可读文本
                if hasattr(res, "content"):
                    text = "\n".join(p.text for p in res.content if getattr(p, "text", None))
                else:
                    text = str(res)
                return text

    def submit(self, task: str, workspace: str = ".") -> Artifact:
        try:
            text = asyncio.run(self._call(task))[:3000]
            status = "done"
        except Exception as ex:
            text = f"MCP 调用失败：{ex}"
            status = "failed"
        return Artifact(id=f"art-{uuid.uuid4().hex[:6]}", status=status,
                        summary=f"[mcp:{self.name}] {task[:40]}",
                        cost_usd=0.0, latency_ms=0.0, detail=text,
                        meta={"name": self.name, "capability": self.capability})
