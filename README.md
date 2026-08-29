# haibala — 管理 Agent 的 Agent

> 一个本地优先、开源的「多 Agent 决策 + 评测」中枢。
> 它站在多个 coding/设计 agent 之上：帮你**观察任务 → 决策（用谁 / 拆不拆 / 优先级 / 预算）→ 派活 → 按 rubric 打分 → 并学会越来越会做这些决策**。你可在签发台界面实时看监控、决策理由、评测与审计，并安全审批。

**一句话**：让"用 AI 干活"这件事更可控、可解释、可量化，而且**越用越懂你**。

---

## ✨ 功能

- **决策中枢（supervisor）**：对一个任务自动给出一份 `DecisionConfig` —— 用哪个 worker、是否拆分成多 agent 并行、优先级、预算，并附**理由与来源案例**。
- **同场比试（benchmark）**：把同一任务派给多个 agent，按 **rubric（带锚点的评分维度）** 打分，形成对比榜单。
- **LLM-as-judge**：可配置的裁判（`mock` 开箱即跑 / 真 DeepSeek-API 打分，带**盲评 + 引用证据**）。
- **学习（边用边学）**：每次跑完把「特征 → 决策 → 实际得分 → 成本」存为案例；下次接相似任务检索推荐（L1），后续升级 L2 路由策略。
- **Agent 画像 / 跨任务榜单**：聚合每个 agent 的能力、平均分、样本数。
- **安全审批（human-in-the-loop）**：敏感动作 / 超成本 → 任务停在"待盖章"，你批准才继续，并全程写**审计日志**。
- **签发台 UI**：总览 / 任务 / 评测 / 审计 / 审批 / 设置，实时接入后端。

## 🔌 平台

- **核心**：Python（默认仅标准库 + sqlite；可选 `langgraph` / `scikit-learn`）
- **界面**：Vue 3 签发台（`frontend/`）；后端也带一份原生 `web/dashboard.html`
- **编排**：M3 手写状态机 + 断点续跑；M5 优先 LangGraph，未装则回退

## 🚀 快速开始

**方式一：浏览器（后端直接带原生界面）**
```bash
cd haibala
python main.py serve          # 打开 http://127.0.0.1:8090
```

**方式二：Vue 前端（签发台还原版，需 Node）**
```bash
cd haibala/frontend
npm install
npm run dev                   # 另开终端先跑后端: python main.py serve
# 浏览器打开 http://localhost:5173（前端经代理调后端 8090）
```

命令行跑一个任务（走完整闭环并打印结果）：

```bash
python main.py --run "批量抠图小程序" --desc "抠图、换背景，交付小程序。"
```

## ⚙️ 启用真实接口（可选，默认 mock 兜底）

1. **真 judge**：复制 `.env.example` 为 `.env` 填 `DEEPSEEK_API_KEY=`，`config.json` 里 `judge.provider` 改为 `api`。
2. **真 worker**：`config.json` 的 `workers` 里把 `codex` / `dsh` 的 `enabled` 改为 `true`（确保命令在 PATH ）。没配好会自动回退 mock，绝不崩。
3. **可选依赖**：`pip install langgraph` —— 装了则状态机用 LangGraph（带断点续跑）。`pip install scikit-learn` —— 装了则路由用更强的逻辑回归，否则回退纯 Python softmax。

## 🖥 桌面打包（Tauri，需先装 Rust）

已搭好 `src-tauri/` 骨架。本机已可安装 **Rust**（`rustc` / `cargo`）。编桌面应用还需要 **MSVC 链接器**（Visual Studio Build Tools 的 C++ 工作负载）以及 WebView2。
装齐后：`npm i -g @tauri-apps/cli` → 在 `src-tauri` 里 `cargo tauri build`（会先 build 前端，`frontendDist` 指向 `frontend/dist`）。
> `/api` 在 Vite 开发时已代理到 `8090`；Tauri 打包后的跨域/代理由桌面壳这边再接。

## 📁 目录

```
main.py            入口（命令行 + 本地 Web）
core/              store · features · pipeline · graph(LangGraph)
workers/           WorkerPlugin 接口 + mock + 真实 CLI 适配 + 注册表
judge/             JudgePlugin 接口 + mock + 真 LLM-as-judge(api)
learn/             router · policy(L2) · model(softmax) · sklearn_model(可选)
frontend/          Vue 3 签发台（榜单/画像图表）
web/dashboard.html 后端自带的签发台页面
src-tauri/         桌面壳骨架（需本机 Rust）
PRD.md / TDD.md    产品与技术设计
```

## 🗺 路线图

- **M1** 监控 + 决策闭环（已完成）
- **M2** 可配置 judge/worker + 安全审批 + 审计 + Agent 榜单（已完成）
- **M3** 状态机 + 断点续跑（checkpoint/resume）+ 真实 CLI 驱动（已完成）
- **M4** 学习升级 L2（在线线性路由策略）+ 案例库 RAG 经验（已完成）
- **M4.5** 真监督学习：softmax 逻辑回归路由（梯度下降，纯 Python）（已完成）
- **M5** LangGraph 状态机 + Vue 签发台（已完成）；Tauri 桌面打包（装好 Rust 后由本机编译，需处理 `/api` 代理）
- **M5.5** 可选 sklearn 逻辑回归路由；评测页榜单/画像图表（已完成）

## 📄 License

[MIT](./LICENSE)
