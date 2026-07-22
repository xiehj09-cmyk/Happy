"""认知训练题库 · 参考 MMSE / MoCA 常见筛查题型随机组卷"""

from __future__ import annotations

import random
from datetime import datetime


def _orient_questions() -> list[dict]:
    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    seasons = {
        1: "冬季", 2: "冬季", 3: "春季", 4: "春季", 5: "春季",
        6: "夏季", 7: "夏季", 8: "夏季", 9: "秋季", 10: "秋季", 11: "秋季", 12: "冬季",
    }
    year = str(now.year)
    month = str(now.month)
    day = str(now.day)
    season = seasons[now.month]
    weekday = weekdays[now.weekday()]

    pool = [
        {
            "id": "orient_year",
            "category": "定向力",
            "type": "choice",
            "prompt": "请问现在是哪一年？",
            "options": _shuffle_options([year, str(now.year - 1), str(now.year + 1), str(now.year - 2)]),
            "answer": year,
            "reference": "MMSE 时间定向",
        },
        {
            "id": "orient_month",
            "category": "定向力",
            "type": "choice",
            "prompt": "请问现在是几月份？",
            "options": _shuffle_options([month, str(max(1, now.month - 2)), str(min(12, now.month + 1)), "10"]),
            "answer": month,
            "reference": "MMSE 时间定向",
        },
        {
            "id": "orient_day",
            "category": "定向力",
            "type": "choice",
            "prompt": "请问今天是几号？",
            "options": _shuffle_options([day, str(max(1, now.day - 3)), str(min(28, now.day + 2)), "15"]),
            "answer": day,
            "reference": "MMSE 时间定向",
        },
        {
            "id": "orient_weekday",
            "category": "定向力",
            "type": "choice",
            "prompt": "请问今天是星期几？",
            "options": _shuffle_options(weekdays[:]),
            "answer": weekday,
            "reference": "MMSE 时间定向",
        },
        {
            "id": "orient_season",
            "category": "定向力",
            "type": "choice",
            "prompt": "请问现在是什么季节？",
            "options": _shuffle_options(["春季", "夏季", "秋季", "冬季"]),
            "answer": season,
            "reference": "MMSE 时间定向",
        },
        {
            "id": "orient_country",
            "category": "定向力",
            "type": "choice",
            "prompt": "请问我们现在在哪个国家？",
            "options": _shuffle_options(["中国", "日本", "韩国", "美国"]),
            "answer": "中国",
            "reference": "MMSE 地点定向",
        },
    ]
    return random.sample(pool, k=min(3, len(pool)))


def _memory_questions() -> list[dict]:
    word_sets = [
        ["皮球", "国旗", "树木"],
        ["面孔", "天鹅绒", "教堂", "菊花", "红色"],
        ["苹果", "硬币", "火车"],
        ["桌子", "钥匙", "河流"],
    ]
    words = random.choice(word_sets)
    return [
        {
            "id": "memory_immediate",
            "category": "即刻记忆",
            "type": "recall",
            "prompt": f"请记住以下词语：{'、'.join(words)}。请在下方按顺序或任意顺序写出您记住的词语（用顿号或逗号分隔）。",
            "words": words,
            "answer": words,
            "reference": "MMSE / MoCA 即刻记忆",
        },
        {
            "id": "memory_delayed",
            "category": "延迟回忆",
            "type": "recall",
            "prompt": "请回忆刚才让您记住的词语，尽可能多地写出来（用顿号或逗号分隔）。",
            "depends_on": "memory_immediate",
            "reference": "MMSE / MoCA 延迟回忆",
        },
    ]


