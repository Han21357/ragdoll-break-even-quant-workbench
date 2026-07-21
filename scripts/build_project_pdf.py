#!/usr/bin/env python3
"""Build the public project introduction PDF."""
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

CREAM = HexColor("#FFF8F1")
SURFACE = HexColor("#FFFCF8")
BROWN = HexColor("#8B623F")
DARK = HexColor("#3B2F2A")
MUTED = HexColor("#746A63")
BORDER = HexColor("#DED6CE")
BLUE = HexColor("#E8F0F7")
GREEN = HexColor("#E8F3EC")
GOLD = HexColor("#FFF1D8")
ROSE = HexColor("#FCE9E6")


def setup_fonts():
    pdfmetrics.registerFont(TTFont("RagdollCN", "/System/Library/Fonts/STHeiti Medium.ttc", subfontIndex=0))


def text(c, value, x, y, size=12, color=DARK, font="RagdollCN"):
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawString(x, y, value)


def wrapped(c, value, x, y, width, size=11, leading=18, color=MUTED, max_lines=5):
    chars = max(8, int(width / size))
    lines = []
    remaining = value
    while remaining and len(lines) < max_lines:
        line = remaining[:chars]
        remaining = remaining[chars:]
        lines.append(line)
    for index, line in enumerate(lines):
        text(c, line, x, y - index * leading, size, color)


def background(c, page, title=None):
    c.setFillColor(CREAM)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    if title:
        text(c, title, 42, H - 52, 20, DARK)
        c.setStrokeColor(BORDER)
        c.line(42, H - 66, W - 42, H - 66)
    text(c, f"老布偶猫量化工作台  |  {page}/4", 42, 20, 8, MUTED)
    text(c, "github.com/Han21357/ragdoll-break-even-quant-workbench", W - 305, 20, 8, MUTED)


def box(c, x, y, width, height, fill=SURFACE, radius=7):
    c.setFillColor(fill)
    c.setStrokeColor(BORDER)
    c.roundRect(x, y, width, height, radius, fill=1, stroke=1)


def draw_image_fit(c, path, x, y, width, height):
    with PILImage.open(path) as image:
        ratio = min(width / image.width, height / image.height)
        draw_w, draw_h = image.width * ratio, image.height * ratio
    c.drawImage(str(path), x + (width - draw_w) / 2, y + (height - draw_h) / 2, draw_w, draw_h, preserveAspectRatio=True, mask="auto")


def page_cover(c):
    background(c, 1)
    text(c, "老布偶猫量化工作台", 42, H - 64, 30, DARK)
    text(c, "Old Ragdoll Cat Quant Workbench", 44, H - 92, 13, BROWN)
    text(c, "真实数据驱动、有温度、可追溯的个人投资研究与复盘工作台", 44, H - 122, 14, MUTED)
    metrics = [("7", "研究角色", BLUE), ("6+", "行情与研究数据源", GREEN), ("31", "自动化测试", GOLD), ("0", "伪造缺失值", ROSE)]
    for index, (value, label, fill) in enumerate(metrics):
        x = 44 + index * 148
        box(c, x, H - 194, 132, 54, fill)
        text(c, value, x + 12, H - 168, 19, DARK)
        text(c, label, x + 48, H - 168, 9, MUTED)
    box(c, 42, 46, W - 84, 325)
    draw_image_fit(c, OVERVIEW, 52, 56, W - 104, 305)
    c.showPage()


