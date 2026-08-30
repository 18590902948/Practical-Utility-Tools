import matplotlib.pyplot as plt
import numpy as np
import os
import glob
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
from io import StringIO
from typing import Optional, Dict, Any, List, Tuple

# ==============================================================================
# ============================ 全局可配置参数（用户仅需修改此区域）============================
# ==============================================================================
# ---------------------- 1. 全局缩放倍率（核心控制，1=基准值，>1放大，<1缩小） ----------------------
GLOBAL_LINEWIDTH_SCALE = 1.0  # 所有线条粗细的全局倍率（1=基准线宽）
GLOBAL_FONT_SIZE_SCALE = 1.0  # 所有字体大小的全局倍率（1=基准字体）

# ---------------------- 2. 文件路径与数据读取参数 ----------------------
DATA_DIR = os.path.dirname(os.path.abspath(__file__))  # 数据文件目录（默认脚本所在目录）
DATA_PATTERN = "*.dat"  # 支持通配符（如*.dat、*.txt、data_*.dat等）
TARGET_FILES = ["PLANAR_AVERAGE.dat"]  # 指定具体文件（优先级最高，空列表则不指定）
RECURSIVE_SEARCH = False  # 是否递归查找子目录中的文件
SKIP_ROWS = 0  # 读取数据时跳过的行数（0=不跳过，1=跳过第一行，以此类推）

# ---------------------- 3. 图表基础配置 ----------------------
FIGSIZE = (7.5, 4.5)  # 图尺寸（宽, 高），单位：英寸
SHOW_GRID = False  # 网格显示开关（True=显示网格，False=隐藏网格）
GRID_ALPHA = 0.3  # 网格透明度（0-1）
GRID_LINESTYLE = '--'  # 网格线型（'--'/'-'/':'等）

# ---------------------- 4. 边缘留白配置（单位：英寸，控制图表与画布边缘的距离） ----------------------
LEFT_MARGIN = 1.5  # 左侧留白（默认0.8英寸，增大值=左侧空间变宽）
RIGHT_MARGIN = 0.5  # 右侧留白（默认0.5英寸，增大值=右侧空间变宽）
TOP_MARGIN = 0.5  # 顶部留白（默认0.5英寸，增大值=顶部空间变宽）
BOTTOM_MARGIN = 1.0  # 底部留白（默认0.8英寸，增大值=底部空间变宽）

# ---------------------- 5. 坐标轴范围控制（设置为None则自动计算） ----------------------
X_LIMITS = [0, 30]  # X轴显示区间 [最小值, 最大值]（Å）
Y_LIMITS = [-25, 15]  # Y轴显示区间 [最小值, 最大值]（eV）

# ---------------------- 6. 垂直虚线配置（X轴位置，空列表则不显示） ----------------------
X_VERTICAL_LINES = [9.68436, 12.78602]  # 垂直虚线位置列表（示例：[10.0, 20.0]）
LINE_DASH_COLOR = 'red'  # 虚线颜色
LINE_DASH_STYLE = '--'  # 虚线样式
LINE_DASH_ALPHA = 1.0  # 虚线透明度（0-1）

# ---------------------- 7. 水平虚线&Y平均值计算配置（=== 新增 ===） ----------------------
# 第一个Y平均值计算区间（X起始, X结束），对应绘制水平虚线
X_AVG1_RANGE = [6.53768, 9.68436]
# 第二个Y平均值计算区间（X起始, X结束），对应绘制水平虚线
X_AVG2_RANGE = [12.78602, 17.33238]
# 水平虚线样式（黑色虚线，固定配置，无需修改）
H_LINE_COLOR = 'black'  # 水平虚线颜色
H_LINE_STYLE = '--'  # 水平虚线样式
H_LINE_ALPHA = 1.0  # 水平虚线透明度
H_LINE_LABEL = None  # 水平虚线图例（None则不显示）

