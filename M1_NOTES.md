# haibala · M1 学习笔记（第一课）

> 这份笔记回答两件事：**M1 做了什么**，以及**你从中学会了什么**。
> 边做边学，概念放在最前面，代码是它最小的落地。

## 0. 你这一课学会的几个概念（先记这些）

1. **接口 / 插件化**：让所有"工人 agent"统一成一个 `submit(task) -> artifact`。核心只认识接口，不认识"Codex 还是 DeepSeek"。加一个 agent = 写一个类实现接口。→ 这就是你在 DSH 看到的插件思想。
2. **抽象 / 依赖反转**：上层（pipeline）不关心具体工具，只管调用统一接口 → 扩展、替换都不改核心。
3. **特征工程（observe）**：把文字需求抽成结构化的 `features`（任务类型/技术栈/规模/复杂度/子任务数）。后续所有决策都建立在它之上。
4. **rubric + judge（评估）**：一组"带权重的评分维度"（1-5 分 + 锚点）。judge 按 rubric 给产物打分。**这是整个系统里最值钱、也最难的一环。**
5. **案例记忆 + 检索（L1 学习）**：每次跑完把「特征 → 决策 → 实际得分 → 成本」存成一条 `case`。下次接相似任务，查历史案例来推荐。→ 这是"越用越会"的最小形态。
6. **闭环（Agent 最小循环）**：observe → decide → dispatch/benchmark → judge → learn。所有高级 agent（含 LangGraph 状态机）都是这个循环的工程化。

## 1. 目录：每个文件教什么

```
agent-pm/
├─ main.py                # 入口：python main.py --run "..."; python main.py serve
├─ core/
│  ├─ store.py            # ☑ 数据层：sqlite 存 工单/评测/案例
│  ├─ features.py         # ☑ observe：文本 -> 特征
│  └─ pipeline.py         # ☑ 闭环：把下面几块串起来
├─ workers/               # ☑ 工人 agent（可插拔）
│  ├─ base.py             #    WorkerPlugin 接口 + Artifact
│  ├─ mock.py             #    MockWorker（假装干活，先跑通）
│  └─ registry.py         #    注册表：按名字找到 worker
├─ judge/                 # ☑ 裁判
│  ├─ base.py             #    JudgePlugin 接口 + DEFAULT_RUBRIC
│  └─ mock.py             #    MockJudge（按能力匹配给分）
├─ learn/
│  └─ router.py           # ☑ 决策/路由器：用案例记忆推荐 worker/拆分/优先级/预算
├─ web/dashboard.html     # ☑ 签发台风格实时界面（连后端）
└─ data/haibala.db        # 数据（删掉=重置）
```

## 2. 怎么运行

```bash
cd agent-pm
# 1) 命令行跑一个任务（走完整闭环，看输出）
python main.py --run "批量抠图小程序" --desc "抠图、换背景，交付小程序。"
# 2) 起实时界面
python main.py serve          # 浏览器打开 http://127.0.0.1:8090
# 3) 重置（清空案例/工单）
删除 data/haibala.db 即可
```

## 3. 你刚才看到的现象（这是关键！）

命令行第二次跑同样的"抠图"任务时，`source` 变成了"**参考 1 个相似案例**"。
- 第一次跑：没有历史案例 → 走**默认规则**。
- 第二次跑：系统查到了上一轮存进库的案例 → **开始参考自己的经验**了。

这就是"**边用边学**"。虽然 M1 还很简单（L1 案例检索），但它证明了**闭环是通的**：跑一次 → 打分 → 写入 → 下次参考。M2 把它升级成更聪明的策略模型，原理一样。

## 4. M1 的局限（诚实说）

- features 用关键词规则 → 不够聪明，真实场景会换 LLM/模型抽取。
- worker 是 mock（假干活）→ M2 换真的 CLI/API（Codex/dsh），接口不变。
- judge 是 mock 打分 → M2 换真的 LLM-as-judge（调 API）。
- 路由是 L1 案例检索 → M2 升级 L2 策略模型。
- 没有 LangGraph 状态机 / 没有前端框架（M1 用原生 JS + 自建 HTTP）→ 后面按 TDD 引入。

## 5. 下一步（M2 方向）

1. 做真的 `CLIWorker`：调 Codex/dsh 的 CLI（注意用"写文件读文件"而非管道捕获）。
2. 做真的 `ApiJudge`：根据 `.env` 里的 key 调 DeepSeek 打分，配**锚点 + 盲评 + 引用证据**。
3. 把界面换成 **Vue**，按你"签发台"那版百分百还原（现在是简化版）。
4. 引入 LangGraph 状态机 + 断点续跑。