def page_product(c):
    background(c, 2, "01  产品闭环")
    text(c, "把一次投资判断，变成未来可以还原和复盘的记录", 42, H - 98, 16, BROWN)
    steps = [
        ("1", "市场与板块", "真实市场宽度、指数、成交额与轮动"),
        ("2", "观察池", "保存当时来源、日期和证据"),
        ("3", "策略 DSL", "自然语言转成可编辑、可校验规则"),
        ("4", "筛选与模拟", "漏斗解释、入选原因和策略版本"),
        ("5", "真实持仓", "模糊搜索、CSV/Excel、冲突处理"),
        ("6", "投资委员会", "多角色独立取证，主席保留分歧"),
        ("7", "用户决策", "确认后保存证据和失效条件"),
        ("8", "到期复盘", "判断、执行、偏差和下一版策略"),
    ]
    fills = [BLUE, GREEN, GOLD, ROSE]
    for index, (number, title, desc) in enumerate(steps):
        col, row = index % 4, index // 4
        x, y = 42 + col * 194, H - 238 - row * 145
        box(c, x, y, 178, 116, fills[col])
        text(c, number, x + 12, y + 82, 18, BROWN)
        text(c, title, x + 44, y + 84, 13, DARK)
        wrapped(c, desc, x + 12, y + 54, 154, 9, 15, MUTED, 3)
    box(c, 42, 58, W - 84, 70, SURFACE)
    text(c, "核心原则", 56, 100, 12, BROWN)
    wrapped(c, "AI 不自动交易。事实来自统一数据层；无法可靠获得的数据保留 null 和缺失原因。用户确认后才形成正式决策。", 130, 102, W - 200, 10, 17, DARK, 3)
    c.showPage()


def page_architecture(c):
    background(c, 3, "02  数据与系统架构")
    layers = [
        ("体验层", "市场总览  |  策略实验室  |  组合中心  |  AI 研究员  |  复盘", BLUE),
        ("工作流层", "WatchItem  |  Strategy  |  Position  |  Transaction  |  Decision  |  Review  |  AgentTask", GREEN),
        ("统一数据层", "重试  |  主备切换  |  字段标准化  |  本地缓存  |  增量更新  |  数据血缘", GOLD),
        ("数据源", "AKShare / AKTools  |  efinance  |  Mootdx  |  BaoStock  |  Tencent  |  Tushare 可选", ROSE),
        ("持久化", "SQLite + Evidence Snapshot + 原子 JSON 缓存", SURFACE),
    ]
    for index, (label, content, fill) in enumerate(layers):
        y = H - 132 - index * 79
        box(c, 42, y, W - 84, 58, fill)
        text(c, label, 58, y + 34, 12, BROWN)
        text(c, content, 155, y + 34, 10, DARK)
    text(c, "每个数据响应都说明", 42, 92, 13, DARK)
    tags = ["data_date", "source", "updated_at", "completeness", "cache_status", "missing_fields", "error", "provenance"]
    x = 42
    for tag in tags:
        width = 54 + len(tag) * 3.8
        box(c, x, 52, width, 25, SURFACE, 5)
        text(c, tag, x + 8, 60, 8, BROWN)
        x += width + 7
    c.showPage()


def page_delivery(c):
    background(c, 4, "03  可展示的真实能力")
    box(c, 42, 78, 500, H - 158)
    draw_image_fit(c, IMPORT, 52, 88, 480, H - 178)
    text(c, "持仓模糊搜索与导入", 565, H - 105, 16, BROWN)
    points = [
        "代码片段、中文名、拼音和首字母搜索",
        "自动回填股票代码、名称、市场与来源",
        "支持粘贴表格、CSV、XLSX 与模拟组合转入",
        "字段映射、逐行校验和冲突预览",
        "持仓与交易流水在同一事务中提交",
        "多角色投委会保留证据、缺失项和反方意见",
        "到期复盘可生成策略修订版本",
    ]
    y = H - 145
    for point in points:
        c.setFillColor(BROWN)
        c.circle(572, y + 3, 2.5, fill=1, stroke=0)
        wrapped(c, point, 584, y + 7, 210, 10, 17, DARK, 2)
        y -= 43
    box(c, 565, 74, 230, 72, GOLD)
    text(c, "工程验证", 580, 120, 11, BROWN)
    text(c, "31 passed, 4 skipped", 580, 96, 16, DARK)
    text(c, "不连接券商，不自动下单，不承诺收益", 580, 82, 8, MUTED)
    c.showPage()


def main():
    setup_fonts()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=landscape(A4), pageCompression=1)
    c.setTitle("老布偶猫量化工作台 - 项目介绍")
    c.setAuthor("Han21357")
    page_cover(c)
    page_product(c)
    page_architecture(c)
    page_delivery(c)
    c.save()
    print(OUT)


if __name__ == "__main__":
    main()
