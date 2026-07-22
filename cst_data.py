"""CST（认知刺激疗法）标准 14 次疗程数据 · 参考 UCL CST 手册结构"""

from __future__ import annotations

from datetime import datetime

# 全部 14 次标准课均可完成
MVP_SESSIONS = set(range(1, 15))

CST_PHASES = {
    "intensive": {"label": "强化期", "weeks": 7, "per_week": 2, "total": 14},
    "maintenance": {"label": "维持期 MCST", "weeks": 24, "per_week": 1, "total": 24},
}

# 单次课图文与 AI 扩展内容（MVP 详稿）
SESSION_ENRICHMENT: dict[int, dict] = {
    1: {
        "title": "图画联想",
        "slug": "picture-words",
        "summary": "通过老照片、生活图卡与词语描述，在视觉与语言之间建立联想，开启 CST 疗程。",
        "ai_theme": "图画联想与词语表达",
        "ai_focus": "以「看图说话」为主：展示熟悉物品、老场景图卡，引导长者描述颜色、用途、回忆与感受；少用肢体游戏。",
        "ai_opening": "您好，欢迎参加{group_name}的第 1 次 CST。今天我们不着急，一起看看几张图、说说话，没有对错。",
        "activities": [
            "【图卡一】看一张「老茶壶/茶杯」图，描述它让您想起什么",
            "【图卡二】看一张「旧时弄堂/胡同」场景，说说熟悉的细节",
            "【词语接龙】从「家」字出发，说出 3 个联想到的词",
            "【温和讨论】分享一种您最喜欢的茶或饮料，以及和谁一起喝",
        ],
        "visual_cards": [
            {
                "id": "tea_set",
                "label": "老茶壶与茶杯",
                "emoji": "🫖",
                "caption": "请看看这张图：一只老茶壶和两只小茶杯。",
                "ai_prompt": "请看屏幕上的茶壶和茶杯。您能说一说，这像不像以前家里用过的茶具吗？",
            },
            {
                "id": "old_street",
                "label": "旧时街景",
                "emoji": "🏮",
                "caption": "一条熟悉的老街，红灯笼、青瓦墙。",
                "ai_prompt": "这是老北京的街景图片。您看到了什么？有没有让您想起某个地方？",
            },
            {
                "id": "family_photo",
                "label": "全家福老照片",
                "emoji": "🖼️",
                "caption": "一张泛黄的合影，笑得很温暖。",
                "ai_prompt": "这是一张老照片。不用说出名字，您可以描述一下照片里的人在做什么吗？",
            },
            {
                "id": "fruit_basket",
                "label": "时令水果",
                "emoji": "🍎",
                "caption": "一篮苹果、橘子和香蕉。",
                "ai_prompt": "看看这些水果，您最喜欢哪一种？小时候常吃吗？",
            },
        ],
        "ai_followups": [
            {"text": "您说得很好。那这种颜色/形状，还让您想到别的什么吗？", "card_id": "tea_set", "step": "main"},
            {"text": "我们换一张图。您看看这条老街，有没有熟悉的铺子或声音？", "card_id": "old_street", "step": "main"},
            {"text": "如果给这张照片配一句话，您会怎么说？", "card_id": "family_photo", "step": "main"},
            {"text": "从「家」这个字，您能想到哪三个词？想到哪个说哪个。", "card_id": None, "step": "main"},
            {"text": "今天您分享了很多。您觉得哪张图最让您有感触？", "card_id": "fruit_basket", "step": "summary"},
        ],
        "practice_items": [
            {
                "id": "s1_tea",
                "emoji": "🫖",
                "prompt": "这只老茶壶，让您想起什么？",
                "hint": "用途、颜色或和谁一起喝茶都可以。",
                "options": ["家里用过类似的", "想喝茶", "想起某个人", "说不准"],
            },
            {
                "id": "s1_street",
                "emoji": "🏮",
                "prompt": "这条老街，您最先注意到什么？",
                "hint": "灯笼、铺子、声音都行。",
                "options": ["红灯笼", "青瓦墙", "小店铺", "人来人往"],
            },
            {
                "id": "s1_photo",
                "emoji": "🖼️",
                "prompt": "合影里的人，看起来在做什么？",
                "hint": "不用说名字。",
                "options": ["在笑", "在站着合影", "像过节", "看不太清"],
            },
            {
                "id": "s1_fruit",
                "emoji": "🍎",
                "prompt": "这些水果里，您最想吃哪一种？",
                "hint": "选一个就好。",
                "options": ["苹果", "橘子", "香蕉", "都喜欢"],
            },
        ],
        "ai_closings": [
            "谢谢您今天的分享。看图说话也是一种很好的 CST 练习，我们下次继续。",
        ],
        "step_overrides": {
            "warmup": {
                "name": "图文热身",
                "guide": "展示第一张图卡，请长者用 1–2 句话描述「看到了什么」，不纠正细节。",
            },
            "discussion": {
                "name": "读图讨论",
                "guide": "围绕图卡上的颜色、形状、用途展开讨论，鼓励联系个人经历。",
            },
            "main": {
                "name": "图画联想主活动",
                "guide": "依次呈现 3–4 张图卡，配合词语联想与温和问答；AI 引导员一次一问。",
            },
        },
    },
    2: {
        "ai_theme": "声音与记忆",
        "ai_focus": "结合声音描述与歌词文字卡片，引导长者读图说声音、谈熟悉旋律；不测验音高或歌词对错。",
        "ai_opening": "欢迎回来。今天第 2 次 CST，主题是「声音」。我们会看描述卡、歌词文字，聊聊熟悉的声音。",
        "activities": [
            "【声音卡】阅读「清晨鸟鸣」描述卡，联想在何处听过",
            "【声音卡】看「雨打屋檐」图，说说下雨天的声音",
            "【歌词卡】展示一句老歌歌词，说说是否熟悉",
            "【温和讨论】从「安静」出发，说出 2 个让您安心的声音",
        ],
        "visual_cards": [
            {
                "id": "bird",
                "label": "清晨鸟鸣",
                "emoji": "🐦",
                "caption": "树梢上的小鸟，像在轻轻叫着。",
                "ai_prompt": "如果听到清晨的鸟叫，您会想到什么时候、什么地方？",
            },
            {
                "id": "radio",
                "label": "老式收音机",
                "emoji": "📻",
                "caption": "一台带旋钮的收音机。",
                "ai_prompt": "看看这台老收音机，您年轻时常听什么节目？",
            },
            {
                "id": "rain",
                "label": "雨打屋檐",
                "emoji": "🌧️",
                "caption": "雨点落在屋檐和窗台上。",
                "ai_prompt": "下雨的声音，您觉得是吵闹，还是让人安心？",
            },
            {
                "id": "old_song",
                "label": "老歌歌词",
                "emoji": "🎵",
                "caption": "【歌词】「好一朵美丽的茉莉花……」",
                "ai_prompt": "这句歌词您听过吗？可以哼一句，也可以只说「听过」。",
            },
        ],
        "practice_items": [
            {
                "id": "s2_bird",
                "emoji": "🐦",
                "prompt": "清晨鸟叫，您最常在哪里听过？",
                "hint": "想到院子、公园或窗外都可以。",
                "options": ["院子里", "公园", "窗外", "记不清了"],
            },
            {
                "id": "s2_radio",
                "emoji": "📻",
                "prompt": "老收音机一开，您最先想起什么？",
                "hint": "戏曲、新闻、歌曲或家人的声音都行。",
                "options": ["戏曲", "新闻", "老歌", "家人说话"],
            },
            {
                "id": "s2_rain",
                "emoji": "🌧️",
                "prompt": "雨打屋檐的声音，让您觉得怎样？",
                "hint": "没有标准答案。",
                "options": ["很安心", "有点吵", "想睡觉", "说不清"],
            },
            {
                "id": "s2_song",
                "emoji": "🎵",
                "prompt": "「茉莉花」这句歌词，您熟悉吗？",
                "hint": "哼一句、点头或说「听过」都很好。",
                "options": ["很熟悉", "有点印象", "不太熟", "想再听一遍"],
            },
        ],
        "ai_followups": [
            {"text": "除了鸟叫，还有什么声音会让您觉得安心？", "card_id": "bird", "step": "main"},
            {"text": "有没有一首歌，听到前几个音符您就认出来了？", "card_id": "radio", "step": "main"},
            {"text": "下雨天，您喜欢待在屋子里做什么？", "card_id": "rain", "step": "main"},
            {"text": "这句歌词里，哪个字您听得最清楚？", "card_id": "old_song", "step": "main"},
            {"text": "今天聊的这些声音里，哪一种最让您有感触？", "card_id": "old_song", "step": "summary"},
        ],
        "ai_closings": [
            "谢谢您分享这些声音。听与说，都是很好的 CST 练习，我们下次继续。",
        ],
        "step_overrides": {
            "warmup": {
                "name": "声音卡片热身",
                "guide": "展示鸟鸣图卡，请长者描述「这是什么声音、在哪里听过」。",
            },
            "discussion": {
                "name": "听图讨论",
                "guide": "围绕雨声、收音机与歌词卡，一次只问一个问题。",
            },
            "main": {
                "name": "声音联想主活动",
                "guide": "依次呈现鸟鸣、收音机、雨声与歌词卡；可完成下方练习题，鼓励哼唱或短答。",
            },
        },
    },
    3: {
        "ai_theme": "童年回忆",
        "ai_focus": "老照片、童年物品图卡与故事叙述，避免复杂问答；不纠正年代细节。",
        "ai_opening": "今天是第 3 次 CST，主题「童年」。我们可以一起看几张图，慢慢回忆小时候的事。",
        "activities": [
            "【图卡】看「放风筝」图，描述小时候的游戏",
            "【图卡】看「旧式书包」图，聊聊上学带什么",
            "【图卡】看「弹珠 / 跳房子」图，说说儿时玩伴",
            "【温和讨论】如果给童年选一个颜色，您会选什么",
        ],
        "visual_cards": [
            {
                "id": "kite",
                "label": "放风筝",
                "emoji": "🪁",
                "caption": "空白蓝天里一只风筝。",
                "ai_prompt": "您小时候放过风筝吗？是在哪里、和谁一起？",
            },
            {
                "id": "school",
                "label": "旧式书包",
                "emoji": "🎒",
                "caption": "一只布书包和铅笔盒。",
                "ai_prompt": "看看这个书包，您上学时最喜欢带什么？",
            },
            {
                "id": "marbles",
                "label": "弹珠与游戏",
                "emoji": "🔵",
                "caption": "几颗玻璃弹珠，阳光下闪着光。",
                "ai_prompt": "弹珠、跳房子、捉迷藏……您小时候最爱哪一种玩法？",
            },
            {
                "id": "childhood_color",
                "label": "童年的颜色",
                "emoji": "🎨",
                "caption": "一块调色板：红、黄、蓝、绿。",
                "ai_prompt": "如果给童年选一个颜色，您会选什么？为什么？",
            },
        ],
        "practice_items": [
            {
                "id": "s3_kite",
                "emoji": "🪁",
                "prompt": "放风筝，您更记得哪一部分？",
                "hint": "场地、同伴或天气都可以。",
                "options": ["空地 / 河边", "和家人一起", "线扯在手里的感觉", "记不太清"],
            },
            {
                "id": "s3_bag",
                "emoji": "🎒",
                "prompt": "旧书包里，您最想再拿出哪一样？",
                "hint": "课本、零食或小玩具都行。",
                "options": ["铅笔 / 橡皮", "一块糖", "一本小人书", "说不准"],
            },
            {
                "id": "s3_game",
                "emoji": "🔵",
                "prompt": "小时候，您更喜欢哪种玩法？",
                "hint": "选一个就好。",
                "options": ["弹珠", "跳房子", "捉迷藏", "其他游戏"],
            },
            {
                "id": "s3_color",
                "emoji": "🎨",
                "prompt": "若给童年涂一个颜色，您选？",
                "hint": "颜色代表心情，没有对错。",
                "options": ["红色", "黄色", "蓝色", "绿色"],
            },
        ],
        "ai_followups": [
            {"text": "那时候放学后，您最喜欢做的一件事是什么？", "card_id": "kite", "step": "main"},
            {"text": "书包带上肩，您最先想起教室还是操场？", "card_id": "school", "step": "main"},
            {"text": "玩弹珠或跳房子时，通常和几个小伙伴一起？", "card_id": "marbles", "step": "main"},
            {"text": "如果给童年起一个颜色，您会选什么颜色？为什么？", "card_id": "childhood_color", "step": "summary"},
        ],
        "ai_closings": [
            "谢谢您分享小时候的故事。回忆本身就是很好的练习，我们下次继续。",
        ],
        "step_overrides": {
            "warmup": {
                "name": "童年图卡热身",
                "guide": "展示风筝图卡，请长者用 1–2 句话说「看到了什么」。",
            },
            "discussion": {
                "name": "儿时故事讨论",
                "guide": "围绕书包与游戏展开，鼓励联系人物与地点，不纠正年代。",
            },
            "main": {
                "name": "童年回忆主活动",
                "guide": "依次呈现风筝、书包、弹珠与颜色卡；可完成下方练习题，一次一问。",
            },
        },
    },
    4: {
        "ai_theme": "食物与味道记忆",
        "ai_focus": "用食材、拿手菜与节日饮食图卡，引导看图说味道、谈家常菜；不评判营养对错。",
        "ai_opening": "欢迎参加{group_name}的第 4 次 CST。今天主题是「食物」，我们一起看几张图，聊聊熟悉的味道。",
        "activities": [
            "【图卡】看「新鲜蔬菜」图，说出您认得的几种菜",
            "【图卡】看「一碗热汤」图，联想家里常喝的汤",
            "【图卡】看「节日点心」图，聊聊过年或中秋吃什么",
            "【温和讨论】分享一道您最拿手或最爱吃的菜，以及和谁一起吃",
        ],
        "visual_cards": [
            {
                "id": "veggies",
                "label": "新鲜蔬菜",
                "emoji": "🥬",
                "caption": "一筐青菜、萝卜和西红柿。",
                "ai_prompt": "看看这些蔬菜，您认得哪几种？家里以前常买什么菜？",
            },
            {
                "id": "hot_soup",
                "label": "一碗热汤",
                "emoji": "🍜",
                "caption": "热气腾腾的一碗汤。",
                "ai_prompt": "这碗热汤让您想起什么？是谁做的、什么时候喝？",
            },
            {
                "id": "festival_snack",
                "label": "节日点心",
                "emoji": "🥮",
                "caption": "月饼、粽子或年糕一类的节日食品。",
                "ai_prompt": "过节时您家常吃什么点心？有没有特别喜欢的一种？",
            },
            {
                "id": "home_dish",
                "label": "家常拿手菜",
                "emoji": "🍲",
                "caption": "一盘热乎乎的家常菜。",
                "ai_prompt": "如果请您选一道拿手菜或最爱吃的菜，您会选什么？",
            },
        ],
        "ai_followups": [
            {"text": "这种菜，您喜欢清炒还是炖着吃？", "card_id": "veggies", "step": "main"},
            {"text": "汤的味道是咸一点、淡一点，还是带点甜？", "card_id": "hot_soup", "step": "main"},
            {"text": "过节时，除了点心，桌上还有什么让您记得住的菜？", "card_id": "festival_snack", "step": "main"},
            {"text": "这道菜，您通常和谁一起吃？", "card_id": "home_dish", "step": "summary"},
        ],
        "ai_closings": [
            "谢谢您分享这些味道。今天聊食物，也是在唤醒美好回忆，我们下次继续。",
        ],
        "step_overrides": {
            "warmup": {
                "name": "食材图卡热身",
                "guide": "展示蔬菜图卡，请长者用 1–2 句话描述「看到了什么菜」。",
            },
            "main": {
                "name": "食物联想主活动",
                "guide": "依次呈现食材、热汤、节日点心与拿手菜图卡，围绕味道与人物展开温和讨论。",
            },
        },
    },
    6: {
        "ai_theme": "面孔与熟悉场景",
        "ai_focus": "用家人合影占位图与街景图卡，引导描述人物活动与空间细节；不要求准确叫出姓名。",
        "ai_opening": "欢迎回来。今天是第 6 次 CST，主题「面孔与场景」。我们一起看看熟悉的人和地方。",
        "activities": [
            "【图卡】看「家人合影」占位图，描述照片里的人在做什么",
            "【图卡】看「邻里街景」图，说说熟悉的店铺或路灯",
            "【图卡】看「公园长椅」图，联想常去的户外地方",
            "【温和讨论】选一张图，用一句话说说「这里让您觉得安心的地方」",
        ],
        "visual_cards": [
            {
                "id": "family_portrait",
                "label": "家人合影（示意）",
                "emoji": "👨‍👩‍👧‍👦",
                "caption": "一张示意用全家福，保护隐私，不展示真实面孔。",
                "ai_prompt": "这是一张合影示意。不用说出名字，您可以描述一下照片里的人在做什么吗？",
            },
            {
                "id": "neighbor_street",
                "label": "邻里街景",
                "emoji": "🏘️",
                "caption": "一条熟悉的居民街，有树、有门牌。",
                "ai_prompt": "看看这条街，您看到了什么？有没有像您以前住过的地方？",
            },
            {
                "id": "park_bench",
                "label": "公园长椅",
                "emoji": "🌳",
                "caption": "树荫下的一张长椅。",
                "ai_prompt": "公园里的长椅，您常和谁一起坐？喜欢看什么风景？",
            },
            {
                "id": "front_door",
                "label": "家门口",
                "emoji": "🚪",
                "caption": "一扇带门牌的家门。",
                "ai_prompt": "站在家门口，您会想起进门后先做什么吗？",
            },
        ],
        "ai_followups": [
            {"text": "照片里谁的笑容最让您觉得温暖？", "card_id": "family_portrait", "step": "main"},
            {"text": "这条街上，有没有一家您常去的小店？", "card_id": "neighbor_street", "step": "main"},
            {"text": "坐在长椅上，您最喜欢听什么声音？", "card_id": "park_bench", "step": "main"},
            {"text": "今天哪张图最让您有「回到熟悉地方」的感觉？", "card_id": "front_door", "step": "summary"},
        ],
        "ai_closings": [
            "谢谢您今天的分享。认出熟悉的人和地方，本身就是很好的练习。",
        ],
        "step_overrides": {
            "warmup": {
                "name": "面孔热身",
                "guide": "展示合影占位图，请长者描述「看到几个人、在做什么」，不追问真实姓名。",
            },
            "discussion": {
                "name": "场景读图",
                "guide": "围绕街景与公园细节展开讨论，鼓励联系个人空间记忆。",
            },
            "main": {
                "name": "面孔与场景主活动",
                "guide": "依次呈现合影、街景、公园与家门口图卡；一次一问，允许沉默后给选项。",
            },
        },
    },
    10: {
        "ai_theme": "时空定向强化",
        "ai_focus": "结合现实定向板、简易地图与日历图卡，巩固「今天是哪天、我们在哪里」；不测验、不纠正。",
        "ai_opening": "今天是第 10 次 CST，主题「定向」。我们先一起看看日期和地点，再看一张简单的地图。",
        "activities": [
            "【定向板】一起朗读今天的日期、星期、季节与地点",
            "【图卡】看「简易社区地图」，指出「家」大概在哪一侧",
            "【图卡】看「日历页」，说说今天大概是月初、月中还是月末",
            "【图卡】看「窗户外景色」，描述现在是白天还是傍晚",
            "【温和讨论】用一句话说说「我现在在家里，和家人在一起」",
        ],
        "visual_cards": [
            {
                "id": "community_map",
                "label": "简易社区地图",
                "emoji": "🗺️",
                "caption": "一张示意地图：家、公园、商店。",
                "ai_prompt": "这是一张简单的地图。您觉得「家」大概在图的哪一边？",
            },
            {
                "id": "calendar_page",
                "label": "日历页",
                "emoji": "📅",
                "caption": "一张标着日期的日历。",
                "ai_prompt": "看看这张日历。您觉得今天更像月初、月中，还是月末？",
            },
            {
                "id": "window_view",
                "label": "窗景",
                "emoji": "🪟",
                "caption": "窗外的天空与树影。",
                "ai_prompt": "透过窗户看看，现在更像白天、傍晚，还是夜里？",
            },
            {
                "id": "compass_home",
                "label": "回家的路",
                "emoji": "🧭",
                "caption": "「回家」两个字与小路示意。",
                "ai_prompt": "「回家」这两个字，让您想到门口的哪一个细节？",
            },
        ],
        "ai_followups": [
            {"text": "地图上公园旁边，您猜还会有什么？", "card_id": "community_map", "step": "main"},
            {"text": "如果在日历上圈出「今天」，您会圈在哪一块？", "card_id": "calendar_page", "step": "main"},
            {"text": "窗外的光是亮一些，还是柔和一些？", "card_id": "window_view", "step": "main"},
            {"text": "我们再一起说一遍：今天是几月几日，我们在家里。", "card_id": "compass_home", "step": "summary"},
        ],
        "ai_closings": [
            "定向练习到这里。您已经和我们一起确认了日期与地点，谢谢参与。",
        ],
        "step_overrides": {
            "ro": {
                "name": "现实定向板（加长）",
                "minutes": 5,
                "guide": "大声朗读日期、星期、季节、时间与地点；可请长者重复「我现在在家里」。",
            },
            "warmup": {
                "name": "地图热身",
                "guide": "展示简易社区地图，请长者指出「家」或「公园」大概位置，不要求精确。",
            },
            "main": {
                "name": "定向主活动",
                "guide": "地图、日历、窗景与「回家」图卡轮转；每次只问一个定向相关问题。",
            },
        },
    },
    14: {
        "ai_theme": "疗程回顾与庆祝",
        "ai_focus": "用回顾问答与庆祝文案，温和回顾 14 次主题亮点；重参与、轻对错，结束时给予肯定。",
        "ai_opening": "您好，这是强化期的第 14 次，也是最后一次标准 CST。今天我们轻松回顾，一起庆祝您的坚持。",
        "celebrate": True,
        "celebrate_title": "恭喜完成强化期 14 次 CST",
        "celebrate_message": "您和家人一起走过图画、声音、童年、食物、面孔与定向……每一次分享都值得被记住。",
        "activities": [
            "【回顾】回想哪一次课的图卡最有感触",
            "【问答】「我们小组叫什么名字？」——答错也完全没关系",
            "【问答】「主题歌是哪一首？」——哼出一两句即可",
            "【庆祝】一起说一句「我们完成了」或鼓掌致谢",
        ],
        "visual_cards": [
            {
                "id": "review_album",
                "label": "疗程相册",
                "emoji": "📔",
                "caption": "记录 14 次课的图文回忆册。",
                "ai_prompt": "打开这本「回忆册」，您最记得哪一张图？",
            },
            {
                "id": "group_name_card",
                "label": "小组名卡片",
                "emoji": "🏷️",
                "caption": "写着小组名字的卡片。",
                "ai_prompt": "我们的小组叫什么名字？想到哪个词就说哪个。",
            },
            {
                "id": "theme_song_card",
                "label": "主题歌",
                "emoji": "🎵",
                "caption": "熟悉的旋律符号。",
                "ai_prompt": "我们的主题歌，您还记得开头一句吗？哼也可以。",
            },
            {
                "id": "celebration",
                "label": "完成庆祝",
                "emoji": "🎉",
                "caption": "完成强化期的小庆祝。",
                "ai_prompt": "我们一起说一句：谢谢自己坚持到今天。您愿意说说今天的心情吗？",
            },
        ],
        "ai_followups": [
            {"text": "在这些课里，有没有一次让您特别想笑或特别温暖？", "card_id": "review_album", "step": "main"},
            {"text": "小组名里，您最喜欢哪一个字？", "card_id": "group_name_card", "step": "main"},
            {"text": "主题歌让您想起和谁在一起听过歌吗？", "card_id": "theme_song_card", "step": "main"},
            {"text": "完成 14 次了。您想对陪伴您的家人说一句什么？", "card_id": "celebration", "step": "summary"},
        ],
        "ai_closings": [
            "恭喜您完成强化期 CST。您的每一次回答都很宝贵，我们为您鼓掌。",
        ],
        "step_overrides": {
            "warmup": {
                "name": "回顾热身",
                "guide": "展示疗程相册图卡，请长者挑一张「记得住的图」简单描述。",
            },
            "main": {
                "name": "团队问答与庆祝",
                "guide": "温和问答小组名、主题歌与最爱图卡；结束时鼓掌或说「我们完成了」。",
            },
            "summary": {
                "name": "结业反馈",
                "guide": "肯定参与、记录心情，提示后续可进入维持期 MCST（若已开放）。",
            },
        },
    },
    5: {
        "ai_theme": "生活趣闻与观点表达",
        "ai_focus": "用简短、温和的生活趣闻文字卡，引导读一读、说一说看法；不谈政治与负面新闻。",
        "ai_opening": "欢迎参加{group_name}的第 5 次 CST。今天主题是「时事」，我们读几张短短的生活趣闻卡，随便聊聊。",
        "activities": [
            "【文字卡】读「社区花园开花了」，说说您喜欢什么花",
            "【文字卡】读「邻里互助送菜」，聊聊邻里之间的小事",
            "【文字卡】读「公园晨练的人多了」，说说您喜欢怎么活动",
            "【温和讨论】选一张卡，用一句话说「我觉得……」",
        ],
        "card_style": "text",
        "visual_cards": [
            {
                "id": "garden_news",
                "label": "社区花园",
                "emoji": "📰",
                "caption": "【趣闻】社区花园的月季开花了，路过的人都停下来看一眼。",
                "ai_prompt": "社区花园开花了。您喜欢什么花？以前院子里种过吗？",
            },
            {
                "id": "neighbor_help",
                "label": "邻里互助",
                "emoji": "📰",
                "caption": "【趣闻】有位邻居买菜多买了一把青菜，分给对门分享。",
                "ai_prompt": "邻里互相送一点菜，您觉得暖和不？您经历过类似的事吗？",
            },
            {
                "id": "morning_park",
                "label": "公园晨练",
                "emoji": "📰",
                "caption": "【趣闻】清晨公园里打拳、散步的人多了起来。",
                "ai_prompt": "公园晨练的人多了。您更喜欢散步，还是在树荫下坐坐？",
            },
            {
                "id": "market_fresh",
                "label": "早市新鲜",
                "emoji": "📰",
                "caption": "【趣闻】早市上新到了当季水果，摊主笑着招呼大家尝尝。",
                "ai_prompt": "早市很热闹。您以前常去早市买什么？",
            },
        ],
        "ai_followups": [
            {"text": "这种花是什么颜色，您觉得最好看？", "card_id": "garden_news", "step": "main"},
            {"text": "邻里之间，还有什么小事会让您觉得安心？", "card_id": "neighbor_help", "step": "main"},
            {"text": "晨练时，您喜欢听什么声音？", "card_id": "morning_park", "step": "main"},
            {"text": "今天哪张趣闻卡最让您想多说两句？", "card_id": "market_fresh", "step": "summary"},
        ],
        "ai_closings": [
            "谢谢您分享看法。读一点温和的生活消息，也是很好的语言练习。",
        ],
        "step_overrides": {
            "warmup": {
                "name": "读卡热身",
                "guide": "大声朗读第一张趣闻卡，请长者用一句话复述「发生了什么」。",
            },
            "main": {
                "name": "趣闻讨论",
                "guide": "依次阅读短文字卡，鼓励表达喜好与经历；避免争议话题。",
            },
        },
    },
    7: {
        "ai_theme": "词语联想与同类列词",
        "ai_focus": "用同类别词卡与词语云，引导说出相关词；不要求数量，想到哪个说哪个。",
        "ai_opening": "今天是第 7 次 CST，主题「词语联想」。我们看词卡、玩词语云，想到什么就说什么。",
        "activities": [
            "【词卡】看「厨房」类词语，再说出 1–2 个同类词",
            "【词卡】看「春天」类词语，联想颜色或气味",
            "【词语云】从屏幕上的词里，点出一个您喜欢的",
            "【温和讨论】从「家」出发，说出三个联想到的词",
        ],
        "word_cloud": ["茶杯", "米饭", "筷子", "燕子", "桃花", "春雨", "孙子", "门口", "收音机", "公园"],
        "visual_cards": [
            {
                "id": "kitchen_words",
                "label": "厨房词语",
                "emoji": "🔤",
                "caption": "锅 · 碗 · 筷 · 灶",
                "ai_prompt": "这些都是厨房里的词。您还能想到一个吗？",
            },
            {
                "id": "spring_words",
                "label": "春天词语",
                "emoji": "🌸",
                "caption": "风筝 · 桃花 · 燕子 · 春雨",
                "ai_prompt": "说到春天，您首先想到哪个词？",
            },
            {
                "id": "home_words",
                "label": "家的词语",
                "emoji": "🏠",
                "caption": "灯 · 床 · 门 · 窗",
                "ai_prompt": "从「家」这个字，您能想到哪三个词？",
            },
            {
                "id": "taste_words",
                "label": "味道词语",
                "emoji": "👅",
                "caption": "甜 · 咸 · 香 · 酸",
                "ai_prompt": "这四种味道里，您最喜欢哪一种？",
            },
        ],
        "ai_followups": [
            {"text": "厨房里还有什么声音，您一听就认得？", "card_id": "kitchen_words", "step": "main"},
            {"text": "春天这个词，让您想起什么颜色？", "card_id": "spring_words", "step": "main"},
            {"text": "「家」旁边，您还想加上哪个词？", "card_id": "home_words", "step": "main"},
            {"text": "今天您说出的哪个词，自己最喜欢？", "card_id": "taste_words", "step": "summary"},
        ],
        "ai_closings": [
            "词语联想到这里。您说出的每一个词都很有价值，谢谢。",
        ],
        "step_overrides": {
            "warmup": {
                "name": "词语热身",
                "guide": "展示厨房词卡，请长者读出其中一个词并说说它的用途。",
            },
            "main": {
                "name": "词语联想主活动",
                "guide": "词卡与词语云交替；AI 一次只请长者补充一个词。",
            },
        },
    },
    8: {
        "ai_theme": "色彩与创意想象",
        "ai_focus": "用色彩卡与想象图卡，引导描述颜色、形状与「如果……会怎样」的轻想象；无对错。",
        "ai_opening": "欢迎回来。第 8 次 CST 主题是「创意」。我们看颜色、想画面，轻松又好玩。",
        "activities": [
            "【色卡】看「暖色」图，说出您喜欢的一种颜色",
            "【图卡】看「未完成的画」，想象接下来可以画什么",
            "【图卡】看「云朵形状」，说说它像什么",
            "【温和讨论】如果给今天选一个颜色，您会选什么",
        ],
        "visual_cards": [
            {
                "id": "warm_colors",
                "label": "暖色色卡",
                "emoji": "🟥",
                "caption": "红、橙、黄三种暖色色块。",
                "ai_prompt": "这三种暖色里，您最喜欢哪一种？它让您想起什么？",
            },
            {
                "id": "cool_colors",
                "label": "冷色色卡",
                "emoji": "🟦",
                "caption": "蓝、绿、紫三种冷色色块。",
                "ai_prompt": "蓝色和绿色，哪个更让您觉得安静？",
            },
            {
                "id": "unfinished_art",
                "label": "未完成的画",
                "emoji": "🎨",
                "caption": "一张只画了一半的风景。",
                "ai_prompt": "这幅画还没画完。您觉得接下来可以画上什么？",
            },
            {
                "id": "cloud_shape",
                "label": "云朵想象",
                "emoji": "☁️",
                "caption": "天上的一朵奇怪形状的云。",
                "ai_prompt": "这朵云像什么？动物、还是一种食物？",
            },
        ],
        "ai_followups": [
            {"text": "这种颜色，穿在衣服上好看吗？", "card_id": "warm_colors", "step": "main"},
            {"text": "安静的颜色，您会用在房间的哪里？", "card_id": "cool_colors", "step": "main"},
            {"text": "如果让您给这幅画起个名字，您会叫它什么？", "card_id": "unfinished_art", "step": "main"},
            {"text": "如果给今天选一个颜色，您会选什么？为什么？", "card_id": "cloud_shape", "step": "summary"},
        ],
        "ai_closings": [
            "创意不需要标准答案。谢谢您今天的想象与分享。",
        ],
        "step_overrides": {
            "warmup": {
                "name": "色彩热身",
                "guide": "展示暖色色卡，请长者指出最喜欢的颜色并说一个联想。",
            },
            "main": {
                "name": "创意想象主活动",
                "guide": "色卡与想象图交替；鼓励比喻，不纠正「像不像」。",
            },
        },
    },
    9: {
        "ai_theme": "物品分类与找不同",
        "ai_focus": "用可点击的分类图组，引导把物品归类或找出「不同类」；重过程、轻对错。",
        "ai_opening": "今天第 9 次 CST，主题「分类」。我们把东西分分组，也可以找找哪一个不太一样。",
        "activities": [
            "【分类】把水果放到「水果」篮，把餐具放到「餐具」篮",
            "【找不同】四样东西里，哪一样和其他不一样",
            "【讨论】说说您家里常怎么收纳碗筷",
            "【练习】完成下方分类与找不同题目",
        ],
        "visual_cards": [
            {
                "id": "fruit_group",
                "label": "水果组",
                "emoji": "🍎",
                "caption": "苹果、香蕉、橘子——都是水果。",
                "ai_prompt": "这些都是水果。您还能再加一种水果吗？",
            },
            {
                "id": "utensil_group",
                "label": "餐具组",
                "emoji": "🥄",
                "caption": "碗、筷、勺——都是餐具。",
                "ai_prompt": "餐具组里，您每天最常用哪一样？",
            },
            {
                "id": "odd_one",
                "label": "找不同",
                "emoji": "🔍",
                "caption": "苹果、香蕉、椅子、橘子——哪一样不同？",
                "ai_prompt": "这四样里，哪一样和其他不太一样？想到哪个说哪个。",
            },
            {
                "id": "storage",
                "label": "收纳",
                "emoji": "🗄️",
                "caption": "厨房柜里整齐的碗筷。",
                "ai_prompt": "家里碗筷通常放在哪里？橱柜还是桌上？",
            },
        ],
        "practice_items": [
            {
                "id": "s9_fruit",
                "emoji": "🍎",
                "prompt": "苹果属于哪一类？",
                "hint": "选一个您觉得对的。",
                "options": ["水果", "餐具", "家具", "说不准"],
            },
            {
                "id": "s9_bowl",
                "emoji": "🥣",
                "prompt": "碗通常和什么放在一起？",
                "hint": "想到哪说哪。",
                "options": ["筷子 / 勺子", "苹果", "椅子", "收音机"],
            },
            {
                "id": "s9_odd",
                "emoji": "🔍",
                "prompt": "苹果、香蕉、椅子、橘子——哪一样不同？",
                "hint": "能说出理由就很好。",
                "options": ["椅子", "苹果", "香蕉", "橘子"],
            },
            {
                "id": "s9_store",
                "emoji": "🗄️",
                "prompt": "碗筷您家常放在哪里？",
                "hint": "没有标准答案。",
                "options": ["橱柜", "桌上", "抽屉", "其他地方"],
            },
        ],
        "classify_game": {
            "bins": [
                {"id": "fruit", "label": "水果", "emoji": "🧺"},
                {"id": "utensil", "label": "餐具", "emoji": "🍽️"},
            ],
            "item_list": [
                {"id": "apple", "label": "苹果", "emoji": "🍎", "bin": "fruit"},
                {"id": "banana", "label": "香蕉", "emoji": "🍌", "bin": "fruit"},
                {"id": "bowl", "label": "碗", "emoji": "🥣", "bin": "utensil"},
                {"id": "chopsticks", "label": "筷子", "emoji": "🥢", "bin": "utensil"},
                {"id": "orange", "label": "橘子", "emoji": "🍊", "bin": "fruit"},
                {"id": "spoon", "label": "勺子", "emoji": "🥄", "bin": "utensil"},
            ],
            "success_hint": "分得好！水果和餐具各归其类。",
        },
        "ai_followups": [
            {"text": "水果里，您最喜欢哪一种的味道？", "card_id": "fruit_group", "step": "main"},
            {"text": "洗碗的时候，您习惯先洗什么？", "card_id": "utensil_group", "step": "main"},
            {"text": "「椅子」为什么和其他不一样？您怎么想都行。", "card_id": "odd_one", "step": "main"},
            {"text": "今天分类时，哪一步您觉得最轻松？", "card_id": "odd_one", "step": "summary"},
        ],
        "ai_closings": [
            "分类练习到此。能说出理由就很好，谢谢参与。",
        ],
        "step_overrides": {
            "warmup": {
                "name": "分类热身",
                "guide": "展示水果组图卡，请长者说出「它们有什么共同点」。",
            },
            "main": {
                "name": "分类与找不同",
                "guide": "先做屏幕上的分类小游戏，再讨论「找不同」；允许改答案。",
            },
        },
    },
    11: {
        "ai_theme": "用钱与购物情景",
        "ai_focus": "用人民币示意卡与购物情景文字，引导识别面额、聊聊买菜；不涉及真实转账或财务建议。",
        "ai_opening": "欢迎参加第 11 次 CST。今天主题「用钱」，我们看一看纸币图卡，聊聊买菜的小事。",
        "activities": [
            "【图卡】辨认「一元 / 十元」示意卡（无真实交易）",
            "【情景】读「去菜场买两斤青菜」文字卡",
            "【讨论】说说以前买东西常怎么付钱",
            "【温和问答】如果买一包盐，您会大概准备多少钱",
        ],
        "visual_cards": [
            {
                "id": "yuan_one",
                "label": "一元示意",
                "emoji": "💴",
                "caption": "一张一元纸币的示意图案（非真实货币扫描件）。",
                "ai_prompt": "这是一元的示意。您还记得一元能买点什么小东西吗？",
            },
            {
                "id": "yuan_ten",
                "label": "十元示意",
                "emoji": "💵",
                "caption": "一张十元纸币的示意图案。",
                "ai_prompt": "十元示意卡。买菜时，十元大概够买些什么？",
            },
            {
                "id": "market_scene",
                "label": "菜场情景",
                "emoji": "🛒",
                "caption": "【情景】去菜场买两斤青菜，摊主笑着找零钱。",
                "ai_prompt": "去菜场买青菜。您喜欢自己挑，还是让摊主帮您拿？",
            },
            {
                "id": "change_coin",
                "label": "零钱",
                "emoji": "🪙",
                "caption": "几枚硬币零钱的示意。",
                "ai_prompt": "找回的零钱，您习惯放在哪里？",
            },
        ],
        "ai_followups": [
            {"text": "除了一元，还有哪种面额您一眼就认得？", "card_id": "yuan_one", "step": "main"},
            {"text": "十元买菜，您会不会再看看有没有找对零钱？", "card_id": "yuan_ten", "step": "main"},
            {"text": "菜场里，什么声音最熟悉？", "card_id": "market_scene", "step": "main"},
            {"text": "今天聊用钱，您觉得哪张图最好懂？", "card_id": "change_coin", "step": "summary"},
        ],
        "ai_closings": [
            "用钱讨论到这里。我们只是回忆生活情景，谢谢您的分享。",
        ],
        "step_overrides": {
            "warmup": {
                "name": "面额热身",
                "guide": "展示一元示意卡，请长者说出「这是多少钱」并联想用途。",
            },
            "main": {
                "name": "购物情景讨论",
                "guide": "面额卡与菜场情景结合；不计算复杂找零，不给财务建议。",
            },
        },
    },
    12: {
        "ai_theme": "数字与日期轻松练习",
        "ai_focus": "用日期、数量图卡做轻松练习：数一数、认一认；不测验算术速度。",
        "ai_opening": "今天是第 12 次 CST，主题「数字」。我们慢慢数、认日期，不着急。",
        "activities": [
            "【图卡】数一数「三个苹果」",
            "【图卡】看日历，说说今天大概是几号附近",
            "【图卡】看「两杯茶」，说说「二」这个数量",
            "【温和讨论】家里门牌或楼层，有没有一个您记得的数字",
        ],
        "visual_cards": [
            {
                "id": "three_apples",
                "label": "三个苹果",
                "emoji": "🍎🍎🍎",
                "caption": "盘子里放着三个苹果。",
                "ai_prompt": "盘子里有几个苹果？您可以一个一个数。",
            },
            {
                "id": "date_card",
                "label": "日期卡",
                "emoji": "📆",
                "caption": "一张写着日期的卡片。",
                "ai_prompt": "看看日期卡。今天更靠近月初，还是月末？",
            },
            {
                "id": "two_teacups",
                "label": "两杯茶",
                "emoji": "🍵",
                "caption": "桌上两只茶杯。",
                "ai_prompt": "两杯茶，通常是两个人喝。您喜欢和谁一起喝茶？",
            },
            {
                "id": "house_number",
                "label": "门牌数字",
                "emoji": "🔢",
                "caption": "一个示意门牌号码。",
                "ai_prompt": "门牌上的数字，您家里有没有一个记得住的数？",
            },
        ],
        "ai_followups": [
            {"text": "如果再加一个苹果，会变成几个？", "card_id": "three_apples", "step": "main"},
            {"text": "日期里的「月」，您最喜欢哪一个月？", "card_id": "date_card", "step": "main"},
            {"text": "两杯茶，茶水是满的还是浅的，您更喜欢哪种？", "card_id": "two_teacups", "step": "main"},
            {"text": "今天哪个数字练习，您觉得最轻松？", "card_id": "house_number", "step": "summary"},
        ],
        "ai_closings": [
            "数字练习结束。慢慢来就很好，谢谢您。",
        ],
        "step_overrides": {
            "warmup": {
                "name": "数数热身",
                "guide": "展示三个苹果，请长者用手指数一数。",
            },
            "main": {
                "name": "数字与日期主活动",
                "guide": "数量与日期交替；允许借助手指，不限时。",
            },
        },
    },
    13: {
        "ai_theme": "谚语与谜语文字游戏",
        "ai_focus": "用熟悉谚语、简单谜语卡保持语言兴趣；猜不出也完全没关系，可读完一起笑一笑。",
        "ai_opening": "欢迎参加第 13 次 CST。今天玩「文字游戏」：读谚语、猜小谜语，轻松就好。",
        "activities": [
            "【谚语卡】读「一日之计在于晨」，说说您怎么理解",
            "【谚语卡】读「远亲不如近邻」，聊聊邻里",
            "【谜语卡】「小小两只船，白天忙不停，夜里港湾停」（提示：手）",
            "【温和讨论】还有没有一句您从小就会念的老话",
        ],
        "card_style": "text",
        "visual_cards": [
            {
                "id": "proverb_morning",
                "label": "谚语 · 晨",
                "emoji": "📜",
                "caption": "一日之计在于晨。",
                "ai_prompt": "「一日之计在于晨」——您觉得这句话在说什么？",
            },
            {
                "id": "proverb_neighbor",
                "label": "谚语 · 邻里",
                "emoji": "📜",
                "caption": "远亲不如近邻。",
                "ai_prompt": "「远亲不如近邻」。您有没有热心的邻居？",
            },
            {
                "id": "riddle_hands",
                "label": "小谜语",
                "emoji": "❓",
                "caption": "小小两只船，白天忙不停，夜里港湾停。（提示：身上的）",
                "ai_prompt": "这则小谜语，您猜是什么？猜不出我们一起看提示。",
            },
            {
                "id": "old_saying",
                "label": "老话",
                "emoji": "🗣️",
                "caption": "您从小就会念的一句老话。",
                "ai_prompt": "还有没有一句您小时候常听的老话？想到哪句说哪句。",
            },
        ],
        "ai_followups": [
            {"text": "早晨您一般先做什么？", "card_id": "proverb_morning", "step": "main"},
            {"text": "邻居之间，什么事最让您觉得方便？", "card_id": "proverb_neighbor", "step": "main"},
            {"text": "谜底是「双手」。您觉得像不像两只小船？", "card_id": "riddle_hands", "step": "main"},
            {"text": "今天哪一句老话或谜语您最有印象？", "card_id": "old_saying", "step": "summary"},
        ],
        "ai_closings": [
            "文字游戏到此。读一读、笑一笑就很好，谢谢您。",
        ],
        "step_overrides": {
            "warmup": {
                "name": "读谚语热身",
                "guide": "大声朗读第一句谚语，请长者用自己的话解释一句。",
            },
            "main": {
                "name": "谚语与谜语",
                "guide": "先谚语后谜语；猜不出立即给提示，保持轻松氛围。",
            },
        },
    },
}

