import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, AutoMinorLocator

# ====================== 核心配置参数（用户按需修改） =======================
# 1. 模拟基础参数
NSW = 50000  # 步数（即dat文件除去表头的行数）
POTIM = 2.0  # 每步时间（单位：fs）
x_major_tick = 20.0  # X轴（时间）主刻度间隔（单位：ps）
x_axis_range = [0, 100]  # X轴范围（手动设为0到100ps，确保显示100刻度）

# 2. 数据列选择（从1开始计数！）
bond_data_col = 1  # 键长数据列（1=第1列，2=第2列，以此类推）
angle_data_col = 1  # 键角数据列（1=第1列，2=第2列，以此类推）

# 3. Y轴配置（区间形式：[最小值, 最大值]）
bond_y_range = [1.4, 2.0]  # 键长Y轴范围（单位：Å）
angle_y_range = [100, 180]  # 键角Y轴范围（单位：°）
bond_y_major_tick = 0.1  # 键长Y轴主刻度间隔（单位：Å）
angle_y_major_tick = 20.0  # 键角Y轴主刻度间隔（单位：°）

# 4. 刻度/标签与轴的距离控制
x_tick_pad = 8  # X轴刻度数字与X轴的距离（单位：pt）
x_label_pad = 12  # X轴标签与X轴的距离（单位：pt）
y_tick_pad = 8  # Y轴刻度数字与Y轴的距离（单位：pt）
y_label_pad = 12  # Y轴标签与Y轴的距离（单位：pt）

# 5. 线条颜色控制（新增！支持英文颜色名/十六进制码/RGB值）
bond_line_color = 'blue'  # 键长曲线颜色（例：'red'/'#FF0000'/(1,0,0)）
angle_line_color = 'red'  # 键角曲线颜色（例：'green'/'#00FF00'/(0,1,0)）

# 6. 通用绘图样式
line_width = 2.5  # 曲线线宽
font_size_global = 28  # 全局基础字体大小
font_size_tick = 24  # 刻度标签字体大小
font_size_label = 28  # 坐标轴标签字体大小
fig_size = (10, 6)  # 图表尺寸（宽, 高）
grid_on = False  # 是否显示网格线

# -------------------------- 新增：图例配置参数（兼容旧版本matplotlib） --------------------------
legend_show = True  # 是否显示图例（True=显示，False=隐藏）
bond_legend_label = 'NCS 300 K Al-O₁'  # 键长图例行文本（可修改为自定义文本）
angle_legend_label = 'NCS 300 K Al-O₁-O₂'  # 键角图例行文本（可修改为自定义文本）
legend_loc = 'upper right'  # 图例位置（可选值见下方说明）
legend_font_size = 22  # 图例字体大小
legend_frame_on = False  # 是否显示图例边框（True=显示，False=隐藏）
legend_framealpha = 0.9  # 图例背景透明度（0=完全透明，1=完全不透明）
legend_bbox_to_anchor = None  # 图例锚点位置（默认None，使用legend_loc控制）
# ==================================================================================

# 图例位置可选值说明：
# 'best'          : 自动选择最佳位置
# 'upper right'   : 右上角（默认）
# 'upper left'    : 左上角
# 'lower right'   : 右下角
# 'lower left'    : 左下角
# 'upper center'  : 上中
# 'lower center'  : 下中
# 'center left'   : 左中
# 'center right'  : 右中
# 'center'        : 中心
# 也可以用数字表示：0=best, 1=upper right, 2=upper left, 3=lower left, 4=lower right,
#                5=right, 6=center left, 7=center right, 8=lower center, 9=upper center, 10=center


# -------------------------- 数据读取与时间计算 --------------------------
try:
    # 读取键长数据（跳过表头）
    bond_raw = np.loadtxt('bond_length_time.dat', skiprows=1)
    bond_col_idx = bond_data_col - 1
    bond_length_data = bond_raw[:, bond_col_idx] if bond_raw.ndim > 1 else bond_raw

    # 读取键角数据（跳过表头）
    angle_raw = np.loadtxt('angle_time.dat', skiprows=1)
    angle_col_idx = angle_data_col - 1
    angle_data = angle_raw[:, angle_col_idx] if angle_raw.ndim > 1 else angle_raw

