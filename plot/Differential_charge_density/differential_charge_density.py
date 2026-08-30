import matplotlib.pyplot as plt
import numpy as np
import os
import glob  # 新增：用于解析通配符文件
from matplotlib.ticker import MultipleLocator
from io import StringIO
from typing import Optional, List

# ==============================================================================
# ============================ 全局可配置参数（用户仅需修改此区域）============================
# ==============================================================================
# ---------------------- 1. 全局缩放倍率（核心控制，1=基准值，>1放大，<1缩小） ----------------------
GLOBAL_LINEWIDTH_SCALE = 1.0  # 所有线条粗细的全局倍率（1=基准线宽）
GLOBAL_FONT_SIZE_SCALE = 1.0  # 所有字体大小的全局倍率（1=基准字体）

# ---------------------- 2. 文件路径与数据读取参数 ----------------------
CHARGE_DENSITY_FILE = "*.dat"  # 支持通配符（如*.dat、*.txt、data_*.txt等）
SKIP_ROWS = 0  # 读取数据时跳过的行数（0=不跳过，1=跳过第一行，以此类推）

# ---------------------- 3. 图表基础配置 ----------------------
FIGSIZE = (7.5,4.5)  # 图尺寸（宽, 高），单位：英寸
SHOW_GRID = False  # 网格显示开关（True=显示网格，False=隐藏网格）
GRID_ALPHA = 0.3  # 网格透明度（0-1）
GRID_LINESTYLE = '--'  # 网格线型

# ---------------------- 4. 边缘留白配置（单位：英寸，控制图表与画布边缘的距离） ----------------------
LEFT_MARGIN = 1.5  # 左侧留白（增大值=左侧空间变宽）
RIGHT_MARGIN = 0.5  # 右侧留白（增大值=右侧空间变宽）
TOP_MARGIN = 0.5  # 顶部留白（增大值=顶部空间变宽）
BOTTOM_MARGIN = 1  # 底部留白（增大值=底部空间变宽）

# ---------------------- 5. 坐标轴范围控制（设置为None则自动计算） ----------------------
X_LIMITS: Optional[list] = [0, 30]  # X轴显示区间 [最小值, 最大值]
Y_LIMITS: Optional[list] = [-0.06, 0.14]  # Y轴显示区间 [最小值, 最大值]

# ---------------------- 6. 垂直虚线配置（X轴位置，设置为None则不显示） ----------------------
X_LINE1 = 9.68436  # 第一条垂直虚线的X轴位置（Å）
X_LINE2 = 12.78602  # 第二条垂直虚线的X轴位置（Å）
LINE_DASH_COLOR = 'red'  # 虚线颜色
LINE_DASH_STYLE = '--'  # 虚线样式
LINE_DASH_ALPHA = 1.0  # 虚线透明度（0-1）

# ---------------------- 7. 数据曲线配置 ----------------------
LINE_COLORS = ['blue']  # 数据曲线颜色（多文件时循环使用）
LINE_STYLE = '-'  # 数据曲线线型

# ---------------------- 8. 文本显示参数 ----------------------
X_LABEL_TEXT = 'Z Distance (Å)'  # X轴标签
Y_LABEL_TEXT = '∆ρ (e/Å)'  # Y轴完整标签（直接包含单位，无需额外拼接）
LEGEND_LABEL = 'Differential Charge Density'  # 图例标签
SHOW_LEGEND = False  # 图例显示开关

# ---------------------- 9. 位置控制参数（距离单位：点/像素，可正可负） ----------------------
X_TICK_PAD = 10  # X轴刻度标签距离X轴的距离
Y_TICK_PAD = 10  # Y轴刻度标签距离Y轴的距离
X_LABEL_PAD = 10  # X轴标签文字距离X轴的距离
Y_LABEL_PAD = 4  # Y轴标签文字距离Y轴的距离
LEGEND_PAD = 5  # 图例内边距

# ---------------------- 10. 刻度配置 ----------------------
TICK_DIRECTION = 'in'  # 刻度方向：'in'（向内）/'out'（向外）/'inout'（双向）
X_TICK_DECIMAL_PLACES = 0  # X轴刻度保留小数位数
Y_TICK_DECIMAL_PLACES = 2  # Y轴刻度保留小数位数
X_TICK_INTERVAL = 5.0  # X轴主刻度间隔（Å）
X_MINOR_TICK_INTERVAL = 2.5  # X轴次刻度间隔（Å）
Y_TICK_INTERVAL = 0.04  # Y轴主刻度间隔
Y_MINOR_TICK_INTERVAL = 0.02  # Y轴次刻度间隔

