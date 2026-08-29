"""
haibala 队长对话：先出决策草案，你说「开始」才盖章派活。
"""
from core import store
from core.pipeline import propose_task, confirm_task

_SESSIONS: dict[str, dict] = {}

START_WORDS = ["开始", "确认", "批准", "执行", "开跑", "go", "start", "盖章"]
BENCH_WORDS = ["同场", "比试", "都跑", "对比"]
TASK_HINTS = ["做", "实现", "写", "开发", "生成", "搭建", "帮我", "小程序", "app",
              "网站", "抠图", "爬", "文案", "脚本", "系统", "批量", "处理", "换背景"]


def _is_start(t):
    t = t.lower().strip()
    return any(w in t for w in START_WORDS) and len(t) <= 16


def _looks_like_task(t):
    return len(t) > 12 or any(h in t.lower() for h in TASK_HINTS)


def _decision_text(features, decision):
    return (f"对「{features['task_type']}」类任务，建议用 **{decision['worker']}**；"
            f"{'拆分 ' + str(decision['n_workers']) + ' 路' if decision['split'] else '不拆分'}；"
            f"预算 ${decision.get('budget_usd')}。"
            f"\n理由：{decision['reason']}")


def supervisor_reply(sid: str, text: str) -> dict:
    store.init_db()
    draft = _SESSIONS.get(sid)

    if _is_start(text) and draft:
        mode = "benchmark" if any(w in text for w in BENCH_WORDS) else draft.get("mode", "dispatch")
        result = confirm_task(draft["job_id"], "accept", mode=mode)
        _SESSIONS.pop(sid, None)
        board = result.get("leaderboard") or []
        top = board[0] if board else {}
        if result.get("status") == "awaiting_manual":
            reply = "已盖章。这是手动任务卡，请在 Cursor 做完后到工单里回填产物。"
        elif result.get("status") == "rejected":
            reply = "已拒绝，没有派活。"
        else:
            reply = (f"已盖章并派活：{result.get('title')}\n"
                     + (f"最强 **{top.get('worker')}**（{top.get('weighted')} 分）。" if top else "已完成。")
                     + (f" 状态：{result.get('status')}。" if result.get("status") != "done" else ""))
        return {"reply": reply, "result": {"job_id": result.get("job_id"), "best": top.get("worker"), "status": result.get("status")}}

    if _looks_like_task(text):
        title = text[:24] if len(text) <= 24 else text[:20] + "…"
        proposed = propose_task(title, text)
        features = proposed["features"]
        decision = proposed["recommended_decision"]
        _SESSIONS[sid] = {"job_id": proposed["job_id"], "mode": "dispatch"}
        warn = "\n这项描述里有敏感动作，盖章即表示你允许派活。" if proposed.get("sensitive") else ""
        reply = (
            f"草案已出，工单 {proposed['job_id']} 停在待盖章：\n"
            f"- 类型：**{features['task_type']}**（规模 {features['size']} / 复杂度 {features['complexity']}）\n"
            f"- {_decision_text(features, decision)}{warn}\n\n"
            f"回复「开始」只派建议的人；回复「开始同场比试」则让能自动跑的工人一起比。"
            f"也可以先去工单库改派再盖章。")
        return {"reply": reply, "result": {"job_id": proposed["job_id"], "status": "awaiting_decision"}}

    if any(w in text for w in ["哪个", "谁好", "用谁", "擅长"]):
        profiles = store.agent_profiles()
        line = "；".join(f"{p['worker']} 均分 {p['avg_score']}" for p in profiles) or "暂无数据"
        return {"reply": f"目前各 agent 的表现：{line}。（跑更多任务后会更准）"}

    return {"reply": "我是 haibala 队长。直接说你想做什么，我会先出决策等你盖章，不会擅自派活。"}
