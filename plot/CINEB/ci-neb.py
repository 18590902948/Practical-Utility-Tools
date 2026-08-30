import matplotlib.pyplot as plt
import numpy as np
import os
from typing import List, Tuple, Optional

# ==============================================================================
# ============================ 全局可配置参数（用户仅需修改此区域）============================
# ==============================================================================
# ---------------------- 1. 全局缩放倍率 ----------------------
GLOBAL_LINEWIDTH_SCALE = 1.0
GLOBAL_FONT_SIZE_SCALE = 1.0

# ---------------------- 2. 文件路径参数 ----------------------
SPLINE_DATA_FILE = 'spline.dat'
SKIP_ROWS = 0

# ---------------------- 3. 边框显示开关 ----------------------
SHOW_TOP_SPINE = True
SHOW_RIGHT_SPINE = True
SHOW_LEFT_SPINE = True
SHOW_BOTTOM_SPINE = True

# ---------------------- 4. 文本显示参数 ----------------------
TITLE_TEXT = ''
X_LABEL_TEXT = 'Reaction Coordinate (Å)'
Y_LABEL_TEXT = 'Energy (eV)'

# ---------------------- 5. 位置控制参数 ----------------------
X_TICK_LABEL_PAD = 8
X_LABEL_PAD = 10
Y_TICK_LABEL_PAD = 8
Y_LABEL_PAD = 10
TITLE_PAD = 12

# ---------------------- 6. 视觉样式 - 颜色 ----------------------
CURVE_COLOR = 'blue'
NEB_POINT_COLOR = 'red'
SPINE_COLOR = 'black'
TICK_COLOR = 'black'
NEB_POINT_EDGECOLOR = None

# ---------------------- 7. 视觉样式 - 线宽基准值 ----------------------
LINEWIDTH_BASE_CURVE = 2.5
LINEWIDTH_BASE_SPINE = 2.5
LINEWIDTH_BASE_TICK = 2.5
LINEWIDTH_BASE_TICK_LENGTH = 8

# ---------------------- 8. 视觉样式 - 字体大小基准值 ----------------------
FONTSIZE_BASE_TITLE = 28
FONTSIZE_BASE_X_TICK = 24
FONTSIZE_BASE_X_LABEL = 28
FONTSIZE_BASE_Y_TICK = 24
FONTSIZE_BASE_Y_LABEL = 28

# ---------------------- 9. 视觉样式 - 刻度配置 ----------------------
TICK_DIRECTION = 'in'
Y_TICK_DECIMAL = 1

# ---------------------- 10. 坐标轴范围配置 ----------------------
X_LIMITS = None
Y_LIMITS = None

# ---------------------- 11. NEB特殊点参数 ----------------------
NEB_POINT_SIZE = 150
NEB_POINT_MARKER = '*'
# 移除间隙因子，改用索引切片天然间隙

# ---------------------- 12. 其他配置 ----------------------
FIGSIZE = (8, 6)
PLT_USE_TEX = False

# ==============================================================================
# ============================ 自动计算最终参数（无需修改） =============================
# ==============================================================================
FINAL_LINEWIDTH_CURVE = LINEWIDTH_BASE_CURVE * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_SPINE = LINEWIDTH_BASE_SPINE * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_TICK = LINEWIDTH_BASE_TICK * GLOBAL_LINEWIDTH_SCALE
FINAL_TICK_LENGTH = LINEWIDTH_BASE_TICK_LENGTH * GLOBAL_LINEWIDTH_SCALE

FINAL_FONTSIZE_TITLE = FONTSIZE_BASE_TITLE * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_X_TICK = FONTSIZE_BASE_X_TICK * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_X_LABEL = FONTSIZE_BASE_X_LABEL * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_Y_TICK = FONTSIZE_BASE_Y_TICK * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_Y_LABEL = FONTSIZE_BASE_Y_LABEL * GLOBAL_FONT_SIZE_SCALE

