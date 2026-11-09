# -*- coding: utf-8 -*-
"""
=============================================================================
脚本:        band alignment.py
分类:        绘图脚本（plot / band alignment）
功能:        【热平衡异质结统一费米能级对齐】全部体系统一减去异质结平衡费米能级，
             以公共 E_F = 0 为基准绘制带隙柱、带边与组分体相带阶
             注：VBO/CBO 只在组分材料之间计算，异质结为复合体系，不参与带阶
             注：图面只画组分体相（PLOT_INDICES 可调），异质结仅保留在源数据表中
使用方法:    python "band alignment.py" [-i 能级表.csv] [-o ./输出目录] [-f svg,pdf,tiff,png] [-d 600] [-s]
参数:        -i/--input      能级 CSV（列：system,vbm,cbm,ef，真空能级为 0），省略则用配置区 SYSTEMS
             -o/--outdir     输出目录，省略则用配置区 OUTPUT_PATH
             -f/--formats    导出格式，逗号分隔（svg / pdf / tiff / png）
             -d/--dpi        位图导出分辨率，默认 600
             -s/--show       导出后在浏览器打开 PNG 预览
             -h/--help       显示本说明并退出
模式参数:    本脚本无运行模式，能量基准固定为统一费米基准（变 FERMI_REF 即可平移）
输入文件:    无（默认使用配置区内置能级；-i 可指定 CSV）
输出文件:
  band_alignment_fermi.svg               矢量主文件（文本可编辑）
  band_alignment_fermi.pdf               矢量备份（Type 42 字体嵌入）
  band_alignment_fermi.tiff              位图（600 dpi，LZW 压缩）
  band_alignment_fermi.png               位图预览（300 dpi）
  band_alignment_fermi_source_data.csv   源数据表（对齐前后能级、带隙、组分带阶）
输出路径:    默认 ./plot_band_alignment_fermi/（相对脚本所在目录），-o 可覆盖
作者:        隼蝶.
最后修改日期: 2026-10-28
=============================================================================
"""
import argparse
import os
import re
import sys
import webbrowser
import numpy as np
import pandas as pd
import matplotlib as mpl
# ============================== 参数配置区 =====================================
INPUT_FILES    = []
OUTPUT_FILES   = ["band_alignment_fermi"]
RECORD_FILE    = "band_alignment_fermi_source_data.csv"
INPUT_PATH     = "./"
OUTPUT_PATH    = "./plot_band_alignment_fermi"
# 原始真空能级数据（不要改动！平移在代码内部自动完成）
SYSTEMS = [
    ("O-Al2O3",       -6.1482,  0.4761, -5.9507),
    ("MoS2",          -3.8399, -1.5672, -3.5865),
    ("O-Al2O3/MoS2",  -1.3378,  0.9349, -1.1010),
]
# ===== 全局统一费米基准：异质结的Ef（热平衡公共零点）=====
FERMI_REF = -1.1010

# ===== 带阶对：VBO/CBO 只定义在两个组分体相之间 =====
# 异质结是界面复合后的整体体系，不是第三个独立组分，不能拿它的带边再与单层求差
OFFSET_PAIRS = [(0, 1)]      # (起点体系, 终点体系)，默认仅 O-Al2O3 ↔ MoS2

COLORS         = ["#484878", "#42949E", "#7884B4"]   # 两体系对比色（深蓝紫 / 青），异质结色备用
PLOT_INDICES   = (0, 1)          # 图中绘制的体系下标：仅组分体相，异质结不进入图面