# ---------------------- 11. 线宽基准值（最终=基准×GLOBAL_LINEWIDTH_SCALE） ----------------------
LINEWIDTH_BASE_DATA = 2.5  # 数据曲线线宽基准
LINEWIDTH_BASE_DASH = 2.5  # 垂直虚线线宽基准
LINEWIDTH_BASE_SPINE = 2.5  # 图表边框线宽基准
LINEWIDTH_BASE_TICK = 2.5  # 刻度线线宽基准
LINEWIDTH_BASE_TICK_LENGTH = 8  # 刻度长度基准（与线宽成比例）

# ---------------------- 12. 字体大小基准值（最终=基准×GLOBAL_FONT_SIZE_SCALE） ----------------------
FONTSIZE_BASE_X_TICK = 24  # X轴刻度字体大小基准
FONTSIZE_BASE_Y_TICK = 24  # Y轴刻度字体大小基准
FONTSIZE_BASE_X_LABEL = 28  # X轴标签字体大小基准
FONTSIZE_BASE_Y_LABEL = 28  # Y轴标签字体大小基准
FONTSIZE_BASE_LEGEND = 16  # 图例字体大小基准

# ---------------------- 13. 其他配置 ----------------------
PLT_USE_TEX = False  # 是否启用LaTeX渲染（False=禁用）
SAVE_FIGURE = False  # 是否保存图片（True=保存，False=仅显示）
SAVE_FIG_PREFIX = "charge_density"  # 保存图片前缀（多文件时自动添加文件名）
SAVE_FIG_DPI = 300  # 保存图片分辨率

# ==============================================================================
# ============================ 自动计算最终参数（无需修改） =============================
# ==============================================================================
# 线宽最终值 = 基准值 × 全局线宽倍率
FINAL_LINEWIDTH_DATA = LINEWIDTH_BASE_DATA * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_DASH = LINEWIDTH_BASE_DASH * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_SPINE = LINEWIDTH_BASE_SPINE * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_TICK = LINEWIDTH_BASE_TICK * GLOBAL_LINEWIDTH_SCALE
FINAL_TICK_LENGTH = LINEWIDTH_BASE_TICK_LENGTH * GLOBAL_LINEWIDTH_SCALE

# 字体大小最终值 = 基准值 × 全局字体倍率
FINAL_FONTSIZE_X_TICK = FONTSIZE_BASE_X_TICK * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_Y_TICK = FONTSIZE_BASE_Y_TICK * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_X_LABEL = FONTSIZE_BASE_X_LABEL * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_Y_LABEL = FONTSIZE_BASE_Y_LABEL * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_LEGEND = FONTSIZE_BASE_LEGEND * GLOBAL_FONT_SIZE_SCALE

# ==============================================================================
# ============================ 基础样式全局设置（无需修改） =============================
# ==============================================================================
plt.rcParams["font.family"] = ["DejaVu Sans", "sans-serif"]  # 统一无衬线字体
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示异常
plt.rcParams["text.usetex"] = PLT_USE_TEX  # LaTeX渲染开关


# ==============================================================================
# ============================ 工具函数（无需修改） =============================
# ==============================================================================
def load_charge_density_data(file_path: str) -> Optional[tuple[np.ndarray, np.ndarray]]:
    """
    加载差分电荷密度数据（支持跳过指定行数）

    Parameters:
        file_path: 数据文件路径

    Returns:
        (z_distance, delta_rho) 或 None（加载失败时）
    """
    # 尝试多种编码读取文件
    encodings = ['utf-16', 'utf-8-sig', 'utf-16le', 'utf-8']
    content = None

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        print(f"❌ 文件 {file_path}：所有编码尝试均失败，无法读取")
        return None

    # 解析数据（支持跳过指定行数）
    try:
        # 将内容按行分割，跳过前SKIP_ROWS行，再重新拼接
        lines = content.split('\n')
        if SKIP_ROWS > 0:
            lines = lines[SKIP_ROWS:]
            print(f"ℹ️  文件 {file_path}：已跳过前 {SKIP_ROWS} 行数据")
        filtered_content = '\n'.join([line.strip() for line in lines if line.strip()])

        data = np.loadtxt(StringIO(filtered_content), usecols=(0, 1))
        z_distance = data[:, 0]  # Z轴距离 (Å)
        delta_rho = data[:, 1]  # 差分电荷密度（单位：e/Å）

        # 打印数据信息
        print(f"\n✅ 处理文件：{file_path}")
        print(f"   数据点数：{len(z_distance)}")
        print(
            f"   Z轴距离范围：{z_distance.min():.{X_TICK_DECIMAL_PLACES}f} Å - {z_distance.max():.{X_TICK_DECIMAL_PLACES}f} Å")
        print(
            f"   差分电荷密度范围：{delta_rho.min():.{Y_TICK_DECIMAL_PLACES}f} e/Å - {delta_rho.max():.{Y_TICK_DECIMAL_PLACES}f} e/Å")

        return z_distance, delta_rho
    except Exception as e:
        print(f"❌ 文件 {file_path}：数据解析失败：{str(e)}")
        return None


