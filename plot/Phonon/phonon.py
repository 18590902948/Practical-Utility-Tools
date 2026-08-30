import matplotlib.pyplot as plt
import numpy as np
import re
from typing import List, Tuple, Optional, Dict

# ==============================================================================
# ============================ 全局可配置参数（用户仅需修改此区域）============================
# ==============================================================================
# ---------------------- 1. 全局缩放倍率（核心控制，1=基准值，>1放大，<1缩小） ----------------------
GLOBAL_LINEWIDTH_SCALE = 1.0  # 所有线条粗细的全局倍率（1=基准线宽）
GLOBAL_FONT_SIZE_SCALE = 1.0  # 所有字体大小的全局倍率（1=基准字体）

# ---------------------- 2. 文件路径参数 ----------------------
BAND_LABELS_FILE = 'band.conf'  # 高对称点标签配置文件
PHONON_DATA_FILE = 'phonon.txt'  # 声子谱数据文件

# ---------------------- 3. 高对称点标签位置参数 ----------------------
S0S2_LABEL_OFFSET = -0.01  # S0|S2标签水平偏移（负值左移，正值右移）
F_LABEL_OFFSET = 0.015  # F标签水平偏移（负值左移，正值右移）
LABEL_VERTICAL_OFFSET_RATIO = 0.02  # 垂直偏移比例（减小该值可使标签上移）
LABEL_HORIZONTAL_PAD = 8  # 高对称点标签水平内边距（替代labelpad）

# ---------------------- 4. 文本显示参数（空字符串则不显示） ----------------------
TITLE_TEXT = ''  # 图表标题（声子谱一般无需标题）
X_LABEL_TEXT = ''  # X轴标签（声子谱X轴为高对称点，一般不显示）
Y_LABEL_TEXT = 'Frequency (THz)'  # Y轴标签

# ---------------------- 5. 位置控制参数（距离单位：点/像素，可正可负） ----------------------
X_TICK_LABEL_PAD = 8  # X轴刻度标签距离X轴的距离
X_LABEL_PAD = 10  # X轴标签文字距离X轴的距离
Y_TICK_LABEL_PAD = 8  # Y轴刻度标签距离Y轴的距离
Y_LABEL_PAD = 10  # Y轴标签文字距离Y轴的距离
TITLE_PAD = 12  # 标题距离图表上边框的距离

# ---------------------- 6. 视觉样式 - 颜色 ----------------------
PHONON_LINE_COLOR = 'blue'  # 声子谱曲线颜色
REFERENCE_LINE_COLOR = 'red'  # Y=0参考线颜色
HIGH_SYM_LINE_COLOR = 'gray'  # 高对称点竖线颜色
SPINE_COLOR = 'black'  # 图表边框颜色

# ---------------------- 7. 视觉样式 - 线宽基准值（最终=基准×GLOBAL_LINEWIDTH_SCALE） ----------------------
LINEWIDTH_BASE_PHONON = 2.5  # 声子谱曲线线宽基准
LINEWIDTH_BASE_REFERENCE = 2.5  # Y=0参考线线宽基准
LINEWIDTH_BASE_HIGH_SYM = 2.5  # 高对称点竖线线宽基准
LINEWIDTH_BASE_SPINE = 2.5  # 图表边框线宽基准
LINEWIDTH_BASE_TICK = 2.5  # 刻度线线宽基准
LINEWIDTH_BASE_TICK_LENGTH = 8  # 刻度长度基准（与线宽成比例）

# ---------------------- 8. 视觉样式 - 字体大小基准值（最终=基准×GLOBAL_FONT_SIZE_SCALE） ----------------------
FONTSIZE_BASE_TITLE = 20  # 标题字体大小基准
FONTSIZE_BASE_X_TICK = 20  # X轴刻度字体大小基准
FONTSIZE_BASE_X_LABEL = 24  # X轴标签字体大小基准
FONTSIZE_BASE_Y_TICK = 20  # Y轴刻度字体大小基准
FONTSIZE_BASE_Y_LABEL = 20  # Y轴标签字体大小基准

# ---------------------- 9. 视觉样式 - 刻度配置 ----------------------
TICK_DIRECTION = 'in'  # 刻度方向：'in'（向内）/'out'（向外）/'inout'（双向）
Y_TICK_DECIMAL = 0  # Y轴刻度保留小数位数（0=整数，1=一位小数）

# ---------------------- 10. Y=0参考线专属配置 ----------------------
REFERENCE_LINE_POSITION = 0.0  # 参考线Y轴位置（默认0）
REFERENCE_LINE_LINestyle = '--'  # 参考线线型：'--'/'-'/':'/'-.'等
REFERENCE_LINE_ALPHA = 0.8  # 参考线透明度（0-1）

# ---------------------- 11. 高对称点竖线配置 ----------------------
HIGH_SYM_LINE_LINestyle = '--'  # 高对称点竖线线型
HIGH_SYM_LINE_ALPHA = 0.5  # 高对称点竖线透明度（0-1）