except FileNotFoundError as e:
    raise FileNotFoundError(f"未找到数据文件：{e.filename}，请确认文件在当前目录")

# 校验数据行数
if len(bond_length_data) != NSW:
    raise ValueError(f"键长数据行数({len(bond_length_data)})与NSW({NSW})不匹配！")
if len(angle_data) != NSW:
    raise ValueError(f"键角数据行数({len(angle_data)})与NSW({NSW})不匹配！")

# 计算模拟时间（单位：ps）
sim_time = np.arange(NSW) * POTIM / 1000.0

# -------------------------- 计算并打印平均值 --------------------------
# 计算键长和键角的平均值
bond_length_avg = np.mean(bond_length_data)
bond_angle_avg = np.mean(angle_data)

# 打印平均值（保留4位小数，显示单位）
print("=" * 50)
print("模拟时间内的平均值统计")
print("=" * 50)
print(f"键长平均值: {bond_length_avg:.4f} Å")
print(f"键角平均值: {bond_angle_avg:.4f} °")
print("=" * 50)

# 可选：打印更多统计信息（如标准差、最大值、最小值）
bond_length_std = np.std(bond_length_data)
bond_angle_std = np.std(angle_data)
bond_length_max = np.max(bond_length_data)
bond_angle_max = np.max(angle_data)
bond_length_min = np.min(bond_length_data)
bond_angle_min = np.min(angle_data)

print("\n扩展统计信息（可选）:")
print(f"键长 - 标准差: {bond_length_std:.4f} Å, 最大值: {bond_length_max:.4f} Å, 最小值: {bond_length_min:.4f} Å")
print(f"键角 - 标准差: {bond_angle_std:.4f} °, 最大值: {bond_angle_max:.4f} °, 最小值: {bond_angle_min:.4f} °")
print("=" * 50)

# -------------------------- 绘制键长随时间变化图 --------------------------
plt.figure(1, figsize=fig_size)
ax_bond = plt.gca()

# 绘制键长曲线（添加label参数，用于图例）
ax_bond.plot(sim_time, bond_length_data,
             color=bond_line_color,
             linewidth=line_width,
             label=bond_legend_label)  # 添加图例标签

