import matplotlib.pyplot as plt
import numpy as np
import os
from matplotlib.ticker import MultipleLocator, FormatStrFormatter, AutoLocator
from typing import Optional, Tuple, List, Dict

# ==============================================================================
# ============================ 全局可配置参数（用户仅需修改此区域）============================
# ==============================================================================
# ---------------------- 1. 全局缩放倍率（核心控制，1=基准值，>1放大，<1缩小） ----------------------
GLOBAL_LINEWIDTH_SCALE = 1.0  # 所有线条粗细的全局倍率（1=基准线宽）
GLOBAL_FONT_SIZE_SCALE = 1.0  # 所有字体大小的全局倍率（1=基准字体）

# ---------------------- 2. 文件路径参数 ----------------------
DATA_DIR = os.path.dirname(os.path.abspath(__file__))  # 数据文件目录（默认脚本所在目录）
REAL_DATA_FILE = "REAL.in"  # 实部数据文件名
IMAG_DATA_FILE = "IMAG.in"  # 虚部数据文件名
DATA_SKIP_ROWS = 4  # 跳过数据文件前N行

# ---------------------- 3. 文本显示参数（空字符串则不显示） ----------------------
TITLE_REAL = ''  # 实部图表标题
TITLE_IMAG = ''  # 虚部图表标题
X_LABEL_TEXT = 'Energy (eV)'  # X轴标签
Y_LABEL_REAL = 'ε₁ (ω)'  # 实部Y轴标签
Y_LABEL_IMAG = 'ε₂ (ω)'  # 虚部Y轴标签

# ---------------------- 4. 位置控制参数（距离单位：点/像素，可正可负） ----------------------
X_TICK_LABEL_PAD = 8  # X轴刻度数值 距离 X轴（左边框）的距离
X_LABEL_PAD = 10  # X轴标签文字 距离 X轴（左边框）的距离
Y_TICK_LABEL_PAD = 8  # Y轴刻度数值 距离 Y轴（下边框）的距离
Y_LABEL_PAD = 10  # Y轴标签文字 距离 Y轴（下边框）的距离
TITLE_PAD = 12  # 标题文字 距离 图表上边框的距离

# ---------------------- 5. 视觉样式 - 颜色 ----------------------
LINE_COLORS = {
    'XX': 'red',  # xx分量线条颜色
    'YY': 'blue',  # yy分量线条颜色
    'ZZ': 'green'  # zz分量线条颜色
}
GRID_COLOR = 'gray'  # 网格线颜色
SPINE_COLOR = 'black'  # 图表边框颜色

# ---------------------- 6. 视觉样式 - 线宽基准值（最终=基准×GLOBAL_LINEWIDTH_SCALE） ----------------------
LINEWIDTH_BASE_CURVE = 2.5  # 介电函数曲线线宽基准
LINEWIDTH_BASE_SPINE = 2.5  # 图表边框线宽基准
LINEWIDTH_BASE_GRID = 1.0  # 网格线宽基准（开启时生效）
LINEWIDTH_BASE_TICK_MAJOR = 2.5  # 主刻度线宽基准
LINEWIDTH_BASE_TICK_MINOR = 1.25  # 子刻度线宽基准
LINEWIDTH_BASE_LEGEND_FRAME = 1.0  # 图例边框线宽基准

# ---------------------- 7. 视觉样式 - 字体大小基准值（最终=基准×GLOBAL_FONT_SIZE_SCALE） ----------------------
FONTSIZE_BASE_TITLE = 28  # 标题字体大小基准
FONTSIZE_BASE_X_LABEL = 28  # X轴标签字体大小基准
FONTSIZE_BASE_Y_LABEL = 28  # Y轴标签字体大小基准
FONTSIZE_BASE_X_TICK = 24  # X轴刻度字体大小基准
FONTSIZE_BASE_Y_TICK = 24  # Y轴刻度字体大小基准
FONTSIZE_BASE_LEGEND = 24  # 图例字体大小基准

# ---------------------- 8. 视觉样式 - 刻度长度基准值（最终=基准×GLOBAL_LINEWIDTH_SCALE） ----------------------
TICKLENGTH_BASE_MAJOR = 8.0  # 主刻度长度基准
TICKLENGTH_BASE_MINOR = 6.0  # 子刻度长度基准