# ---------------------- 8. 数据曲线配置 ----------------------
LINE_COLORS = ['blue']  # 数据曲线颜色（多文件时循环使用）
LINE_STYLE = '-'  # 数据曲线线型
CURVE_COLOR = 'blue'  # 单文件曲线颜色（优先级低于循环颜色）

# ---------------------- 9. 文本显示参数（空字符串则不显示） ----------------------
TITLE_TEXT = ''  # 图表标题（示例：'Planar Average Electrostatic Potential'）
X_LABEL_TEXT = 'Z Distance (Å)'  # X轴标签
Y_LABEL_TEXT = ' φ (eV)'  # Y轴标签（直接包含单位）
LEGEND_LABEL = 'Planar Average Electrostatic Potential'  # 图例标签
SHOW_LEGEND = False  # 图例显示开关

# ---------------------- 10. 位置控制参数（距离单位：点/像素，可正可负） ----------------------
X_TICK_PAD = 10  # X轴刻度标签距离X轴的距离
Y_TICK_PAD = 10  # Y轴刻度标签距离Y轴的距离
X_LABEL_PAD = 10  # X轴标签文字距离X轴的距离
Y_LABEL_PAD = 10  # Y轴标签文字距离Y轴的距离
TITLE_PAD = 12  # 标题文字距离图表上边框的距离
LEGEND_PAD = 5  # 图例内边距

# ---------------------- 11. 刻度配置 ----------------------
TICK_DIRECTION = 'in'  # 刻度方向：'in'（向内）/'out'（向外）/'inout'（双向）
X_TICK_DECIMAL_PLACES = 0  # X轴刻度保留小数位数
Y_TICK_DECIMAL_PLACES = 2  # === 修改 ===：Y均值打印保留2位小数，此处同步调整
X_TICK_INTERVAL = 5.0  # X轴主刻度间隔（Å）
X_MINOR_TICK_INTERVAL = 2.5  # X轴次刻度间隔（Å）
Y_TICK_INTERVAL = 10  # Y轴主刻度间隔（eV）
Y_MINOR_TICK_INTERVAL = 5  # Y轴次刻度间隔（eV）

# ---------------------- 12. 线宽基准值（最终=基准×GLOBAL_LINEWIDTH_SCALE） ----------------------
LINEWIDTH_BASE_DATA = 2.5  # 数据曲线线宽基准
LINEWIDTH_BASE_DASH = 2.5  # 垂直虚线线宽基准
LINEWIDTH_BASE_HLINE = 2.5  # === 新增 ===：水平虚线线宽基准
LINEWIDTH_BASE_SPINE = 2.5  # 图表边框线宽基准
LINEWIDTH_BASE_GRID = 2.5  # 网格线宽基准（开启时生效）
LINEWIDTH_BASE_TICK_MAJOR = 2.5  # 主刻度线宽基准
LINEWIDTH_BASE_TICK_MINOR = 1.25  # 次刻度线宽基准
LINEWIDTH_BASE_LEGEND_FRAME = 1.25  # 图例边框线宽基准

# ---------------------- 13. 刻度长度基准值（最终=基准×GLOBAL_LINEWIDTH_SCALE） ----------------------
TICKLENGTH_BASE_MAJOR = 8.0  # 主刻度长度基准（单位：点）
TICKLENGTH_BASE_MINOR = 6.0  # 次刻度长度基准（单位：点）

# ---------------------- 14. 字体大小基准值（最终=基准×GLOBAL_FONT_SIZE_SCALE） ----------------------
FONTSIZE_BASE_TITLE = 28  # 标题字体大小基准
FONTSIZE_BASE_X_TICK = 24  # X轴刻度字体大小基准
FONTSIZE_BASE_X_LABEL = 28  # X轴标签字体大小基准
FONTSIZE_BASE_Y_TICK = 24  # Y轴刻度字体大小基准
FONTSIZE_BASE_Y_LABEL = 28  # Y轴标签字体大小基准
FONTSIZE_BASE_LEGEND = 24  # 图例字体大小基准

