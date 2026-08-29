"""
haibala · M1 · core/store.py
===========================
【这一课：数据层 / 存储】
整个系统的"记忆"在这里。我们先用 Python 自带的 sqlite（零安装），
后面再换更强的（postgres / 向量库）。你用到的存储其实就这几种：

  - job        一张"工单"（一个接单项目）
  - subtask    拆出来的子任务
  - run        一次"分发执行"（某 worker 干某子任务的记录）
  - evaluation 一次 rubric 打分
  - case       一条"学到的经验"（特征 -> 决策 -> 实际得分）

为什么要持久化（存到硬盘 sqlite）？
  因为"决策+学习"需要：这次决定好不好，要留给下次参考（案例库）。
  也方便你随时查看、审计、断点续跑。
"""
import sqlite3, json, os, uuid
from datetime import datetime

# 数据库文件放在项目 data/ 目录
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "haibala.db")

def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    """建表。只在第一次运行时需要。"""
    c = _conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS job(
      id TEXT PRIMARY KEY,
      title TEXT,
      description TEXT,
      task_type TEXT,
      features_json TEXT,          -- 特征(observe 抽取)
      decision_json TEXT,          -- 决策(decide 生成)
      status TEXT,
      created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS subtask(
      id TEXT PRIMARY KEY,
      job_id TEXT,
      title TEXT,
      worker TEXT,
      priority INT,
      status TEXT,
      artifact_path TEXT
    );
    CREATE TABLE IF NOT EXISTS evaluation(
      id TEXT PRIMARY KEY,
      job_id TEXT,
      worker TEXT,
      scores_json TEXT,            -- 各维度分数
      weighted REAL,               -- 加权总分
      rationale TEXT,
      judge TEXT
    );
    CREATE TABLE IF NOT EXISTS case_tab(
      id TEXT PRIMARY KEY,
      task_type TEXT,
      features_json TEXT,
      decision_json TEXT,          -- 当时用了什么决策
      actual_score REAL,           -- 实际打分(judge)
      cost_usd REAL,
      pitfalls TEXT,
      created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS audit_log(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT, actor TEXT, action TEXT, detail TEXT, job_id TEXT
    );
    CREATE TABLE IF NOT EXISTS approval(
      id TEXT PRIMARY KEY,
      job_id TEXT, worker TEXT, action TEXT, reason TEXT,
      status TEXT,                  -- pending / approved / denied
      decided_at TEXT
    );
    """)
    c.commit(); c.close()

# ---------- 工具 ----------
def _now(): return datetime.now().isoformat(timespec="seconds")
def _uid(prefix): return f"{prefix}-{uuid.uuid4().hex[:8]}"

# ---------- Job ----------
def create_job(title, description, task_type, features, decision):
    c = _conn(); jid = _uid("JOB")
    c.execute("INSERT INTO job VALUES (?,?,?,?,?,?,?,?)",
              (jid, title, description, task_type,
               json.dumps(features, ensure_ascii=False),
               json.dumps(decision, ensure_ascii=False),
               "running", _now()))
    c.commit(); c.close()
    return jid

def update_job_status(jid, status):
    c = _conn(); c.execute("UPDATE job SET status=? WHERE id=?", (status, jid)); c.commit(); c.close()

def list_jobs():
    c = _conn()
    rows = c.execute("SELECT * FROM job ORDER BY created_at DESC").fetchall()
    c.close()
    return [dict(r) for r in rows]

def get_job(jid):
    c = _conn(); r = c.execute("SELECT * FROM job WHERE id=?", (jid,)).fetchone(); c.close()
    return dict(r) if r else None

# ---------- Evaluation ----------
def add_evaluation(job_id, worker, scores, weighted, rationale, judge):
    c = _conn()
    c.execute("INSERT INTO evaluation VALUES (?,?,?,?,?,?,?)",
              (_uid("EVAL"), job_id, worker,
               json.dumps(scores, ensure_ascii=False), weighted, rationale, judge))
    c.commit(); c.close()

def list_evaluations(job_id):
    c = _conn()
    rows = c.execute("SELECT * FROM evaluation WHERE job_id=? ORDER BY weighted DESC", (job_id,)).fetchall()
    c.close()
    return [dict(r) for r in rows]

# ---------- Case (学到的经验) ----------
def add_case(task_type, features, decision, actual_score, cost_usd, pitfalls=""):
    c = _conn()
    c.execute("INSERT INTO case_tab VALUES (?,?,?,?,?,?,?,?)",
              (_uid("CASE"), task_type,
               json.dumps(features, ensure_ascii=False),
               json.dumps(decision, ensure_ascii=False),
               actual_score, cost_usd, pitfalls, _now()))
    c.commit(); c.close()

def list_cases():
    c = _conn()
    rows = c.execute("SELECT * FROM case_tab ORDER BY created_at DESC").fetchall()
    c.close()
    return [dict(r) for r in rows]

# ---------- 审计 ----------
def add_audit(actor, action, detail, job_id=None):
    c = _conn()
    c.execute("INSERT INTO audit_log(ts,actor,action,detail,job_id) VALUES (?,?,?,?,?)",
              (_now(), actor, action, detail, job_id))
    c.commit(); c.close()

def list_audit(limit=100):
    c = _conn()
    rows = c.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return [dict(r) for r in rows]

# ---------- 审批 ----------
def add_approval(job_id, worker, action, reason):
    c = _conn(); aid = _uid("APR")
    c.execute("INSERT INTO approval VALUES (?,?,?,?,?,?,?)",
              (aid, job_id, worker, action, reason, "pending", None))
    c.commit(); c.close()
    return aid

def list_approvals(status="pending"):
    c = _conn()
    rows = c.execute("SELECT * FROM approval WHERE status=? ORDER BY id DESC", (status,)).fetchall()
    c.close()
    return [dict(r) for r in rows]

def approve(aid, decision):
    c = _conn()
    c.execute("UPDATE approval SET status=?, decided_at=? WHERE id=?",
              ("approved" if decision == "approve" else "denied", _now(), aid))
    c.commit(); c.close()

# ---------- Agent 画像（跨任务聚合，回答"谁一直擅长什么"）----------
def agent_profiles():
    c = _conn()
    rows = c.execute("SELECT worker, AVG(weighted) AS avg, COUNT(*) AS n,"
                     " MAX(weighted) AS best FROM evaluation GROUP BY worker").fetchall()
    c.close()
    return [{"worker": r["worker"], "avg_score": round(r["avg"], 2),
             "samples": r["n"], "best_score": r["best"]} for r in rows]
