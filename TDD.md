# TDD — haibala：Agent 决策中枢（Agent Command Center）v1.0

> 状态：技术设计稿 v1.0，对应 PRD v1.0
> 产品名：**haibala**（自由职业 agent 决策中枢）。
> 架构哲学：**插件化（借鉴 DeepSeek Harness 的插件 / 技能思想，见 §4.5）**——worker、judge、路由策略、技能、钩子全部做成可插拔插件，核心稳定、扩展不动核心。
> 决策锁定：桌面端 **Tauri (Rust + Web 前端)**；核心/AI 层 **Python**；judge **可插拔 Provider（API 默认 / 本地可选 / 混合）**；首类任务 **编码/脚本类**；学 **worker 路由 / 拆分 / 优先级 / 预算**；v1 **先跑通监控+决策闭环（无画布）**。
> 目标读者：开发者（你自己），用于实现与评审。

---

## 1. 系统架构（分层）

```
┌─────────────────────────────────────────────────────────────────┐
│ 桌面壳 Tauri (Rust)                                              │
│   窗口 / 系统托盘 / 通知 / 崩溃重启 / Python sidecar 生命周期     │
├─────────────────────────────────────────────────────────────────┤
│ Web 前端 (在 Tauri WebView 中)  ← 监控/决策/评测/安全 UI          │
│      │ HTTP(rest)       │ WebSocket(实时监控事件流)              │
├──────┴───────────────────┴──────────────────────────────────────┤
│ Python 核心服务 (FastAPI, 本地 sidecar)  —— 大脑                  │
│  ┌──────────┬──────────┬───────────┬───────────┬────────────┐  │
│  │Supervisor│ Judge    │ Learn/Router│ Store     │ Security   │  │
│  │(LangGraph│(Provider │(案例+策略)  │(sqlite/   │(权限/审计/  │  │
│  │ 状态机)   │ API/本地) │            │ checkpoint)│ 防注入)    │  │
│  └────┬─────┴────┬─────┴─────┬─────┴─────┬─────┴─────┬──────┘  │
│       │          │           │           │           │          │
│  ┌────▼──────────▼───────────▼───────────▼───────────▼──────┐  │
│  │  Worker 适配层 (可插拔)                                     │  │
│  │   CLI/API 适配器 │ MCP 适配器 │ GUI 手动任务卡               │  │
│  └──────────────────────────────────────────────────────────┘  │
│        │subprocess/HTTP/MCP      │ 受限沙箱工作区                 │
│  ┌─────▼────────────────────────────────────────────────────┐  │
│  │  Agent 工具们: DeepSeek Harness / Codex CLI / Cursor / ... │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

**关键决策**：桌面壳只负责"壳/窗口/生命周撑/通知 + 拉起 Python 核心服务"；**所有编排、judge、学习逻辑在 Python**。前端 WebView 通过 `http://127.0.0.1:<port>` 与 Python 通信，用 WebSocket 订阅实时监控事件。

---

## 2. 进程与通信（Tauri ↔ Python sidecar）

- **启动**：Tauri（Rust）在启动时 spawn Python 核心（`tauri-plugin-shell` sidecar 或直接托管子进程）。核心服务监听 `127.0.0.1` 本地端口（随机或固定，写入配置文件/环境变量）。
- **健康检查**：Rust 探测核心 `/health`；崩溃时**自动重启**并恢复（核心状态落在磁盘 checkpoint）。
- **通信**：
  - 前端 → 核心：REST（读数据/触发动作）+ WebSocket（实时事件）。
  - 前端 ↔ Rust：Tauri command（系统级：托盘、通知、窗口、密钥链存取）。
- **安全**：核心只监听 localhost；加一个随机 token 校验请求来源，防本机其他进程调用。

---

## 3. 核心状态机（LangGraph · supervisor）

