"""AI工具箱：省流总结、识图、阴阳怪气、地理定位。

移植自渔火（https://github.com/yhArcadia）的 ai-tools.js。
"""

import re
import time

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import At, Image, Plain, Reply
from astrbot.api.star import Context, Star, register

# ── 默认提示词（来自渔火的 ai-tools.js） ──────────────────────

DEFAULT_TLDR_PROMPT = (
    "你是一个群聊内容总结助手（省流专家）。\n"
    '请阅读用户提供的聊天记录、图片或文本，用极其简明扼要的语言提炼出核心信息，进行"省流"总结。\n'
    "\n"
    "【绝对规则】\n"
    "1. 你的总结必须一针见血，总输出字数严格控制在300字以内。\n"
    "压缩你的思考环节，尽可能使用尽量少的思考，最好直接输出答案，避免思考。\n"
    "2. 严禁长篇大论打草稿！\n"
    '3. 严禁使用任何 Markdown 格式（绝对不要使用 ** 加粗、# 标题等符号），必须输出适合普通群聊软件阅读的纯文本！\n'
    '4. 请严格回避任何敏感涉政键政问题，遇到这类问题直接回一句"见nm证呢滚"。'
)

DEFAULT_SHITU_PROMPT = (
    "你是一个识图AI系统，需根据图片内容分类并生成对应回应。请严格按照以下分类逻辑和回应规则处理图片：\n"
    "\n"
    "### 一、角色识别类\n"
    "#### 1. 动漫/游戏角色\n"
    "- 识别条件：二次元风格角色形象，源自动画、漫画、游戏\n"
    "- 回应内容：必须包含「角色名称」「作品出处」「角色介绍」（如身份、能力、经典台词），例：\n"
    "  > 这是《火影忍者》中的宇智波佐助，宇智波一族成员，擅长雷遁忍术，目标是复兴家族。\n"
    "\n"
    "#### 2. 原创角色（PIXIV等平台）\n"
    "- 识别条件：非公开IP的原创人设图，可能带有画师水印或签名\n"
    "- 回应内容：包含「角色名称」「画师/作者」「设定介绍」（如世界观、角色背景），若检测到来源链接，需提示「该角色出自画师[作者名]的PIXIV作品：[链接]」\n"
    "\n"
    "#### 3. 真人照片\n"
    "- 识别条件：现实人物肖像照、活动照\n"
    "- 回应内容：包含「人物姓名」「职业背景」「代表成就」，例：\n"
    "  > 这是演员周迅，中国内地知名艺人，代表作《苏州河》《如懿传》，曾获金马奖影后。\n"
    "\n"
    "### 二、场景与实物类\n"
    "#### 1. 实景照片\n"
    "- 识别条件：自然景观、城市建筑、室内环境等真实场景\n"
    "- 回应内容：优先定位「拍摄地点」（如具体景点、城市地标），若无法定位则描述场景特征（如「这是海边日落场景，可见沙滩与椰树」）\n"
    "\n"
    "#### 2. 实物物品（建筑/物品）\n"
    "- 识别条件：具体物体、建筑、器械等\n"
    "- 回应内容：包含「物品名称」「用途/历史」「特征描述」，例：\n"
    "  > 这是埃菲尔铁塔，位于巴黎，1889年建成，高300米，是法国文化象征之一。\n"
    "\n"
    "#### 3. 电影截图\n"
    "- 识别条件：影视画面，含角色或场景\n"
    "- 回应内容：包含「电影名称」「上映年份」「导演」「场景说明」，例：\n"
    "  > 这是《星际穿越》（2014）的截图，诺兰执导，画面为宇航员在米勒星球的场景。\n"
    "\n"
    "### 三、艺术创作类\n"
    "#### 1. 绘画/雕塑作品\n"
    "- 识别条件：油画、水彩画、素描、雕塑等艺术作品\n"
    "- 回应内容：包含「作品名称」「创作者」「创作年代」「艺术风格」，例：\n"
    "  > 这是梵高的《星月夜》（1889），后印象派代表作，用旋转笔触表现星空动态。\n"
    "\n"
    "#### 2. 插画/漫画（非角色类）\n"
    "- 识别条件：独立插画、漫画场景分镜\n"
    "- 回应内容：说明「插画类型」「画面主题」，若有作者信息则补充，例：\n"
    "  > 这是治愈系插画，描绘森林中的小动物聚会场景，作者@插画师阿茶。\n"
    "\n"
    "### 四、自然与科学类\n"
    "#### 1. 动物/植物\n"
    "- 识别条件：生物个体或群体\n"
    "- 回应内容：包含「物种名称」「分类」「生活习性」，例：\n"
    "  > 这是大熊猫（学名：Ailuropoda melanoleuca），熊科动物，主要以竹子为食，中国特有物种。\n"
    "\n"
    "#### 2. 自然现象/天文\n"
    "- 识别条件：极光、彩虹、星系、行星等\n"
    "- 回应内容：包含「现象名称」「形成原理」「观测地点/条件」，例：\n"
    "  > 这是极光，由太阳风与地球磁场作用形成，最佳观测地为挪威特罗姆瑟。\n"
    "\n"
    "#### 3. 医学/科学影像\n"
    "- 识别条件：X光片、显微镜图像、实验数据图\n"
    "- 回应内容：仅说明「影像类型」与「观测对象」，不做诊断，例：\n"
    "  > 这是人体胸部X光片，可见肋骨与肺部轮廓，建议结合临床分析。\n"
    "\n"
    "### 五、信息与符号类\n"
    "#### 1. 屏幕截图/文档\n"
    "- 识别条件：电脑界面、手机截图、票据、证书\n"
    "- 回应内容：说明「内容类型」与「关键信息」（模糊处理敏感数据），例：\n"
    "  > 这是增值税发票截图，可识别为餐饮类消费，金额信息已模糊处理。\n"
    "\n"
    "#### 2. 二维码/Logo/符号\n"
    "- 识别条件：品牌标识、功能符号、条码\n"
    "- 回应内容：包含「符号名称」「所属品牌/用途」，例：\n"
    "  > 这是苹果公司Logo，被咬掉一口的苹果形象，象征创新与科技。\n"
    "\n"
    "#### 3. 表情包/梗图\n"
    "- 识别条件：网络流行图像、搞笑素材\n"
    "- 回应内容：说明「梗的来源」「流行时间」「含义」，例：\n"
    "  > 这是「黑人问号」表情包，源自NBA球员尼克·杨的采访截图，2015年起用于表达困惑。\n"
    "\n"
    "### 六、数字虚拟类\n"
    "#### 1. 游戏/影视道具\n"
    "- 识别条件：虚拟装备、武器、场景道具\n"
    "- 回应内容：包含「道具名称」「出处作品」「设定功能」，例：\n"
    "  > 这是《塞尔达传说》中的大师剑，寄宿着封印魔王的神圣力量，需Link拥有足够力量才能拔出。\n"
    "\n"
    "#### 2. AI生成图像/3D模型\n"
    "- 识别条件：算法生成艺术图、虚拟场景\n"
    "- 回应内容：说明「生成技术」「画面主题」，例：\n"
    "  > 这是Stable Diffusion生成的赛博朋克风格图像，检测到关键词：机械义体、霓虹招牌、雨夜城市。\n"
    "\n"
    "### 七、生活实用类\n"
    "#### 1. 食品/日用品\n"
    "- 识别条件：餐饮、化妆品、电子产品等\n"
    "- 回应内容：包含「物品名称」「用途」「特征」，例：\n"
    "  > 这是乐事原味薯片，净含量70g，主要原料为马铃薯，适合休闲零食。\n"
    "\n"
    "#### 2. 家居/建筑风格\n"
    "- 识别条件：装修设计、家具、户型图\n"
    "- 回应内容：说明「风格类型」「设计特点」，例：\n"
    "  > 这是北欧风格装修，以白色为主色调，搭配原木家具与绿植，强调极简与功能性。\n"
    "\n"
    "### 八、兜底处理：未知类型\n"
    "- 触发条件：无法匹配以上任何分类的模糊图像\n"
    "- 回应内容：按照你的理解自由发挥，同时明确告知你也不太确定是否正确。\n"
    "\n"
    "### 响应规则\n"
    "1. **优先级逻辑**：角色类 > 场景类 > 实物类 > 信息类，优先处理高优先级分类\n"
    "2. **信息完整性**：每个回应必须包含该分类要求的核心字段（如角色类必须有名称+出处）\n"
    "3. **隐私保护**：文档类仅识别类型，不提取具体文字；医学影像不做诊断建议\n"
    "4. **格式规范**：使用中文口语化表达，链接需完整标注。你的回答不要放在引号中。字数不必局限于我所给的例子，尽量丰富你的回答内容，尽可能地详实、充分、面面俱到。\n"
    '5. **敏感词过滤**：请严格回避任何敏感涉政键政问题，遇到这类问题直接回一句"见nm证呢滚"。'
)

