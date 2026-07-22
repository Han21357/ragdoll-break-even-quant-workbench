#!/usr/bin/env python3
"""Build the interview-facing project case study PDF."""
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pdf" / "ragdoll-quant-workbench-introduction.pdf"
OVERVIEW = ROOT / "docs" / "assets" / "dashboard-overview.png"
IMPORT = ROOT / "docs" / "assets" / "holdings-import.png"
W, H = landscape(A4)
PAGES = 12

CREAM = HexColor("#FFF9F2")
SURFACE = HexColor("#FFFFFF")
BROWN = HexColor("#754723")
CARAMEL = HexColor("#B77B45")
DARK = HexColor("#29231F")
MUTED = HexColor("#746A62")
BORDER = HexColor("#E3D5C8")
BLUE = HexColor("#EAF1F6")
GREEN = HexColor("#E4EEE5")
GOLD = HexColor("#FFF0D6")
ROSE = HexColor("#F9E5E1")
CHARCOAL = HexColor("#2C3438")


def setup_fonts():
    pdfmetrics.registerFont(TTFont("RagdollCN", "/System/Library/Fonts/STHeiti Medium.ttc", subfontIndex=0))


def text(c, value, x, y, size=12, color=DARK, font="RagdollCN"):
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawString(x, y, value)


def wrapped(c, value, x, y, width, size=10, leading=16, color=MUTED, max_lines=6):
    lines, current = [], ""
    for char in value:
        candidate = current + char
        if current and pdfmetrics.stringWidth(candidate, "RagdollCN", size) > width:
            lines.append(current)
            current = char
            if len(lines) >= max_lines:
                break
        else:
            current = candidate
    if current and len(lines) < max_lines:
        lines.append(current)
    for index, line in enumerate(lines):
        text(c, line, x, y - index * leading, size, color)


def background(c, page, title=None, section=None):
    c.setFillColor(CREAM)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    if title:
        if section:
            text(c, section, 42, H - 43, 8, CARAMEL)
        text(c, title, 42, H - 66, 20, BROWN)
        c.setStrokeColor(BORDER)
        c.line(42, H - 78, W - 42, H - 78)
    text(c, f"老布偶猫量化工作台  |  CASE STUDY  |  {page}/{PAGES}", 42, 20, 7.5, MUTED)
    text(c, "github.com/Han21357/ragdoll-break-even-quant-workbench", W - 305, 20, 7.5, MUTED)


def box(c, x, y, width, height, fill=SURFACE, radius=6, border=BORDER):
    c.setFillColor(fill)
    c.setStrokeColor(border)
    c.roundRect(x, y, width, height, radius, fill=1, stroke=1)


def draw_image_fit(c, path, x, y, width, height):
    with PILImage.open(path) as image:
        ratio = min(width / image.width, height / image.height)
        draw_w, draw_h = image.width * ratio, image.height * ratio
    c.drawImage(str(path), x + (width - draw_w) / 2, y + (height - draw_h) / 2, draw_w, draw_h, preserveAspectRatio=True, mask="auto")


def bullet(c, value, x, y, width, size=9.5, color=DARK):
    c.setFillColor(CARAMEL)
    c.circle(x + 3, y + 3, 2.2, fill=1, stroke=0)
    wrapped(c, value, x + 13, y + 7, width - 13, size, 15, color, 3)


def page_cover(c):
    background(c, 1)
    text(c, "AI PRODUCT CASE STUDY", 43, H - 52, 9, CARAMEL)
    text(c, "老布偶猫量化工作台", 42, H - 86, 29, BROWN)
    text(c, "Evidence-first A 股投资研究与复盘工作台", 44, H - 114, 13, DARK)
    wrapped(c, "不是替用户预测涨跌，而是让每次判断有依据、有约束、能复盘。", 44, H - 142, 500, 12, 18, MUTED, 2)
    metrics = [("6", "研究工作区", BLUE), ("8", "闭环关键节点", GREEN), ("31", "自动化测试", GOLD), ("0", "公网动态后端", ROSE)]
    for index, (value, label, fill) in enumerate(metrics):
        x = 44 + index * 146
        box(c, x, H - 208, 132, 48, fill)
        text(c, value, x + 12, H - 186, 18, BROWN)
        text(c, label, x + 46, H - 185, 8.5, MUTED)
    box(c, 42, 45, W - 84, 320)
    draw_image_fit(c, OVERVIEW, 51, 54, W - 102, 302)
    c.showPage()