# ===== 视觉样式：基准值取自 MD_timeVSenergy.py，按图宽等比缩放以保持同样的视觉密度 =====
# 参考脚本：8×6 in 画布（宽 203.2 mm）/ 轴标签 28 pt / 刻度与图例 24 pt / 线宽 2.5 / 刻度长 8.0
FIG_WIDTH_MM   = 120.0           # 成图宽
FIG_HEIGHT_MM  = 92.0            # 成图高
MD_REF_WIDTH_MM  = 8 * 25.4                    # 参考脚本画布宽度（8 in）
STYLE_SCALE      = FIG_WIDTH_MM / MD_REF_WIDTH_MM   # ≈0.59，字号与线宽同比缩放
FONT_SIZE        = 28 * STYLE_SCALE   # 轴标签
TICK_FONT_SIZE   = 24 * STYLE_SCALE   # 刻度与类目标签
LEGEND_FONT_SIZE = 24 * STYLE_SCALE   # 图例
VALUE_FONT_SIZE  = 10.5              # 带边数值标注（比轴标签低一档）
OFFSET_FONT_SIZE = 9.5               # CBO / VBO 标注
SPINE_WIDTH      = 2.5 * STYLE_SCALE  # 边框线宽
TICK_WIDTH       = 2.5 * STYLE_SCALE  # 刻度线宽
TICK_LENGTH      = 8.0 * STYLE_SCALE  # 刻度长度
TICK_DIRECTION   = "in"               # 刻度方向：向内
TICK_PAD         = 8 * STYLE_SCALE    # 刻度标签与轴的距离
LABEL_PAD        = 10 * STYLE_SCALE   # 轴标签与轴的距离
EDGE_WIDTH     = 2.0             # 带边线宽
FERMI_WIDTH    = 1.2             # 费米线线宽
X_STEP         = 1.15            # 体系间距（字号放大后需留出标注空隙）
X_MARGIN       = 0.38            # 左右留白（数据单位）
Y_MAJOR        = 2.0             # Y 主轴刻度间隔（锚定 0，使费米线落在刻度上）
BAR_HALF_WIDTH = 0.24            # 带隙柱半宽（仅两柱，加宽后更饱满）
NEUTRAL_MID    = "#8A8A8A"       # 带阶引线
NEUTRAL_DARK   = "#3A3A3A"       # 图例与文字
FERMI_COLOR    = "#c83c3c"       # 红色统一费米线
DEFAULT_DPI    = 600
PREVIEW_DPI    = 300
# =============================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
mpl.rcParams.update({
    "font.family":       "sans-serif",
    "font.sans-serif":   ["Arial", "Helvetica", "DejaVu Sans"],
    "mathtext.fontset":  "custom",
    "mathtext.rm":       "Arial",
    "mathtext.it":       "Arial:italic",
    "mathtext.bf":       "Arial:bold",
    "font.size":         FONT_SIZE,
    "axes.unicode_minus": False,
    "axes.linewidth":    SPINE_WIDTH,
    "axes.spines.right": False,
    "axes.spines.top":   False,
    "xtick.direction":   TICK_DIRECTION,
    "ytick.direction":   TICK_DIRECTION,
    "xtick.major.width": TICK_WIDTH,
    "ytick.major.width": TICK_WIDTH,
    "xtick.major.size":  TICK_LENGTH,
    "ytick.major.size":  TICK_LENGTH,
    "legend.frameon":    False,
    "svg.fonttype":      "none",
    "pdf.fonttype":      42,
    "ps.fonttype":       42,
})
# =============================================================================
def dw(text):
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in str(text))
def pad(text, width, align="left"):
    text = str(text)
    blank = " " * max(width - dw(text), 0)
    return text + blank if align == "left" else blank + text
def parse_args(argv):
    formatter = type(
        "_Formatter",
        (argparse.RawDescriptionHelpFormatter, argparse.ArgumentDefaultsHelpFormatter),
        {},
    )
    parser = argparse.ArgumentParser(prog=os.path.basename(__file__), description=__doc__, formatter_class=formatter)
    parser.add_argument("-i", "--input", default=None, help="能级CSV（system,vbm,cbm,ef，真空为0）")
    parser.add_argument("-o", "--outdir", default=None, help=f"输出目录（默认 {OUTPUT_PATH}）")
    parser.add_argument("-f", "--formats", default="svg,pdf,tiff,png", help="导出格式")
    parser.add_argument("-d", "--dpi", type=int, default=DEFAULT_DPI, help="位图分辨率")
    parser.add_argument("-s", "--show", action="store_true", help="打开PNG预览")
    return parser.parse_args(argv)
def resolve_path(raw, base_dir):
    raw = os.path.expanduser(raw)
    if os.path.isabs(raw):
        return os.path.abspath(raw)
    if raw.startswith(("./", "../", ".\\", "..\\")) or raw in (".", ".."):
        return os.path.abspath(raw)
    return os.path.abspath(os.path.join(base_dir, raw))