# ---------------------- 15. 其他配置 ----------------------
PLT_USE_TEX = False  # 是否启用LaTeX渲染（False=禁用）
SAVE_FIGURE = False  # 是否保存图片（True=保存，False=仅显示）
SAVE_FIG_PREFIX = "electrostatic_potential"  # 保存图片前缀（多文件时自动添加文件名）
SAVE_FIG_DPI = 300  # 保存图片分辨率
SUPPORTED_ENCODINGS = ['utf-16', 'utf-8-sig', 'utf-16le', 'utf-8']  # 文件编码尝试列表
LEGEND_FRAME_ON = False  # 图例边框开关（True/False）
LOC_LEGEND = 'best'  # 图例位置：'best'/'upper left'等

# ==============================================================================
# ============================ 自动计算最终参数（无需修改） =============================
# ==============================================================================
# 线宽最终值 = 基准值 × 全局线宽倍率
FINAL_LINEWIDTH_DATA = LINEWIDTH_BASE_DATA * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_DASH = LINEWIDTH_BASE_DASH * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_HLINE = LINEWIDTH_BASE_HLINE * GLOBAL_LINEWIDTH_SCALE  # === 新增 ===
FINAL_LINEWIDTH_SPINE = LINEWIDTH_BASE_SPINE * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_GRID = LINEWIDTH_BASE_GRID * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_TICK_MAJOR = LINEWIDTH_BASE_TICK_MAJOR * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_TICK_MINOR = LINEWIDTH_BASE_TICK_MINOR * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_LEGEND_FRAME = LINEWIDTH_BASE_LEGEND_FRAME * GLOBAL_LINEWIDTH_SCALE

# 刻度长度最终值 = 基准值 × 全局线宽倍率（保持与线宽的视觉协调）
FINAL_TICKLENGTH_MAJOR = TICKLENGTH_BASE_MAJOR * GLOBAL_LINEWIDTH_SCALE  # 主刻度最终长度
FINAL_TICKLENGTH_MINOR = TICKLENGTH_BASE_MINOR * GLOBAL_LINEWIDTH_SCALE  # 次刻度最终长度

# 字体大小最终值 = 基准值 × 全局字体倍率
FINAL_FONTSIZE_TITLE = FONTSIZE_BASE_TITLE * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_X_TICK = FONTSIZE_BASE_X_TICK * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_X_LABEL = FONTSIZE_BASE_X_LABEL * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_Y_TICK = FONTSIZE_BASE_Y_TICK * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_Y_LABEL = FONTSIZE_BASE_Y_LABEL * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_LEGEND = FONTSIZE_BASE_LEGEND * GLOBAL_FONT_SIZE_SCALE

# ==============================================================================
# ============================ 基础样式全局设置（无需修改） =============================
# ==============================================================================
plt.rcParams["font.family"] = ["DejaVu Sans", "sans-serif"]  # 统一无衬线字体
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示异常问题
plt.rcParams["text.usetex"] = PLT_USE_TEX  # LaTeX渲染开关


# ==============================================================================
# ============================ 工具函数（无需修改） =============================
# ==============================================================================
def get_target_files() -> List[str]:
    """
    获取目标数据文件列表：
    1. 优先使用用户指定的TARGET_FILES
    2. 否则从DATA_DIR查找符合DATA_PATTERN的文件
    """
    # 优先使用指定文件
    if TARGET_FILES:
        target_files = []
        for file in TARGET_FILES:
            file_path = os.path.join(DATA_DIR, file)
            if os.path.exists(file_path):
                target_files.append(file_path)
            else:
                print(f"⚠️  警告：指定文件 {file} 不存在于 {DATA_DIR}")
        return target_files

    # 否则查找目录中的文件
    search_pattern = os.path.join(DATA_DIR, DATA_PATTERN)
    target_files = glob.glob(search_pattern, recursive=RECURSIVE_SEARCH)

    # 转换为绝对路径并去重，过滤目录
    target_files = [os.path.abspath(f) for f in target_files if os.path.isfile(f)]
    target_files.sort()  # 按文件名排序，确保结果可重复
    return target_files