```
┌──────────────────────────────────────────────────────────────┐
│ observe ─▶ decide ─▶ (approve?) ─▶ split/plan ─▶ dispatch      │
│    ▲                                        │                 │
│    │                                        ▼                 │
│    │                                      execute(每子任务)      │
│    │                                        │                 │
│    │                                        ▼                 │
│    │                                      verify/collect       │
│    │                                        │                 │
│    └──── learn ◀──── store_case ◀──── judge ◀──────────────────┘
│                                        │
│                                        ▼
│                                    report/summary
│   任意节点都可 interrupt → 等用户 approve/reject/改方向
└──────────────────────────────────────────────────────────────┘
```

- **observe**：抽取任务特征（类型/技术栈/规模/复杂度/子任务数/多模态）。
- **decide**：Learner 基于特征 + 历史案例给出 `DecisionConfig`，附理由。
- **approve**：按审批策略决定是否暂停等用户确认（敏感/超支才必批）。
- **split/plan**：决定是否拆分、拆几个、依赖与优先级（基于 Learner 的建议）。
- **dispatch/execute**：按计划把子任务派给对应 worker 适配器；管理 run 状态。
- **verify/collect**：收集产物，归一到同一形态；跑可行性校验（代码类：lint/单测/冒烟）。
- **judge**：对每个产物按 rubric 打分（judge provider），盲评 + 引用证据。
- **learn**：写案例 → 更新 AgentProfile → (L2)更新路由策略模型。
- **report**：汇总榜单/交付物；写审计。

> **可断点续跑**：状态机每步把 state 落盘（checkpoint 到 sqlite/文件），中断后从 checkpoint 恢复。

---

## 4. 模块划分与职责

| 模块 | 职责 |
|---|---|
| `core/graph.py` | LangGraph 状态机与转换 |
| `core/store.py` | sqlite + checkpoint + 审计 |
| `bench/` | 任务构造、特征提取、编排分发、收集 |
| `judge/` | rubric、provider、打分、校准 |
| `learn/` | 案例库、检索(L1)、路由策略(L2) |
| `workers/` | 适配层（CLI/MCP/manual）+ worker 注册表 |
| `security/` | 权限、沙箱、审批、防注入、密钥、审计记录 |
| `monitor/` | 事件总线、遥测、WebSocket 推送 |
| `api/` | FastAPI REST + WS 路由（供前端） |
| `dashboard/` | Web 前端（Tauri WebView 内） |
| `desktop-tauri/` | Rust 壳 |

---

## 4.5 插件化架构（借鉴 DeepSeek Harness 的插件 / 技能思想）⭐

> 设计目标：**核心稳定，扩展不动核心**。把"会变的东西"全部抽象成插件：新增 agent、换 judge、加一个抓取工具、教一种任务如何验收，都通过"放一个插件"完成，而不是改核心代码。这正是你欣赏的 dsh 的做法。

### 4.5.1 插件模型（Plugin）
```python
@dataclass
class PluginManifest:
    name: str                 # 插件名（唯一）
    type: str                 # worker | judge | skill | router | hook
    entry: str                # 入口模块/文件
    version: str
    capability: list[str]     # 能力 tags，如 ["coding","image","text"]
    requires: dict[str,str]   # 依赖的运行时/其他插件
    hooks: list[str]          # 可挂载的钩子点（见 4.5.3）
```

### 4.5.2 统一插件接口（每个类型一个基类）
- `WorkerPlugin`：`submit(task, workspace) -> Artifact` + `status` + `cancel`（§8 的三种适配模式就是三类 WorkerPlugin）。
- `JudgePlugin`：`score(...)` + `pair_compare(...)`（§6 的 provider 就是一个 JudgePlugin）。
- `SkillPlugin`：封装"怎么干某类活/怎么验收"的知识（见 4.5.4）。
- `RouterPlugin`：给出 `DecisionConfig` 的策略插件（§7 学习机制里的 L1/L2 都是 RouterPlugin）。
- `Hook`：在管线固定节点挂执行逻辑（judge 前、dispatch 前、审批后等）。