def load_levels(path):
    table = pd.read_csv(path)
    table.columns = [str(c).lstrip("#").strip() for c in table.columns]
    # 兼容本脚本导出的宽表列名（vbm_ev / cbm_ev / ef_ev）
    table = table.rename(columns={k: v for k, v in {"vbm_ev": "vbm", "cbm_ev": "cbm", "ef_ev": "ef"}.items()
                                  if k in table.columns and v not in table.columns})
    missing = {"system", "vbm", "cbm", "ef"} - set(table.columns)
    if missing:
        raise ValueError(f"CSV缺少列：{', '.join(sorted(missing))}")
    return [(str(r.system), float(r.vbm), float(r.cbm), float(r.ef)) for r in table.itertuples()]

# ========== 核心改动：统一减去公共费米能级，不再各自减Ef ==========
def build_table(levels):
    names = [item[0] for item in levels]
    # 原始真空能级
    vbm_raw = [item[1] for item in levels]
    cbm_raw = [item[2] for item in levels]
    ef_raw  = [item[3] for item in levels]
    # 全部平移到公共费米基准 E_F=0
    vbm_plot = [v - FERMI_REF for v in vbm_raw]
    cbm_plot = [c - FERMI_REF for c in cbm_raw]
    ef_plot  = [0.0 for _ in ef_raw]   # 所有体系费米统一置零

    table = pd.DataFrame({
        "system":    names,
        "vbm_ev":    vbm_plot,
        "cbm_ev":    cbm_plot,
        "ef_ev":     ef_plot,
        "vbm_raw":   vbm_raw,
        "cbm_raw":   cbm_raw,
        "ef_raw":    ef_raw,
    })
    table["band_gap_ev"] = table["cbm_ev"] - table["vbm_ev"]
    # 组分体相带阶：只写在参 OFFSET_PAIRS 的行上，其余留空
    # 异质结为复合体系，不参与 VBO/CBO，因此源数据表里也不会出现第三行带阶
    cbo = [np.nan] * len(table)
    vbo = [np.nan] * len(table)
    for i, j in OFFSET_PAIRS:
        if i < len(table) and j < len(table):
            cbo[i] = cbo[j] = abs(cbm_plot[j] - cbm_plot[i])
            vbo[i] = vbo[j] = abs(vbm_plot[j] - vbm_plot[i])
    table["cbo_ev"] = cbo
    table["vbo_ev"] = vbo
    return table


def detect_rigid_shift(table):
    """检测带隙相同且带边刚性平移的体系对（通常指向真空能级参考不一致）。"""
    names = table.system.tolist()
    hits = []
    for i in range(len(table) - 1):
        for j in range(i + 1, len(table)):
            dv = table.vbm_raw[j] - table.vbm_raw[i]
            dc = table.cbm_raw[j] - table.cbm_raw[i]
            dg = table.band_gap_ev[j] - table.band_gap_ev[i]
            if abs(dv) > 0.3 and abs(dv - dc) < 0.02 and abs(dg) < 0.02:
                hits.append((names[i], names[j], dv, table.band_gap_ev[j]))
    return hits

def format_label(name):
    return re.sub(r"(?<=[A-Za-z\)])(\d+)", r"$_{\1}$", name)