# ---------------------- 12. 其他配置 ----------------------
FIGSIZE = (6, 10)  # 图尺寸（宽, 高），单位：英寸
PLT_USE_TEX = False  # 是否启用LaTeX渲染（False=禁用）

# ==============================================================================
# ============================ 自动计算最终参数（无需修改） =============================
# ==============================================================================
# 线宽最终值 = 基准值 × 全局线宽倍率
FINAL_LINEWIDTH_PHONON = LINEWIDTH_BASE_PHONON * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_REFERENCE = LINEWIDTH_BASE_REFERENCE * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_HIGH_SYM = LINEWIDTH_BASE_HIGH_SYM * GLOBAL_LINEWIDTH_SCALE
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
def convert_latex_label(label: str) -> str:
    """将LaTeX格式标签转换为带角标的普通文本（如Γ、S₀等）"""
    # 替换Gamma符号
    label = label.replace('$\\Gamma$', 'Γ').replace('\\Gamma', 'Γ')
    # 移除多余的$符号
    label = label.replace('$', '')
    # 替换数字下标
    subscript_map = {'0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
                     '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉'}
    label = re.sub(r'_(\d)', lambda m: subscript_map.get(m.group(1), m.group(0)), label)
    return label

def merge_underscore_labels(raw_labels: List[str]) -> List[str]:
    """合并相邻的带下划线标签（如S_0和S_2合并为S₀|S₂）"""
    merged = []
    i = 0
    while i < len(raw_labels):
        current = raw_labels[i]
        # 合并相邻的带下划线标签
        if '_' in current and i + 1 < len(raw_labels) and '_' in raw_labels[i + 1]:
            merged.append(f"{convert_latex_label(current)}|{convert_latex_label(raw_labels[i + 1])}")
            i += 2
        else:
            merged.append(convert_latex_label(current))
            i += 1
    return merged