### 4.5.3 插件注册表 + 发现（Discovery）
- **发现**：启动时扫描 `plugins/` 目录，读取每个插件的 `manifest`。
- **注册**：`PluginRegistry` 按 `type` 归类并校验依赖；无效插件**跳过并告警**，不阻塞核心启动。
- **生命周期**：`load → init(注入运行时依赖) → activate → (deactivate/hot-reload) → unload`。插件在**独立命名空间/隔离环境**加载，接口破坏不影响核心。
- **版本与兼容**：manifest 声明 `requires`；核心定义 stable plugin API，插件升级不动核心。

### 4.5.4 技能（Skill）与渐进式披露（Progressive Disclosure）
- 借鉴 dsh 的 `SKILL.md`：把"某类任务怎么做、怎么验收、常见坑"打包成一个 `SkillPlugin`（一个目录：`SKILL.md` + 示例 + 参考）。
- **按需加载**：只有当某类任务被触发时才把对应 skill 注入上下文，避免 prompt 臃肿（渐进式披露）。
- 你之前提的"RAG 记项目经验/怎么验收"可直接落地成 `SkillPlugin` + 案例检索，二者互补。

### 4.5.5 为什么这样设计（对你的好处）
- **你跟着学 agent、怕细节**：核心只关心 plugin API，扩展是"放插件"，学习成本低、不会把核心搞坏。
- **加 agent**：放一个 `WorkerPlugin` 或一个 MCP 注册，不用改核心。
- **换 judge**：换一个 `JudgePlugin`（api/local/hybrid 都是现成插件）。
- **学新经验**：新增一个 `SkillPlugin` 或案例即可让系统"会"新的任务类型。
- **符合 dsh 思想**：稳定内核 + 插件面，你以后想贡献/扩展都很顺。

---

## 5. 数据模型（sqlite / 存储初稿）

```sql
-- Job（一个项目/接单任务）
CREATE TABLE job(
  id TEXT PRIMARY KEY, title, description, task_type,
  features_json TEXT,          -- 抽取的路由特征
  decision_config_json TEXT,   -- {worker, split, priority_order, budget}
  status TEXT, budget_cents INTEGER, created_at, updated_at
);

-- Subtask
CREATE TABLE subtask(
  id TEXT PRIMARY KEY, job_id, title, depends_on TEXT, assignee TEXT,
  estimate, priority INT, status TEXT, artifact_path TEXT,
  acceptance_json TEXT, attempts INT, max_attempts INT
);

-- Run（一次分发执行 = 一个 worker 干活）
CREATE TABLE run(
  id TEXT PRIMARY KEY, job_id, subtask_id, worker TEXT,
  status TEXT, artifact_path TEXT, cost_usd REAL,
  latency_ms INTEGER, input_tokens INTEGER, output_tokens INTEGER,
  started_at, finished_at, error TEXT
);

-- Rubric
CREATE TABLE rubric(
  id TEXT PRIMARY KEY, title, dimensions_json TEXT -- [{name,weight,scale,anchors}]
);

-- Evaluation（judge 打分）
CREATE TABLE evaluation(
  id TEXT PRIMARY KEY, job_id, run_id, rubric_id, scores_json TEXT,
  weighted_total REAL, rationale TEXT, judge_provider TEXT, judge TEXT
);

-- AgentProfile（按 worker 聚合的长期画像）
CREATE TABLE agent_profile(
  worker TEXT PRIMARY KEY, avg_weighted_total REAL, strengths_json TEXT,
  weaknesses_json TEXT, avg_cost_usd REAL, avg_latency_ms INTEGER,
  sample_eval_ids TEXT, updated_at
);

-- Case（学习案例：特征→决策→结果）
CREATE TABLE case (
  id TEXT PRIMARY KEY, task_type TEXT, features_json TEXT,
  decision_config_json TEXT, chosen_worker TEXT, result_json TEXT,
  cost_usd REAL, actual_score REAL, pitfalls TEXT, created_at
);

-- AuditEvent（审计，只增不删）
CREATE TABLE audit_event(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts, actor, action, detail_json,
  job_id, approved_by, outcome
);

-- BudgetSnapshot（成本预算）
CREATE TABLE budget_snapshot(job_id, ts, cost_usd, budget_usd, alert_level);
```