CST_SESSIONS = [
    {"num": 1, "title": "图画联想", "slug": "picture-words", "summary": "通过图卡与老照片引发词语联想，激活视觉记忆与语言表达。"},
    {"num": 2, "title": "声音", "slug": "sounds", "summary": "结合声音描述卡片与歌词文字，联结听觉记忆与情感。"},
    {"num": 3, "title": "童年", "slug": "childhood", "summary": "围绕儿时生活图卡与故事叙述，开展回忆性 CST 讨论。"},
    {"num": 4, "title": "食物", "slug": "food", "summary": "用食材图卡讨论拿手菜与节日饮食，多感官文字刺激。"},
    {"num": 5, "title": "时事", "slug": "current-affairs", "summary": "阅读简短生活趣闻卡片，鼓励表达观点。"},
    {"num": 6, "title": "面孔与场景", "slug": "faces-scenes", "summary": "辨认家人照片与熟悉街景图卡，联结人物与空间记忆。"},
    {"num": 7, "title": "词语联想", "slug": "word-association", "summary": "文字卡片上的同类别列词与联想游戏。"},
    {"num": 8, "title": "创意", "slug": "being-creative", "summary": "看图描述、色彩卡片与创意想象。"},
    {"num": 9, "title": "分类", "slug": "categorising", "summary": "物品图片分类与「找不同类」文字游戏。"},
    {"num": 10, "title": "定向", "slug": "orientation", "summary": "结合定向板文字与地图图片，巩固时空定向。"},
    {"num": 11, "title": "用钱", "slug": "using-money", "summary": "人民币图卡与购物情景文字讨论。"},
    {"num": 12, "title": "数字", "slug": "numbers", "summary": "日期、数量相关的轻松文字与图片游戏。"},
    {"num": 13, "title": "文字游戏", "slug": "word-games", "summary": "谚语、谜语卡片，保持语言兴趣。"},
    {"num": 14, "title": "团队问答", "slug": "team-quiz", "summary": "回顾疗程的图片与文字小问答，庆祝完成。"},
]