# ==============================================================================
# ============================ 基础样式全局设置（无需修改） =============================
# ==============================================================================
plt.rcParams["font.family"] = ["DejaVu Sans", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["text.usetex"] = PLT_USE_TEX


# ==============================================================================
# ============================ 工具函数（无需修改） =============================
# ==============================================================================
def load_and_filter_data(filename: str = SPLINE_DATA_FILE, skiprows: int = SKIP_ROWS):
    if not os.path.exists(filename):
        raise FileNotFoundError(f"文件 {filename} 不存在")

    spline_data = np.loadtxt(filename, skiprows=skiprows)
    if spline_data.shape[1] < 3:
        raise ValueError("数据文件至少需要3列（序号, 反应坐标, 能量）")

    reaction_coord = spline_data[:, 1]
    energy = spline_data[:, 2]
    is_integer_row = np.isclose(spline_data[:, 0], np.round(spline_data[:, 0]))
    neb_indices = np.where(is_integer_row)[0]
    neb_coord = spline_data[neb_indices, 1]
    neb_energy = spline_data[neb_indices, 2]

    return reaction_coord, energy, neb_coord, neb_energy, neb_indices


# ==============================================================================
# ============================ 核心绘图函数（核心修复部分） =============================
# ==============================================================================
def plot_reaction_energy():
    try:
        reaction_coord, energy, neb_coord, neb_energy, neb_indices = load_and_filter_data()
        print(f"\n✅ 数据加载成功：")
        print(f"   总数据点数量：{len(reaction_coord)}")
        print(f"   NEB特殊点数量：{len(neb_coord)}")

        fig, ax = plt.subplots(figsize=FIGSIZE)

        # 核心修复：按NEB索引直接切片，不修改任何数据坐标
        if len(neb_indices) > 0:
            # 生成分段的起止索引
            segment_starts = np.concatenate([[0], neb_indices + 1])
            segment_ends = np.concatenate([neb_indices, [len(reaction_coord)]])

            # 遍历绘制每一段曲线
            for start, end in zip(segment_starts, segment_ends):
                if start < end:  # 仅绘制有效分段
                    ax.plot(
                        reaction_coord[start:end], energy[start:end],
                        color=CURVE_COLOR,
                        linewidth=FINAL_LINEWIDTH_CURVE
                    )
        else:
            ax.plot(
                reaction_coord, energy,
                color=CURVE_COLOR,
                linewidth=FINAL_LINEWIDTH_CURVE
            )

        # 绘制NEB星星（层级置顶）
        if len(neb_coord) > 0:
            ax.scatter(
                neb_coord, neb_energy,
                color=NEB_POINT_COLOR,
                s=NEB_POINT_SIZE,
                marker=NEB_POINT_MARKER,
                edgecolor=NEB_POINT_EDGECOLOR,
                zorder=10
            )

        # 边框与刻度配置（保持不变）
        ax.spines['top'].set_visible(SHOW_TOP_SPINE)
        ax.spines['right'].set_visible(SHOW_RIGHT_SPINE)
        ax.spines['left'].set_visible(SHOW_LEFT_SPINE)
        ax.spines['bottom'].set_visible(SHOW_BOTTOM_SPINE)
        for spine in ax.spines.values():
            spine.set_color(SPINE_COLOR)
            spine.set_linewidth(FINAL_LINEWIDTH_SPINE)

        if TITLE_TEXT:
            ax.set_title(TITLE_TEXT, fontsize=FINAL_FONTSIZE_TITLE, pad=TITLE_PAD)
        ax.set_xlabel(X_LABEL_TEXT, fontsize=FINAL_FONTSIZE_X_LABEL, labelpad=X_LABEL_PAD)
        ax.set_ylabel(Y_LABEL_TEXT, fontsize=FINAL_FONTSIZE_Y_LABEL, labelpad=Y_LABEL_PAD)

        if X_LIMITS is not None:
            ax.set_xlim(X_LIMITS)
        if Y_LIMITS is not None:
            ax.set_ylim(Y_LIMITS)

        ax.tick_params(
            axis='x', labelsize=FINAL_FONTSIZE_X_TICK, width=FINAL_LINEWIDTH_TICK,
            length=FINAL_TICK_LENGTH, direction=TICK_DIRECTION, pad=X_TICK_LABEL_PAD,
            color=TICK_COLOR, labelcolor=TICK_COLOR
        )
        ax.tick_params(
            axis='y', labelsize=FINAL_FONTSIZE_Y_TICK, width=FINAL_LINEWIDTH_TICK,
            length=FINAL_TICK_LENGTH, direction=TICK_DIRECTION, pad=Y_TICK_LABEL_PAD,
            color=TICK_COLOR, labelcolor=TICK_COLOR
        )
        ax.yaxis.set_major_formatter(plt.FormatStrFormatter(f'%.{Y_TICK_DECIMAL}f'))

        plt.tight_layout()
        plt.show()

    except FileNotFoundError as e:
        print(f"\n❌ 错误：{e}")
    except ValueError as e:
        print(f"\n❌ 数据格式错误：{e}")
    except Exception as e:
        print(f"\n❌ 未知错误：{e}")
        import traceback
        traceback.print_exc()


# ==============================================================================
# ============================ 主程序入口 =============================
# ==============================================================================
if __name__ == "__main__":
    print(f"\n📌 全局配置信息：")
    print(f"   线宽缩放倍率：{GLOBAL_LINEWIDTH_SCALE} | 字体缩放倍率：{GLOBAL_FONT_SIZE_SCALE}")
    print(f"   能量曲线线宽：{FINAL_LINEWIDTH_CURVE:.2f} | X轴标签字体大小：{FINAL_FONTSIZE_X_LABEL:.0f}")
    print(
        f"   边框显示配置：上={SHOW_TOP_SPINE} | 右={SHOW_RIGHT_SPINE} | 左={SHOW_LEFT_SPINE} | 下={SHOW_BOTTOM_SPINE}")
    print(f"   NEB点样式：{NEB_POINT_MARKER} | 大小：{NEB_POINT_SIZE}")

    plot_reaction_energy()