def read_file_with_multiple_encodings(file_path: str) -> Optional[str]:
    """
    尝试多种编码读取文件，返回文件内容
    :param file_path: 文件路径
    :return: 文件内容（None表示所有编码尝试失败）
    """
    for encoding in SUPPORTED_ENCODINGS:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return None


def load_electrostatic_potential_data(file_path: str) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """
    加载静电势数据（支持跳过指定行数）
    :param file_path: 文件路径
    :return: (z_distance, electrostatic_potential) 或 None（加载失败）
    """
    # 读取文件内容
    content = read_file_with_multiple_encodings(file_path)
    if content is None:
        print(f"❌ 文件 {os.path.basename(file_path)}：所有编码尝试均失败，无法读取")
        return None

    # 解析数据（支持跳过指定行数）
    try:
        # 将内容按行分割，跳过前SKIP_ROWS行，再重新拼接
        lines = content.split('\n')
        if SKIP_ROWS > 0:
            lines = lines[SKIP_ROWS:]
            print(f"ℹ️  文件 {os.path.basename(file_path)}：已跳过前 {SKIP_ROWS} 行数据")
        filtered_content = '\n'.join([line.strip() for line in lines if line.strip()])

        data = np.loadtxt(StringIO(filtered_content), usecols=(0, 1))
        z_distance = data[:, 0]  # Z轴距离 (Å)
        electrostatic_potential = data[:, 1]  # 静电势（eV）
        return z_distance, electrostatic_potential
    except Exception as e:
        print(f"❌ 文件 {os.path.basename(file_path)}：数据解析失败：{str(e)}")
        return None


def print_data_info(file_name: str, z_distance: np.ndarray, potential: np.ndarray) -> None:
    """打印数据基本信息（美化输出）"""
    print(f"\n=== 处理文件：{file_name} ===")
    print(f"📊 数据点数：{len(z_distance)}")
    print(
        f"📏 Z轴距离范围：{z_distance.min():.{X_TICK_DECIMAL_PLACES}f} Å - {z_distance.max():.{X_TICK_DECIMAL_PLACES}f} Å")
    print(
        f"⚡ 静电势范围：{potential.min():.{Y_TICK_DECIMAL_PLACES}f} eV - {potential.max():.{Y_TICK_DECIMAL_PLACES}f} eV")


# === 新增 ===：计算指定X区间内的Y值平均值
def calculate_y_average_in_x_range(z: np.ndarray, y: np.ndarray, x_start: float, x_end: float) -> Optional[float]:
    """
    计算指定X区间 [x_start, x_end] 内的Y值平均值
    :param z: X轴数据（z距离）
    :param y: Y轴数据（静电势）
    :param x_start: X区间起始值
    :param x_end: X区间结束值
    :return: 平均值（None表示区间内无数据点）
    """
    # 筛选X在区间内的索引
    mask = (z >= x_start) & (z <= x_end)
    y_in_range = y[mask]

    if len(y_in_range) == 0:
        return None
    # 计算平均值
    return np.mean(y_in_range)


def get_tick_kwargs(axis: str) -> Dict[str, Any]:
    """生成刻度配置通用参数（减少重复代码）"""
    base_kwargs = {
        'direction': TICK_DIRECTION,
        'pad': X_TICK_PAD if axis == 'x' else Y_TICK_PAD,
        'labelsize': FINAL_FONTSIZE_X_TICK if axis == 'x' else FINAL_FONTSIZE_Y_TICK
    }
    return base_kwargs