# 字体配置
plt.rcParams["font.family"] = ["DejaVu Sans", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

# 图表边框线宽
for spine in ax_bond.spines.values():
    spine.set_linewidth(line_width)

# 网格设置
if grid_on:
    ax_bond.grid(True, alpha=0.3, linewidth=0.6)

# 坐标轴范围（X轴设为0到100，确保显示100刻度）
ax_bond.set_xlim(x_axis_range)
ax_bond.set_ylim(bond_y_range)

# 坐标轴标签（添加labelpad控制距离）
ax_bond.set_xlabel('Simulation Time (ps)', fontsize=font_size_label, labelpad=x_label_pad)
ax_bond.set_ylabel('Bond Length (Å)', fontsize=font_size_label, labelpad=y_label_pad)

# 刻度样式（添加pad控制刻度数字与轴的距离）
ax_bond.tick_params(
    which='major',
    direction='in',
    width=2.5,
    length=8.0,
    labelsize=font_size_tick,
    pad=x_tick_pad  # X轴刻度数字与轴的距离
)
ax_bond.tick_params(
    which='minor',
    direction='in',
    width=2.0,
    length=6.0,
    pad=x_tick_pad
)
# Y轴刻度单独设置pad
ax_bond.tick_params(
    axis='y',
    which='both',
    pad=y_tick_pad  # Y轴刻度数字与Y轴的距离
)

# 主刻度间隔
ax_bond.xaxis.set_major_locator(MultipleLocator(x_major_tick))
ax_bond.yaxis.set_major_locator(MultipleLocator(bond_y_major_tick))

# 子刻度
ax_bond.xaxis.set_minor_locator(AutoMinorLocator(2))
ax_bond.yaxis.set_minor_locator(AutoMinorLocator(2))

# -------------------------- 应用图例配置（兼容旧版本） --------------------------
if legend_show:
    # 基础兼容参数
    legend_kwargs = {
        'loc': legend_loc,
        'fontsize': legend_font_size,
        'frameon': legend_frame_on,
        'shadow': False
    }

    # 尝试添加framealpha（如果版本支持）
    try:
        legend_kwargs['framealpha'] = legend_framealpha
    except:
        pass

    # 如果设置了锚点位置，添加到参数中
    if legend_bbox_to_anchor is not None:
        legend_kwargs['bbox_to_anchor'] = legend_bbox_to_anchor

    # 绘制图例
    legend = ax_bond.legend(**legend_kwargs)

    # 手动设置图例背景透明度（兼容旧版本）
    try:
        if legend_frame_on and hasattr(legend, 'get_frame'):
            frame = legend.get_frame()
            frame.set_alpha(legend_framealpha)
            frame.set_edgecolor('black')  # 设置边框颜色
    except:
        pass

plt.tight_layout()

# -------------------------- 绘制键角随时间变化图 --------------------------
plt.figure(2, figsize=fig_size)
ax_angle = plt.gca()

# 绘制键角曲线（添加label参数，用于图例）
ax_angle.plot(sim_time, angle_data,
              color=angle_line_color,
              linewidth=line_width,
              label=angle_legend_label)  # 添加图例标签

# 图表边框线宽
for spine in ax_angle.spines.values():
    spine.set_linewidth(line_width)

# 网格设置
if grid_on:
    ax_angle.grid(True, alpha=0.3, linewidth=0.6)

# 坐标轴范围（X轴设为0到100）
ax_angle.set_xlim(x_axis_range)
ax_angle.set_ylim(angle_y_range)

# 坐标轴标签（添加labelpad）
ax_angle.set_xlabel('Simulation Time (ps)', fontsize=font_size_label, labelpad=x_label_pad)
ax_angle.set_ylabel('Bond Angle (°)', fontsize=font_size_label, labelpad=y_label_pad)

# 刻度样式（添加pad）
ax_angle.tick_params(
    which='major',
    direction='in',
    width=2.5,
    length=8.0,
    labelsize=font_size_tick,
    pad=x_tick_pad
)
ax_angle.tick_params(
    which='minor',
    direction='in',
    width=2.0,
    length=6.0,
    pad=x_tick_pad
)
# Y轴刻度pad
ax_angle.tick_params(
    axis='y',
    which='both',
    pad=y_tick_pad
)

# 主刻度间隔
ax_angle.xaxis.set_major_locator(MultipleLocator(x_major_tick))
ax_angle.yaxis.set_major_locator(MultipleLocator(angle_y_major_tick))

# 子刻度
ax_angle.xaxis.set_minor_locator(AutoMinorLocator(2))
ax_angle.yaxis.set_minor_locator(AutoMinorLocator(2))

# -------------------------- 应用图例配置（兼容旧版本） --------------------------
if legend_show:
    # 基础兼容参数
    legend_kwargs = {
        'loc': legend_loc,
        'fontsize': legend_font_size,
        'frameon': legend_frame_on,
        'shadow': False
    }

    # 尝试添加framealpha（如果版本支持）
    try:
        legend_kwargs['framealpha'] = legend_framealpha
    except:
        pass

    # 如果设置了锚点位置，添加到参数中
    if legend_bbox_to_anchor is not None:
        legend_kwargs['bbox_to_anchor'] = legend_bbox_to_anchor

    # 绘制图例
    legend = ax_angle.legend(**legend_kwargs)

    # 手动设置图例背景透明度（兼容旧版本）
    try:
        if legend_frame_on and hasattr(legend, 'get_frame'):
            frame = legend.get_frame()
            frame.set_alpha(legend_framealpha)
            frame.set_edgecolor('black')  # 设置边框颜色
    except:
        pass

plt.tight_layout()

# 显示图表
plt.show()