DEFAULT_SARCASTIC_PROMPT = (
    "你是一个专门说反话的AI。\n"
    '用户问什么东西"好吃吗/好喝吗/好用吗/好玩吗/好看吗"，你都要贬低它，想办法论证它很差劲，但是又要让自己言论显得理中客。\n'
    '不必使用语气词，就用平铺直叙的陈述方式来论证即可,不必使用"也就骗骗外行人"、"也就只能……"这样的句式。\n'
    "不要使用任何Markdown格式，控制在100字以内。\n"
    '但是，请严格回避任何敏感涉政键政问题，遇到这类问题直接回一句"见nm证呢滚"。'
)

DEFAULT_LOCATE_PROMPT = (
    "请注意，这不是一个生成图片的任务，请你按照我的要求输出文本。\n"
    "请你作为一名专业的开源情报（OSINT）地理位置分析师，具备极其敏锐的观察力和丰富的地理、植被、建筑及人文知识。\n"
    "\n"
    "请仔细观察我提供的图片，系统性地推断拍摄地点的真实位置。\n"
    "\n"
    "**⚠️ 重要原则：请不要急于给出具体的坐标或地点。你必须严格按照以下【分析步骤】进行逐步推理，展示你的思考过程。**\n"
    "\n"
    "---\n"
    "## 📋 分析步骤\n"
    "\n"
    "### 第一步：自然环境特征分析\n"
    "请详细描述画面中的自然元素，并推断其对应的气候带或地理区域：\n"
    "* **植被分析：** 树种（如针叶、阔叶、棕榈）、草地形态、植被密度。这暗示了什么气候（热带、亚热带、温带、寒带）？\n"
    '* **地形地貌：** 是平原、盆地（如"坝子"）、山地（花岗岩、喀斯特）、河谷还是沿海？\n'
    "* **气象与光影：** 云层特征（积云、层云）、光照强度、影子的长短。推测大概的季节或纬度范围。\n"
    "\n"
    "### 第二步：人文与基础设施分析\n"
    "请挖掘画面中的人造线索：\n"
    "* **交通特征：** 车辆靠左还是靠右行驶？路面铺装情况（柏油、红土）？车牌样式或车型（如Tuk-Tuk、皮卡、特定品牌）。\n"
    "* **建筑风格：** 屋顶形状（坡顶、平顶）、建筑材料（木质、水泥、红砖）、是否有特定的宗教或文化装饰（如寺庙尖顶）。\n"
    "* **文字与符号：** 路牌、广告牌上的文字语言、字体、交通标志的颜色和形状。\n"
    "\n"
    "### 第三步：关键线索提取\n"
    '* 总结出 2-3 个最具辨识度的核心特征（例如："高大雪山+U型谷地"或"湄公河风格建筑+红土路"）。\n'
    "\n"
    "### 第四步：综合判断与输出（重点）\n"
    "\n"
    "**请按照以下逻辑顺序，撰写一段详细的推理总结（不包含在列表中）：**\n"
    "\n"
    '1.  **宏观定位：** 基于气候、植被和交通规则，首先将范围锁定在某个大区域（例如：东南亚内陆国家、中国西南地区）。\n'
    "2.  **进一步缩小：** 结合大型地貌（河流、山脉）和建筑细节，将推断范围缩小至具体的国家或省份。请说明哪些细节支持了这一推断（如：桥梁栏杆颜色、特有的民居屋顶）。\n"
    '3.  **精确搜索思路：** 明确列出你为了核实地点而构建的搜索关键词。格式为：**"进一步精确搜索目标：[关键词A] + [关键词B] + [关键词C]"**。\n'
    "4.  **候选锁定：** 提出 1-2 个具体的候选城市或区域，并说明它们为什么符合上述特征。\n"
    "\n"
    "**在完成上述文字推理后，请给出最终的结构化排名：**\n"
    "\n"
    "**🏆 第一可能位置：[国家] - [省/州] - [城市/具体区域]**\n"
    "* **经纬度（可选，当位置比较确定时，请附带经纬度，否则不加此条）：[精确的经纬度]（如东经xx°xx′，北纬xx°xx′）**\n"
    "* **可能性概率：** [例如：85%]\n"
    "* **🔍 判断依据：**\n"
    "    * **依据1（地貌/环境）：** [详细解释]\n"
    "    * **依据2（植被/气候）：** [详细解释]\n"
    "    * **依据3（人文/基建）：** [详细解释]\n"
    "\n"
    "**🥈 第二可能位置：[备选地点]**\n"
    "* **可能性概率：** [例如：15%]\n"
    "* **🔍 判断依据：** [简述理由]\n"
    "\n"
    "---\n"
    "请开始你的分析，输出文本，不要生成图片。"
)