CST_STEP_TEMPLATE = [
    {"key": "welcome", "name": "欢迎", "minutes": 2, "guide": "称呼小组名，介绍今日主题，营造轻松、无评判的氛围。"},
    {"key": "ro", "name": "现实定向板", "minutes": 3, "guide": "一起阅读屏幕上的日期、星期、地点与天气文字。"},
    {"key": "warmup", "name": "图文热身", "minutes": 5, "guide": "展示第一张主题图卡，请长者描述「看到了什么」。"},
    {"key": "discussion", "name": "读图讨论", "minutes": 5, "guide": "围绕图卡上的细节展开讨论，鼓励联系个人经历。"},
    {"key": "main", "name": "主题主活动", "minutes": 25, "guide": "依次呈现图卡与文字话题，AI 引导员一次一问。"},
    {"key": "summary", "name": "总结反馈", "minutes": 5, "guide": "回顾今天看了哪些图、聊了哪些词，感谢参与。"},
]


def _practice_from_cards(cards: list | None) -> list[dict]:
    """由图卡 AI 引导语生成默认课程练习题（语音作答，无对错评判）。"""
    out: list[dict] = []
    for i, card in enumerate(cards or [], 1):
        prompt = (card.get("ai_prompt") or card.get("caption") or card.get("label") or "").strip()
        if not prompt:
            continue
        out.append(
            {
                "id": card.get("id") or f"practice_{i}",
                "emoji": card.get("emoji") or "💬",
                "prompt": prompt,
                "hint": "慢慢想就好，没有对错。",
                "speak_label": card.get("label") or prompt[:12],
                "speak_caption": card.get("caption") or "",
                "ai_prompt": card.get("ai_prompt") or prompt,
            }
        )
    return out