def draw_figure(table):
    """绘制能带对齐图（只画组分体相，异质结不进入图面），返回 Figure。"""
    idx = [i for i in PLOT_INDICES if i < len(table)]
    if not idx:
        raise ValueError("PLOT_INDICES 为空，没有可绘制的体系")
    xs = {i: k * X_STEP for k, i in enumerate(idx)}      # 体系索引 → 横坐标
    half = BAR_HALF_WIDTH

    fig, ax = plt.subplots(figsize=(FIG_WIDTH_MM / 25.4, FIG_HEIGHT_MM / 25.4))
    fig.subplots_adjust(left=0.17, right=0.965, bottom=0.165, top=0.840)

    # ===== 组分体相带阶 VBO / CBO =====
    # VBO/CBO 只定义在两个组分材料之间；异质结是界面复合后的整体体系，不是第三个独立组分，
    # 因此绝不能画 MoS2 → heterojunction 的带边连线（那会被当成概念错误）
    for i, j in OFFSET_PAIRS:
        if i not in xs or j not in xs:
            continue
        xa, xb = xs[i] + half, xs[j] - half
        for key, va, vb in (("CBO", table.cbm_ev[i], table.cbm_ev[j]),
                            ("VBO", table.vbm_ev[i], table.vbm_ev[j])):
            ax.plot([xa, xb], [va, vb], color=NEUTRAL_MID, lw=0.9,
                    ls=(0, (1.6, 1.6)), zorder=1)
            # 引线是斜线，标注带白底以免被虚线穿过
            ax.text((xa + xb) / 2, (va + vb) / 2 + 0.10, f"{key} = {abs(vb - va):.2f} eV",
                    ha="center", va="bottom", fontsize=OFFSET_FONT_SIZE,
                    color=NEUTRAL_DARK, zorder=6,
                    bbox=dict(facecolor="white", edgecolor="none", boxstyle="square,pad=0.12"))

    # ===== 带隙柱 + 带边线 + 数值标注 =====
    for i in idx:
        row, color, x = table.iloc[i], COLORS[i % len(COLORS)], xs[i]
        ax.add_patch(Rectangle((x - half, row.vbm_ev), 2 * half, row.band_gap_ev,
                               facecolor=color, edgecolor="none", alpha=0.13, zorder=2))
        for edge in (row.vbm_ev, row.cbm_ev):
            ax.plot([x - half, x + half], [edge, edge], color=color, lw=EDGE_WIDTH,
                    solid_capstyle="round", zorder=4)
        ax.text(x, row.cbm_ev + 0.14, f"{row.cbm_ev:+.2f}", ha="center", va="bottom",
                fontsize=VALUE_FONT_SIZE, color=color, zorder=5)
        ax.text(x, row.vbm_ev - 0.14, f"{row.vbm_ev:+.2f}", ha="center", va="top",
                fontsize=VALUE_FONT_SIZE, color=color, zorder=5)

    # ===== 统一费米能级（全图仅此一条）=====
    ax.axhline(0.0, color=FERMI_COLOR, lw=FERMI_WIDTH, ls=(0, (3.0, 2.0)), zorder=3)

    # ===== 坐标轴 =====
    vbm_min = min(table.vbm_ev[i] for i in idx)
    cbm_max = max(table.cbm_ev[i] for i in idx)
    y_lo, y_hi = vbm_min - 0.75, cbm_max + 0.80
    ax.set_xlim(min(xs.values()) - X_MARGIN, max(xs.values()) + X_MARGIN)
    ax.set_ylim(y_lo, y_hi)
    ax.set_xticks([xs[i] for i in idx])
    ax.set_xticklabels([format_label(table.system[i]) for i in idx], fontsize=TICK_FONT_SIZE)
    ax.tick_params(axis="x", labelsize=TICK_FONT_SIZE, pad=TICK_PAD)
    # 刻度锚定 0，使公共费米线正好落在一条主刻度上
    ax.set_yticks(np.arange(np.ceil(y_lo / Y_MAJOR) * Y_MAJOR, y_hi, Y_MAJOR))
    ax.tick_params(axis="y", labelsize=TICK_FONT_SIZE, pad=TICK_PAD)
    ax.set_ylabel("$E - E_\\mathrm{F}$ (eV)", fontsize=FONT_SIZE, labelpad=LABEL_PAD)

    # ===== 图例（只解释线型，颜色由 x 轴体系名承担）=====
    handles = [
        Line2D([], [], color=NEUTRAL_DARK, lw=EDGE_WIDTH, label="Band edges"),
        Line2D([], [], color=FERMI_COLOR, lw=FERMI_WIDTH, ls=(0, (3.0, 2.0)),
               label="Unified $E_\\mathrm{F}$ = 0"),
    ]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.015), ncol=2,
              fontsize=LEGEND_FONT_SIZE, handlelength=1.8, handletextpad=0.7,
              columnspacing=2.0, borderaxespad=0.0)
    return fig

def export_figures(fig, outdir, stem, formats, dpi):
    os.makedirs(outdir, exist_ok=True)
    saved, base = [], os.path.join(outdir, stem)
    for fmt in formats:
        path = f"{base}.{fmt}"
        if fmt == "tiff":
            fig.savefig(path, format="tiff", dpi=dpi, pil_kwargs={"compression": "tiff_lzw"})
        elif fmt == "png":
            fig.savefig(path, format="png", dpi=min(dpi, PREVIEW_DPI))
        else:
            fig.savefig(path, format=fmt, dpi=dpi)
        saved.append(path)
    return saved

