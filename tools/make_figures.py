# -*- coding: utf-8 -*-
"""生成报告插图（系统架构、状态机、机械布局、乘积效应曲线）。"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle, Polygon
import numpy as np

matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun"]
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "report", "figures")
os.makedirs(OUT, exist_ok=True)

C_BLUE, C_LBLUE = "#2F5D8A", "#DCE8F5"
C_GREEN, C_LGREEN = "#3C7A4A", "#E2F0E4"
C_ORANGE, C_LORANGE = "#B5651D", "#FBEBD9"
C_GRAY, C_LGRAY = "#5A5A5A", "#EFEFEF"
C_RED, C_LRED = "#A33A2E", "#F7E3DF"


def box(ax, xy, w, h, text, fc, ec, fs=11, bold=False, lw=1.4):
    ax.add_patch(FancyBboxPatch((xy[0], xy[1]), w, h,
                                boxstyle="round,pad=0.006,rounding_size=0.02",
                                linewidth=lw, edgecolor=ec, facecolor=fc, zorder=3))
    ax.text(xy[0] + w / 2, xy[1] + h / 2, text, ha="center", va="center",
            fontsize=fs, color="#222222", zorder=4,
            fontweight="bold" if bold else "normal", linespacing=1.35)


def arrow(ax, p1, p2, color=C_GRAY, lw=1.6, ls="-", rad=0.0):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=13,
                                linewidth=lw, color=color, linestyle=ls,
                                connectionstyle=f"arc3,rad={rad}", zorder=2,
                                shrinkA=2, shrinkB=2))


# ---------------------------------------------------------------- 图 1 系统架构
def fig_architecture():
    fig, ax = plt.subplots(figsize=(16, 9.2))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9.2)
    ax.axis("off")

    for x0, x1, title, color in [(0.15, 4.45, "机械 / 传感层", C_BLUE),
                                 (4.75, 8.55, "ESP32 控制层", C_GREEN),
                                 (8.85, 15.85, "PC 视觉与决策层", C_ORANGE)]:
        ax.add_patch(Rectangle((x0, 1.35), x1 - x0, 7.35, fill=False,
                               ec="#B9C7D6", lw=1.2, ls="--"))
        ax.text((x0 + x1) / 2, 8.95, title, ha="center", fontsize=13,
                color=color, fontweight="bold")

    # 机械 / 传感
    box(ax, (0.35, 7.45), 3.9, 1.05, "牌仓 + 弹簧压板 + 摩擦取牌轮\n限高门 / 分离垫（防双张）", C_LGRAY, C_GRAY, 10.5)
    box(ax, (0.35, 5.95), 3.9, 1.05, "输送辊 + 玻璃扫描台\n（上/下相机拍摄位）", C_LGRAY, C_GRAY, 10.5)
    box(ax, (0.35, 4.45), 3.9, 1.05, "摆动滑槽 + 舵机\n→ 收纳盒 A/B/复核盒", C_LGRAY, C_GRAY, 10.5)
    box(ax, (0.35, 2.55), 3.9, 1.45, "传感器\nS1 有牌 / S2 入口\nS3 扫描位 / S4 出口", C_LGREEN, C_GREEN, 10)

    # ESP32
    box(ax, (4.95, 7.45), 3.4, 1.15, "运动控制\n步进电机（加减速/限位）\n舵机（分流/挡板）", C_LGREEN, C_GREEN, 10.5)
    box(ax, (4.95, 5.75), 3.4, 1.15, "传感器采样\n去抖 / 边沿 / 双张时长\n状态位图", C_LGREEN, C_GREEN, 10.5)
    box(ax, (4.95, 4.05), 3.4, 1.15, "通信与安全\n帧协议 + CRC + ACK\n心跳 / 看门狗 / 急停", C_LGREEN, C_GREEN, 10.5)
    box(ax, (4.95, 2.95), 3.4, 0.75, "ESP32-S3 DevKitC-1（固件）", C_GREEN, C_GREEN, 10.5, bold=True)

    # PC
    box(ax, (9.05, 7.45), 6.55, 1.05, "图像采集：双 USB 相机（上/下，1080p）\n锁定曝光 / 白平衡 / 对焦", C_LORANGE, C_ORANGE, 10.5)
    box(ax, (9.05, 5.95), 6.55, 1.05, "牌面检测 + 透视校正 + 正反面判别", C_LORANGE, C_ORANGE, 10.5)
    box(ax, (9.05, 4.45), 6.55, 1.05, "角标 ROI → 点数/花色分类 → 多帧投票 + 置信度", C_LORANGE, C_ORANGE, 10.5)
    box(ax, (9.05, 2.95), 6.55, 1.05, "52 维计数表 → A / B / 复核 → 整叠校验与异常报告", C_LORANGE, C_ORANGE, 10.5)
    box(ax, (9.05, 1.55), 6.55, 0.85, "日志 / 图像存档 / 回放 / 人工复核界面", C_LGRAY, C_GRAY, 10.5)

    # 电源
    box(ax, (0.35, 0.3), 15.3, 0.75,
        "12V/5A 电源 + 保险丝 + 急停（硬件切断电机电源） + 5V 降压（逻辑与舵机独立供电）",
        C_LRED, C_RED, 10.5, bold=True)

    # 区域间连线
    arrow(ax, (4.35, 8.0), (4.95, 8.0), C_GREEN, 1.8)
    ax.text(4.65, 8.15, "执行器", fontsize=8.5, color=C_GREEN, ha="center")
    arrow(ax, (4.95, 6.85), (4.35, 6.85), C_BLUE, 1.8)
    ax.text(4.65, 6.65, "传感器", fontsize=8.5, color=C_BLUE, ha="center")
    arrow(ax, (8.45, 7.8), (9.05, 7.8), C_RED, 1.8)
    ax.text(8.75, 8.0, "命令/ACK", fontsize=8.5, color=C_RED, ha="center")
    arrow(ax, (9.05, 7.1), (8.45, 7.1), C_RED, 1.8)
    ax.text(8.75, 6.9, "状态/事件", fontsize=8.5, color=C_RED, ha="center")
    ax.text(8.75, 7.55, "USB 串口", fontsize=8, color=C_RED, ha="center", rotation=90)

    # PC 内部
    for y0, y1 in [(7.45, 7.0), (5.95, 5.5), (4.45, 4.0)]:
        arrow(ax, (12.3, y0), (12.3, y1), C_ORANGE)
    ax.text(8.75, 1.25, "注：上/下相机直接接 PC，不经过 ESP32", fontsize=8.5,
            color="#555", ha="center")

    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_system_architecture.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- 图 2 状态机
def fig_state_machine():
    fig, ax = plt.subplots(figsize=(17.5, 8.6))
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 9.0)
    ax.axis("off")

    W, H, ytop = 1.8, 0.95, 5.6
    names = ["WAIT_CARD", "FEED", "DETECT", "CLASSIFY", "ASSIGN", "DIVERT", "VERIFY"]
    subs = ["检查 S1/S3", "发 FEED", "抓帧/检测", "双面/投票", "计数 A/B", "舵机/出口", "传感器确认"]
    xs = [0.25 + i * 2.05 for i in range(7)]
    for x, n, s in zip(xs, names, subs):
        box(ax, (x, ytop), W, H, f"{n}\n{s}", C_LBLUE, C_BLUE, 9.8)
    for i in range(6):
        arrow(ax, (xs[i] + W, ytop + H / 2), (xs[i + 1], ytop + H / 2), C_BLUE, 1.7)

    # 循环箭头（VERIFY -> WAIT_CARD），画在上方
    xw, xv = xs[0] + W / 2, xs[6] + W / 2
    ax.plot([xv, xv], [ytop + H, 8.3], color=C_BLUE, lw=1.5, zorder=2)
    ax.plot([xv, xw], [8.3, 8.3], color=C_BLUE, lw=1.5, zorder=2)
    arrow(ax, (xw, 8.3), (xw, ytop + H), C_BLUE, 1.5)
    ax.text(8.6, 8.55, "还有牌：回到 WAIT_CARD（循环 104 次）", fontsize=9.5,
            color=C_BLUE, ha="center")

    # 底行
    ybot = 2.35
    box(ax, (0.25, ybot), W, H, "PAUSE\n人工检查", C_LORANGE, C_ORANGE, 9.8)
    box(ax, (2.55, ybot), W, H, "REVIEW\n人工补录", C_LORANGE, C_ORANGE, 9.8)
    box(ax, (4.85, ybot), W, H, "ERROR\n停/蜂鸣", C_LRED, C_RED, 9.8)
    box(ax, (7.15, ybot), W, H, "ANOMALY\n缺/多/异常牌", C_LRED, C_RED, 9.8)
    box(ax, (12.9, ybot), W, H, "VERIFY_RUN\n104 张校验", C_LGREEN, C_GREEN, 9.8)
    box(ax, (15.2, ybot), W, H, "DONE\n报告/归档", C_LGRAY, C_GRAY, 9.8)

    arrow(ax, (0.25 + W / 2, ybot + H), (0.25 + W / 2, ytop), C_ORANGE, 1.0, ls=":")

    # 异常分支
    arrow(ax, (xs[2] + W / 2, ytop), (2.55 + W / 2, ybot + H), C_ORANGE, 1.2, ls="--")
    arrow(ax, (xs[3] + W / 2, ytop), (2.55 + W, ybot + H / 2), C_ORANGE, 1.2, ls="--")
    ax.text(3.85, 4.95, "低置信/冲突", fontsize=8.5, color=C_ORANGE, ha="center")
    ax.text(4.5, 1.75, "人工补录后回 ASSIGN", fontsize=8, color=C_ORANGE, ha="center")

    arrow(ax, (xs[1] + W / 2, ytop), (4.85 + W / 2, ybot + H), C_RED, 1.2, ls="--")
    arrow(ax, (xs[5] + W / 2, ytop), (4.85 + W, ybot + H / 2), C_RED, 1.2, ls="--")
    ax.text(9.75, 4.55, "超时/堵转/急停/通信中断", fontsize=8.5, color=C_RED, ha="center")

    arrow(ax, (xs[4] + W / 2, ytop), (7.15 + W / 2, ybot + H), C_RED, 1.2, ls="--")
    ax.text(9.65, 3.55, "同类第 3 张", fontsize=8.5, color=C_RED, ha="center")

    arrow(ax, (4.85 + W / 2, ybot), (xs[0] + W / 2, ytop), C_RED, 1.1, ls=":")
    ax.text(1.55, 3.95, "人工复位", fontsize=8.5, color=C_RED, ha="center")

    # VERIFY -> VERIFY_RUN -> DONE
    arrow(ax, (xs[6] + W / 2, ytop), (12.9 + W / 2, ybot + H), C_GREEN, 1.6)
    ax.text(15.0, 4.0, "104 张处理完", fontsize=8.5, color=C_GREEN, ha="center")
    arrow(ax, (12.9 + W, ybot + H / 2), (15.2, ybot + H / 2), C_GREEN, 1.6)

    ax.text(9.0, 0.7, "实线：正常流程；虚线：异常/复核；点线：人工恢复。所有等待步骤均带超时。",
            fontsize=10, color="#444444", ha="center")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_state_machine.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- 图 3 机械布局
def fig_mechanical():
    fig = plt.figure(figsize=(15, 10))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.15, 0.75], hspace=0.30)

    # ---------- 侧视
    ax = fig.add_subplot(gs[0])
    ax.set_xlim(0, 210)
    ax.set_ylim(-55, 100)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("侧视示意图（非比例，仅说明相对位置）", fontsize=13, pad=4)

    ax.add_patch(Rectangle((0, -38), 200, 7, fc="#D9D2C5", ec="#8A8172", lw=1.2))
    ax.text(4, -27, "机架/底板", fontsize=9, color="#555")

    # 牌仓
    ax.add_patch(Polygon([[5, 72], [50, 72], [50, 18], [5, 38]], closed=True,
                         fc="#EDE7DA", ec="#8A8172", lw=1.6))
    for i in range(5):
        y = 24 + i * 7
        ax.plot([10, 45], [y, y + 14], color="#7A9EBD", lw=1.0, alpha=0.75)
    ax.text(24, 58, "牌仓\n弹簧压板", fontsize=10, ha="center", color="#4A4235")

    # 取牌轮 / 限高门 / 分离垫
    ax.add_patch(Circle((56, 26), 5.2, fc="#3C3C3C", ec="#111", lw=1.2))
    ax.plot([62.5, 62.5], [8, 26], color="#8A2E22", lw=3)
    ax.add_patch(Rectangle((62.5, 4.5), 12, 3, fc="#8A2E22", ec="#5A1E15"))
    ax.text(45, 15, "取牌轮", fontsize=8.8, ha="center")
    ax.text(62.5, 36, "限高门 0.5–0.8 mm", fontsize=8.2, ha="left", color="#8A2E22")
    ax.text(68.5, 0.5, "分离垫", fontsize=8.2, ha="center", color="#8A2E22")

    # 玻璃台 + 牌
    ax.add_patch(Rectangle((75, 10), 60, 2.5, fc="#CFE6F2", ec="#5B8CA8", lw=1.5, alpha=0.95))
    ax.add_patch(Rectangle((89, 12.5), 28, 1.6, fc="#FFFFFF", ec="#333", lw=1.0))
    ax.text(103, 16.5, "牌（停机位）", fontsize=8.8, ha="center")
    ax.text(76, -5, "玻璃扫描台（透明）", fontsize=8.8, ha="left", color="#2F5D8A")

    # 输送辊
    for x in (80, 127):
        ax.add_patch(Circle((x, 20), 4.0, fc="#3C3C3C", ec="#111", lw=1.0))
        ax.text(x, 27, "输送辊", fontsize=8.2, ha="center")
    # 上相机
    ax.add_patch(Rectangle((94, 58), 18, 9, fc="#DCE8F5", ec="#2F5D8A", lw=1.5))
    ax.add_patch(Rectangle((98, 52), 10, 6, fc="#2F5D8A", ec="#2F5D8A"))
    ax.text(103, 71, "上相机", fontsize=9.2, ha="center", color="#1E3F60")
    ax.plot([103, 103], [52, 14], color="#2F5D8A", lw=1.0, ls="--")
    ax.text(106, 38, "视场", fontsize=8, color="#2F5D8A")
    # 下相机
    ax.add_patch(Rectangle((94, -30), 18, 9, fc="#DCE8F5", ec="#2F5D8A", lw=1.5))
    ax.add_patch(Rectangle((98, -21), 10, 6, fc="#2F5D8A", ec="#2F5D8A"))
    ax.text(103, -47, "下相机（透过玻璃）", fontsize=9.2, ha="center", color="#1E3F60")
    ax.plot([103, 103], [-15, 10], color="#2F5D8A", lw=1.0, ls="--")

    # 光源
    for x in (82, 120):
        ax.add_patch(Rectangle((x, 84), 14, 3, fc="#FFF2B3", ec="#C9A227", lw=1.0))
    ax.text(108, 89.5, "柔光 LED（左右各一）", fontsize=8.8, ha="center", color="#7A5B00")

    # 摆动滑槽 + 收纳
    ax.add_patch(Polygon([[136, 12], [152, 5], [152, 1], [136, 8]], closed=True,
                         fc="#E2F0E4", ec="#3C7A4A", lw=1.5))
    ax.text(151, 20, "摆动滑槽\n（舵机两位）", fontsize=8.6, ha="center", color="#2F5D3A")
    ax.add_patch(Rectangle((140, -33), 20, 25, fc="#F5F0E6", ec="#8A8172", lw=1.2))
    ax.text(150, -22, "收纳盒\nA / B", fontsize=9, ha="center")
    ax.add_patch(Rectangle((168, -33), 16, 25, fc="#F5F0E6", ec="#8A8172", lw=1.2))
    ax.text(176, -22, "复核盒", fontsize=9, ha="center")

    # 传感器（放在台面下方，避免与上方标签冲突）
    for x, name in [(54, "S1"), (74, "S2"), (124, "S3"), (136, "S4")]:
        ax.add_patch(Circle((x, 8), 2.0, fc="#D9A441", ec="#8A6A1E", lw=1.0))
        ax.text(x, 3.2, name, fontsize=8.5, ha="center", color="#6B4F13")
    ax.text(4, -52, "传感器：S1 有牌  S2 入口  S3 扫描位  S4 出口（位置为示意）",
            fontsize=8.8, ha="left", color="#444")

    # ---------- 俯视
    ax2 = fig.add_subplot(gs[1])
    ax2.set_xlim(0, 210)
    ax2.set_ylim(-30, 50)
    ax2.set_aspect("equal")
    ax2.axis("off")
    ax2.set_title("俯视示意图（非比例）", fontsize=13, pad=4)

    ax2.add_patch(Rectangle((74, 3), 60, 36, fc="#CFE6F2", ec="#5B8CA8", lw=1.5, alpha=0.7))
    ax2.add_patch(Rectangle((88, 10), 28, 22, fc="#FFFFFF", ec="#333", lw=1.2))
    ax2.text(102, 21, "牌 88.9 × 63.5", fontsize=8.4, ha="center")
    ax2.text(104, -2, "玻璃扫描台", fontsize=8.8, ha="center", color="#2F5D8A")
    ax2.plot([102, 102], [39, 43], color="#2F5D8A", lw=1.0, ls="--")
    ax2.text(104, 44.5, "上/下相机光轴", fontsize=8.2, ha="center", color="#2F5D8A")

    ax2.annotate("", xy=(72, 21), xytext=(38, 21),
                 arrowprops=dict(arrowstyle="-|>", color="#3C7A4A", lw=2.0))
    ax2.text(36, 26, "入口", fontsize=10, color="#3C7A4A")
    ax2.annotate("", xy=(160, 21), xytext=(138, 21),
                 arrowprops=dict(arrowstyle="-|>", color="#3C7A4A", lw=2.0))
    ax2.text(146, 26, "走纸方向", fontsize=9, color="#3C7A4A")

    ax2.annotate("", xy=(88, -8), xytext=(116, -8),
                 arrowprops=dict(arrowstyle="<->", color="#555", lw=1.0))
    ax2.text(102, -13, "88.9 mm（长边沿走纸方向）", fontsize=8.2, ha="center", color="#555")
    ax2.annotate("", xy=(81, 10), xytext=(81, 32),
                 arrowprops=dict(arrowstyle="<->", color="#555", lw=1.0))
    ax2.text(77.5, 21, "63.5 mm", fontsize=8.2, ha="center", rotation=90, color="#555")

    fig.savefig(os.path.join(OUT, "fig_mechanical_layout.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- 图 4 乘积效应
def fig_product_effect():
    fig, ax = plt.subplots(figsize=(10, 6))
    e = np.logspace(-4.2, -1.3, 400)
    p = (1 - e) ** 104 * 100
    ax.plot(e * 100, p, color=C_BLUE, lw=2.4)
    ax.set_xscale("log")
    ax.set_xlabel("单张静默错误率 e（%，对数轴）", fontsize=12)
    ax.set_ylabel("一次 104 张运行完全正确的概率（%）", fontsize=12)
    ax.set_title("乘积效应：单张准确率很高，整叠成功率仍可能很低", fontsize=13)
    ax.grid(True, which="both", ls=":", alpha=0.5)
    for x, lab in [(2.0, "98% 单张"), (1.0, "99% 单张"), (0.5, "99.5% 单张"),
                   (0.1, "99.9% 单张"), (0.01, "99.99% 单张")]:
        y = (1 - x / 100) ** 104 * 100
        ax.plot([x], [y], "o", color=C_ORANGE, ms=6, zorder=5)
        ax.annotate(f"{lab}\n整叠 {y:.0f}%", (x, y), textcoords="offset points",
                    xytext=(8, 12), fontsize=9.5, color=C_ORANGE)
    ax.set_ylim(0, 102)
    ax.axhline(80, color=C_GREEN, ls="--", lw=1.2)
    ax.text(0.012, 82, "80% 目标线", color=C_GREEN, fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_product_effect.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    fig_architecture()
    fig_state_machine()
    fig_mechanical()
    fig_product_effect()
    print("figures written to", OUT)
