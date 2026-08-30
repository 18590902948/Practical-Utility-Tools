import matplotlib.pyplot as plt
import numpy as np
import os
from typing import List, Tuple, Optional

# ==============================================================================
# ============================ 全局可配置参数（用户仅需修改此区域）============================
# ==============================================================================
# ---------------------- 1. 全局缩放倍率（核心控制，1=基准值，>1放大，<1缩小） ----------------------
GLOBAL_LINEWIDTH_SCALE = 1.0  # 所有线条粗细的全局倍率（1=基准线宽）
GLOBAL_FONT_SIZE_SCALE = 1.0  # 所有字体大小的全局倍率（1=基准字体）

# ---------------------- 2. 文件路径参数 ----------------------
SPLINE_DATA_FILE = 'spline.dat'  # 反应能量数据文件
SKIP_ROWS = 0  # 读取数据时跳过的行数

# ---------------------- 3. 边框显示开关（True=显示，False=隐藏） ----------------------
SHOW_TOP_SPINE = False  # 上边框
SHOW_RIGHT_SPINE = False  # 右边框
SHOW_LEFT_SPINE = True  # 左边框
SHOW_BOTTOM_SPINE = True  # 下边框

# ---------------------- 4. 文本显示参数（空字符串则不显示） ----------------------
TITLE_TEXT = ''  # 图表标题
X_LABEL_TEXT = 'Reaction Coordinate (Å)'  # X轴标签
Y_LABEL_TEXT = 'Energy (eV)'  # Y轴标签

# ---------------------- 5. 位置控制参数（距离单位：点/像素，可正可负） ----------------------
X_TICK_LABEL_PAD = 8  # X轴刻度标签距离X轴的距离
X_LABEL_PAD = 10  # X轴标签文字距离X轴的距离
Y_TICK_LABEL_PAD = 8  # Y轴刻度标签距离Y轴的距离
Y_LABEL_PAD = 10  # Y轴标签文字距离Y轴的距离
TITLE_PAD = 12  # 标题距离图表上边框的距离

# ---------------------- 6. 视觉样式 - 颜色 ----------------------
CURVE_COLOR = 'blue'  # 能量曲线颜色
NEB_POINT_COLOR = 'red'  # NEB特殊点填充色
SPINE_COLOR = 'black'  # 图表边框颜色
TICK_COLOR = 'black'  # 刻度线颜色
NEB_POINT_EDGECOLOR = None  # NEB点轮廓色（None=无轮廓）

# ---------------------- 7. 视觉样式 - 线宽基准值（最终=基准×GLOBAL_LINEWIDTH_SCALE） ----------------------
LINEWIDTH_BASE_CURVE = 2.5  # 能量曲线线宽基准（原脚本值）
LINEWIDTH_BASE_SPINE = 2.5  # 图表边框线宽基准
LINEWIDTH_BASE_TICK = 2.5  # 刻度线线宽基准
LINEWIDTH_BASE_TICK_LENGTH = 8  # 刻度长度基准（与线宽成比例）

# ---------------------- 8. 视觉样式 - 字体大小基准值（最终=基准×GLOBAL_FONT_SIZE_SCALE） ----------------------
FONTSIZE_BASE_TITLE = 28  # 标题字体大小基准
FONTSIZE_BASE_X_TICK = 24  # X轴刻度字体大小基准（原脚本值）
FONTSIZE_BASE_X_LABEL = 28  # X轴标签字体大小基准（原脚本值）
FONTSIZE_BASE_Y_TICK = 24  # Y轴刻度字体大小基准（原脚本值）
FONTSIZE_BASE_Y_LABEL = 28  # Y轴标签字体大小基准（原脚本值）

# ---------------------- 9. 视觉样式 - 刻度配置 ----------------------
TICK_DIRECTION = 'in'  # 刻度方向：'in'（向内）/'out'（向外）/'inout'（双向）
Y_TICK_DECIMAL = 2  # Y轴刻度保留小数位数（0=整数，1=一位小数，2=两位）