def print_summary(table, saved, record_path):
    drawn = "、".join(table.system[i] for i in PLOT_INDICES if i < len(table))
    print(f"\nℹ️  能级（已对齐到统一热平衡费米 E_F=0；图中仅绘制 {drawn}）")
    header = [("序号", 4, "right"), ("体系", 16, "left"),
              ("VBM-E_F", 10, "right"), ("CBM-E_F", 10, "right"), ("Eg", 8, "right")]
    print("   " + "  ".join(pad(t, w, a) for t, w, a in header))
    print("   " + "-" * (sum(w for _, w, _ in header) + 2 * (len(header) - 1)))
    for i, row in enumerate(table.itertuples(), start=1):
        print("   " + "  ".join([
            pad(i, 4, "right"),
            pad(row.system, 16, "left"),
            pad(f"{row.vbm_ev:+.4f}", 10, "right"),
            pad(f"{row.cbm_ev:+.4f}", 10, "right"),
            pad(f"{row.band_gap_ev:.4f}", 8, "right"),
        ]))
    if OFFSET_PAIRS:
        print("\nℹ️  组分体相带阶（异质结为复合体系，不参与 VBO/CBO）")
        for i, j in OFFSET_PAIRS:
            cbo = abs(table.cbm_ev[j] - table.cbm_ev[i])
            vbo = abs(table.vbm_ev[j] - table.vbm_ev[i])
            d_eg = abs(table.band_gap_ev[j] - table.band_gap_ev[i])
            flag = "✓" if abs(cbo + vbo - d_eg) < 0.02 else "✗ 请核对能级数据"
            print(f"   {pad(table.system[i], 16)} ↔ {pad(table.system[j], 16)}"
                  f" CBO = {cbo:.4f} eV   VBO = {vbo:.4f} eV")
            print(f"      自洽校验：VBO + CBO = {cbo + vbo:.4f} eV，ΔEg = {d_eg:.4f} eV  {flag}")

    # 统一基准只是坐标平移：各体系自身 E_F 与公共基准的距离不会因此消失
    mismatch = [(row.system, row.ef_raw - FERMI_REF) for row in table.itertuples()]
    if any(abs(d) > 0.05 for _, d in mismatch):
        print("\n⚠️  各体系自身 E_F 与公共基准的偏差（不会因平移而消失）")
        for name, d in mismatch:
            print(f"   {pad(name, 16)} E_F,own - E_F,ref = {d:+.4f} eV")

    for a, b, d, gap in detect_rigid_shift(table):
        print(f"\n⚠️  {b} 相对 {a} 带边刚性平移 {d:+.4f} eV，且带隙完全相同（{gap:.4f} eV）")
        print("    → 疑似两次计算的真空能级参考未统一（slab 偶极/真空层厚度不对称），建议核对")
    print("\n📦 输出文件")
    for path in saved + [record_path]:
        print(f"   {os.path.abspath(path)}")
    print(f"\n🎉 完成：{len(saved)} 个图件 + 1 个源数据表 → {os.path.abspath(os.path.dirname(saved[0]))}\n")

def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.input:
        input_path = resolve_path(args.input, SCRIPT_DIR)
        if not os.path.isfile(input_path):
            raise FileNotFoundError(f"能级文件不存在：{input_path}")
        levels = load_levels(input_path)
    elif INPUT_FILES:
        input_path = resolve_path(INPUT_FILES[0], os.path.join(SCRIPT_DIR, INPUT_PATH))
        levels = load_levels(input_path)
    else:
        levels = SYSTEMS
    table = build_table(levels)
    if abs(FERMI_REF - levels[-1][3]) > 0.05:
        print(f"⚠️  统一费米基准 {FERMI_REF:+.4f} eV 与末体系 E_F {levels[-1][3]:+.4f} eV 不一致")
    outdir = resolve_path(args.outdir, SCRIPT_DIR) if args.outdir else os.path.join(SCRIPT_DIR, OUTPUT_PATH)
    formats = [f.strip().lower() for f in args.formats.split(",") if f.strip()]
    fig = draw_figure(table)
    saved = export_figures(fig, outdir, OUTPUT_FILES[0], formats, args.dpi)
    plt.close(fig)
    record_path = os.path.join(outdir, RECORD_FILE)
    table.to_csv(record_path, index=False, float_format="%.4f",
                  header=["# " + c if i == 0 else c for i, c in enumerate(table.columns)])
    print_summary(table, saved, record_path)
    if args.show:
        preview = os.path.join(outdir, f"{OUTPUT_FILES[0]}.png")
        if os.path.isfile(preview):
            webbrowser.open("file:///" + preview.replace(os.sep, "/"))

if __name__ == "__main__":
    main()
# =============================================================================