---

## 6. Judge 设计（JudgePlugin · 可插拔 Provider）

### 6.1 Provider 抽象（回答"我只有API、别人要本地"）

```python
class JudgeProvider(ABC):
    def score(self, rubric, artifact, context) -> Evaluation: ...
    def pair_compare(self, a, b, rubric) -> (winner, rationale): ...

class ApiJudgeProvider(JudgeProvider):   # 默认：任意 OpenAI 兼容接口(base_url)
    # 配置 base_url/model/api_key；支持 DeepSeek/OpenAI/any
class LocalJudgeProvider(JudgeProvider): # ollama / llama.cpp
class HybridJudgeProvider(JudgeProvider):# 按任务敏感度路由 本地/云端
```
- **配置驱动**：`.env`/`config.yaml` 里 `judge.provider=api|local|hybrid` + 各 provider 参数。**切 Judge 不改核心代码**。
- 这是对"你很灵活"需求的落地：你只用 API 就配 `api`；别人只跑本地就配 `local`。

### 6.2 打分可靠度（judge 质量 = 学习质量的地基）
1. **锚点 rubric**：每维度 1-5 都有"几分长什么样"。
2. **盲评**：隐藏 worker 身份，防对知名工具高看一眼。
3. **引用证据**：必须引用产物具体片段作为依据，防空口打分。
4. **双模态**：绝对打分 + 两两对比(pairwise) 交叉校准。
5. **人工校准**：用户 override 若干为 ground truth，量化 judge 偏差/一致度，并可微调 prompt。
6. **去偏**：警惕 verbosity/长度/位置偏好；多次采样取均值。

> 目标定位：**相对排序稳定、可解释、可校准**，而非绝对真理。

---

## 7. 学习 / 自我改进机制（核心差异化）

### 7.1 决策目标（学什么）
对每个任务输出一个 `DecisionConfig`：
```
{ "worker": chosen_worker,        // 路由：用哪一个 agent
  "split": true|false,            // 是否拆分成多 agent 并行
  "n_workers": 3,                 // 拆几个
  "priority_order": ["data","model","frontend"], // 子任务优先级
  "budget_usd": 5.0 }             // 预算
```

### 7.2 层级
- **L1 案例检索（v1 必做）**：接单时对 `features` 做向量化检索相似案例，直接采用历史最优 `DecisionConfig`。可解释（"参考案例 C-x 同样类型，用 codex 效果好"）。用 sqlite + 轻量向量（本地 embed 或 API embed 可配）。
- **L2 路由策略模型（v1 后期 / v2）**：用积累的 `features → (decision, actual_score)` 数据，训练一个轻量模型（决策树/梯度提升/小分类器），**泛化到新任务**。特征：task_type, stack, size, complexity, n_subtasks, multimodal, urgency, budget。标签：最佳 worker + split 是否 + priority。用 `actual_score` 作为奖励来挑最优决策。冷启动用**人工种子基线**（用户先填几条"这类任务用谁"）。
- **L3（暂缓）**：多臂老虎机选 worker / RLHF 式偏好优化（研究向）。

### 7.3 闭环与评估
- 每次执行 → judge 得到 `actual_score`/成本 → 更新 `case` → 更新 `AgentProfile` → 周期性重训 L2 模型。
- 用"同类型任务最佳 worker 命中率""平均 actual_score 随轮次变化"作为**学习有效性**指标。
- **警告：judge 噪声会污染学习信号**，所以 judge 校准必须在学习之前做好。

---

## 8. Worker 适配层（WorkerPlugin：怎么适配更多 agent / CLI 好不好适配）

> 工人 = 一组 `WorkerPlugin`。下表三种模式就是三类 WorkerPlugin；经由 §4.5 的插件注册表加载，新增 agent 只加插件，不改核心。

