"""
haibala · M5 · core/graph.py
============================
【这一课：用真正的框架 LangGraph 做状态机】
M3 我们自己手写了状态机 + 断点。M5 把它换成 **LangGraph**：
  - StateGraph 显式定义节点(observe/decide/dispatch/judge/learn)与连线。
  - 带 checkpointer：同一个 thread_id 再次 invoke 就自动从断点继续(断点续跑)。
这样状态机更规范、可扩展(加节点/条件边/并行)，也是业界主流做法。

节点复用 pipeline 里的 do_* 阶段函数(它们写 store/案例/策略)，只是把"数据流"交给 LangGraph。
"""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from core import store
from core.pipeline import (do_observe, do_decide, do_dispatch, do_judge, do_learn,
                           _summary)
from workers import registry

class GraphState(TypedDict, total=False):
    job_id: str
    title: str
    description: str
    features: dict
    decision: dict
    artifacts: list
    leaderboard: list
    best_worker: str
    best_weighted: float
    status: str
    approvals: list

# 每个节点：在"副本"上调用阶段函数(避免直接改图状态)，返回变更字段
def n_observe(state):
    st = dict(state); do_observe(st); return {"features": st["features"]}
def n_decide(state):
    st = dict(state); do_decide(st); store.update_job_decision(state["job_id"], st["decision"]); return {"decision": st["decision"]}
def n_dispatch(state):
    st = dict(state); do_dispatch(st); return {"artifacts": st["artifacts"]}
def n_judge(state):
    st = dict(state); do_judge(st); return {"leaderboard": st["leaderboard"]}
def n_learn(state):
    st = dict(state); do_learn(st)
    return {"best_worker": st["best_worker"], "best_weighted": st["best_weighted"],
            "status": st["status"], "approvals": st["approvals"]}

def build_graph():
    g = StateGraph(GraphState)
    g.add_node("observe", n_observe)
    g.add_node("decide", n_decide)
    g.add_node("dispatch", n_dispatch)
    g.add_node("judge", n_judge)
    g.add_node("learn", n_learn)
    g.add_edge(START, "observe")
    g.add_edge("observe", "decide")
    g.add_edge("decide", "dispatch")
    g.add_edge("dispatch", "judge")
    g.add_edge("judge", "learn")
    g.add_edge("learn", END)
    # MemorySaver = 按 thread_id 记住每个 job 的状态（同进程内可断点续跑）
    return g.compile(checkpointer=MemorySaver())

def run_graph_task(title: str, description: str = "") -> dict:
    store.init_db()
    job_id = store.create_job(title, description, "", {}, {})
    app = build_graph()
    cfg = {"configurable": {"thread_id": job_id}}
    state = app.invoke({"job_id": job_id, "title": title, "description": description}, cfg)
    # 把最终特征/决策写回 job 表
    if state.get("features"):
        store.update_job_meta(job_id, state["features"]["task_type"], state["features"])
    return _summary(state)