# ---------------------- 10. 坐标轴范围配置（[最小值, 最大值]，None则自动调整） ----------------------
X_LIMITS = [-0.2, 3.6]  # 反应坐标范围（Å）- 保留原脚本值
Y_LIMITS = [-0.02, 0.10]  # 能量范围（eV）- 保留原脚本值

# ---------------------- 11. NEB特殊点参数 ----------------------
NEB_POINT_SIZE = 60  # NEB点大小（原脚本值）
NEB_POINT_MARKER = 'o'  # NEB点标记样式（原脚本值）

# ---------------------- 12. 其他配置 ----------------------
FIGSIZE = (18, 6)  # 图尺寸（宽, 高）- 保留原脚本值
PLT_USE_TEX = False  # 是否启用LaTeX渲染（False=禁用）

# ==============================================================================
# ============================ 自动计算最终参数（无需修改） =============================
# ==============================================================================
# 线宽最终值 = 基准值 × 全局线宽倍率
FINAL_LINEWIDTH_CURVE = LINEWIDTH_BASE_CURVE * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_SPINE = LINEWIDTH_BASE_SPINE * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_TICK = LINEWIDTH_BASE_TICK * GLOBAL_LINEWIDTH_SCALE
FINAL_TICK_LENGTH = LINEWIDTH_BASE_TICK_LENGTH * GLOBAL_LINEWIDTH_SCALE

# 字体大小最终值 = 基准值 × 全局字体倍率
FINAL_FONTSIZE_TITLE = FONTSIZE_BASE_TITLE * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_X_TICK = FONTSIZE_BASE_X_TICK * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_X_LABEL = FONTSIZE_BASE_X_LABEL * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_Y_TICK = FONTSIZE_BASE_Y_TICK * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_Y_LABEL = FONTSIZE_BASE_Y_LABEL * GLOBAL_FONT_SIZE_SCALE

# ==============================================================================
# ============================ 基础样式全局设置（无需修改） =============================
# ==============================================================================
plt.rcParams["font.family"] = ["DejaVu Sans", "sans-serif"]  # 统一无衬线字体
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示异常
plt.rcParams["text.usetex"] = PLT_USE_TEX  # LaTeX渲染开关


