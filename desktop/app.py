"""
haibala 桌面壳：独立窗口 + 本机 Python 后端。
始终拉起当前代码，并加载 Vue 签发台，不复用可能还在跑的旧 8090 页面。
"""
from __future__ import annotations

import atexit
import ctypes
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON = Path(__file__).resolve().parent / "haibala.ico"
DIST_INDEX = ROOT / "frontend" / "dist" / "index.html"
PORT = 18765
URL = f"http://127.0.0.1:{PORT}/?desk=1"

_backend: subprocess.Popen | None = None
_started_here = False


def _python() -> str:
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        sibling = exe.with_name("python.exe")
        if sibling.exists():
            return str(sibling)
    if exe.exists() and exe.name.lower() != "pythonw.exe":
        return str(exe)
    return shutil.which("python") or shutil.which("python3") or str(exe)


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def _pids_listening(port: int) -> list[int]:
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            creationflags=0x08000000,
            text=True,
            errors="ignore",
        )
    except Exception:
        return []
    pids: list[int] = []
    token = f":{port}"
    for line in out.splitlines():
        if "LISTENING" not in line.upper():
            continue
        if token not in line:
            continue
        parts = line.split()
        try:
            pid = int(parts[-1])
        except (ValueError, IndexError):
            continue
        if pid and pid not in pids:
            pids.append(pid)
    return pids


def _is_python(pid: int) -> bool:
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            creationflags=0x08000000,
            text=True,
            errors="ignore",
        )
        name = (out.split(",")[0] if out else "").strip('"').lower()
        return name in ("python.exe", "pythonw.exe")
    except Exception:
        return False


def _free_port(port: int) -> None:
    me = os.getpid()
    for pid in _pids_listening(port):
        if pid == me or not _is_python(pid):
            continue
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            creationflags=0x08000000,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    for _ in range(20):
        if not _port_open(port):
            return
        time.sleep(0.1)


def _ensure_ui() -> None:
    if DIST_INDEX.exists() and "id=\"app\"" in DIST_INDEX.read_text(encoding="utf-8"):
        return
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise RuntimeError("桌面界面未构建，且找不到 npm。请先在 frontend 目录执行 npm run build。")
    r = subprocess.run([npm, "run", "build"], cwd=str(ROOT / "frontend"))
    if r.returncode != 0 or not DIST_INDEX.exists():
        raise RuntimeError("前端构建失败，桌面窗口无法加载新界面。")


def start_backend() -> None:
    global _backend, _started_here
    _free_port(PORT)
    flags = 0x08000000
    _backend = subprocess.Popen(
        [_python(), "main.py", "--port", str(PORT)],
        cwd=str(ROOT),
        creationflags=flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _started_here = True
    for _ in range(80):
        if _port_open(PORT):
            break
        time.sleep(0.15)
    else:
        raise RuntimeError("haibala 后端没有在 18765 端口起来")
    html = ""
    for _ in range(20):
        try:
            html = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1).read().decode("utf-8", "ignore")
            break
        except Exception:
            time.sleep(0.15)
    if 'id="app"' not in html or "/assets/" not in html:
        raise RuntimeError("桌面窗口拿到的不是新版 Vue 界面，请关掉旧的 haibala 后再开。")


def stop_backend() -> None:
    global _backend
    if not _started_here or _backend is None:
        return
    try:
        _backend.terminate()
        _backend.wait(timeout=3)
    except Exception:
        try:
            _backend.kill()
        except Exception:
            pass
    _backend = None
    _free_port(PORT)


def main() -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("aii.haibala.desk")
    except Exception:
        pass

    os.chdir(ROOT)
    _ensure_ui()
    start_backend()
    atexit.register(stop_backend)

    import webview
    from webview.menu import Menu, MenuAction, MenuSeparator

    storage = ROOT / "data" / "webview-desk"
    storage.mkdir(parents=True, exist_ok=True)

    window = webview.create_window(
        "haibala",
        URL,
        width=1320,
        height=880,
        min_size=(1024, 680),
        background_color="#f3f3f5",
        text_select=True,
        zoomable=False,
        shadow=True,
    )

    def _js(code: str) -> None:
        try:
            window.evaluate_js(code)
        except Exception:
            pass

    menu = [
        Menu("文件", [
            MenuAction("新建工单", lambda: _js("window.__haibala && window.__haibala.newJob()")),
            MenuSeparator(),
            MenuAction("退出", window.destroy),
        ]),
        Menu("编辑", [
            MenuAction("设置", lambda: _js("window.__haibala && window.__haibala.go('settings')")),
        ]),
        Menu("窗口", [
            MenuAction("工单库", lambda: _js("window.__haibala && window.__haibala.go('dash')")),
            MenuAction("评测", lambda: _js("window.__haibala && window.__haibala.go('eval')")),
            MenuAction("审计", lambda: _js("window.__haibala && window.__haibala.go('audit')")),
        ]),
        Menu("帮助", [
            MenuAction("关于 haibala", lambda: ctypes.windll.user32.MessageBoxW(
                0, "haibala · 本地签发台\n先出决策，盖章后再派活。", "haibala", 0x40)),
        ]),
    ]
    icon = str(ICON) if ICON.exists() else None
    webview.start(
        gui="edgechromium",
        icon=icon,
        menu=menu,
        private_mode=False,
        storage_path=str(storage),
    )
    stop_backend()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(0, str(e), "haibala", 0x10)
        sys.exit(1)
