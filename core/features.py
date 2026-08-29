"""
haibala · M1 · core/features.py
===============================
【这一课：observe（观察）· 特征提取】
supervisor 的第一步是"看懂这个任务"。
它不能像人一样读需求，只能把文本里识别出的信号抽成「特征」，
后续的"决策(用谁/拆不拆/优先级)"全靠这些特征。这就是经典 ML 的
特征工程：把原始输入变成机器能利用的结构化字段。

M1 先用简单关键词规则，让你看清"特征"长什么样。
（M2 可换成 LLM 抽取 / 模型，但概念一样。）
"""

def extract_features(text: str) -> dict:
    t = text.lower()
    has = lambda *kws: any(k in t for k in kws)

    # 1) 任务类型
    if has("图像", "图片", "照片", "抠图", "识别", "检测", "视频", "ocr", "img", "image", "cv"):
        task_type = "image"
    elif has("app", "小程序", "前端", "界面", "网页", "页面", "ui", "web", "站点"):
        task_type = "frontend"
    elif has("爬", "抓取", "抓数据", "采集", "数据", "dataset", "csv", "spider"):
        task_type = "data"
    elif has("文案", "写作", "文案", "生成", "营销", "小红书", "文章", "report", "text", "写"):
        task_type = "text"
    else:
        task_type = "coding"

    # 2) 技术栈线索
    stack = []
    for s in ["python", "javascript", "react", "vue", "rembg", "opencv", "chatgpt", "llm",
              "sqlite", "node", "css", "前后端", "deepseek", "selenium", "爬虫"]:
        if s in t: stack.append(s)

    # 3) 规模 / 复杂度（启发式，先粗糙）
    size = "small" if len(text) < 60 else ("large" if len(text) > 300 else "medium")
    complex_hint = has("并行", "多模块", "联调", "全流程", "端到端", "多个", "复杂", "整合")
    complexity = "high" if complex_hint else "medium"

    # 4) 是否多模态（涉及图片/视频/音频）
    multimodal = has("图片", "图像", "视频", "音频", "语音", "图", "视频")

    # 5) 粗估子任务数（先按是否含几个面来判断）
    n_subtasks = 1
    if task_type == "frontend" and has("后端", "前端", "接口"): n_subtasks = 3
    elif task_type == "image" and has("文案", "后台", "前端", "生成"): n_subtasks = 4
    elif complexity == "high": n_subtasks = 3

    return {
        "task_type": task_type,
        "stack": stack,
        "size": size,
        "complexity": complexity,
        "multimodal": multimodal,
        "n_subtasks": n_subtasks,
    }
