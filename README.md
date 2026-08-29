<p align="center">
  <img src="frontend/public/logo.png" width="88" alt="haibala">
</p>

<h1 align="center">haibala</h1>

<p align="center">
  本地优先的多 Agent 签发台：先出决策，你盖章后再派活。
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11+-3776AB.svg">
  <img alt="Vue 3" src="https://img.shields.io/badge/ui-Vue%203-42b883.svg">
</p>

haibala 站在多个 coding / 设计 agent 上面，做一件事：把「用谁、拆不拆、预算多少」变成可解释的决策，等人确认后才真正派活，再按 rubric 打分、把结果记成案例。

它不是画布，也不是 SaaS。数据默认在本机 SQLite。

## 现状（请先读这一段）

能跑通的是 **mock 工人 + 签发闭环 + 本机界面**。真 CLI 工人、真 LLM 裁判、安装包都还要自己配，有的还没做完。

| 能力 | 状态 |
| --- | --- |
| 观察 → 决策 → **盖章** → 派活 → 打分 → 学习 | 已接通 |
| 新建只出决策，`accept` / `modify` / `reject` 之后才派活 | 已接通 |
| 默认只派选中的 worker；可选同场比试 | 已接通 |
| Cursor 走手动任务卡，回填后再打分 | 已接通 |
| L1 案例检索；L2（sklearn / softmax / 线性策略） | 已接通 |
| Mock judge 盲评（理由里不写 worker 名） | 已接通 |
| Vue 签发台（工单库 / 对话 / 评测 / 审计 / 待确认 / 设置） | 已接通 |
| Windows 桌面窗（pywebview + WebView2，端口 `18765`） | 已接通 |
| 默认真实 CLI worker（codex / dsh 等） | 适配器有，`config.json` 里默认关闭 |
| 真 LLM judge | 有，需要 API key |
| Tauri 安装包 | 仅有 `src-tauri/` 骨架，本机还需 MSVC `link.exe` |
| OS 密钥链 / 沙箱 / `plugins/` 自动发现 | 未做 |
| Rubric 编辑器、pairwise、人工校准 | 未做 |
| 超支审批拦住执行 | 未做（超支是事后记账，活已经干完） |

技术说明见 [TDD.md](TDD.md)。

## 它怎么走一单

```
observe → decide → [你盖章] → dispatch → judge → learn
```

1. 新建工单或对话里描述任务，队长只给出 `DecisionConfig`（worker、是否拆分、预算、理由和参考案例）。
2. 你选择接受、改派或拒绝。拒绝不会派活。
3. 盖章后才调用 worker。手动工人（例如 Cursor）会停在任务卡，等你回填产物。
4. Judge 按带锚点的 rubric 打分；学习模块把「特征 → 决策 → 得分 → 成本」写入案例库。

命令行 `python main.py --run "..."` 会 **自动盖章并同场比试**，方便演示榜单，和界面路径不一样。

## 环境

- Python 3.11+
- 前端构建需要 Node.js 18+（`npm`）
- 桌面窗：Windows 10/11 + WebView2 + `pywebview`
- 可选：`langgraph`（状态机）、`scikit-learn`（路由）

```bash
git clone https://github.com/haibala-aii/haibala.git
cd haibala
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
```

没装可选依赖也能跑：LangGraph 导入失败会回退手写状态机；没装 sklearn 会回退纯 Python softmax。

## 用法

### 浏览器

```bash
python main.py serve          # http://127.0.0.1:8090
```

若还没 `npm run build`，这里会退回 `web/dashboard.html` 备用页，不是 Vue 签发台。开发时也可以：

```bash
python main.py serve          # 终端 1，8090
cd frontend && npm run dev    # 终端 2，5173，/api 代理到后端
```

### Windows 桌面窗

桌面壳 **不会复用** 可能还在跑的 8090 旧页面，它固定拉 `18765`：

```bash
pip install pywebview
python desktop/app.py
```

也可以双击 `desktop/launch.vbs`（无控制台）。第一次会检查 `frontend/dist`，没有则尝试 `npm run build`。

### 命令行（演示闭环）

```bash
python main.py --run "批量抠图小程序" --desc "抠图、换背景，交付小程序。"
python main.py --run "..." --stop-after dispatch
python main.py --resume JOB-xxxx
```

`--run` 会自动盖章、默认走同场比试。待盖章的任务不能直接 `--resume`。

## 配置

复制 `.env.example` 为 `.env`。密钥只放环境变量，不要写进 `config.json`。

| 目的 | 怎么开 |
| --- | --- |
| 真 judge | `.env` 填 `DEEPSEEK_API_KEY`，`config.json` 里 `judge.provider` 改为 `api` |
| 真 CLI worker | `config.json` → `workers.<name>.enabled: true`，且命令在 `PATH` 里 |
| MCP worker | `mcp_servers` 里打开对应项 |

配不好会回退 mock，进程不应因此崩溃。仓库里的 `config.json` 默认全部真实工人关闭。

## 目录

```
main.py              HTTP + CLI 入口（优先托管 frontend/dist）
core/                存储、特征、pipeline、LangGraph 封装
agents/              对话队长（只提案，不擅自派活）
workers/             WorkerPlugin：mock / cli / manual / mcp
judge/               JudgePlugin：mock / OpenAI 兼容 API
learn/               L1 检索 + L2 策略（线性 / softmax / sklearn）
frontend/            Vue 3 签发台
desktop/             pywebview 桌面壳（端口 18765）
web/dashboard.html   未构建 Vue 时的备用页
src-tauri/           Tauri 打包骨架（尚未在本仓库编出安装包）
config.json          默认 mock；真实工人默认 enabled: false
TDD.md               技术设计
```

运行时数据在 `data/`（SQLite、webview 缓存），已加入 `.gitignore`。

## 还没做

对照产品预期，下面这些 **不要当成已经交付**：

- 可分发的桌面安装包（Tauri + MSVC 链接器）
- 密钥进系统钥匙串、执行沙箱、FastAPI 化
- `plugins/` 目录扫描与热加载
- 在派活前拦住超支（现在超支审批发生在 learn 之后）
- 用 LLM 抽特征（现在是关键词规则）
- Rubric 可视化编辑、pairwise、人工校准分

## License

[MIT](LICENSE)