def _static_pool() -> list[dict]:
    return [
        {
            "id": "attention_subtract",
            "category": "注意力与计算",
            "type": "input",
            "prompt": "从 100 开始连续减 7，第一次减 7 的结果是多少？",
            "answer": "93",
            "reference": "MMSE 连续减 7",
        },
        {
            "id": "attention_subtract2",
            "category": "注意力与计算",
            "type": "input",
            "prompt": "100 减 7 得 93，再减 7 等于多少？",
            "answer": "86",
            "reference": "MMSE 连续减 7",
        },
        {
            "id": "naming_watch",
            "category": "命名",
            "type": "choice",
            "prompt": "（展示常见物品）请问这是什么？",
            "image_label": "⌚ 手表",
            "options": _shuffle_options(["手表", "手机", "遥控器", "眼镜"]),
            "answer": "手表",
            "reference": "MMSE 物体命名",
        },
        {
            "id": "naming_pencil",
            "category": "命名",
            "type": "choice",
            "prompt": "（展示常见物品）请问这是什么？",
            "image_label": "✏️ 铅笔",
            "options": _shuffle_options(["铅笔", "筷子", "钢笔", "蜡烛"]),
            "answer": "铅笔",
            "reference": "MMSE 物体命名",
        },
        {
            "id": "language_repeat",
            "category": "语言复述",
            "type": "input",
            "prompt": "请完整复述这句话：「四十四只石狮子」",
            "answer": "四十四只石狮子",
            "reference": "MMSE 语言复述",
        },
        {
            "id": "language_read",
            "category": "语言理解",
            "type": "choice",
            "prompt": "请阅读并理解：「请闭上您的眼睛」。您应该做什么？",
            "options": _shuffle_options(["闭上您的眼睛", "张开您的嘴巴", "举起您的手", "站起来"]),
            "answer": "闭上您的眼睛",
            "reference": "MMSE 阅读理解",
        },
        {
            "id": "abstract_similarity",
            "category": "抽象思维",
            "type": "choice",
            "prompt": "请问「香蕉」和「橙子」有什么相同点？",
            "options": _shuffle_options(["都是水果", "都是蔬菜", "都是红色", "都是方形"]),
            "answer": "都是水果",
            "reference": "MoCA 抽象思维",
        },
        {
            "id": "abstract_train_bicycle",
            "category": "抽象思维",
            "type": "choice",
            "prompt": "请问「火车」和「自行车」有什么相同点？",
            "options": _shuffle_options(["都是交通工具", "都在天上飞", "都是动物", "都是食物"]),
            "answer": "都是交通工具",
            "reference": "MoCA 抽象思维",
        },
        {
            "id": "attention_digit",
            "category": "注意力",
            "type": "choice",
            "prompt": "请听数字序列：2、5、1、8、4、7。其中最大的数字是？",
            "options": _shuffle_options(["8", "2", "5", "4"]),
            "answer": "8",
            "reference": "MoCA 注意力",
        },
        {
            "id": "attention_clap",
            "category": "注意力",
            "type": "choice",
            "prompt": "数字序列：3、1、5、1、2、1、9。按照 MoCA 规则，应在听到数字「1」时拍手。一共应拍手几次？",
            "options": _shuffle_options(["3", "1", "2", "4"]),
            "answer": "3",
            "reference": "MoCA 听数字拍手",
        },
        {
            "id": "visuospatial",
            "category": "视空间",
            "type": "choice",
            "prompt": "一个标准的时钟，时针指向 3、分针指向 12，表示的时间是？",
            "options": _shuffle_options(["3:00", "12:03", "6:00", "9:00"]),
            "answer": "3:00",
            "reference": "MoCA 视空间 / 画钟",
        },
    ]


def _shuffle_options(options: list[str]) -> list[str]:
    shuffled = options[:]
    random.shuffle(shuffled)
    return shuffled


def build_quiz(count: int = 8) -> list[dict]:
    """随机组卷：定向 + 记忆（成对）+ 其他题型。"""
    orient = _orient_questions()
    memory = _memory_questions()
    need_static = max(1, count - len(orient) - len(memory))
    static = random.sample(_static_pool(), min(need_static, len(_static_pool())))

    quiz = orient + memory + static
    random.shuffle(quiz)

    for idx, item in enumerate(quiz, start=1):
        item["index"] = idx

    return quiz


def score_quiz(questions: list[dict], answers: dict[str, str]) -> dict:
    total = 0
    correct = 0
    details = []

    memory_words: list[str] | None = None

    for q in questions:
        qid = q["id"]
        user_raw = (answers.get(qid) or "").strip()
        is_correct = False
        expected = ""

        if q["type"] == "recall" and qid == "memory_immediate":
            memory_words = q.get("words", [])
            expected = "、".join(memory_words)
            user_tokens = _tokenize_recall(user_raw)
            hit = sum(1 for w in memory_words if w in user_tokens)
            is_correct = hit >= max(1, len(memory_words) - 1)
            user_raw = user_raw or "（未作答）"
        elif q["type"] == "recall" and qid == "memory_delayed":
            expected = "、".join(memory_words or [])
            user_tokens = _tokenize_recall(user_raw)
            if memory_words:
                hit = sum(1 for w in memory_words if w in user_tokens)
                is_correct = hit >= max(1, len(memory_words) // 2)
            user_raw = user_raw or "（未作答）"
        elif q["type"] == "input":
            expected = str(q.get("answer", ""))
            is_correct = _normalize(user_raw) == _normalize(expected)
        elif q["type"] == "choice":
            expected = str(q.get("answer", ""))
            is_correct = user_raw == expected

        total += 1
        if is_correct:
            correct += 1

        details.append(
            {
                "id": qid,
                "category": q.get("category", ""),
                "prompt": q.get("prompt", ""),
                "user_answer": user_raw,
                "expected": expected,
                "correct": is_correct,
            }
        )

    percent = round(correct / total * 100) if total else 0
    level = "良好"
    if percent < 60:
        level = "需加强"
    elif percent < 80:
        level = "一般"

    return {
        "total": total,
        "correct": correct,
        "percent": percent,
        "level": level,
        "details": details,
    }


def _tokenize_recall(text: str) -> set[str]:
    for sep in ["、", "，", ",", " ", "；", ";"]:
        text = text.replace(sep, "|")
    return {t.strip() for t in text.split("|") if t.strip()}


def _normalize(text: str) -> str:
    return text.replace(" ", "").replace("　", "").lower()