def get_matching_files(pattern: str) -> List[str]:
    """
    根据通配符模式查找所有匹配的文件（按文件名排序）

    Parameters:
        pattern: 通配符模式（如*.dat、*.txt、data_*.txt等）

    Returns:
        匹配的文件路径列表（排序后）
    """
    # 查找所有匹配文件
    matching_files = glob.glob(pattern)
    # 过滤掉目录，只保留文件
    matching_files = [f for f in matching_files if os.path.isfile(f)]
    # 按文件名排序（确保结果可重复）
    matching_files.sort()
    return matching_files


# ==============================================================================
# ============================ 核心绘图函数（修改部分） =============================
# ==============================================================================
def plot_charge_density(z_distance: np.ndarray, delta_rho: np.ndarray, color: str, file_name: str = ""):
    """
    绘制差分电荷密度曲线

    Parameters:
        z_distance: Z轴距离数据
        delta_rho: 差分电荷密度数据
        color: 曲线颜色
        file_name: 当前绘制的文件名（用于保存时命名）
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

    # 1. 基础样式配置
    # 边框样式（最终线宽）
    for spine in ax.spines.values():
        spine.set_linewidth(FINAL_LINEWIDTH_SPINE)

    # 2. 绘制数据曲线
    ax.plot(
        z_distance, delta_rho,
        color=color,
        linewidth=FINAL_LINEWIDTH_DATA,
        linestyle=LINE_STYLE,
        label=LEGEND_LABEL
    )

    # 3. 绘制垂直虚线（根据用户设置）
    if X_LINE1 is not None:
        ax.axvline(
            x=X_LINE1,
            color=LINE_DASH_COLOR,
            linestyle=LINE_DASH_STYLE,
            linewidth=FINAL_LINEWIDTH_DASH,
            alpha=LINE_DASH_ALPHA
        )
    if X_LINE2 is not None:
        ax.axvline(
            x=X_LINE2,
            color=LINE_DASH_COLOR,
            linestyle=LINE_DASH_STYLE,
            linewidth=FINAL_LINEWIDTH_DASH,
            alpha=LINE_DASH_ALPHA
        )

    # 4. 坐标轴标签配置（直接使用合并后的Y轴标签）
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

    # 5. X轴刻度与范围设置
    if X_LIMITS is None:
        x_min = np.floor(z_distance.min() / X_TICK_INTERVAL) * X_TICK_INTERVAL
        x_max = np.ceil(z_distance.max() / X_TICK_INTERVAL) * X_TICK_INTERVAL
    else:
        x_min, x_max = X_LIMITS

    x_ticks = np.arange(x_min, x_max + X_TICK_INTERVAL, X_TICK_INTERVAL)
    ax.set_xticks(x_ticks)
    ax.set_xticklabels(
        [f'{t:.{X_TICK_DECIMAL_PLACES}f}' for t in x_ticks],
        fontsize=FINAL_FONTSIZE_X_TICK
    )

    # 6. Y轴刻度与范围设置
    if Y_LIMITS is None:
        y_min = np.floor(delta_rho.min() / Y_TICK_INTERVAL) * Y_TICK_INTERVAL
        y_max = np.ceil(delta_rho.max() / Y_TICK_INTERVAL) * Y_TICK_INTERVAL
    else:
        y_min, y_max = Y_LIMITS

    y_ticks = np.arange(y_min, y_max + Y_TICK_INTERVAL, Y_TICK_INTERVAL)
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(
        [f'{t:.{Y_TICK_DECIMAL_PLACES}f}' for t in y_ticks],
        fontsize=FINAL_FONTSIZE_Y_TICK
    )

    # 7. 刻度样式配置
    # 主刻度
    ax.tick_params(
        axis='x',
        which='major',
        direction=TICK_DIRECTION,
        labelsize=FINAL_FONTSIZE_X_TICK,
        pad=X_TICK_PAD,
        width=FINAL_LINEWIDTH_TICK,
        length=FINAL_TICK_LENGTH
    )
    ax.tick_params(
        axis='y',
        which='major',
        direction=TICK_DIRECTION,
        labelsize=FINAL_FONTSIZE_Y_TICK,
        pad=Y_TICK_PAD,
        width=FINAL_LINEWIDTH_TICK,
        length=FINAL_TICK_LENGTH
    )

    # 次刻度
    ax.xaxis.set_minor_locator(MultipleLocator(X_MINOR_TICK_INTERVAL))
    ax.yaxis.set_minor_locator(MultipleLocator(Y_MINOR_TICK_INTERVAL))
    ax.tick_params(
        axis='x',
        which='minor',
        direction=TICK_DIRECTION,
        width=FINAL_LINEWIDTH_TICK * 0.7,  # 次刻度线宽为主要刻度的70%
        length=FINAL_TICK_LENGTH * 0.6  # 次刻度长度为主要刻度的60%
    )
    ax.tick_params(
        axis='y',
        which='minor',
        direction=TICK_DIRECTION,
        width=FINAL_LINEWIDTH_TICK * 0.7,
        length=FINAL_TICK_LENGTH * 0.6
    )

    # 8. 网格配置（根据开关控制）
    if SHOW_GRID:
        ax.grid(
            True,
            alpha=GRID_ALPHA,
            linestyle=GRID_LINESTYLE,
            linewidth=FINAL_LINEWIDTH_TICK * 0.5
        )

    # 9. 图例配置
    if SHOW_LEGEND:
        ax.legend(
            fontsize=FINAL_FONTSIZE_LEGEND,
            loc='best',
            frameon=SHOW_GRID,  # 图例边框是否显示（与网格开关一致）
            fancybox=True,
            shadow=False,
            borderpad=LEGEND_PAD
        )

    # 10. 应用坐标轴范围
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)

    # 11. 布局优化与显示/保存（注释tight_layout，避免与留白配置冲突）
    # plt.tight_layout()
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
    print(f"📌 Global Configuration：")
    print(f"   Line width scale：{GLOBAL_LINEWIDTH_SCALE} | Font size scale：{GLOBAL_FONT_SIZE_SCALE}")
    print(f"   Data line width：{FINAL_LINEWIDTH_DATA:.2f} | Y-label font size：{FINAL_FONTSIZE_Y_LABEL:.0f}")
    print(f"   Figure size：{FIGSIZE} | Save figure：{SAVE_FIGURE} | Skip rows：{SKIP_ROWS}")
    print(f"   File pattern：{CHARGE_DENSITY_FILE}")
    print(f"   Margins：Left={LEFT_MARGIN}in | Right={RIGHT_MARGIN}in | Top={TOP_MARGIN}in | Bottom={BOTTOM_MARGIN}in")

    # 查找所有匹配的文件
    matching_files = get_matching_files(CHARGE_DENSITY_FILE)

    if not matching_files:
        print(f"\n❌ 错误：未找到匹配 {CHARGE_DENSITY_FILE} 的文件，请检查文件路径和通配符格式")
    else:
        print(f"\n✅ 找到 {len(matching_files)} 个匹配文件：")
        for i, file in enumerate(matching_files, 1):
            print(f"   {i}. {file}")

        # 遍历所有匹配文件，逐个绘图
        for file_idx, file_path in enumerate(matching_files):
            print(f"\n{'=' * 50} 处理文件 {file_idx + 1}/{len(matching_files)} {'=' * 50}")
            # 加载数据
            data = load_charge_density_data(file_path)
            if data is None:
                print(f"⚠️  跳过文件：{file_path}（加载失败）")
                continue

            z_distance, delta_rho = data

            # 获取当前文件的颜色（循环使用颜色列表）
            color = LINE_COLORS[file_idx % len(LINE_COLORS)]

            # 绘图
            plot_charge_density(z_distance, delta_rho, color, file_path)

        print(f"\n🎉 所有文件处理完成！")