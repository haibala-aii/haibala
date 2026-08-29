"""
haibala · M2 · core/config.py
=============================
【这一课：配置 / 依赖注入】
真实产品不能让"用哪个 judge、接哪个 agent"写死在代码里。
所以用配置文件（config.json + .env）来决定，代码只读配置。
关键点：**默认给一套"开箱即跑"的 mock 配置**，你在配置里填了真实
API/命令，就切换成真的；没填就一直用 mock，永远不会因为你没配而崩。
"""
import os, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
ENV_PATH = ROOT / ".env"

_load = lambda p: json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

# 读取 config.json；缺字段用默认值
_raw = _load(CONFIG_PATH)

# ------- 简单 .env 解析（key=value，用于放 API key，避免硬编码）------
def _env_kv():
    kv = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                kv[k.strip()] = v.strip()
    return kv

_ENV = {**_env_kv(), **os.environ}  # 环境变量优先

def get(key, default=None):
    return _ENV.get(key, default)

# ------- Judge 配置（默认 mock，配了 api 就换真的）------
JUDGE_PROVIDER = _raw.get("judge", {}).get("provider", "mock")   # mock | api
JUDGE_BASE_URL = _raw.get("judge", {}).get("base_url", "https://api.deepseek.com")
JUDGE_MODEL = _raw.get("judge", {}).get("model", "deepseek-chat")
JUDGE_API_KEY = get("DEEPSEEK_API_KEY", "")                      # 从 .env 或环境变量读

# ------- 预算 / 审批阈值 -------
BUDGET_DEFAULT = float(_raw.get("budget", {}).get("default_usd", 5.0))
APPROVAL_COST_THRESHOLD = float(_raw.get("budget", {}).get("approve_over_usd", 2.0))