# ==============================================================================
# ============================ 工具函数（无需修改） =============================
# ==============================================================================
def load_and_filter_data(filename: str = SPLINE_DATA_FILE, skiprows: int = SKIP_ROWS):
    """
    读取数据文件并筛选NEB特殊点
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"文件 {filename} 不存在")

    spline_data = np.loadtxt(filename, skiprows=skiprows)

    if spline_data.shape[1] < 3:
        raise ValueError("数据文件至少需要3列（序号, 反应坐标, 能量）")

    # 提取数据
    reaction_coord = spline_data[:, 1]
    energy = spline_data[:, 2]

    # 筛选整数行（包括0）- 浮点精度安全判断
    is_integer_row = np.isclose(spline_data[:, 0], np.round(spline_data[:, 0]))
    neb_coord = spline_data[is_integer_row, 1]
    neb_energy = spline_data[is_integer_row, 2]

    return reaction_coord, energy, neb_coord, neb_energy


# ==============================================================================
# ============================ 核心绘图函数（无需修改） =============================
# ==============================================================================
def plot_reaction_energy():
    """绘制反应能量图主函数"""
    try:
        # 1. 读取数据
        reaction_coord, energy, neb_coord, neb_energy = load_and_filter_data()
        print(f"\n✅ 数据加载成功：")
        print(f"   总数据点数量：{len(reaction_coord)}")
        print(f"   NEB特殊点数量：{len(neb_coord)}")

        # 2. 创建画布
        fig, ax = plt.subplots(figsize=FIGSIZE)

        # 3. 绘制能量曲线
        ax.plot(
            reaction_coord, energy,
            color=CURVE_COLOR,
            linewidth=FINAL_LINEWIDTH_CURVE
        )

        # 4. 绘制NEB特殊点（确保点在曲线上方）
        if len(neb_coord) > 0:
            ax.scatter(
                neb_coord, neb_energy,
                color=NEB_POINT_COLOR,
                s=NEB_POINT_SIZE,
                marker=NEB_POINT_MARKER,
                edgecolor=NEB_POINT_EDGECOLOR,
                zorder=5
            )

        # 5. 边框样式配置
        # 设置边框显示状态
        ax.spines['top'].set_visible(SHOW_TOP_SPINE)
        ax.spines['right'].set_visible(SHOW_RIGHT_SPINE)
        ax.spines['left'].set_visible(SHOW_LEFT_SPINE)
        ax.spines['bottom'].set_visible(SHOW_BOTTOM_SPINE)

        # 设置边框样式（颜色+最终线宽）
        for spine in ax.spines.values():
            spine.set_color(SPINE_COLOR)
            spine.set_linewidth(FINAL_LINEWIDTH_SPINE)

        # 6. 标题配置（空则不显示）
        if TITLE_TEXT:
            ax.set_title(
                TITLE_TEXT,
                fontsize=FINAL_FONTSIZE_TITLE,
                pad=TITLE_PAD
            )

        # 7. 坐标轴标签配置
        ax.set_xlabel(
            X_LABEL_TEXT,
            fontsize=FINAL_FONTSIZE_X_LABEL,
            labelpad=X_LABEL_PAD
        )
        ax.set_ylabel(
            Y_LABEL_TEXT,
            fontsize=FINAL_FONTSIZE_Y_LABEL,
            labelpad=Y_LABEL_PAD
        )

        # 8. 坐标轴范围配置
        if X_LIMITS is not None:
            ax.set_xlim(X_LIMITS)
        if Y_LIMITS is not None:
            ax.set_ylim(Y_LIMITS)

        # 9. 刻度样式配置
        # X轴刻度配置
        ax.tick_params(
            axis='x',
            labelsize=FINAL_FONTSIZE_X_TICK,
            width=FINAL_LINEWIDTH_TICK,
            length=FINAL_TICK_LENGTH,
            direction=TICK_DIRECTION,
            pad=X_TICK_LABEL_PAD,
            color=TICK_COLOR,
            labelcolor=TICK_COLOR
        )

        # Y轴刻度配置
        ax.tick_params(
            axis='y',
            labelsize=FINAL_FONTSIZE_Y_TICK,
            width=FINAL_LINEWIDTH_TICK,
            length=FINAL_TICK_LENGTH,
            direction=TICK_DIRECTION,
            pad=Y_TICK_LABEL_PAD,
            color=TICK_COLOR,
            labelcolor=TICK_COLOR
        )

        # Y轴刻度小数点格式
        ax.yaxis.set_major_formatter(plt.FormatStrFormatter(f'%.{Y_TICK_DECIMAL}f'))

        # 10. 布局优化+显示
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
# ============================ 主程序入口（无需修改） =============================
# ==============================================================================
if __name__ == "__main__":
    # 打印全局配置信息（便于调试）
    print(f"\n📌 全局配置信息：")
    print(f"   线宽缩放倍率：{GLOBAL_LINEWIDTH_SCALE} | 字体缩放倍率：{GLOBAL_FONT_SIZE_SCALE}")
    print(f"   能量曲线线宽：{FINAL_LINEWIDTH_CURVE:.2f} | X轴标签字体大小：{FINAL_FONTSIZE_X_LABEL:.0f}")
    print(
        f"   边框显示配置：上={SHOW_TOP_SPINE} | 右={SHOW_RIGHT_SPINE} | 左={SHOW_LEFT_SPINE} | 下={SHOW_BOTTOM_SPINE}")

    # 执行绘图
    plot_reaction_energy()