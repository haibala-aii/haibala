"""
haibala · M2 · judge/api.py
===========================
【这一课：真的 LLM-as-judge】
M1 的 MockJudge 是"假打分"。这里做真的：把"产物 + rubric"发给一个大模型，
让它按每个维度打分并**引用证据**，返回 JSON。
关键点（也是这系统最值钱、最难的一环）：
  - 锚点 rubric：告诉模型"几分长什么样"
  - 盲评：绝不告诉模型这是哪个 worker 做的（防它偏心大厂工具）
  - 引用证据：要求打分时引用产物片段，防空口打分
  - 输出严格的 JSON，便于解析
用 urllib 实现（零依赖）。没有 API key 时，pipeline 会自动回退到 MockJudge。
"""
import json, urllib.request
from judge.base import DEFAULT_RUBRIC, JudgePlugin, Evaluation
from core import config

class ApiJudge(JudgePlugin):
    name = "api"

    def _prompt(self, rubric, artifact, context):
        dims = "\n".join(
            f"- {d['name']}（权重{d['weight']}，1-{d['scale']}分）锚点：{d['anchors']}"
            for d in rubric["dimensions"])
        return (
            "你是严格的评审。请针对下面这个产物，按评分标准逐维度打分。\n"
            f"评分标准（每维度1-5分）：\n{dims}\n\n"
            f"待评审产物：\n{artifact.detail}\n\n"
            f"摘要：{artifact.summary}\n\n"
            "要求：\n"
            "1) 只输出 JSON，不要多余文字。\n"
            "2) scores 键为每个维度的名称，值是该维度分数(1-5)。\n"
            "3) rationale 用一句中文给"加权总分"并引用产物中具体表现作为依据。\n"
            '输出格式: {"scores":{...},"weighted":数,"rationale":"..."}'
        )

    def score(self, rubric, artifact, context):
        if not config.JUDGE_API_KEY:
            raise RuntimeError("ApiJudge 需要 DEEPSEEK_API_KEY；未配置时请用 mock")
        url = f"{config.JUDGE_BASE_URL}/chat/completions"
        payload = {
            "model": config.JUDGE_MODEL,
            "messages": [
                {"role": "system", "content": "你是严格的代码/产物评审，客观打分。"},
                {"role": "user", "content": self._prompt(rubric, artifact, context)},
            ],
            "temperature": 0.1,
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {config.JUDGE_API_KEY}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]

        # 解析 LLM 返回（鲁棒处理：去掉可能的 markdown 代码块）
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        parsed = json.loads(text)
        scores = parsed.get("scores", {})
        weighted = float(parsed.get("weighted", 0))
        rationale = parsed.get("rationale", "")
        return Evaluation(worker=artifact.meta.get("name", "?"), scores=scores,
                          weighted=weighted, rationale=rationale, judge="api")
