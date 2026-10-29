# -*- coding: utf-8 -*-
"""从 report/sections/s06_bom.md 解析 BOM 表，生成 report/BOM_预算表.xlsx。"""
import re
import os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = os.path.join(ROOT, "report", "sections", "s06_bom.md")
OUT = os.path.join(ROOT, "report", "BOM_预算表.xlsx")

rows = []
category = ""
with open(MD, encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        m = re.match(r"### 6\.3\.\d\s+(.+)", line)
        if m:
            category = m.group(1).strip()
            continue
        if not re.match(r"^\|\s*(A\d{2}|B\d{2})\s*\|", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 10:
            continue
        code, name, spec, func, qty, price, subtotal, must, alt, note = cells[:10]
        qty_n = int(re.search(r"\d+", qty).group())
        price_n = float(re.search(r"\d+(?:\.\d+)?", price).group())
        rows.append(dict(code=code, cat=category, name=name, spec=spec, func=func,
                         qty=qty_n, price=price_n, subtotal=round(qty_n * price_n),
                         must=must, alt=alt, note=note))

wb = Workbook()

# ---------------- Sheet 1 预算汇总
ws = wb.active
ws.title = "预算汇总"
ws.sheet_view.showGridLines = False
ws.column_dimensions["A"].width = 4
ws.column_dimensions["B"].width = 30
ws.column_dimensions["C"].width = 14
ws.column_dimensions["D"].width = 52

title_font = Font(name="微软雅黑", size=16, bold=True, color="1F3864")
h_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
h_fill = PatternFill("solid", fgColor="2F5D8A")
note_font = Font(name="微软雅黑", size=9, color="7F7F7F")
base_font = Font(name="微软雅黑", size=10)
bold_font = Font(name="微软雅黑", size=10, bold=True)
money_fmt = '"¥"#,##0'
thin = Side(style="thin", color="BFBFBF")
border = Border(left=thin, right=thin, top=thin, bottom=thin)

ws.merge_cells("B2:D2")
ws["B2"] = "无标记扑克牌自动分拣机 — BOM 与预算表"
ws["B2"].font = title_font
ws["B3"] = "价格口径：2026-10-19 中国市场检索，区间中值/估算；采购前必须复核"
ws["B3"].font = note_font

headers = ["序号", "项目", "金额（元）", "说明"]
for c, h in enumerate(headers, start=1):
    cell = ws.cell(row=5, column=c, value=h)
    cell.font = h_font
    cell.fill = h_fill
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = border

summary = [
    ("1", "必需项合计（A01–A42）", "=SUMIF(BOM!$I$3:$I$80,\"是\",BOM!$H$3:$H$80)", "不做会卡住验收"),
    ("2", "建议项合计（不计可选）", "=SUMIF(BOM!$I$3:$I$80,\"建议\",BOM!$H$3:$H$80)", "PETG 标为可选，不计入"),
    ("3", "工程小计", "=C6+C7", "必需 + 建议"),
    ("4", "返工/耗材余量（12%）", "=ROUND(C8*0.12,0)", "3D 打印失败、螺丝线材损耗、补购运费"),
    ("5", "应急备件", 20, "备用 MG90S 2 + 线材/端子；相机故障时改单相机降级模式"),
    ("6", "合计", "=C8+C9+C10", "含余量与备件"),
    ("7", "预算上限", 1000, "课程项目预算"),
    ("8", "预算余额", "=C12-C11", "建议不低于 50 元"),
]
for i, (no, item, val, desc) in enumerate(summary, start=6):
    ws.cell(row=i, column=1, value=no).font = base_font
    ws.cell(row=i, column=2, value=item).font = base_font
    vc = ws.cell(row=i, column=3, value=val)
    vc.font = bold_font if item in ("工程小计", "合计", "预算余额") else base_font
    vc.number_format = money_fmt
    ws.cell(row=i, column=4, value=desc).font = note_font
    for c in range(1, 5):
        ws.cell(row=i, column=c).border = border
        ws.cell(row=i, column=c).alignment = Alignment(vertical="center",
                                                       horizontal="center" if c in (1, 3) else "left")

ws["B17"] = "风险提示"
ws["B17"].font = Font(name="微软雅黑", size=11, bold=True, color="A33A2E")
tips = [
    "约 55% 条目为区间估算（淘宝/京东反爬），下单前用“到手价”复核；",
    "相机必须支持 MJPG，否则 1080p 双路带宽不足；",
    "舵机独立 5V/3A 供电，电机与逻辑单点共地；",
    "3D 打印件先打小样，热熔铜螺母孔留 0.1–0.2 mm 余量；",
    "若学校提供耗材/切割/工具，可再省 120–150 元。",
]
for i, t in enumerate(tips, start=18):
    ws.cell(row=i, column=2, value=f"• {t}").font = note_font
    ws.merge_cells(start_row=i, start_column=2, end_row=i, end_column=4)

# ---------------- Sheet 2 BOM
ws2 = wb.create_sheet("BOM")
ws2.sheet_view.showGridLines = False
heads = ["编号", "类别", "部件", "建议规格", "功能 / 用途", "数量", "单价（元）",
         "小计（元）", "必需/建议", "可替代型号", "采购注意", "价格依据"]
widths = [8, 18, 20, 30, 24, 7, 10, 10, 10, 26, 40, 20]
for i, w in enumerate(widths, start=1):
    ws2.column_dimensions[get_column_letter(i)].width = w

ws2.merge_cells("A1:L1")
ws2["A1"] = "BOM 明细（自动求和；单价为 2026-10-19 估算中值，采购前复核）"
ws2["A1"].font = title_font
ws2["A1"].alignment = Alignment(vertical="center")

for c, h in enumerate(heads, start=1):
    cell = ws2.cell(row=2, column=c, value=h)
    cell.font = h_font
    cell.fill = h_fill
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = border
ws2.row_dimensions[2].height = 30

must_fill = PatternFill("solid", fgColor="E2F0E4")
opt_fill = PatternFill("solid", fgColor="FBEBD9")
for r, item in enumerate(rows, start=3):
    ws2.cell(row=r, column=1, value=item["code"])
    ws2.cell(row=r, column=2, value=item["cat"])
    ws2.cell(row=r, column=3, value=item["name"])
    ws2.cell(row=r, column=4, value=item["spec"])
    ws2.cell(row=r, column=5, value=item["func"])
    ws2.cell(row=r, column=6, value=item["qty"])
    ws2.cell(row=r, column=7, value=item["price"])
    ws2.cell(row=r, column=8, value=f"=F{r}*G{r}")
    ws2.cell(row=r, column=9, value=item["must"])
    ws2.cell(row=r, column=10, value=item["alt"])
    ws2.cell(row=r, column=11, value=item["note"])
    ws2.cell(row=r, column=12, value="2026-10 估算/区间中值")
    for c in range(1, 13):
        cell = ws2.cell(row=r, column=c)
        cell.font = base_font
        cell.border = border
        cell.alignment = Alignment(vertical="top", wrap_text=True,
                                   horizontal="center" if c in (1, 6, 7, 8, 9) else "left")
    ws2.cell(row=r, column=7).number_format = money_fmt
    ws2.cell(row=r, column=8).number_format = money_fmt
    ws2.cell(row=r, column=9).fill = must_fill if item["must"] == "是" else opt_fill

last = 2 + len(rows)
ws2.cell(row=last + 1, column=5, value="合计（自动求和）").font = bold_font
ws2.cell(row=last + 1, column=5).alignment = Alignment(horizontal="right")
tot = ws2.cell(row=last + 1, column=8, value=f"=SUM(H3:H{last})")
tot.font = bold_font
tot.number_format = money_fmt
tot.border = border
for c in (6, 7):
    ws2.cell(row=last + 1, column=c).border = border

ws2.freeze_panes = "A3"
ws2.auto_filter.ref = f"A2:L{last}"

# ---------------- Sheet 3 采购渠道
ws3 = wb.create_sheet("采购渠道")
ws3.sheet_view.showGridLines = False
ws3.column_dimensions["A"].width = 20
ws3.column_dimensions["B"].width = 60
ws3.column_dimensions["C"].width = 40
chans = [
    ("渠道", "建议采购内容", "注意事项"),
    ("淘宝 / 天猫", "相机、HUB、电机、驱动、舵机、传感器、机械件、耗材", "虚标/翻新集中地；选企业店，看差评，留发票"),
    ("京东自营", "电源、急停、工具、螺丝（急件）", "贵 10–30%，可退换，安全件优先"),
    ("立创商城", "驱动芯片、光耦、电平转换、接插件", "价格需登录/商品编号核对；注意现货"),
    ("微雪 / DFRobot", "ESP32-S3 开发板、相机模组", "原厂正品但溢价；国内天猫店另计价"),
    ("学校 / 实验室", "3D 打印、激光切割、亚克力、螺丝、工具", "提前预约；打印排队 1–3 天"),
    ("1688 / 拼多多", "螺丝、扎带、热缩管等低值耗材", "质量参差；不建议买电机/电源/相机"),
]
for r, row in enumerate(chans, start=2):
    for c, v in enumerate(row, start=1):
        cell = ws3.cell(row=r, column=c, value=v)
        cell.font = h_font if r == 2 else base_font
        cell.fill = h_fill if r == 2 else PatternFill()
        cell.border = border
        cell.alignment = Alignment(vertical="top", wrap_text=True)

# ---------------- Sheet 4 说明
ws4 = wb.create_sheet("价格说明")
ws4.sheet_view.showGridLines = False
ws4.column_dimensions["A"].width = 100
notes = [
    "价格说明与使用限制",
    "",
    "1. 所有价格均为 2026-10-19（Asia/Shanghai）检索的估算/区间中值，单位为人民币元。",
    "2. 淘宝/京东商品页普遍反爬（JS 渲染/需登录），本表无法逐项取得实时到手价；正式采购前必须由采购人复核。",
    "3. 官方规格类信息（ESP32-S3 GPIO/PSRAM、OV2640 分辨率、OpenCV 属性、树莓派价格）来自官方文档/官方新闻，链接见报告附录。",
    "4. 本表不构成报价承诺；实际支出以采购发票为准。",
    "5. 必需项合计约 836 元 + 12% 余量 100 元 + 备件 20 元 = 约 956 元；预算 1000 元，余量约 44 元。",
    "6. PETG（45 元）标为可选，不计入；快递费、激光切割加工费、工具通常另计或由实验室提供。",
    "",
    "相关来源：",
    "• Raspberry Pi 官方新闻（2026-10-01 涨价）: https://www.raspberrypi.com/news/price-increases-for-2gb-raspberry-pi-4-and-raspberry-pi-5/",
    "• espressif/esp32-camera（OV2640 规格/PSRAM）: https://github.com/espressif/esp32-camera",
    "• OpenCV VideoCapture 文档: https://docs.opencv.org/4.x/d8/dfe/classcv_1_1VideoCapture.html",
    "• pySerial 文档: https://pyserial.readthedocs.io/en/latest/shortintro.html",
]
for r, t in enumerate(notes, start=1):
    cell = ws4.cell(row=r, column=1, value=t)
    cell.font = title_font if r == 1 else base_font
    cell.alignment = Alignment(vertical="top", wrap_text=True)

wb.calculation.fullCalcOnLoad = True
wb.save(OUT)
req = sum(r["subtotal"] for r in rows if r["must"] == "是")
opt = sum(r["subtotal"] for r in rows if r["must"] == "建议")
sub = req + opt
cont = round(sub * 0.12)
total = sub + cont + 20
print("saved", OUT, "rows:", len(rows))
print(f"required={req} optional={opt} subtotal={sub} contingency={cont} spares=20 total={total} balance={1000-total}")