def _enrich_practice_speak(items: list | None, cards: list | None) -> list[dict]:
    """为课程练习补齐听题播报所需字段。"""
    cards = list(cards or [])
    enriched: list[dict] = []
    for i, raw in enumerate(items or []):
        item = dict(raw)
        card = cards[i] if i < len(cards) else {}
        prompt = (item.get("prompt") or "").strip()
        item.setdefault("speak_label", card.get("label") or prompt[:16] or "练习题")
        item.setdefault("speak_caption", card.get("caption") or item.get("hint") or "")
        item.setdefault("ai_prompt", card.get("ai_prompt") or prompt)
        enriched.append(item)
    return enriched


def _merge_session(base: dict, extra: dict | None) -> dict:
    item = dict(base)
    if not extra:
        item["activities"] = [f"围绕「{item['title']}」的 CST 图文活动（内容完善中）"]
        item["visual_cards"] = []
        item["ai_followups"] = []
        item["ai_closings"] = ["今天辛苦了，我们下次继续。"]
        item["practice_items"] = []
        item["ai_theme"] = item["title"]
        item["ai_focus"] = item["summary"]
        item["ai_opening"] = f"您好，欢迎参加{{group_name}}的第 {item['num']} 次 CST，今天主题「{item['title']}」。"
        return item

    item.update({k: v for k, v in extra.items() if k != "step_overrides"})
    if "activities" not in item:
        item["activities"] = extra.get("activities", [])
    if not item.get("practice_items"):
        item["practice_items"] = _practice_from_cards(item.get("visual_cards"))
    else:
        item["practice_items"] = _enrich_practice_speak(
            item.get("practice_items"), item.get("visual_cards")
        )

    steps = [dict(x) for x in CST_STEP_TEMPLATE]
    overrides = extra.get("step_overrides") or {}
    for step in steps:
        if step["key"] in overrides:
            step.update(overrides[step["key"]])
    item["steps"] = steps
    return item