统一接口：
```python
class WorkerAdapter(ABC):
    name: str
    capability: list[str]          # ["coding","image","text",...]
    automate_scope: "auto"|"manual"
    def submit(self, task, workspace) -> Artifact: ...
    def status(self, run_id) -> WorkerStatus: ...
    def cancel(self, run_id): ...
```

**三种模式（覆盖几乎所有 agent）：**
1. **CLI/API 适配器（最容易）**：包一层 `subprocess`（Codex CLI、dsh CLI）或 HTTP。**注意**：受限环境下 `subprocess` 捕获 stdout 管道会 EPERM，所以**用"写文件+读文件"或 `stdio:inherit` 取结果**；统一以 `artifact`（产物路径 + 元数据）返回。
2. **MCP 适配器（最通用，零代码接新 agent）**：实现一个通用 MCP client。**任何提供 MCP server 的工具**都能以 `<mcp://...>` 接入，无需逐个写适配器。这是"加 agent 最省事"的方案。
3. **GUI 手动任务卡（兜底）**：Cursor 界面/Coze/MiniMax 这类 GUI，走"控制台发任务卡 → 用户手动完成 → 登记 done + 产物"。

**Worker 注册表**：以配置声明新增 worker：
```yaml
workers:
  codex:   {type: cli,     cmd: "codex",   capability: [coding]}
  dsh:     {type: cli,     cmd: "dsh",     capability: [coding, agent]}
  mcp-tool:{type: mcp,     server: "...",  capability: [...]}
  cursor:  {type: manual,  note: "GUI工具，手动完成"}
```
**加 agent = 填一段配置**；遇到新类型的自动工具再写一个薄适配器即可。不侵入核心。

---

## 9. 安全模型

- **沙箱**：每个 worker 独立工作区（临时目录）+ 受限网络（可选）+ 隔离进程/容器；防互相污染、可审计。
- **权限与审批**：定义动作权限等级；不可逆/敏感/高成本动作 → **暂停等用户显式批准**；最小权限。
- **防 prompt injection**：一切外部来源内容（网页、工具返回、客户文档）进入 prompt 前做分隔转义 + 护栏校验，防止提权/泄密。⚠️ 最重要的一条。
- **密钥管理**：API key/凭证用 OS 密钥链（Tauri 插件）存取，禁止明文入库；`config.yaml` 只引用变量。
- **审计**：所有动作、审批、越权尝试写 `audit_event`（只增不删），提供回放/导出。
- **进程安全**：核心只监听 `127.0.0.1` + 随机 token 鉴权。

---

## 10. 监控与遥测

- **事件总线**：核心内所有状态变化/决策/评测/成本/安全事件发布到 event bus。
- **WebSocket 推送**：前端订阅，实时刷新（状态、进度、token/成本、决策理由、评分、日志、安全告警）。
- **指标**：任务级与 worker 级的状态、成本、延迟、token、成功/失败、超预算告警。
- **日志**：结构化日志（JSON Lines），可检索/回放；关键节点落 `audit_event`。

---

## 11. 技术选型与依赖

| 分类 | 选型 | 备注 |
|---|---|---|
| 桌面壳 | Tauri 2（Rust） | 轻量、省内存，适合常驻监控 |
| 前端 | Vue 3 / Vite（WebView 内） | 你熟（用过 Astro/Vue/uni-app） |
| 核心服务 | Python 3.11 + FastAPI + Uvicorn | 本地 sidecar |
| 编排 | LangGraph | 状态机 + checkpoint |
| 存储 | SQLite + 轻量向量（sqlite-vec 或 faiss） | v1 规模小够用；后续可换 pg+pgvector |
| Judge | 自写 provider 层（API/本地/混合） | 见 §6 |
| 向量/embed | OpenAI-compatible embed 或本地 embed | 可配 |
| 进程/沙箱 | subprocess（文件IO）/ Docker 可选 | 注意 stdout 管道 EPERM |
| 打包 | cargo-tauri + 管道打包 Windows | 后续 macOS/Linux |

---

## 12. 目录结构

