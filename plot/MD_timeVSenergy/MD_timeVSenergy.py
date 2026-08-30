import matplotlib.pyplot as plt
import numpy as np
import os
import glob
import re
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
from typing import Optional, Dict, Any, List

# ==============================================================================
# ============================ 全局可配置参数（用户仅需修改此区域）============================
# ==============================================================================
# ---------------------- 1. 全局缩放倍率（核心控制，1=基准值，>1放大，<1缩小） ----------------------
GLOBAL_LINEWIDTH_SCALE = 1.0  # 所有线条粗细的全局倍率（1=基准线宽）
GLOBAL_FONT_SIZE_SCALE = 1.0  # 所有字体大小的全局倍率（1=基准字体）

# ---------------------- 2. 文件路径参数 ----------------------
DATA_DIR = os.path.dirname(os.path.abspath(__file__))  # 数据文件目录（默认脚本所在目录）
DATA_SUFFIX = "energy3.txt"  # 数据文件后缀（支持通配符，如"*.dat"）
RECURSIVE_SEARCH = False  # 是否递归查找子目录中的数据文件
TARGET_FILES = []  # 指定具体文件（优先级最高，如["AIMD300.dat", "AIMD400.dat"]）

# ---------------------- 3. 核心计算参数 ----------------------
POTIM = 2  # 每步的时间长度（fs），根据模拟设置修改
X_UNIT = 'ps'  # X轴显示单位，可选：'ps'（皮秒） / 'fs'（飞秒）
ENERGY_OFFSET = -898.55705664  # 能量偏移值（用于能量校正）

# ---------------------- 4. 文本显示参数（空字符串则不显示） ----------------------
TITLE_TEXT = ''  # 图表标题（示例：'AIMD 300K Energy Evolution'）
X_LABEL_TEXT = 'Simulation Time ({unit})'  # X轴标签（{unit}自动替换为X_UNIT）
Y_LABEL_TEXT = 'Energy (eV)'  # Y轴标签
LEGEND_LABEL_GLOBAL = 'AIMD 1500 K'  # 全局统一图例（所有文件共用，空则不使用）
LEGEND_LABELS = []  # 多文件分别指定图例（与TARGET_FILES顺序对应，优先级最高）
# 示例：TARGET_FILES = ["AIMD300.dat", "AIMD400.dat"] 时，可设置：
# LEGEND_LABELS = ["300 K", "400 K"] （一一对应）

# ---------------------- 5. 位置控制参数（距离单位：点/像素，可正可负） ----------------------
# 图表矩形边框距离控制
X_TICK_LABEL_PAD = 8  # X轴刻度数值 距离 X轴（图表左边框）的距离
X_LABEL_PAD = 10  # X轴标签文字 距离 X轴（图表左边框）的距离
Y_TICK_LABEL_PAD = 8  # Y轴刻度数值 距离 Y轴（图表下边框）的距离
Y_LABEL_PAD = 10  # Y轴标签文字 距离 Y轴（图表下边框）的距离
TITLE_PAD = 12  # 标题文字 距离 图表上边框的距离

# ---------------------- 6. 视觉样式 - 颜色 ----------------------
LINE_COLORS = ['blue', 'green', 'red', 'purple', 'orange']  # 多文件循环颜色
MD_LINE_COLOR = 'blue'  # 单文件曲线颜色（优先级低于循环颜色）

# ---------------------- 7. 视觉样式 - 线宽基准值（最终=基准×GLOBAL_LINEWIDTH_SCALE） ----------------------
LINEWIDTH_BASE_CURVE = 2.5  # MD曲线线宽基准
LINEWIDTH_BASE_SPINE = 2.5  # 图表边框线宽基准
LINEWIDTH_BASE_GRID = 2.5  # 网格线宽基准（开启时生效）
LINEWIDTH_BASE_TICK_MAJOR = 2.5  # 主刻度线宽基准
LINEWIDTH_BASE_TICK_MINOR = 1.25  # 子刻度线宽基准
LINEWIDTH_BASE_LEGEND_FRAME = 1.25  # 图例边框线宽基准

