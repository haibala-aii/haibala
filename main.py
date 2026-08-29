"""
haibala 入口：命令行跑任务，或本地桌面/浏览器打开签发台。
"""
import sys, json, argparse, mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from core.pipeline import (
    run_task, resume_task, Interrupt,
    propose_task, confirm_task, complete_manual,
)
from core import store, events
from core.events import notify

ROOT = Path(__file__).parent
DIST = ROOT / "frontend" / "dist"
WEB = ROOT / "web" / "dashboard.html"

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")


def cmd_run(title, desc, stop_after=None):
    try:
        result = run_task(title, desc, stop_after=stop_after)
    except Interrupt as e:
        result = {"interrupted": str(e)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def cmd_resume(job_id):
    try:
        result = resume_task(job_id)
    except Exception as e:
        result = {"error": str(e)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def _read_body(handler):
    n = int(handler.headers.get("Content-Length", 0) or 0)
    if n <= 0:
        return {}
    return json.loads(handler.rfile.read(n) or b"{}")


def _status_payload():
    from workers import registry
    from core import config as cfg
    workers = []
    raw = cfg.raw()
    declared = raw.get("workers", {})
    for name in registry.worker_names():
        w = registry.get_worker(name)
        workers.append({
            "name": name,
            "kind": getattr(w, "kind", ""),
            "capability": getattr(w, "capability", []),
            "enabled": bool((declared.get(name) or {}).get("enabled")) or getattr(w, "kind", "") in ("mock", "manual"),
        })
    return {
        "judge": cfg.JUDGE_PROVIDER,
        "has_key": bool(cfg.JUDGE_API_KEY),
        "judge_model": cfg.JUDGE_MODEL,
        "workers": workers,
        "declared": raw.get("workers", {}),
        "budget": {"default_usd": cfg.BUDGET_DEFAULT, "approve_over_usd": cfg.APPROVAL_COST_THRESHOLD},
        "worker_options": registry.worker_names(),
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _parsed(self):
        u = urlparse(self.path)
        return u.path, parse_qs(u.query)

    def do_GET(self):
        path, qs = self._parsed()
        if path == "/api/jobs":
            self._json(200, store.list_jobs())
        elif path == "/api/job":
            jid = (qs.get("id") or [""])[0]
            job = store.get_job(jid)
            self._json(200 if job else 404, job or {"error": "not found"})
        elif path == "/api/leaderboard":
            self._json(200, store.agent_profiles())
        elif path == "/api/learning":
            from workers import registry
            from learn.policy import policy_summary
            self._json(200, policy_summary(registry.worker_names()))
        elif path == "/api/status":
            self._json(200, _status_payload())
        elif path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = events.bus.subscribe()
            try:
                self.wfile.write(b": connected\n\n"); self.wfile.flush()
                while True:
                    evt = q.get()
                    if evt is None:
                        break
                    self.wfile.write(("data: " + json.dumps(evt, ensure_ascii=False) + "\n\n").encode("utf-8"))
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                events.bus.unsubscribe(q)
        elif path == "/api/audit":
            self._json(200, store.list_audit())
        elif path == "/api/approvals":
            self._json(200, store.list_approvals())
        else:
            self._static(path)

    def _static(self, path):
        rel = unquote(path).lstrip("/") or "index.html"
        if ".." in rel.split("/"):
            self._json(403, {"error": "forbidden"})
            return
        if DIST.exists():
            target = DIST / rel
            if target.is_file():
                ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                self._send(200, target.read_bytes(), ctype)
                return
            index = DIST / "index.html"
            if index.is_file() and not rel.startswith("api/"):
                self._send(200, index.read_bytes(), "text/html; charset=utf-8")
                return
        if path == "/" or path.startswith("/index"):
            if WEB.exists():
                self._send(200, WEB.read_text(encoding="utf-8"), "text/html; charset=utf-8")
                return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        path, _qs = self._parsed()
        try:
            body = _read_body(self)
        except Exception:
            self._json(400, {"error": "invalid json"})
            return
        if path == "/api/run":
            title = body.get("title", "未命名任务")
            desc = body.get("description", "")
            budget = body.get("budget_usd")
            result = propose_task(title, desc, budget_usd=budget)
            notify("job_updated", job_id=result.get("job_id"))
            self._json(200, result)
        elif path == "/api/confirm":
            try:
                result = confirm_task(
                    body.get("job_id", ""),
                    action=body.get("action", "accept"),
                    worker=body.get("worker"),
                    mode=body.get("mode", "dispatch"),
                    budget_usd=body.get("budget_usd"),
                    split=body.get("split"),
                )
            except Exception as e:
                result = {"error": str(e)}
            notify("job_updated", job_id=body.get("job_id"))
            self._json(200, result)
        elif path == "/api/manual":
            try:
                result = complete_manual(body.get("job_id", ""), body.get("detail", ""))
            except Exception as e:
                result = {"error": str(e)}
            notify("job_updated", job_id=body.get("job_id"))
            self._json(200, result)
        elif path == "/api/approve":
            aid = body.get("id")
            decision = body.get("decision", "approve")
            store.approve(aid, decision)
            store.add_audit("user", "approval", f"{decision} 审批 #{aid}")
            notify("approval_updated")
            notify("job_updated")
            self._json(200, {"ok": True})
        elif path == "/api/resume":
            try:
                result = resume_task(body.get("job_id", ""))
            except Exception as e:
                result = {"error": str(e)}
            notify("job_updated", job_id=body.get("job_id"))
            self._json(200, result)
        elif path == "/api/chat":
            from agents.supervisor import supervisor_reply
            out = supervisor_reply(body.get("session_id", "default"), body.get("text", ""))
            notify("job_updated")
            self._json(200, out)
        elif path == "/api/settings":
            from core import config as cfg
            from workers import registry
            saved = cfg.save_patch(body)
            registry.reload()
            notify("settings_updated")
            self._json(200, _status_payload() | {"saved": True, "config": saved})
        else:
            self._json(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        pass


def cmd_serve(port=8090):
    store.init_db()
    ui = "Vue 签发台" if (DIST / "index.html").exists() else "备用 HTML"
    print(f"\n  haibala 已启动 -> http://127.0.0.1:{port}  ({ui})\n  关闭：Ctrl+C\n")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="haibala")
    ap.add_argument("--run", help="跑一个任务（自动盖章并同场比试）")
    ap.add_argument("--desc", default="", help="任务详情")
    ap.add_argument("--resume", help="从某个 job_id 断点续跑")
    ap.add_argument("--stop-after", help="演示中断：observe/decide/dispatch/judge/learn")
    ap.add_argument("serve", nargs="?", const=True, help="启动本地界面")
    ap.add_argument("--port", type=int, default=8090)
    a = ap.parse_args()

    if a.resume:
        cmd_resume(a.resume)
    elif a.run:
        cmd_run(a.run, a.desc, a.stop_after)
    else:
        cmd_serve(a.port)