QQ_AVATAR_URL = "https://q1.qlogo.cn/g?b=qq&nk={qq}&s=640"

TIP_NO_CONTENT = {
    "tldr": "请引用一条包含文本/图片的消息，或者直接在指令后输入文本。",
    "shitu": "图呢？请发送图片、引用包含图片的消息，或者艾特某人识别人家头像。",
    "sarcastic": "请引用一条包含文本/图片的消息，或者在问什么东西好吃吗/好喝吗/好用吗/好玩吗/好看吗。",
    "locate": "请引用一张图片或直接发送图片，然后使用地理定位指令。",
}

DEFAULT_TEXT = {
    "tldr": "请帮我提取并总结这幅图中的关键信息。",
    "shitu": "请识别并描述这张图片的内容。",
    "sarcastic": "请评价这个东西怎么样，用阴阳怪气说反话的方式。",
    "locate": "请分析这张图片的拍摄地理位置。",
}


def _parse_keywords(value, default):
    """将配置值解析为关键词列表，兼容 list / str 两种格式。"""
    if value is None:
        return list(default)
    if isinstance(value, list):
        return [str(k).strip() for k in value if str(k).strip()]
    if isinstance(value, str):
        parts = [k.strip() for k in value.split(",") if k.strip()]
        return parts if parts else list(default)
    return list(default)


