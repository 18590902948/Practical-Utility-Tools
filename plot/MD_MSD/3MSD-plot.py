import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from matplotlib.ticker import MultipleLocator, AutoMinorLocator, FuncFormatter

# ====================== 核心时间参数（优先修改！） =======================
POTIM = 2.0  # 步长，单位：fs/步（VASP MD的POTIM参数，优先确认并修改）
time_unit = "ps"  # X轴显示单位（可选："fs" 或 "ps"）

# ====================== 文件与绘图基础参数 =======================
msd_file = "MSD.txt"  # 输入的MSD数据文件（第一列=离子步NSW）
save_fig = "MSD_plot.png"  # 输出图片文件名
figsize = (10, 6)  # 图片尺寸（宽, 高）

# 坐标轴范围（按time_unit单位设置，设为None则自动识别）
x_range = [0,100]  # 关键修正：改回None，自动适配X轴范围（如需手动设则填[min, max]，如[0, 50]）
y_range = [0,2]  # 自动适配即可

# 字体配置
font_family = "DejaVu Sans"  # 字体
font_size_global = 24  # 全局基础字体大小
font_size_x_tick = 20  # X轴刻度字体大小
font_size_y_tick = 20  # Y轴刻度字体大小
font_size_x_label = 24  # X轴标签字体大小
font_size_y_label = 24  # Y轴标签字体大小
font_size_legend = 20  # 图例字体大小

# 线条配置
line_width = 2.5  # 曲线线宽
line_width_spine = 2.5  # 边框线宽
line_width_tick = 2.5  # 主刻度线宽
line_width_tick_minor = 2.0  # 子刻度线宽

# 刻度配置（重点修改：X轴刻度间隔改小！）
tick_length_major = 8.0  # 主刻度长度（像素）
tick_length_minor = 6.0  # 子刻度长度（像素）
x_major_tick = 20  # 改为0.5（按ps单位，每0.5ps一个刻度，适配短时间模拟）
y_major_tick = 0.5  # Y轴主刻度间隔（单位Å²）
x_tick_pad = 8  # X轴刻度数字与X轴的距离（像素）
y_tick_pad = 8  # Y轴刻度数字与Y轴的距离（像素）
x_label_pad = 10  # X轴标签与X轴的距离（像素）
y_label_pad = 10  # Y轴标签与Y轴的距离（像素）
x_decimal_places = 0  # X轴刻度小数点后位数
y_decimal_places = 1  # Y轴刻度小数点后位数

# 元素颜色（按出现顺序分配）
default_element_colors = [
    '#FF0000',  # 第一个元素：红色（Al）
    '#0000FF',  # 第二个元素：蓝色（O）
    '#008000',  # 第三个元素：绿色
    '#FFFF00'  # 第四个元素：黄色
]


# ==================================================================

def plot_msd():
    # 1. 读取MSD数据（第一列=离子步NSW）
    df = pd.read_csv(msd_file, sep=r"\s+", header=0)
    df.rename(columns={df.columns[0]: "step"}, inplace=True)
    print("成功读取MSD数据，列名：", df.columns.tolist())
    print(f"模拟步长POTIM={POTIM} fs/步，X轴显示单位={time_unit}")

    # 2. 自动识别元素
    elements = []
    for col in df.columns:
        if col.endswith("_total"):
            elem = col.replace("_total", "")
            elements.append(elem)
    if not elements:
        raise ValueError("未找到以'_total'结尾的列，请检查MSD.txt的列头格式！")
    print(f"识别到的元素（按顺序）：{elements}")

    # 3. 计算模拟时间（修正精度：避免浮点误差）
    nsw_steps = df["step"].values.astype(np.float64)  # 转为浮点型，避免整数运算误差
    time_fs = nsw_steps * POTIM
    if time_unit == "fs":
        time_display = time_fs
    elif time_unit == "ps":
        time_display = time_fs / 1000.0  # 明确浮点除法
    else:
        raise ValueError("time_unit仅支持'fs'或'ps'")
    df["time_display"] = time_display
    print(f"总模拟步数：{int(nsw_steps[-1])} 步")
    print(f"总模拟时间：{time_display[-1]:.2f} {time_unit}（{time_fs[-1]:.0f} fs）")

    # 4. 绘图基础设置
    plt.rcParams["font.family"] = font_family
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=figsize)

    # 5. 绘制曲线
    for idx, elem in enumerate(elements):
        msd_total = df[f"{elem}_total"].values
        color = default_element_colors[idx] if idx < len(default_element_colors) else plt.cm.tab10(idx)
        ax.plot(df["time_display"], msd_total, label=elem, color=color, linewidth=line_width)

    # 6. 坐标轴精细控制
    # 边框线宽
    for spine in ax.spines.values():
        spine.set_linewidth(line_width_spine)

    # 刻度设置
    ax.tick_params(axis='x', which='major', direction='in', width=line_width_tick, length=tick_length_major,
                   labelsize=font_size_x_tick, pad=x_tick_pad)
    ax.tick_params(axis='y', which='major', direction='in', width=line_width_tick, length=tick_length_major,
                   labelsize=font_size_y_tick, pad=y_tick_pad)
    ax.tick_params(which='minor', direction='in', width=line_width_tick_minor, length=tick_length_minor)

    # 刻度间隔
    ax.xaxis.set_major_locator(MultipleLocator(x_major_tick))
    ax.yaxis.set_major_locator(MultipleLocator(y_major_tick))
    ax.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))

    # 刻度格式化
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.{x_decimal_places}f}"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.{y_decimal_places}f}"))

    # 坐标轴范围（修复X轴逻辑）
    if x_range is None:
        x_min = df["time_display"].min()
        x_max = df["time_display"].max()
        # 自动扩展5%的范围，避免曲线贴边
        x_pad = 0.05 * (x_max - x_min)
        ax.set_xlim([x_min - x_pad, x_max + x_pad])
    else:
        # 确保手动设置的x_range是[min, max]格式
        if len(x_range) != 2:
            raise ValueError("手动设置x_range时必须传入包含2个值的列表，如[0, 50]")
        ax.set_xlim(x_range)

    if y_range is None:
        all_msd = np.concatenate([df[f"{e}_total"].values for e in elements])
        y_min = min(all_msd)
        y_max = max(all_msd)
        # 自动扩展范围，Y轴从0开始（MSD不可能为负）
        y_pad_min = 0.1 * (y_max - y_min)
        y_pad_max = 0.5 * (y_max - y_min)
        ax.set_ylim([max(y_min - y_pad_min, 0), y_max + y_pad_max])
    else:
        if len(y_range) != 2:
            raise ValueError("手动设置y_range时必须传入包含2个值的列表，如[0, 10]")
        ax.set_ylim(y_range)

    # 坐标轴标签
    ax.set_xlabel(f"Simulation Time ({time_unit})", fontsize=font_size_x_label, labelpad=x_label_pad)
    ax.set_ylabel("MSD (Å²)", fontsize=font_size_y_label, labelpad=y_label_pad)

    # 图例：修改loc为upper right（右上角）
    ax.legend(frameon=False, fontsize=font_size_legend, loc="upper right")

    # 保存+显示
    plt.tight_layout()
    plt.savefig(save_fig, dpi=300, bbox_inches="tight")
    print(f"MSD图已保存至：{save_fig}")
    plt.show()


if __name__ == "__main__":
    plot_msd()