# ==============================================================================
# ============================ 核心绘图函数（修改部分） =============================
# ==============================================================================
# === 修改 ===：新增4个参数，接收两个区间的X范围和Y平均值
def plot_electrostatic_potential(z_distance: np.ndarray, potential: np.ndarray,
                                 color: str, file_name: str = "",
                                 x1_range: List[float] = None, y1_avg: float = None,
                                 x2_range: List[float] = None, y2_avg: float = None) -> None:
    """
    绘制静电势曲线
    :param z_distance: Z轴距离数据
    :param potential: 静电势数据
    :param color: 曲线颜色
    :param file_name: 当前绘制的文件名（用于保存时命名）
    :param x1_range: 第一个平均区间X范围 [start, end]
    :param y1_avg: 第一个区间的Y平均值
    :param x2_range: 第二个平均区间X范围 [start, end]
    :param y2_avg: 第二个区间的Y平均值
    """
    # 创建画布
    fig, ax = plt.subplots(figsize=FIGSIZE)

    # 应用边缘留白配置（关键修改：控制图表与画布边缘的距离）
    plt.subplots_adjust(
        left=LEFT_MARGIN / FIGSIZE[0],  # 左侧留白比例 = 实际留白/图宽
        right=1 - RIGHT_MARGIN / FIGSIZE[0],  # 右侧留白比例 = 1 - 实际留白/图宽
        top=1 - TOP_MARGIN / FIGSIZE[1],  # 顶部留白比例 = 1 - 实际留白/图高
        bottom=BOTTOM_MARGIN / FIGSIZE[1]  # 底部留白比例 = 实际留白/图高
    )

    # 1. 基础样式配置：图表边框线宽
    for spine in ax.spines.values():
        spine.set_linewidth(FINAL_LINEWIDTH_SPINE)

    # 2. 绘制数据曲线
    ax.plot(
        z_distance, potential,
        color=color,
        linewidth=FINAL_LINEWIDTH_DATA,
        linestyle=LINE_STYLE,
        label=LEGEND_LABEL if SHOW_LEGEND else ''
    )

    # 3. 绘制垂直虚线（遍历配置列表）
    for x_pos in X_VERTICAL_LINES:
        if x_pos is not None and isinstance(x_pos, (int, float)):
            ax.axvline(
                x=x_pos,
                color=LINE_DASH_COLOR,
                linestyle=LINE_DASH_STYLE,
                linewidth=FINAL_LINEWIDTH_DASH,
                alpha=LINE_DASH_ALPHA
            )

    # === 新增 ===：绘制水平虚线（两个区间，仅当有平均值时绘制）
    if x1_range and y1_avg is not None:
        ax.hlines(y=y1_avg, xmin=x1_range[0], xmax=x1_range[1],
                  color=H_LINE_COLOR, linestyle=H_LINE_STYLE,
                  linewidth=FINAL_LINEWIDTH_HLINE, alpha=H_LINE_ALPHA,
                  label=H_LINE_LABEL)
    if x2_range and y2_avg is not None:
        ax.hlines(y=y2_avg, xmin=x2_range[0], xmax=x2_range[1],
                  color=H_LINE_COLOR, linestyle=H_LINE_STYLE,
                  linewidth=FINAL_LINEWIDTH_HLINE, alpha=H_LINE_ALPHA,
                  label=H_LINE_LABEL)

    # 4. 文本配置
    # 标题
    if TITLE_TEXT:
        ax.set_title(
            TITLE_TEXT,
            fontsize=FINAL_FONTSIZE_TITLE,
            pad=TITLE_PAD
        )
    # X轴标签
    ax.set_xlabel(
        X_LABEL_TEXT,
        fontsize=FINAL_FONTSIZE_X_LABEL,
        labelpad=X_LABEL_PAD
    )
    # Y轴标签
    ax.set_ylabel(
        Y_LABEL_TEXT,
        fontsize=FINAL_FONTSIZE_Y_LABEL,
        labelpad=Y_LABEL_PAD
    )

    # 5. 坐标轴范围
    if X_LIMITS is not None:
        ax.set_xlim(X_LIMITS)
    else:
        x_min = np.floor(z_distance.min() / X_TICK_INTERVAL) * X_TICK_INTERVAL
        x_max = np.ceil(z_distance.max() / X_TICK_INTERVAL) * X_TICK_INTERVAL
        ax.set_xlim(x_min, x_max)

    if Y_LIMITS is not None:
        ax.set_ylim(Y_LIMITS)
    else:
        y_min = np.floor(potential.min() / Y_TICK_INTERVAL) * Y_TICK_INTERVAL
        y_max = np.ceil(potential.max() / Y_TICK_INTERVAL) * Y_TICK_INTERVAL
        ax.set_ylim(y_min, y_max)

    # 6. 刻度配置
    # 主/次刻度间隔
    ax.xaxis.set_major_locator(MultipleLocator(X_TICK_INTERVAL))
    ax.yaxis.set_major_locator(MultipleLocator(Y_TICK_INTERVAL))
    ax.xaxis.set_minor_locator(MultipleLocator(X_MINOR_TICK_INTERVAL))
    ax.yaxis.set_minor_locator(MultipleLocator(Y_MINOR_TICK_INTERVAL))

    # 刻度小数点格式
    ax.xaxis.set_major_formatter(FormatStrFormatter(f'%.{X_TICK_DECIMAL_PLACES}f'))
    ax.yaxis.set_major_formatter(FormatStrFormatter(f'%.{Y_TICK_DECIMAL_PLACES}f'))

    # 刻度样式（方向/长度/线宽/字体/距离）
    # X轴主刻度
    ax.tick_params(
        axis='x', which='major',
        length=FINAL_TICKLENGTH_MAJOR,
        width=FINAL_LINEWIDTH_TICK_MAJOR,
        **get_tick_kwargs('x')
    )
    # X轴次刻度
    ax.tick_params(
        axis='x', which='minor',
        length=FINAL_TICKLENGTH_MINOR,
        width=FINAL_LINEWIDTH_TICK_MINOR,
        **get_tick_kwargs('x')
    )
    # Y轴主刻度
    ax.tick_params(
        axis='y', which='major',
        length=FINAL_TICKLENGTH_MAJOR,
        width=FINAL_LINEWIDTH_TICK_MAJOR,
        **get_tick_kwargs('y')
    )
    # Y轴次刻度
    ax.tick_params(
        axis='y', which='minor',
        length=FINAL_TICKLENGTH_MINOR,
        width=FINAL_LINEWIDTH_TICK_MINOR,
        **get_tick_kwargs('y')
    )

    # 7. 网格配置
    if SHOW_GRID:
        ax.grid(
            True, alpha=GRID_ALPHA,
            linestyle=GRID_LINESTYLE, linewidth=FINAL_LINEWIDTH_GRID
        )

    # 8. 图例配置
    if SHOW_LEGEND and LEGEND_LABEL:
        legend = ax.legend(
            fontsize=FINAL_FONTSIZE_LEGEND,
            loc=LOC_LEGEND,
            frameon=LEGEND_FRAME_ON,
            borderpad=LEGEND_PAD
        )
        if LEGEND_FRAME_ON:
            legend.get_frame().set_linewidth(FINAL_LINEWIDTH_LEGEND_FRAME)

    # 9. 布局优化与显示/保存（注意：subplots_adjust已手动配置，tight_layout可根据需要选择是否启用）
    # plt.tight_layout()  # 若留白配置与tight_layout冲突，可注释此行
    if SAVE_FIGURE:
        # 多文件时按“前缀_文件名.png”保存，单文件时直接用前缀
        if file_name:
            file_base = os.path.splitext(os.path.basename(file_name))[0]
            save_path = f"{SAVE_FIG_PREFIX}_{file_base}.png"
        else:
            save_path = f"{SAVE_FIG_PREFIX}.png"
        plt.savefig(save_path, dpi=SAVE_FIG_DPI, bbox_inches='tight')
        print(f"\n📁 图片已保存为：{save_path}")
    plt.show()