@register(
    "astrbot_plugin_kktools",
    "konley",
    "AI工具箱——省流总结、识图、阴阳怪气、地理定位",
    "1.0.0",
)
class KKTools(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        config = config or {}

        # 全局设置
        self.ignore_slash: bool = bool(config.get("ignore_slash", True))
        self.enable_vision: bool = bool(config.get("enable_vision", True))
        self.cooldown: int = int(config.get("cooldown", 5))

        # 省流总结
        self.tldr_enabled: bool = bool(config.get("tldr_enabled", True))
        self.tldr_keywords: list[str] = _parse_keywords(
            config.get("tldr_keywords"), ["省流", "总结", "tldr", "TLDR"]
        )
        self.tldr_prompt: str = config.get("tldr_prompt") or DEFAULT_TLDR_PROMPT

        # 识图
        self.shitu_enabled: bool = bool(config.get("shitu_enabled", True))
        self.shitu_keywords: list[str] = _parse_keywords(
            config.get("shitu_keywords"), ["识图"]
        )
        self.shitu_prompt: str = config.get("shitu_prompt") or DEFAULT_SHITU_PROMPT

        # 阴阳怪气
        self.sarcastic_enabled: bool = bool(config.get("sarcastic_enabled", True))
        self.sarcastic_keywords: list[str] = _parse_keywords(
            config.get("sarcastic_keywords"),
            ["好吃吗", "好喝吗", "好用吗", "好玩吗", "好看吗"],
        )
        self.sarcastic_prompt: str = (
            config.get("sarcastic_prompt") or DEFAULT_SARCASTIC_PROMPT
        )

        # 地理定位
        self.locate_enabled: bool = bool(config.get("locate_enabled", True))
        self.locate_keywords: list[str] = _parse_keywords(
            config.get("locate_keywords"), ["在哪"]
        )
        self.locate_prompt: str = config.get("locate_prompt") or DEFAULT_LOCATE_PROMPT

        # 冷却记录
        self._cooldowns: dict[str, float] = {}

    # ── 主入口 ────────────────────────────────────

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def handle_message(self, event: AstrMessageEvent):
        raw = self._plain_text(event).strip()
        if not raw:
            return

        # 去前缀
        match_text = raw
        if self.ignore_slash and (match_text.startswith("/") or match_text.startswith("#")):
            match_text = match_text[1:].strip()

        # 按优先级匹配
        if self.tldr_enabled:
            kw = self._match_prefix(match_text, self.tldr_keywords)
            if kw:
                async for r in self._run_feature(event, "tldr", kw, is_prefix=True):
                    yield r
                return

        if self.shitu_enabled:
            kw = self._match_prefix(match_text, self.shitu_keywords)
            if kw:
                async for r in self._run_feature(event, "shitu", kw, is_prefix=True):
                    yield r
                return

        if self.locate_enabled:
            kw = self._match_prefix(match_text, self.locate_keywords)
            if kw:
                async for r in self._run_feature(event, "locate", kw, is_prefix=True):
                    yield r
                return

        if self.sarcastic_enabled:
            kw = self._match_suffix(match_text, self.sarcastic_keywords)
            if kw:
                async for r in self._run_feature(event, "sarcastic", kw, is_prefix=False):
                    yield r
                return

    # ── 功能执行 ──────────────────────────────────

    async def _run_feature(self, event, feature, matched_kw, is_prefix):
        """通用流程：冷却 → 提取内容 → 调模型 → 回复。"""
        user_id = event.get_sender_id()
        now = time.time()
        last = self._cooldowns.get(user_id)
        if last is not None and now - last < self.cooldown:
            remain = int(self.cooldown - (now - last)) + 1
            yield event.plain_result(f"冷却中，请 {remain} 秒后再试。")
            return

        text, images = self._extract_content(event, feature, matched_kw, is_prefix)
        logger.info(
            f"[kktools:{feature}] text={text!r} images={len(images)}张"
        )

        if not text and not images:
            yield event.plain_result(TIP_NO_CONTENT[feature])
            return

        provider = self.context.get_using_provider()
        if provider is None:
            yield event.plain_result("当前未配置任何大模型提供商，请在 AstrBot 后台配置后再使用。")
            return

        self._cooldowns[user_id] = now

        # 纯图场景兜底文案
        if not text:
            text = DEFAULT_TEXT[feature]

        prompt_map = {
            "tldr": self.tldr_prompt,
            "shitu": self.shitu_prompt,
            "sarcastic": self.sarcastic_prompt,
            "locate": self.locate_prompt,
        }

        try:
            llm_resp = await provider.text_chat(
                prompt=text,
                image_urls=images if self.enable_vision else [],
                system_prompt=prompt_map[feature],
            )
            content = (llm_resp.completion_text or "").strip()
        except Exception as e:
            logger.error(f"[kktools:{feature}] 调用大模型失败: {e}")
            yield event.plain_result(f"调用失败，请稍后重试。")
            return

        if not content:
            yield event.plain_result("模型未返回有效内容。")
            return

        content = self._strip_markdown(content)

        prefix_label = {
            "tldr": "【省流总结】\n",
            "shitu": "【识图结果】\n",
            "sarcastic": "",
            "locate": "【OSINT地理定位】\n",
        }
        yield event.plain_result(prefix_label[feature] + content)

    # ── 内容提取 ──────────────────────────────────

    def _extract_content(self, event, feature, matched_kw, is_prefix):
        """提取文本与图片，优先取引用消息。"""
        chain = event.get_messages()

        # 优先：引用消息
        for comp in chain:
            if isinstance(comp, Reply) and comp.chain:
                text, images = self._parse_chain(comp.chain)
                if text or images:
                    return text, images

        # 否则：当前消息，去掉 @机器人
        self_id = str(event.get_self_id())
        cleaned = [
            c for c in chain
            if not (isinstance(c, At) and str(c.qq) == self_id)
        ]
        text, images = self._parse_chain(cleaned)

        # 剥离关键词
        if text and matched_kw:
            if is_prefix and text.startswith(matched_kw):
                text = text[len(matched_kw):].strip()
            elif not is_prefix and text.endswith(matched_kw):
                text = text[: -len(matched_kw)].strip()

        # 识图/定位：没图则取 @头像
        if feature in ("shitu", "locate") and not images:
            at_qq = self._get_at_qq(event)
            if at_qq:
                images.append(QQ_AVATAR_URL.format(qq=at_qq))

        return text, images

    def _parse_chain(self, chain):
        """解析消息链，返回 (文本, 图片URL列表)。"""
        text_parts: list[str] = []
        images: list[str] = []
        for comp in chain:
            if isinstance(comp, Plain) and comp.text:
                text_parts.append(comp.text.strip())
            elif isinstance(comp, Image):
                url = getattr(comp, "url", None) or getattr(comp, "file", None)
                if url:
                    images.append(url)
        return " ".join(p for p in text_parts if p).strip(), images

    # ── 关键词匹配 ────────────────────────────────

    @staticmethod
    def _match_prefix(text, keywords):
        """前缀匹配，返回命中的关键词或 None。"""
        for kw in keywords:
            if text.startswith(kw):
                return kw
        return None

    @staticmethod
    def _match_suffix(text, keywords):
        """后缀匹配（允许紧跟 ?/？），返回命中的完整后缀或 None。"""
        for kw in keywords:
            if text.endswith(kw):
                return kw
            for suffix in ("？", "?"):
                if text.endswith(kw + suffix):
                    return kw + suffix
        return None

    # ── 辅助 ──────────────────────────────────────

    @staticmethod
    def _plain_text(event: AstrMessageEvent) -> str:
        return "".join(
            c.text for c in event.get_messages()
            if isinstance(c, Plain) and c.text
        )

    @staticmethod
    def _get_at_qq(event: AstrMessageEvent) -> str | None:
        """获取消息中 @ 的目标 QQ（排除 @机器人）。"""
        self_id = str(event.get_self_id())
        for comp in event.get_messages():
            if isinstance(comp, At) and str(comp.qq) != self_id:
                return str(comp.qq)
        return None

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """去除 Markdown 加粗和标题标记。"""
        text = re.sub(r"\*{1,2}", "", text)
        text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
        return text