```
agent-cmd/
├─ PRD.md / TDD.md
├─ README.md
├─ Cargo.toml                 # Tauri(Rust) 壳
├─ src-tauri/                 # Rust: 窗口/托盘/通知/sidecar管理
│  ├─ src/main.rs
│  └─ tauri.conf.json
├─ src/                       # Web 前端 (Vue)
│  ├─ views/ (Dashboard/Job/Evaluate/Security/Logs)
│  └─ ...
├─ plugins/                   # ⭐ 插件目录（worker/judge/skill/router/hook，各自manifest）
│  ├─ workers/ (codex, dsh, cursor, mcp-*)
│  ├─ judges/  (api, local, hybrid)
│  ├─ skills/  (SKILL.md for 各任务类型)
│  └─ routers/ (case-bank, policy-model)
├─ core/                      # Python 核心
│  ├─ main.py                 # FastAPI 入口
│  ├─ graph.py / store.py
│  ├─ bench/ (features, dispatch, collect)
│  ├─ judge/ (rubric, provider, calibrate)
│  ├─ learn/ (cases, retrieve, policy)
│  ├─ workers/ (base, cli, mcp, manual, registry)
│  ├─ security/ (permissions, sandbox, sanitize, audit)
│  ├─ monitor/ (event bus, telemetry, ws)
│  └─ config.yaml / .env.example
├─ data/                      # sqlite / checkpoint / faiss
└─ runs/                      # 每次任务的产物/日志
```

---

## 13. M1（v1）交付清单

- [ ] Tauri 壳能拉起 Python 核心并 WebSocket 连上，面板显示"在线/健康"。
- [ ] 建任务 → 特征抽取 → 决策生成（含理由）→ 审批 → 分发到 1-2 个 CLI worker。
- [ ] 监控：实时状态 + token/成本/延迟 + 决策理由展示（WebSocket 推送）。
- [ ] rubric 定义（含锚点）→ judge 打分（API provider）→ 榜单 + 引用证据。
- [ ] 案例入库 → 接单时按相似案例推荐（L1）。
- [ ] 安全：敏感/超支审批 + 审计日志 + 密钥链存取 + 沙箱工作区。
- [ ] 一条真实"编码/脚本类"任务全流程跑通。

---

## 14. 风险与缓解

| 风险 | 缓解 |
|---|---|
| judge 噪声污染学习 | judge 校准先于学习；锚点+盲评+引用证据+人工校准 |
| 学习冷启动 | 人工种子基线；先 L1 案例检索，L2 后置 |
| 适配 agent 困难 | CLI/MCP/manual 三种模式；MCP 通用接入；注册表配置即插 |
| 范围大 | v1 只做 M1 闭环，无画布；严格按里程碑推进 |
| subprocess stdout EPERM | 用文件IO / stdio:inherit，不用管道捕获 |
| 本地/云端切换 | judge provider 配置化（api/local/hybrid） |
| 密钥泄露 | OS 密钥链 + 混淆/不落盘明文 |

---

## 15. 测试策略

- **单元**：特征抽取、决策生成、rubric 打分（mock provider）、案例检索、权限判定、防注入清洗。
- **集成**：一次真实任务全流程（CLI worker + judge + 学习入库）；监控事件订阅正确性。
- **judge 一致性**：同一批产物多次打分，衡量方差；用户校准集上的偏差。
- **学习有效性**：用合成/历史数据验证 L1→L2 命中率上升。
- **安全**：注入样本不越权；未授权敏感操作被拦截；审计完整。
- **端到端**：Tauri 界面触发→核心执行→面板实时更新。

---

## 16. 待定 / TODO

1. 存储：sqlite+轻量向量 还是直接 postgres+pgvector（取决于数据量）。
2. v1 是否含"手动任务卡"，还是仅 CLI 自动 worker。
3. 预算货币与单位；API 单价自动折算来源。
4. 是否支持多任务并行（v1 单任务，后续多任务）。
5. 开源许可（建议 MIT）与项目命名。
6. 界面中文 or 中英双语。
7. 各 agent 的具体 CLI 命令/API 参数（写适配器时定）。
