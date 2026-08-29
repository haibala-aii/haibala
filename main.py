"""
haibala · M1 · main.py
======================
【这一课：把闭环接上「入口」和「能看的界面」】
两种用法：
  1) 命令行跑一个任务:      python main.py --run "批量抠图小程序" --desc "..."
  2) 起来一个本地界面:      python main.py serve      -> 浏览器开 http://127.0.0.1:8090

为了零依赖、马上能跑，这里用 Python 自带的 http.server 起服务。
M2 会换成 FastAPI（更工程化），但原理一样：前端通过 HTTP 拿数据。
"""
import sys, json, argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# 让 Windows 控制台也能正确显示中文（否则默认编码会乱码，只影响显示不影响数据）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from core.pipeline import run_task
from core import store

ROOT = Path(__file__).parent

# ---------------- 命令行运行一个任务 ----------------
def cmd_run(title, desc):
    result = run_task(title, desc)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result

# ---------------- 本地 Web ----------------
class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def do_GET(self):
        if self.path.startswith("/api/jobs"):
            jobs = store.list_jobs()
            out = []
            for j in jobs:
                evals = store.list_evaluations(j["id"])
                out.append({**j, "evals": evals})
            self._json(200, out)
        elif self.path.startswith("/api/leaderboard"):
            self._json(200, store.agent_profiles())
        elif self.path.startswith("/api/audit"):
            self._json(200, store.list_audit())
        elif self.path.startswith("/api/approvals"):
            self._json(200, store.list_approvals())
        elif self.path == "/" or self.path.startswith("/index"):
            page = (ROOT / "web" / "dashboard.html").read_text(encoding="utf-8")
            self._send(200, page, "text/html; charset=utf-8")
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/api/run":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            title = body.get("title", "未命名任务")
            desc = body.get("description", "")
            result = run_task(title, desc)
            self._json(200, result)
        elif self.path == "/api/approve":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            aid = body.get("id")
            decision = body.get("decision", "approve")
            store.approve(aid, decision)
            store.add_audit("user", "approval", f"{decision} 审批 #{aid}")
            self._json(200, {"ok": True})
        else:
            self._json(404, {"error": "not found"})

    def log_message(self, fmt, *args):  # 精简日志，避免刷屏
        pass

def cmd_serve(port=8090):
    store.init_db()
    print(f"\n  haibala M1 已启动 -> http://127.0.0.1:{port}\n"
          "  关闭：Ctrl+C\n")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()

# ---------------- 入口 ----------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="haibala M1")
    ap.add_argument("--run", help="跑一个任务")
    ap.add_argument("--desc", default="", help="任务详情")
    ap.add_argument("serve", nargs="?", const=True, help="启动本地界面")
    ap.add_argument("--port", type=int, default=8090)
    a = ap.parse_args()

    if a.run:
        cmd_run(a.run, a.desc)
    else:
        cmd_serve(a.port)
