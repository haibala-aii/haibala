# haibala · M2 说明（怎么测、怎么开真接口）

## 现在能测什么（M2 完成）

- 建任务 → 抽特征 → 决策(用谁/拆不拆/优先级/预算) → **同场比试**多个 agent
- **跨任务 Agent 榜单**（/api/leaderboard）：谁一直擅长什么、平均分、样本数
- **安全审批**：敏感动作 / 高成本 → 任务变 `awaiting_approval` + 一条"待盖章"，可在界面批准/拒绝，并写审计
- **审计日志**：decide/judge/approval 每一步都记录
- **可配置**：judge、worker 都能切真/切假，开箱即跑，不配就回退 mock

## 怎么运行

```bash
cd agent-pm
python main.py serve        # 浏览器打开 http://127.0.0.1:8090
```
界面里：**总览**看卡片；**任务**看决策+同场比试；**评测**看 Agent 榜单；**审计**看全链路；**审批**处理"待盖章"。

## 怎么开"真"的（关键，你用的时候再开）

### 1) 真 judge（LLM-as-judge）
- 复制 `.env.example` 为 `.env`，填 `DEEPSEEK_API_KEY=你的key`
- 改 `config.json`：`"judge": {"provider": "api", ...}`（base_url/model 默认 DeepSeek）
- 重启。此后评分走真大模型（带锚点+盲评+引用证据）；没 key 就自动回退 mock。

### 2) 真 worker（Codex / dsh / MiniMax CLI）
- 在 `config.json` 的 `workers` 里，把要用的改成 `"enabled": true`（如 codex）。
- 确保命令在 PATH / 可调用（`cmd` 填命令名，可带参数）。
- 该 worker 会以"CLIWorker"注册，跑真实命令；命令不行会自动回退 mock，不会崩。

## 这一课你学会（M2 比 M1 多的）

1. **配置驱动**：真实产品不把"用哪个"写死，用配置文件 + 环境变量注入密钥；默认给 mock 兜底。
2. **真 LLM-as-judge 的正确姿势**：锚点 rubric、盲评（不透露 worker）、引用证据、严格 JSON 输出。
3. **真实 CLI worker**：用"写文件/读文件"而不是捕获 stdout 管道（受限环境会 EPERM；很多 agent 命令还交互）。
4. **安全审批流**：敏感/超支 → 状态机停在"待盖章"，人批准才继续（human-in-the-loop）。
5. **审计与画像**：所有动作可查，跨任务聚合出"每个 agent 的能力画像"。

## 局限（下一步/真实化）
- features 仍未用 LLM 抽取（关键词），真实场景换 LLM。
- CLI worker 尚未真正验证（需你在本机的 codex/dsh 跑通）。
- 前端还是原生 JS；后续按 TDD 换 Vue + Tauri 壳。
- 学习仍是 L1(案例检索)；L2 策略模型在 M4。