# ---------------------- 9. 视觉样式 - 坐标轴范围（按能量单位eV设置） ----------------------
X_RANGE = (0, 30)  # X轴能量范围 [最小值, 最大值]
Y_RANGE_REAL = (0.0, 2.5)  # 实部Y轴范围 [最小值, 最大值]
Y_RANGE_IMAG = (-0.3, 2.0)  # 虚部Y轴范围 [最小值, 最大值]

# ---------------------- 10. 视觉样式 - 刻度配置 ----------------------
# 刻度间隔（按能量单位eV设置）
X_MAJOR_TICK = 5.0  # X轴主刻度间隔
X_MINOR_TICK = X_MAJOR_TICK * 0.5  # X轴子刻度间隔（主刻度的0.5）
Y_MAJOR_TICK_REAL = 0.5  # 实部Y轴主刻度间隔
Y_MINOR_TICK_REAL = Y_MAJOR_TICK_REAL * 0.5  # 实部Y轴子刻度间隔
Y_MAJOR_TICK_IMAG = 0.5  # 虚部Y轴主刻度间隔
Y_MINOR_TICK_IMAG = Y_MAJOR_TICK_IMAG * 0.5  # 虚部Y轴子刻度间隔

# 刻度方向（默认向内）：'in'（向内）/'out'（向外）/'inout'（双向）
TICK_DIRECTION = 'in'

# 刻度小数点位数（0=整数，1=一位小数，以此类推）
X_TICK_DECIMAL = 0  # X轴刻度保留小数位数
Y_TICK_DECIMAL = 1  # Y轴刻度保留小数位数

# ---------------------- 11. 视觉样式 - 网格 ----------------------
GRID_ON = False  # 网格线开关（True/False）
GRID_ALPHA = 0.5  # 网格透明度（0-1）
GRID_LINestyle = '--'  # 网格线型（'--'/'-'/':'等）

# ---------------------- 12. 视觉样式 - 图例 ----------------------
LOC_LEGEND = 'upper right'  # 图例位置：'best'/'upper left'/'upper right'/'lower left'/'lower right'
LEGEND_FRAME_ON = False  # 图例边框开关（True/False）
LEGEND_LABELS = {
    'XX': 'ε$_{xx}$',  # xx分量图例标签
    'YY': 'ε$_{yy}$',  # yy分量图例标签
    'ZZ': 'ε$_{zz}$'  # zz分量图例标签
}

# ---------------------- 13. 其他配置 ----------------------
FIGSIZE = (8, 5)  # 图像尺寸（宽:高），单位：英寸
FONT_FAMILY = ["DejaVu Sans", "sans-serif"]  # 字体族
SHOW_MINOR_TICKS = True  # 是否显示次要刻度

# ==============================================================================
# ============================ 自动计算最终参数（无需修改） =============================
# ==============================================================================
# 线宽最终值 = 基准值 × 全局线宽倍率
FINAL_LINEWIDTH_CURVE = LINEWIDTH_BASE_CURVE * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_SPINE = LINEWIDTH_BASE_SPINE * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_GRID = LINEWIDTH_BASE_GRID * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_TICK_MAJOR = LINEWIDTH_BASE_TICK_MAJOR * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_TICK_MINOR = LINEWIDTH_BASE_TICK_MINOR * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_LEGEND_FRAME = LINEWIDTH_BASE_LEGEND_FRAME * GLOBAL_LINEWIDTH_SCALE

# 字体大小最终值 = 基准值 × 全局字体倍率
FINAL_FONTSIZE_TITLE = FONTSIZE_BASE_TITLE * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_X_LABEL = FONTSIZE_BASE_X_LABEL * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_Y_LABEL = FONTSIZE_BASE_Y_LABEL * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_X_TICK = FONTSIZE_BASE_X_TICK * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_Y_TICK = FONTSIZE_BASE_Y_TICK * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_LEGEND = FONTSIZE_BASE_LEGEND * GLOBAL_FONT_SIZE_SCALE

# 刻度长度最终值 = 基准值 × 全局线宽倍率
FINAL_TICKLENGTH_MAJOR = TICKLENGTH_BASE_MAJOR * GLOBAL_LINEWIDTH_SCALE
FINAL_TICKLENGTH_MINOR = TICKLENGTH_BASE_MINOR * GLOBAL_LINEWIDTH_SCALE


