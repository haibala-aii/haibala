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

- **核心**：Python（零第三方依赖，仅标准库；`sqlite` 存储）
- **界面**：原生 HTML/JS（签发台风格，本地 Web）
- **编排**：M1 用清晰的状态循环；后续引入 LangGraph 状态机 + 断点续跑

## 🚀 快速开始

```bash
cd haibala
python main.py serve          # 打开 http://127.0.0.1:8090
```

命令行跑一个任务（走完整闭环并打印结果）：

```bash
python main.py --run "批量抠图小程序" --desc "抠图、换背景，交付小程序。"
```

## ⚙️ 启用真实接口（可选，默认 mock 兜底）

1. **真 judge**：复制 `.env.example` 为 `.env` 填 `DEEPSEEK_API_KEY=`，`config.json` 里 `judge.provider` 改为 `api`。
2. **真 worker**：`config.json` 的 `workers` 里把 `codex` / `dsh` 的 `enabled` 改为 `true`（确保命令在 PATH ）。没配好会自动回退 mock，绝不崩。

## 📁 目录

```
main.py            入口（命令行 + 本地 Web）
core/              store(数据/审计) · features(特征) · pipeline(闭环)
workers/           WorkerPlugin 接口 + mock + 真实 CLI 适配 + 注册表
judge/             JudgePlugin 接口 + mock + 真 LLM-as-judge(api)
learn/             router（决策/案例检索学习）
web/dashboard.html 签发台界面
PRD.md / TDD.md    产品与技术设计
```

## 🗺 路线图

- **M1** 监控 + 决策闭环（已完成）
- **M2** 可配置 judge/worker + 安全审批 + 审计 + Agent 榜单（已完成）
- **M3** 前端 Vue 化 + 真正驱动 Codex/dsh；引入 LangGraph + 断点续跑
- **M4** 学习升级 L2（路由策略模型）+ 案例库 RAG
- **M5** Tauri 桌面壳 + 打包分发

## 📄 License

[MIT](./LICENSE)