# ==============================================================================
# ============================ 主程序入口（修改部分） =============================
# ==============================================================================
if __name__ == "__main__":
    # 打印全局配置信息
    print(f"\n📌 全局配置：")
    print(f"   线宽倍率：{GLOBAL_LINEWIDTH_SCALE} | 字体倍率：{GLOBAL_FONT_SIZE_SCALE}")
    print(f"   数据目录：{DATA_DIR} | 文件模式：{DATA_PATTERN}")
    print(f"   递归查找：{RECURSIVE_SEARCH} | 指定文件：{TARGET_FILES if TARGET_FILES else '无'}")
    print(f"   跳过行数：{SKIP_ROWS} | 保存图片：{SAVE_FIGURE}")
    print(f"   垂直虚线位置：{X_VERTICAL_LINES if X_VERTICAL_LINES else '无'}")
    # === 新增 ===：打印Y平均值计算区间
    print(f"   Y均值计算区间1：X∈{X_AVG1_RANGE} Å | 区间2：X∈{X_AVG2_RANGE} Å")
    print(f"   坐标轴范围：X={X_LIMITS} Å | Y={Y_LIMITS} eV")
    print(f"   刻度长度：主刻度={TICKLENGTH_BASE_MAJOR}pt | 次刻度={TICKLENGTH_BASE_MINOR}pt（已乘线宽倍率）")
    print(f"   边缘留白：左={LEFT_MARGIN}in | 右={RIGHT_MARGIN}in | 上={TOP_MARGIN}in | 下={BOTTOM_MARGIN}in")

    # 获取目标文件
    target_files = get_target_files()

    if not target_files:
        print("\n❌ 错误：未找到任何符合条件的数据文件")
    else:
        print(f"\n✅ 发现 {len(target_files)} 个数据文件，开始处理...")
        for idx, file_path in enumerate(target_files):
            print(f"\n{'=' * 50} 处理文件 {idx + 1}/{len(target_files)} {'=' * 50}")
            # 加载数据
            data = load_electrostatic_potential_data(file_path)
            if data is None:
                print(f"⚠️  跳过文件：{os.path.basename(file_path)}（加载失败）")
                continue

            z_distance, potential = data

            # 打印数据信息
            print_data_info(os.path.basename(file_path), z_distance, potential)

            # === 新增 ===：计算两个区间的Y平均值并格式化打印
            y1_average = calculate_y_average_in_x_range(z_distance, potential, X_AVG1_RANGE[0], X_AVG1_RANGE[1])
            y2_average = calculate_y_average_in_x_range(z_distance, potential, X_AVG2_RANGE[0], X_AVG2_RANGE[1])

            # 打印第一个区间结果
            if y1_average is not None:
                print(
                    f"⚡ 区间1 [X={X_AVG1_RANGE[0]:.6f}~{X_AVG1_RANGE[1]:.6f} Å] 平均静电势：{y1_average:.{Y_TICK_DECIMAL_PLACES}f} eV")
            else:
                print(f"⚠️  区间1 [X={X_AVG1_RANGE[0]:.6f}~{X_AVG1_RANGE[1]:.6f} Å] 无数据点，无法计算平均值")

            # 打印第二个区间结果
            if y2_average is not None:
                print(
                    f"⚡ 区间2 [X={X_AVG2_RANGE[0]:.6f}~{X_AVG2_RANGE[1]:.6f} Å] 平均静电势：{y2_average:.{Y_TICK_DECIMAL_PLACES}f} eV")
            else:
                print(f"⚠️  区间2 [X={X_AVG2_RANGE[0]:.6f}~{X_AVG2_RANGE[1]:.6f} Å] 无数据点，无法计算平均值")

            # 获取当前文件的颜色（循环使用颜色列表）
            color = LINE_COLORS[idx % len(LINE_COLORS)]

            # === 修改 ===：传递水平虚线的区间和平均值给绘图函数
            plot_electrostatic_potential(z_distance, potential, color, file_path,
                                         X_AVG1_RANGE, y1_average,
                                         X_AVG2_RANGE, y2_average)

        print(f"\n🎉 所有文件处理完成！")