# ==============================================================================
# ============================ 基础样式全局设置（无需修改） =============================
# ==============================================================================
def setup_plot_style() -> None:
    """设置全局绘图样式"""
    plt.rcParams.update({
        "font.family": FONT_FAMILY,
        "axes.unicode_minus": False,  # 正确显示负号
        "text.usetex": False,
        "axes.grid": GRID_ON,
        "grid.color": GRID_COLOR,
        "grid.linestyle": GRID_LINestyle,
        "grid.alpha": GRID_ALPHA,
        "grid.linewidth": FINAL_LINEWIDTH_GRID,
        "xtick.direction": TICK_DIRECTION,
        "ytick.direction": TICK_DIRECTION,
        "xtick.major.size": FINAL_TICKLENGTH_MAJOR,
        "ytick.major.size": FINAL_TICKLENGTH_MAJOR,
        "xtick.minor.size": FINAL_TICKLENGTH_MINOR,
        "ytick.minor.size": FINAL_TICKLENGTH_MINOR,
        "xtick.major.width": FINAL_LINEWIDTH_TICK_MAJOR,
        "ytick.major.width": FINAL_LINEWIDTH_TICK_MAJOR,
        "xtick.minor.width": FINAL_LINEWIDTH_TICK_MINOR,
        "ytick.minor.width": FINAL_LINEWIDTH_TICK_MINOR,
        "xtick.minor.visible": SHOW_MINOR_TICKS,
        "ytick.minor.visible": SHOW_MINOR_TICKS
    })


# ==============================================================================
# ============================ 工具函数（无需修改） =============================
# ==============================================================================
def load_dielectric_data(file_name: str) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """
    读取介电函数数据文件
    :param file_name: 数据文件名
    :return: (energy, xx_data, yy_data, zz_data) 或 None（读取失败）
    """
    file_path = os.path.join(DATA_DIR, file_name)
    try:
        # 读取数据
        data = np.loadtxt(file_path, skiprows=DATA_SKIP_ROWS)

        # 数据格式校验
        if data.ndim != 2 or data.shape[1] < 4:
            raise ValueError(f"数据格式错误：需至少4列（能量, xx, yy, zz），当前形状{data.shape}")

        energy = data[:, 0]
        xx_data = data[:, 1]
        yy_data = data[:, 2]
        zz_data = data[:, 3]

        print(f"✅ 成功读取 {file_name}：")
        print(f"   数据点数：{len(energy)} | 能量范围：{energy.min():.1f} ~ {energy.max():.1f} eV")
        return energy, xx_data, yy_data, zz_data

    except FileNotFoundError:
        print(f"❌ 错误：数据文件 {file_path} 不存在")
    except Exception as e:
        print(f"❌ 读取 {file_name} 失败：{str(e)}")
    return None


def get_tick_kwargs(axis: str) -> Dict[str, Any]:
    """生成刻度配置通用参数（减少重复代码）"""
    base_kwargs = {
        'direction': TICK_DIRECTION,
        'pad': X_TICK_LABEL_PAD if axis == 'x' else Y_TICK_LABEL_PAD,
        'labelsize': FINAL_FONTSIZE_X_TICK if axis == 'x' else FINAL_FONTSIZE_Y_TICK
    }
    return base_kwargs