def page_problem(c):
    background(c, 2, "从更多观点，转向更可信的判断过程", "01  PROBLEM & PRODUCT JUDGMENT")
    text(c, "用户不缺行情和观点，缺的是一次判断的完整上下文", 42, H - 112, 14, DARK)
    problems = [
        ("信息分散", "行情、策略、持仓与复盘存在于不同工具，无法还原当时上下文。", BLUE),
        ("AI 黑箱", "结论听起来合理，但证据日期、来源、缺失项与反方意见不可见。", ROSE),
        ("结果偏差", "只看盈亏会混淆判断质量、执行质量和市场条件变化。", GOLD),
    ]
    for i, (title, desc, fill) in enumerate(problems):
        x = 42 + i * 258
        box(c, x, H - 270, 240, 125, fill)
        text(c, f"0{i + 1}", x + 14, H - 177, 11, CARAMEL)
        text(c, title, x + 14, H - 204, 15, BROWN)
        wrapped(c, desc, x + 14, H - 229, 210, 9.5, 15, MUTED, 4)
    box(c, 42, 58, W - 84, 218, SURFACE)
    text(c, "我的核心产品判断", 58, 244, 15, BROWN)
    text(c, "投资 AI 的专业感不在“敢给结论”，而在“能解释、能制衡、能验证”。", 58, 215, 16, DARK)
    decisions = [
        "不做荐股入口：先组织观察、策略、持仓、决策与复盘对象。",
        "不隐藏缺失：保留 null、来源、完整度、失败原因和 stale 状态。",
        "不让 AI 越权：多角色独立取证，用户确认后才形成正式决策。",
        "不只用盈亏评价：分别记录判断、执行、偏差与下一次调整。",
    ]
    for i, value in enumerate(decisions):
        bullet(c, value, 60 + (i % 2) * 370, 169 - (i // 2) * 58, 335)
    c.showPage()


def page_principles(c):
    background(c, 3, "把可信度设计成产品机制", "02  PRODUCT PRINCIPLES")
    principles = [
        ("01", "Evidence first", "任何结论先显示证据值、日期、来源、完整度与缺失项。", BLUE),
        ("02", "Human in the loop", "AI 只能提出研究意见；用户确认后才保存动作与复盘日期。", GREEN),
        ("03", "Fail visibly", "主源失败自动降级；全部失败时说明原因，不用 0 或静态数字冒充。", GOLD),
        ("04", "Review the process", "复盘分别评价判断、执行、偏差和环境变化，不只看最终盈亏。", ROSE),
    ]
    for i, (number, title, desc, fill) in enumerate(principles):
        x = 42 + (i % 2) * 382
        y = H - 225 - (i // 2) * 150
        box(c, x, y, 360, 126, fill)
        text(c, number, x + 16, y + 92, 11, CARAMEL)
        text(c, title, x + 58, y + 91, 15, BROWN)
        wrapped(c, desc, x + 16, y + 61, 326, 9.5, 16, MUTED, 4)
    box(c, 42, 55, W - 84, 95, CHARCOAL, border=CHARCOAL)
    text(c, "产品目标不是提高交易频率，而是提高判断可追溯性", 58, 119, 13, HexColor("#FFFFFF"))
    text(c, "North Star 方向：有效决策记录覆盖率、证据完整度、复盘完成率、用户修改率与重复错误下降。", 58, 91, 9, HexColor("#D7E0E2"))
    text(c, "明确不采用：自动下单、收益承诺、缺失值伪造、单一模型给出无证据结论。", 58, 70, 8.5, HexColor("#C5D0D3"))
    c.showPage()


def page_workflow(c):
    background(c, 4, "把一次投资想法变成可追溯闭环", "03  PRODUCT WORKFLOW")
    steps = [
        ("01", "市场/板块", "宽度、指数、轮动"),
        ("02", "观察池", "日期、来源、证据"),
        ("03", "策略 DSL", "规则确认与版本"),
        ("04", "筛选/回测", "漏斗与假设"),
        ("05", "真实持仓", "导入、冲突、流水"),
        ("06", "投委会", "角色意见与反证"),
        ("07", "用户决策", "动作与失效条件"),
        ("08", "到期复盘", "偏差与策略修订"),
    ]
    fills = [BLUE, GREEN, GOLD, ROSE]
    for i, (number, title, desc) in enumerate(steps):
        col, row = i % 4, i // 4
        x, y = 42 + col * 194, H - 225 - row * 120
        box(c, x, y, 178, 96, fills[col])
        text(c, number, x + 12, y + 68, 11, CARAMEL)
        text(c, title, x + 48, y + 68, 12, BROWN)
        wrapped(c, desc, x + 12, y + 40, 150, 8.5, 14, MUTED, 2)
    box(c, 42, 52, 500, 150)
    draw_image_fit(c, IMPORT, 49, 59, 486, 136)
    box(c, 561, 52, 234, 150, GOLD)
    text(c, "示例：持仓导入", 577, 171, 13, BROWN)
    bullet(c, "支持代码、中文名、全拼和首字母模糊搜索。", 577, 139, 200, 8.5)
    bullet(c, "导入前完成映射、校验、冲突预览和确认。", 577, 102, 200, 8.5)
    bullet(c, "持仓与交易流水在同一事务中提交。", 577, 65, 200, 8.5)
    c.showPage()


def page_market(c):
    background(c, 5, "首页不是行情堆叠，而是行动优先级", "04  MARKET WORKBENCH")
    box(c, 42, 130, 515, 375)
    draw_image_fit(c, OVERVIEW, 50, 138, 499, 359)
    box(c, 575, 317, 220, 188, BLUE)
    text(c, "信息结构", 591, 476, 13, BROWN)
    bullets = [
        "第一层：市场环境、宽度、成交额与组合盈亏",
        "第二层：结合时间、行情和持仓压力形成今日结论",
        "第三层：指数结构、板块轮动与可执行任务",
        "所有指标保留数据日期、来源和刷新状态",
    ]
    for i, value in enumerate(bullets):
        bullet(c, value, 591, 442 - i * 37, 185, 8.2)
    box(c, 575, 130, 220, 170, GOLD)
    text(c, "关键取舍", 591, 270, 13, BROWN)
    bullet(c, "波动率是风险指标，不套用涨跌颜色。", 591, 235, 185, 8.2)
    bullet(c, "数据不足时显示原因，不输出“强烈建议”。", 591, 198, 185, 8.2)
    bullet(c, "猫状态服务于情绪反馈，不遮挡数据。", 591, 161, 185, 8.2)
    box(c, 42, 54, W - 84, 58, SURFACE)
    text(c, "面试可讲", 58, 88, 10, CARAMEL)
    text(c, "我没有把首页做成指标大屏，而是用“环境 -> 组合压力 -> 今日任务”降低每天重新理解系统的成本。", 127, 87, 9, DARK)
    c.showPage()


def page_strategy(c):
    background(c, 6, "自然语言只能是起点，规则确认才是策略", "05  STRATEGY DSL & BACKTEST")
    stages = [
        ("输入想法", "保留用户原始意图与适用范围", BLUE),
        ("生成 DSL", "股票池、因子、运算符、阈值与缺失策略", GREEN),
        ("数据检查", "逐个确认因子可用性、日期与来源", GOLD),
        ("筛选漏斗", "解释每条规则排除了多少标的", ROSE),
        ("真实回测", "A 股费用、整手、T+1、滑点与复权假设", SURFACE),
    ]
    for i, (title, desc, fill) in enumerate(stages):
        x = 42 + i * 151
        box(c, x, H - 190, 137, 92, fill)
        text(c, f"0{i + 1}", x + 11, H - 130, 8, CARAMEL)
        text(c, title, x + 11, H - 151, 11, BROWN)
        wrapped(c, desc, x + 11, H - 171, 116, 7.7, 12, MUTED, 2)
    box(c, 42, 60, 400, 305, CHARCOAL, border=CHARCOAL)
    text(c, "策略 DSL（示意）", 58, 335, 12, HexColor("#FFFFFF"))
    code_lines = [
        '{',
        '  "universe": ["消费", "制造"],',
        '  "rules": [',
        '    {"factor": "pe_ttm", "op": "between",',
        '     "value": [8, 35]},',
        '    {"factor": "roe", "op": ">=", "value": 12},',
        '    {"factor": "return_20d", "op": ">=",',
        '     "value": -5}',
        '  ],',
        '  "missing_policy": "exclude_and_explain"',
        '}',
    ]
    for i, line in enumerate(code_lines):
        text(c, line, 58, 307 - i * 20, 8.2, HexColor("#E4ECEE"))
    box(c, 462, 60, 333, 305, SURFACE)
    text(c, "回测不是一张收益图", 478, 335, 13, BROWN)
    checks = [
        "明确价格复权口径与交易日范围",
        "计算佣金、最低佣金、印花税、过户费和滑点",
        "按 100 股整手与 T+1 可卖约束执行",
        "输出权益、回撤、成交记录和未成交限制",
        "保留退市、ST、涨跌停和公司行动的数据边界",
        "策略版本与回测配置共同持久化",
    ]
    for i, value in enumerate(checks):
        bullet(c, value, 478, 300 - i * 39, 290, 8.5)
    c.showPage()


def page_portfolio(c):
    background(c, 7, "导入持仓是一次数据确认，不是简单粘贴", "06  PORTFOLIO & POSITION WORKFLOW")
    box(c, 42, 112, 500, 393)
    draw_image_fit(c, IMPORT, 50, 120, 484, 377)
    box(c, 560, 308, 235, 197, GREEN)
    text(c, "模糊搜索", 576, 474, 13, BROWN)
    bullet(c, "预载 A 股代码、名称、市场与拼音信息", 576, 440, 202, 8.3)
    bullet(c, "支持代码片段、中文名、全拼和首字母", 576, 403, 202, 8.3)
    bullet(c, "选择后回填标准代码、名称和市场", 576, 366, 202, 8.3)
    bullet(c, "匹配失败时保留核验提示，不静默写入", 576, 329, 202, 8.3)
    box(c, 560, 112, 235, 180, ROSE)
    text(c, "事务与审计", 576, 261, 13, BROWN)
    bullet(c, "解析 -> 映射 -> 校验 -> 预览 -> 确认", 576, 227, 202, 8.3)
    bullet(c, "重复持仓支持合并、覆盖、跳过或新组合", 576, 190, 202, 8.3)
    bullet(c, "持仓与交易流水在同一事务中提交", 576, 153, 202, 8.3)
    box(c, 42, 52, W - 84, 44, SURFACE)
    text(c, "组合分析继续计算：复权价格、今日/累计收益、回撤、波动率、仓位、行业集中度、单股暴露与收益曲线。", 58, 68, 8.7, DARK)
    c.showPage()


def page_data(c):
    background(c, 8, "数据失败也必须给出可解释结果", "07  DATA TRUST & ARCHITECTURE")
    layers = [
        ("体验层", "市场 / 策略 / 组合 / AI 研究员 / 复盘", BLUE),
        ("工作流对象", "WatchItem / Strategy / Position / Transaction / Decision / Review / AgentTask", GREEN),
        ("统一数据层", "超时重试 / 主备切换 / 字段标准化 / 缓存 / 增量更新 / 数据血缘", GOLD),
        ("数据源", "AKShare / AKTools / efinance / Mootdx / BaoStock / Tencent / Tushare 可选", ROSE),
        ("持久化", "SQLite / Evidence Snapshot / 原子 JSON 缓存", SURFACE),
    ]
    for i, (label, content, fill) in enumerate(layers):
        y = H - 142 - i * 64
        box(c, 42, y, W - 84, 47, fill)
        text(c, label, 57, y + 27, 10, BROWN)
        text(c, content, 145, y + 27, 8.8, DARK)
    box(c, 42, 55, W - 84, 105, CHARCOAL, border=CHARCOAL)
    text(c, "统一响应契约", 58, 128, 12, HexColor("#FFFFFF"))
    tags = ["data_date", "source", "updated_at", "completeness", "cache_status", "missing_fields", "error", "provenance"]
    x = 58
    for tag in tags:
        tag_w = pdfmetrics.stringWidth(tag, "RagdollCN", 7.5) + 18
        c.setFillColor(HexColor("#3B474D"))
        c.roundRect(x, 83, tag_w, 24, 5, fill=1, stroke=0)
        text(c, tag, x + 9, 91, 7.5, HexColor("#EAF0F2"))
        x += tag_w + 7
    text(c, "原则：缺失值不使用 0 冒充；缓存降级必须标记 stale；页面不直接调用第三方接口。", 58, 65, 8.5, HexColor("#CAD4D7"))
    c.showPage()


def page_ai(c):
    background(c, 9, "多角色不是热闹，而是责任分离", "08  AI GOVERNANCE")
    roles = [("基本面", "盈利与现金流"), ("估值", "区间与隐含预期"), ("行业", "景气与竞争"), ("趋势", "价格与资金"), ("风险", "暴露与失效条件"), ("反方", "主动寻找反证")]
    for i, (role, focus) in enumerate(roles):
        x = 42 + (i % 3) * 175
        y = H - 170 - (i // 3) * 80
        box(c, x, y, 158, 60, [BLUE, GREEN, GOLD][i % 3])
        text(c, role, x + 13, y + 36, 11, BROWN)
        text(c, focus, x + 13, y + 17, 8, MUTED)
    box(c, 570, H - 250, 225, 140, ROSE)
    text(c, "主席汇总保留", 586, H - 142, 12, BROWN)
    bullet(c, "各角色证据值、日期与来源", 586, H - 174, 190, 8.5)
    bullet(c, "分歧、反证和无法判断项", 586, H - 207, 190, 8.5)
    bullet(c, "用户修改与人工确认记录", 586, H - 240, 190, 8.5)
    box(c, 42, 61, W - 84, 205, SURFACE)
    text(c, "从结论到复盘的审计链", 58, 234, 13, BROWN)
    chain = [
        ("证据快照", "保留当时数据，而不是事后覆盖"),
        ("用户决策", "动作、理由、风险、失效条件"),
        ("执行记录", "交易流水与用户修改"),
        ("到期复盘", "判断、执行、偏差、调整"),
    ]
    for i, (title, desc) in enumerate(chain):
        x = 58 + i * 180
        box(c, x, 112, 160, 85, [BLUE, GREEN, GOLD, ROSE][i])
        text(c, f"0{i + 1}", x + 12, 172, 9, CARAMEL)
        text(c, title, x + 12, 150, 11, BROWN)
        wrapped(c, desc, x + 12, 130, 135, 8, 13, MUTED, 2)
    text(c, "人工门禁：AI 不连接券商、不自动下单；用户确认后才保存正式决策。", 58, 82, 9.5, DARK)
    c.showPage()


def page_review(c):
    background(c, 10, "复盘要还原当时，而不是用结果改写记忆", "09  DECISION EVIDENCE & REVIEW")
    items = [
        ("Decision", "动作、理由、风险、失效条件、计划复盘日", BLUE),
        ("Evidence Snapshot", "证据值、日期、来源、完整度、缺失项", GREEN),
        ("Execution", "用户修改、交易流水、执行时间与偏离", GOLD),
        ("Review", "判断正确性、执行正确性、偏差类型、下一次调整", ROSE),
    ]
    for i, (title, desc, fill) in enumerate(items):
        x = 42 + i * 194
        box(c, x, H - 215, 178, 110, fill)
        text(c, f"0{i + 1}", x + 12, H - 142, 9, CARAMEL)
        text(c, title, x + 12, H - 165, 11, BROWN)
        wrapped(c, desc, x + 12, H - 187, 152, 8, 13, MUTED, 3)
    box(c, 42, 80, 360, 245, SURFACE)
    text(c, "复盘问题", 58, 293, 13, BROWN)
    questions = [
        "当时的证据是否足以支持这个判断？",
        "用户执行是否符合原计划与风险限制？",
        "偏差来自信息缺失、认知偏差还是市场变化？",
        "下一版策略应该增加、删除或收紧什么规则？",
    ]
    for i, value in enumerate(questions):
        bullet(c, value, 58, 255 - i * 44, 320, 8.8)
    box(c, 422, 80, 373, 245, GOLD)
    text(c, "为什么不只看收益", 438, 293, 13, BROWN)
    wrapped(c, "一次赚钱的决策可能来自错误逻辑，一次亏损也可能是在已知风险下正确执行。系统把判断质量与执行质量分开记录，再结合证据覆盖和环境变化归因。", 438, 260, 337, 9.5, 17, DARK, 7)
    text(c, "复盘输出", 438, 158, 11, CARAMEL)
    wrapped(c, "保留原判断 -> 标注实际结果 -> 归因偏差 -> 形成下一次调整 -> 创建策略修订版本。", 438, 132, 337, 9, 16, MUTED, 4)
    c.showPage()


def page_engineering(c):
    background(c, 11, "作品不是概念稿：实现、测试与安全边界可核验", "10  ENGINEERING DELIVERY")
    metrics = [("31", "tests passed", BLUE), ("4", "optional skips", GREEN), ("6+", "data adapters", GOLD), ("127.0.0.1", "default bind", ROSE)]
    for i, (value, label, fill) in enumerate(metrics):
        x = 42 + i * 194
        box(c, x, H - 180, 178, 78, fill)
        text(c, value, x + 14, H - 141, 17, BROWN)
        text(c, label, x + 14, H - 164, 8, MUTED)
    columns = [
        ("测试覆盖", ["主源失败与备源回退", "策略 DSL 校验", "持仓导入与冲突", "交易流水与复盘", "敏感文件与 CORS"]),
        ("静态交付", ["GitHub Pages 无后端", "脱敏样例持续标注", "HTML 可离线打开", "PDF 使用真实截图", "Actions 自动发布"]),
        ("动态边界", ["默认只监听本机", "密钥不进入前端", "不使用临时公网隧道", "生产需身份认证", "生产需受管数据库"]),
    ]
    for i, (title, values) in enumerate(columns):
        x = 42 + i * 258
        box(c, x, 88, 240, 278, SURFACE)
        text(c, title, x + 15, 335, 13, BROWN)
        for j, value in enumerate(values):
            bullet(c, value, x + 15, 300 - j * 43, 210, 8.5)
    text(c, "GitHub Actions：Python 3.11 安装核心依赖并执行 pytest；页面与 PDF 通过独立静态发布流程交付。", 42, 58, 8.5, MUTED)
    c.showPage()


def page_delivery(c):
    background(c, 12, "如何在面试中有效展示这个项目", "11  INTERVIEW DEMO & DISCUSSION")
    box(c, 42, 250, 365, 250)
    draw_image_fit(c, OVERVIEW, 49, 257, 351, 236)
    box(c, 425, 250, 370, 250, SURFACE)
    text(c, "可验证交付", 442, 469, 14, BROWN)
    proofs = [
        "GitHub Pages：脱敏静态 HTML，六工作区可交互",
        "本地真实系统：Flask + SQLite + DataProvider",
        "真实截图：市场总览与持仓模糊搜索",
        "工程验证：31 passed，4 skipped，GitHub Actions",
        "安全边界：默认仅监听 127.0.0.1，不使用公网隧道",
    ]
    for i, value in enumerate(proofs):
        bullet(c, value, 442, 432 - i * 40, 328, 8.7)
    text(c, "建议面试演示路线（3 分钟）", 42, 217, 13, BROWN)
    demo = [
        ("0:00", "工作台", "讲用户问题与今日结论"),
        ("0:40", "策略", "自然语言 -> DSL -> 缺失项"),
        ("1:20", "组合", "名称/代码/拼音模糊搜索"),
        ("2:00", "AI", "角色分歧、证据与人工门禁"),
        ("2:35", "复盘", "还原证据并修订策略"),
    ]
    for i, (tm, title, desc) in enumerate(demo):
        x = 42 + i * 151
        box(c, x, 102, 137, 88, [BLUE, GREEN, GOLD, ROSE, SURFACE][i])
        text(c, tm, x + 11, 166, 8, CARAMEL)
        text(c, title, x + 11, 145, 11, BROWN)
        wrapped(c, desc, x + 11, 125, 115, 7.5, 12, MUTED, 2)
    text(c, "静态演示：han21357.github.io/ragdoll-break-even-quant-workbench/demo.html", 42, 70, 8.5, DARK)
    text(c, "说明：静态页面使用脱敏样例数据；动态后端仅在本地或经批准且具备身份认证的环境运行。", 42, 51, 8, MUTED)
    c.showPage()


def main():
    setup_fonts()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=landscape(A4), pageCompression=1)
    c.setTitle("老布偶猫量化工作台 - AI 产品案例")
    c.setAuthor("Han21357")
    c.setSubject("AI 产品经理面试作品集案例")
    page_cover(c)
    page_problem(c)
    page_principles(c)
    page_workflow(c)
    page_market(c)
    page_strategy(c)
    page_portfolio(c)
    page_data(c)
    page_ai(c)
    page_review(c)
    page_engineering(c)
    page_delivery(c)
    c.save()
    print(OUT)


if __name__ == "__main__":
    main()