def load_high_symmetry_points() -> Tuple[List[str], List[float]]:
    """加载高对称点标签和坐标（从band.conf和phonon.dat读取）"""
    klabels, klabel_coords = [], []

    # 读取高对称点标签
    try:
        with open(BAND_LABELS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r'BAND_LABELS\s*=\s*([^\n]+)', content)
            if match:
                raw_labels = [l for l in re.split(r'\s+', match.group(1).strip()) if l]
                klabels = merge_underscore_labels(raw_labels)
            else:
                raise ValueError("未找到BAND_LABELS定义")
    except Exception as e:
        print(f"⚠️  高对称点标签读取错误：{str(e)}")

    # 读取高对称点坐标
    try:
        with open(PHONON_DATA_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if len(lines) >= 2:
                second_line = lines[1].strip()
                coords_str = second_line.split('#')[1].strip() if '#' in second_line else second_line
                klabel_coords = [float(c) for c in re.split(r'\s+', coords_str) if c]
            else:
                raise ValueError("phonon.dat行数不足，至少需要2行")
    except Exception as e:
        print(f"⚠️  高对称点坐标读取错误：{str(e)}")

    # 校验并截断不匹配的标签/坐标
    if len(klabels) != len(klabel_coords):
        min_len = min(len(klabels), len(klabel_coords))
        klabels, klabel_coords = klabels[:min_len], klabel_coords[:min_len]
        print(f"⚠️  警告：标签数量与坐标数量不匹配，已截断至{min_len}个")

    return klabels, klabel_coords

def load_phonon_data() -> List[np.ndarray]:
    """加载声子谱数据（从phonon.dat读取）"""
    phonon_blocks = []
    try:
        with open(PHONON_DATA_FILE, 'r', encoding='utf-8') as f:
            # 跳过前两行头部信息
            lines = f.readlines()[2:]
            current_block = []
            for line in lines:
                line = line.strip()
                if line:
                    current_block.append([float(x) for x in re.split(r'\s+', line) if x])
                else:
                    if current_block:
                        phonon_blocks.append(np.array(current_block))
                        current_block = []
            # 处理最后一个数据块
            if current_block:
                phonon_blocks.append(np.array(current_block))

        if not phonon_blocks:
            raise ValueError("未找到有效的声子数据块")
        print(f"✅ 成功读取{len(phonon_blocks)}个声子数据块")
    except Exception as e:
        print(f"❌ 声子数据读取错误：{str(e)}")

    return phonon_blocks

# ==============================================================================
# ============================ 核心绘图函数（无需修改） =============================
# ==============================================================================
def plot_phonon_spectrum():
    """绘制声子谱主函数"""
    # 1. 加载数据
    klabels, klabel_coords = load_high_symmetry_points()
    phonon_blocks = load_phonon_data()

    # 2. 创建画布
    fig, ax = plt.subplots(figsize=FIGSIZE)

    # 3. 基础样式配置
    # 边框样式（最终线宽+颜色）
    for spine in ax.spines.values():
        spine.set_linewidth(FINAL_LINEWIDTH_SPINE)
        spine.set_color(SPINE_COLOR)

    # 标题配置（空则不显示，最终字体+位置）
    if TITLE_TEXT:
        ax.set_title(
            TITLE_TEXT,
            fontsize=FINAL_FONTSIZE_TITLE,
            pad=TITLE_PAD
        )

    # 坐标轴标签配置（最终字体+位置）
    if X_LABEL_TEXT:
        ax.set_xlabel(
            X_LABEL_TEXT,
            fontsize=FINAL_FONTSIZE_X_LABEL,
            labelpad=X_LABEL_PAD
        )
    if Y_LABEL_TEXT:
        ax.set_ylabel(
            Y_LABEL_TEXT,
            fontsize=FINAL_FONTSIZE_Y_LABEL,
            labelpad=Y_LABEL_PAD
        )

    # 4. 数据绘图（数据加载成功时）
    if phonon_blocks and klabels and klabel_coords:
        # 绘制声子谱曲线（最终线宽+颜色）
        for block in phonon_blocks:
            k = block[:, 0]
            freqs = block[:, 1:]
            for freq in freqs.T:
                ax.plot(k, freq, color=PHONON_LINE_COLOR, linewidth=FINAL_LINEWIDTH_PHONON)

        # 绘制Y=0参考线（最终线宽+专属配置）
        ax.axhline(
            y=REFERENCE_LINE_POSITION,
            color=REFERENCE_LINE_COLOR,
            linestyle=REFERENCE_LINE_LINestyle,
            alpha=REFERENCE_LINE_ALPHA,
            linewidth=FINAL_LINEWIDTH_REFERENCE
        )

        # 绘制高对称点竖线（最终线宽+专属配置）
        for coord in klabel_coords:
            ax.axvline(
                x=coord,
                color=HIGH_SYM_LINE_COLOR,
                linestyle=HIGH_SYM_LINE_LINestyle,
                alpha=HIGH_SYM_LINE_ALPHA,
                linewidth=FINAL_LINEWIDTH_HIGH_SYM
            )

        # 设置X轴刻度（高对称点坐标）
        ax.set_xticks(klabel_coords)
        ax.set_xticklabels(['' for _ in klabels])  # 隐藏默认标签

        # 手动添加高对称点标签（最终字体+位置偏移）
        y_lim = ax.get_ylim()
        y_pos = y_lim[0] - LABEL_VERTICAL_OFFSET_RATIO * (y_lim[1] - y_lim[0])
        for label, coord in zip(klabels, klabel_coords):
            # 水平偏移调整
            if label == 'S₀|S₂':
                x_pos = coord + S0S2_LABEL_OFFSET
            elif label == 'F':
                x_pos = coord + F_LABEL_OFFSET
            else:
                x_pos = coord

            # 添加标签文本（最终字体大小，移除错误的labelpad参数）
            ax.text(
                x_pos, y_pos, label,
                fontsize=FINAL_FONTSIZE_X_TICK,
                ha='center', va='top'  # 仅保留支持的参数
            )

        # 设置X轴范围（适配数据）
        all_k = np.concatenate([b[:, 0] for b in phonon_blocks])
        ax.set_xlim(min(all_k.min(), min(klabel_coords)), max(all_k.max(), max(klabel_coords)))

    # 数据加载失败时显示提示
    else:
        ax.text(
            0.5, 0.5, 'Data loading failed',  # 改用英文避免字体问题
            ha='center', va='center',
            fontsize=FINAL_FONTSIZE_X_TICK,
            color='red'
        )

    # 5. 刻度样式配置（最终参数）
    # Y轴刻度配置（方向+最终线宽/长度/字体）
    ax.tick_params(
        axis='y',
        labelsize=FINAL_FONTSIZE_Y_TICK,
        width=FINAL_LINEWIDTH_TICK,
        length=FINAL_TICK_LENGTH,
        direction=TICK_DIRECTION,
        pad=Y_TICK_LABEL_PAD
    )

    # X轴刻度配置（无标签，仅样式）
    ax.tick_params(
        axis='x',
        width=FINAL_LINEWIDTH_TICK,
        length=FINAL_TICK_LENGTH,
        direction=TICK_DIRECTION,
        pad=X_TICK_LABEL_PAD
    )

    # Y轴刻度小数点格式
    ax.yaxis.set_major_formatter(plt.FormatStrFormatter(f'%.{Y_TICK_DECIMAL}f'))

    # 6. 布局优化+显示
    plt.tight_layout()
    plt.show()

# ==============================================================================
# ============================ 主程序入口（无需修改） =============================
# ==============================================================================
if __name__ == "__main__":
    # 打印全局缩放信息（便于调试）
    print(f"\n📌 Global Configuration：")
    print(f"   Line width scale：{GLOBAL_LINEWIDTH_SCALE} | Font size scale：{GLOBAL_FONT_SIZE_SCALE}")
    print(f"   Phonon line width：{FINAL_LINEWIDTH_PHONON:.2f} | Y-label font size：{FINAL_FONTSIZE_Y_LABEL:.0f}")

    # 执行绘图
    plot_phonon_spectrum()