def get_session(num: int) -> dict | None:
    base = next((s for s in CST_SESSIONS if s["num"] == num), None)
    if base is None:
        return None
    extra = SESSION_ENRICHMENT.get(num)
    item = _merge_session(base, extra)
    if "steps" not in item:
        item["steps"] = [dict(x) for x in CST_STEP_TEMPLATE]
    if not item.get("practice_items"):
        item["practice_items"] = _practice_from_cards(item.get("visual_cards"))
    else:
        item["practice_items"] = _enrich_practice_speak(
            item.get("practice_items"), item.get("visual_cards")
        )
    item["mvp_ready"] = num in MVP_SESSIONS
    item["duration"] = sum(step["minutes"] for step in item["steps"])
    return item


def all_sessions_enriched() -> list[dict]:
    return [get_session(s["num"]) for s in CST_SESSIONS]


def reality_orientation_context() -> dict:
    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    seasons = {
        1: "冬季", 2: "冬季", 3: "春季", 4: "春季", 5: "春季",
        6: "夏季", 7: "夏季", 8: "夏季", 9: "秋季", 10: "秋季", 11: "秋季", 12: "冬季",
    }
    return {
        "date": now.strftime("%Y年%m月%d日"),
        "weekday": weekdays[now.weekday()],
        "season": seasons[now.month],
        "time": now.strftime("%H:%M"),
        "place": "居家 · 记忆港湾 CST 小组",
    }