def configure_axis(ax: plt.Axes, is_real: bool = True) -> None:
    """
    配置坐标轴（通用，适配实部/虚部）
    :param ax: 坐标轴对象
    :param is_real: 是否为实部（True=实部，False=虚部）
    """
    # 设置X轴范围和刻度
    ax.set_xlim(X_RANGE)
    ax.xaxis.set_major_locator(MultipleLocator(X_MAJOR_TICK))
    ax.xaxis.set_minor_locator(MultipleLocator(X_MINOR_TICK))
    ax.xaxis.set_major_formatter(FormatStrFormatter(f'%.{X_TICK_DECIMAL}f'))

    # 设置Y轴范围和刻度
    y_range = Y_RANGE_REAL if is_real else Y_RANGE_IMAG
    y_major_tick = Y_MAJOR_TICK_REAL if is_real else Y_MAJOR_TICK_IMAG
    y_minor_tick = Y_MINOR_TICK_REAL if is_real else Y_MINOR_TICK_IMAG

    ax.set_ylim(y_range)
    ax.yaxis.set_major_locator(MultipleLocator(y_major_tick))
    ax.yaxis.set_minor_locator(MultipleLocator(y_minor_tick))
    ax.yaxis.set_major_formatter(FormatStrFormatter(f'%.{Y_TICK_DECIMAL}f'))

    # 设置坐标轴标签
    ax.set_xlabel(X_LABEL_TEXT, fontsize=FINAL_FONTSIZE_X_LABEL, labelpad=X_LABEL_PAD)
    y_label = Y_LABEL_REAL if is_real else Y_LABEL_IMAG
    ax.set_ylabel(y_label, fontsize=FINAL_FONTSIZE_Y_LABEL, labelpad=Y_LABEL_PAD)

    # 设置标题
    title = TITLE_REAL if is_real else TITLE_IMAG
    if title:
        ax.set_title(title, fontsize=FINAL_FONTSIZE_TITLE, pad=TITLE_PAD)

    # 配置刻度样式
    # X轴主刻度
    ax.tick_params(axis='x', which='major', **get_tick_kwargs('x'))
    # X轴子刻度
    ax.tick_params(axis='x', which='minor', **get_tick_kwargs('x'))
    # Y轴主刻度
    ax.tick_params(axis='y', which='major', **get_tick_kwargs('y'))
    # Y轴子刻度
    ax.tick_params(axis='y', which='minor', **get_tick_kwargs('y'))

    # 设置图表边框线宽
    for spine in ax.spines.values():
        spine.set_linewidth(FINAL_LINEWIDTH_SPINE)
        spine.set_color(SPINE_COLOR)


# ==============================================================================
# ============================ 核心绘图函数（无需修改） =============================
# ==============================================================================
def plot_dielectric_curve(is_real: bool = True) -> Optional[plt.Figure]:
    """
    绘制介电函数曲线（实部/虚部）
    :param is_real: 是否绘制实部（True=实部，False=虚部）
    :return: 绘图Figure对象或None（失败）
    """
    # 读取数据
    data_file = REAL_DATA_FILE if is_real else IMAG_DATA_FILE
    data = load_dielectric_data(data_file)
    if data is None:
        return None

    energy, xx_data, yy_data, zz_data = data

    # 创建画布
    fig, ax = plt.subplots(figsize=FIGSIZE)

    # 绘制各分量曲线
    ax.plot(energy, xx_data, color=LINE_COLORS['XX'], linewidth=FINAL_LINEWIDTH_CURVE, label=LEGEND_LABELS['XX'])
    ax.plot(energy, yy_data, color=LINE_COLORS['YY'], linewidth=FINAL_LINEWIDTH_CURVE, label=LEGEND_LABELS['YY'])
    ax.plot(energy, zz_data, color=LINE_COLORS['ZZ'], linewidth=FINAL_LINEWIDTH_CURVE, label=LEGEND_LABELS['ZZ'])

    # 配置坐标轴
    configure_axis(ax, is_real)

    # 配置图例
    legend = ax.legend(
        fontsize=FINAL_FONTSIZE_LEGEND,
        loc=LOC_LEGEND,
        frameon=LEGEND_FRAME_ON
    )
    if LEGEND_FRAME_ON:
        legend.get_frame().set_linewidth(FINAL_LINEWIDTH_LEGEND_FRAME)

    # 布局优化
    plt.tight_layout()
    return fig


# ==============================================================================
# ============================ 主程序入口（无需修改） =============================
# ==============================================================================
if __name__ == "__main__":
    # 打印全局配置信息
    print(f"\n📌 全局配置：")
    print(f"   线宽倍率：{GLOBAL_LINEWIDTH_SCALE} | 字体倍率：{GLOBAL_FONT_SIZE_SCALE}")
    print(f"   数据目录：{DATA_DIR}")
    print(f"   实部文件：{REAL_DATA_FILE} | 虚部文件：{IMAG_DATA_FILE}")
    print(f"   能量范围：{X_RANGE[0]} ~ {X_RANGE[1]} eV")
    print(f"   实部Y范围：{Y_RANGE_REAL[0]} ~ {Y_RANGE_REAL[1]} | 虚部Y范围：{Y_RANGE_IMAG[0]} ~ {Y_RANGE_IMAG[1]}")

    # 初始化绘图样式
    setup_plot_style()

    # 绘制实部和虚部图像
    real_fig = plot_dielectric_curve(is_real=True)
    imag_fig = plot_dielectric_curve(is_real=False)

    # 同时显示两个窗口
    if real_fig or imag_fig:
        plt.show()
    else:
        print("\n❌ 绘图失败：未成功读取任何数据文件")