# ---------------------- 8. 视觉样式 - 字体大小基准值（最终=基准×GLOBAL_FONT_SIZE_SCALE） ----------------------
FONTSIZE_BASE_TITLE = 28  # 标题字体大小基准
FONTSIZE_BASE_X_TICK = 24  # X轴刻度字体大小基准
FONTSIZE_BASE_X_LABEL = 28  # X轴标签字体大小基准
FONTSIZE_BASE_Y_TICK = 24  # Y轴刻度字体大小基准
FONTSIZE_BASE_Y_LABEL = 28  # Y轴标签字体大小基准
FONTSIZE_BASE_LEGEND = 24  # 图例字体大小基准

# ---------------------- 9. 视觉样式 - 刻度长度基准值（最终=基准×GLOBAL_LINEWIDTH_SCALE） ----------------------
TICKLENGTH_BASE_MAJOR = 8.0  # 主刻度长度基准
TICKLENGTH_BASE_MINOR = 6.0  # 子刻度长度基准

# ---------------------- 10. 视觉样式 - 坐标轴范围（按X_UNIT单位设置） ----------------------
X_RANGE = [0, 50]  # X轴固定范围 [起始时间, 结束时间]（支持任意中间区间）
Y_RANGE = [0,40]  # Y轴固定范围 [最小值, 最大值]

# ---------------------- 11. 视觉样式 - 刻度配置 ----------------------
# 刻度间隔（按X_UNIT单位设置）
X_MAJOR_TICK = 10.0  # X轴主刻度间隔（30~50ps建议设为5，更清晰）
Y_MAJOR_TICK = 10  # Y轴主刻度间隔
X_MINOR_TICK = X_MAJOR_TICK * 0.5  # X轴子刻度间隔（主刻度的0.5）
Y_MINOR_TICK = Y_MAJOR_TICK * 0.5  # Y轴子刻度间隔（主刻度的0.5）

# 刻度方向（默认向内）：'in'（向内）/'out'（向外）/'inout'（双向）
TICK_DIRECTION = 'in'

# 刻度小数点位数（0=整数，1=一位小数，以此类推）
X_TICK_DECIMAL = 0  # X轴刻度保留小数位数
Y_TICK_DECIMAL = 0  # Y轴刻度保留小数位数

# ---------------------- 12. 视觉样式 - 网格 ----------------------
GRID_ON = False  # 网格线开关（True/False）
GRID_ALPHA = 0.3  # 网格透明度（0-1）
GRID_LINestyle = '--'  # 网格线型（'--'/'-'/':'等）

# ---------------------- 13. 视觉样式 - 图例 ----------------------
LOC_LEGEND = 'best'  # 图例位置：'best'/'upper left'/'upper right'/'lower left'/'lower right'
LEGEND_FRAME_ON = False  # 图例边框开关（True/False）

# ---------------------- 14. 其他配置 ----------------------
FIGSIZE = (8, 6)  # 图尺寸（宽, 高），单位：英寸

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
FINAL_FONTSIZE_X_TICK = FONTSIZE_BASE_X_TICK * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_X_LABEL = FONTSIZE_BASE_X_LABEL * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_Y_TICK = FONTSIZE_BASE_Y_TICK * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_Y_LABEL = FONTSIZE_BASE_Y_LABEL * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_LEGEND = FONTSIZE_BASE_LEGEND * GLOBAL_FONT_SIZE_SCALE

# 刻度长度最终值 = 基准值 × 全局线宽倍率
FINAL_TICKLENGTH_MAJOR = TICKLENGTH_BASE_MAJOR * GLOBAL_LINEWIDTH_SCALE
FINAL_TICKLENGTH_MINOR = TICKLENGTH_BASE_MINOR * GLOBAL_LINEWIDTH_SCALE

# ==============================================================================
# ============================ 基础样式全局设置（无需修改） =============================
# ==============================================================================
plt.rcParams["font.family"] = ["DejaVu Sans", "sans-serif"]  # 统一无衬线字体
plt.rcParams["axes.unicode_minus"] = False  # 解决负号显示异常问题


# ==============================================================================
# ============================ 工具函数（无需修改） =============================
# ==============================================================================
def get_target_dat_files() -> List[str]:
    """
    获取目标.dat文件列表：
    1. 优先使用用户指定的TARGET_FILES
    2. 否则从DATA_DIR查找符合DATA_SUFFIX的文件
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
    search_pattern = os.path.join(DATA_DIR, DATA_SUFFIX)
    dat_files = glob.glob(search_pattern, recursive=RECURSIVE_SEARCH)

    # 转换为绝对路径并去重
    dat_files = [os.path.abspath(f) for f in dat_files if os.path.isfile(f)]
    return dat_files


def format_legend_label(file_path: str, file_index: int) -> str:
    """
    格式化图例标签（优先级：LEGEND_LABELS > LEGEND_LABEL_GLOBAL > 自动格式化）
    :param file_path: 文件路径
    :param file_index: 文件索引（用于匹配LEGEND_LABELS）
    :return: 最终图例文本
    """
    # 1. 优先使用多文件分别指定的图例（与文件顺序对应）
    if LEGEND_LABELS and file_index < len(LEGEND_LABELS):
        label = LEGEND_LABELS[file_index].strip()
        if label:  # 非空字符串才使用
            return label

    # 2. 其次使用全局统一图例
    if LEGEND_LABEL_GLOBAL.strip():
        return LEGEND_LABEL_GLOBAL.strip()

    # 3. 最后自动格式化（AIMD300 → AIMD 300 K）
    file_base_name = os.path.splitext(os.path.basename(file_path))[0]
    match = re.match(r'(AIMD)(\d+)', file_base_name)
    return f"{match.group(1)} {match.group(2)} K" if match else file_base_name


def calculate_simulation_time(steps: np.ndarray, potim: int, unit: str) -> np.ndarray:
    """
    计算每个数据点的模拟时间（适配单位切换）
    :param steps: 步数数组
    :param potim: 每步步长（fs）
    :param unit: 目标单位（ps/fs）
    :return: 每个数据点对应的时间数组（对应单位）
    """
    time_fs = steps * potim
    if unit == 'ps':
        return time_fs / 1000  # fs → ps（1ps=1000fs）
    elif unit == 'fs':
        return time_fs
    raise ValueError(f"不支持的X轴单位：{unit}，仅支持 'ps' 或 'fs'")


def get_tick_kwargs(axis: str) -> Dict[str, Any]:
    """生成刻度配置通用参数（减少重复代码）"""
    base_kwargs = {
        'direction': TICK_DIRECTION,
        'pad': X_TICK_LABEL_PAD if axis == 'x' else Y_TICK_LABEL_PAD,
        'labelsize': FINAL_FONTSIZE_X_TICK if axis == 'x' else FINAL_FONTSIZE_Y_TICK
    }
    return base_kwargs


# ==============================================================================
# ============================ 核心绘图函数（关键修改区域） =============================
# ==============================================================================
def process_dat_file(file_path: str, color: str, file_index: int) -> None:
    """处理单个.dat文件并绘制能量-时间曲线（支持任意时间区间筛选）"""
    file_name = os.path.basename(file_path)
    try:
        # 1. 读取数据（列索引：0=步数，1=温度，2=能量）
        data = np.loadtxt(file_path)
        if data.ndim != 2 or data.shape[1] < 3:
            raise ValueError(f"数据格式错误：需至少3列（步数、温度、能量），当前{data.shape}")

        steps, temperature, energy = data[:, 0], data[:, 1], data[:, 2]
        NSW_ACTUAL = len(steps)  # 从文件行数获取实际总步数
        print(f"\n=== 处理文件：{file_name} ===")

        # 2. 能量校正
        energy = energy - ENERGY_OFFSET

        # 3. 计算每个数据点的精确时间（关键修改1：不再只算总时间，而是每个点的时间）
        time_data_full = calculate_simulation_time(steps, POTIM, X_UNIT)
        total_time = time_data_full[-1]  # 实际总时间（最后一个点的时间）

        # 4. 解析目标时间范围（支持任意起始/结束时间）
        target_min_time = X_RANGE[0]
        target_max_time = X_RANGE[1]

        # 边界修正：避免目标时间超出实际总时间范围
        if target_min_time < 0:
            target_min_time = 0.0
            print(f"⚠️  警告：起始时间小于0，自动修正为0 {X_UNIT}")
        if target_max_time > total_time:
            target_max_time = total_time
            print(f"⚠️  警告：结束时间大于实际总时间（{total_time:.1f} {X_UNIT}），自动修正为{total_time:.1f} {X_UNIT}")
        if target_min_time >= target_max_time:
            raise ValueError(f"时间范围无效：起始时间（{target_min_time}）≥ 结束时间（{target_max_time}）")

        # 5. 按时间区间筛选数据点（核心修改2：精准提取中间区间）
        # 生成布尔索引：只保留时间在[target_min_time, target_max_time]之间的点
        mask = (time_data_full >= target_min_time) & (time_data_full <= target_max_time)
        # 筛选数据
        steps_filtered = steps[mask]
        energy_filtered = energy[mask]
        temperature_filtered = temperature[mask]
        time_data_filtered = time_data_full[mask]

        # 验证筛选结果
        if len(time_data_filtered) == 0:
            raise ValueError(f"无匹配数据：实际时间范围（0~{total_time:.1f} {X_UNIT}）与目标范围（{target_min_time}~{target_max_time} {X_UNIT}）无重叠")

        # 6. 打印调试信息（清晰展示筛选逻辑）
        print(f"🔧 核心参数：POTIM={POTIM}fs | X轴单位={X_UNIT} | 能量偏移={ENERGY_OFFSET}")
        print(f"📊 原始数据：总步数={NSW_ACTUAL} | 总时长={total_time:.{X_TICK_DECIMAL}f} {X_UNIT}")
        print(f"🎯 目标范围：{target_min_time:.{X_TICK_DECIMAL}f}~{target_max_time:.{X_TICK_DECIMAL}f} {X_UNIT}")
        print(f"📋 筛选后：保留点数={len(steps_filtered)} | 实际显示时间={time_data_filtered[0]:.{X_TICK_DECIMAL}f}~{time_data_filtered[-1]:.{X_TICK_DECIMAL}f} {X_UNIT}")
        print(f"🌡️ 温度范围：{temperature_filtered.min():.1f}K ~ {temperature_filtered.max():.1f}K | 平均={np.mean(temperature_filtered):.1f}K")
        print(f"⚡ 能量范围：{energy_filtered.min():.{Y_TICK_DECIMAL}f} ~ {energy_filtered.max():.{Y_TICK_DECIMAL}f} eV")
        print(f"🎨 样式参数：线宽倍率={GLOBAL_LINEWIDTH_SCALE} | 字体倍率={GLOBAL_FONT_SIZE_SCALE}")

        # 7. 创建画布
        fig, ax = plt.subplots(figsize=FIGSIZE)

        # 8. 绘制曲线（使用筛选后的中间数据）
        legend_label = format_legend_label(file_path, file_index)
        ax.plot(
            time_data_filtered, energy_filtered,  # 关键修改3：用筛选后的时间和能量数据
            color=color,
            linewidth=FINAL_LINEWIDTH_CURVE,
            label=legend_label
        )

        # 9. 文本配置（位置+显示控制）
        if TITLE_TEXT:
            ax.set_title(
                TITLE_TEXT,
                fontsize=FINAL_FONTSIZE_TITLE,
                pad=TITLE_PAD
            )
        if X_LABEL_TEXT:
            ax.set_xlabel(
                X_LABEL_TEXT.format(unit=X_UNIT),
                fontsize=FINAL_FONTSIZE_X_LABEL,
                labelpad=X_LABEL_PAD
            )
        if Y_LABEL_TEXT:
            ax.set_ylabel(
                Y_LABEL_TEXT,
                fontsize=FINAL_FONTSIZE_Y_LABEL,
                labelpad=Y_LABEL_PAD
            )

        # 10. 坐标轴范围（严格锁定目标区间）
        ax.set_xlim([target_min_time, target_max_time])
        ax.set_ylim(Y_RANGE)

        # 11. 刻度基础配置（适配中间区间）
        ax.xaxis.set_major_locator(MultipleLocator(X_MAJOR_TICK))
        ax.yaxis.set_major_locator(MultipleLocator(Y_MAJOR_TICK))
        ax.xaxis.set_minor_locator(MultipleLocator(X_MINOR_TICK))
        ax.yaxis.set_minor_locator(MultipleLocator(Y_MINOR_TICK))

        ax.xaxis.set_major_formatter(FormatStrFormatter(f'%.{X_TICK_DECIMAL}f'))
        ax.yaxis.set_major_formatter(FormatStrFormatter(f'%.{Y_TICK_DECIMAL}f'))

        # 12. 刻度样式
        ax.tick_params(
            axis='x', which='major',
            length=FINAL_TICKLENGTH_MAJOR,
            width=FINAL_LINEWIDTH_TICK_MAJOR,
            **get_tick_kwargs('x')
        )
        ax.tick_params(
            axis='x', which='minor',
            length=FINAL_TICKLENGTH_MINOR,
            width=FINAL_LINEWIDTH_TICK_MINOR,
            **get_tick_kwargs('x')
        )
        ax.tick_params(
            axis='y', which='major',
            length=FINAL_TICKLENGTH_MAJOR,
            width=FINAL_LINEWIDTH_TICK_MAJOR,
            **get_tick_kwargs('y')
        )
        ax.tick_params(
            axis='y', which='minor',
            length=FINAL_TICKLENGTH_MINOR,
            width=FINAL_LINEWIDTH_TICK_MINOR,
            **get_tick_kwargs('y')
        )

        # 13. 图表边框线宽
        for spine in ax.spines.values():
            spine.set_linewidth(FINAL_LINEWIDTH_SPINE)

        # 14. 网格配置
        if GRID_ON:
            ax.grid(
                True, alpha=GRID_ALPHA,
                linestyle=GRID_LINestyle, linewidth=FINAL_LINEWIDTH_GRID
            )

        # 15. 图例配置
        if legend_label:
            legend = ax.legend(
                fontsize=FINAL_FONTSIZE_LEGEND,
                loc=LOC_LEGEND,
                frameon=LEGEND_FRAME_ON
            )
            if LEGEND_FRAME_ON:
                legend.get_frame().set_linewidth(FINAL_LINEWIDTH_LEGEND_FRAME)

        # 16. 布局优化+显示
        plt.tight_layout()
        plt.show()

    except Exception as e:
        print(f"\n❌ 处理文件 {file_name} 失败：{str(e)}")


# ==============================================================================
# ============================ 主程序入口（无需修改） =============================
# ==============================================================================
if __name__ == "__main__":
    # 打印全局配置信息
    print(f"\n📌 全局配置：")
    print(f"   线宽倍率：{GLOBAL_LINEWIDTH_SCALE} | 字体倍率：{GLOBAL_FONT_SIZE_SCALE}")
    print(f"   数据目录：{DATA_DIR} | 文件后缀：{DATA_SUFFIX}")
    print(f"   递归查找：{RECURSIVE_SEARCH} | 指定文件：{TARGET_FILES if TARGET_FILES else '无'}")
    print(f"   图例配置：全局图例='{LEGEND_LABEL_GLOBAL}' | 多文件图例={LEGEND_LABELS if LEGEND_LABELS else '无'}")
    print(f"   时间配置：POTIM={POTIM}fs | 目标范围={X_RANGE[0]}-{X_RANGE[1]} {X_UNIT}")

    # 获取目标文件
    dat_files = get_target_dat_files()

    if not dat_files:
        print("❌ 错误：未找到任何符合条件的.dat文件")
    else:
        print(f"✅ 发现 {len(dat_files)} 个.dat文件，开始处理...")
        for idx, file_path in enumerate(dat_files):
            color = LINE_COLORS[idx % len(LINE_COLORS)]
            process_dat_file(file_path, color, file_index=idx)