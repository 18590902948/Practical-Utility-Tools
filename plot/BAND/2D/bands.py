import matplotlib.pyplot as plt
import numpy as np
import os
import re
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import FormatStrFormatter, MultipleLocator  # 补充导入MultipleLocator
from typing import List, Tuple, Optional, Dict, Any

# ==============================================================================
# ============================ 全局可配置参数（用户仅需修改此区域）============================
# ==============================================================================
# ---------------------- 1. 全局缩放倍率（核心控制） ----------------------
GLOBAL_LINEWIDTH_SCALE = 1.0  # 所有线条粗细全局倍率
GLOBAL_FONT_SIZE_SCALE = 1.0  # 所有字体大小全局倍率

# ---------------------- 2. 文件路径参数 ----------------------
DATA_DIR = os.path.dirname(os.path.abspath(__file__))  # 数据文件目录
# 能带相关文件
FILE_BAND = os.path.join(DATA_DIR, "BAND.dat")  # 能带数据
FILE_BAND_GAP = os.path.join(DATA_DIR, "BAND_GAP")  # 带隙数据
FILE_KLABELS = os.path.join(DATA_DIR, "KLABELS")  # k点标签

# ---------------------- 3. 文本显示参数（空字符串则不显示） ----------------------
TITLE_TEXT = ''  # 图表总标题
BAND_Y_LABEL = 'Energy (eV)'  # 能带Y轴标签

# ---------------------- 4. 位置控制参数 ----------------------
# 标签距离控制
BAND_Y_LABEL_PAD = 0  # 能带Y轴标签距离Y轴的距离
TITLE_PAD = 12  # 标题距离图表上边框的距离
# 刻度距离控制
BAND_X_TICK_PAD = 8  # 能带X轴刻度标签距离X轴的距离
BAND_Y_TICK_PAD = 8  # 能带Y轴刻度标签距离Y轴的距离

# ---------------------- 5. 视觉样式 - 颜色 ----------------------
COLOR_BAND = 'blue'  # 能带曲线颜色
# 其他颜色
COLOR_FERMI_LEVEL = 'red'  # 费米能级线颜色
COLOR_BAND_GAP_FILL = 'gray'  # 带隙填充颜色
COLOR_KLINE = 'gray'  # k点竖线颜色
COLOR_VBM = 'black'  # VBM线颜色
COLOR_CBM = 'black'  # CBM线颜色
COLOR_SPINE = 'black'  # 图表边框颜色
COLOR_VBM_CBM_MARKER = 'red'  # VBM/CBM标记点颜色
MARKER_EDGE_COLOR = 'red'  # 标记点轮廓颜色

# ---------------------- 6. 视觉样式 - 线宽基准值 ----------------------
# 主线条线宽
LINEWIDTH_BASE_BAND = 2.5  # 能带曲线线宽基准
LINEWIDTH_BASE_SPINE = 2.5  # 图表边框线宽基准
# 刻度线宽
LINEWIDTH_BASE_BAND_TICK_MAJOR = 2.5  # 能带主刻度线宽基准
# 辅助线线宽
LINEWIDTH_BASE_FERMI = 2.5  # 费米能级线宽基准
LINEWIDTH_BASE_KLINE = 2.5  # k点竖线线宽基准
LINEWIDTH_BASE_VBM_CBM = 2.5  # VBM/CBM线宽基准

# ---------------------- 7. 视觉样式 - 字体大小基准值 ----------------------
FONTSIZE_BASE_TITLE = 28  # 总标题字体大小基准
FONTSIZE_BASE_BAND_X_TICK = 28  # 能带X轴刻度字体大小基准
FONTSIZE_BASE_BAND_Y_TICK = 24  # 能带Y轴刻度字体大小基准
FONTSIZE_BASE_BAND_Y_LABEL = 28  # 能带Y轴标签字体大小基准
FONTSIZE_BASE_ERROR_TEXT = 26  # 数据缺失提示文字大小基准

# ---------------------- 8. 视觉样式 - 刻度长度基准值 ----------------------
TICKLENGTH_BASE_BAND_MAJOR = 8.0  # 能带主刻度长度基准

# ---------------------- 9. 视觉样式 - 坐标轴范围（None=自动计算） ----------------------
Y_RANGE = [-10, 10]  # 能量轴范围 [最小值, 最大值]（偏移后自动计算）
Y_TICK_DECIMAL = 0  # 能量轴刻度小数位数

# ---------------------- 10. 视觉样式 - 刻度配置 ----------------------
TICK_DIRECTION = 'in'  # 刻度方向：'in'/'out'/'inout'
Y_MAJOR_TICK = 2.0  # 能量轴主刻度间隔（eV）

# ---------------------- 11. 视觉样式 - 网格 ----------------------
GRID_ON = False  # 网格开关
GRID_ALPHA = 0.3  # 网格透明度
GRID_LINestyle = '--'  # 网格线型

# ---------------------- 12. 能带专属配置 ----------------------
FERMI_LEVEL_Y = 0.0  # 费米能级Y轴位置
FILL_BAND_GAP = False  # 带隙填充开关
BAND_GAP_ALPHA = 0.3  # 带隙填充透明度
KLINE_ALPHA = 0.5  # k点竖线透明度
VBM_CBM_ALPHA = 1.0  # VBM/CBM线透明度
FERMI_LINE_LINestyle = "--"  # 费米能级线型
KLINE_LINestyle = "--"  # k点竖线线型
VBM_CBM_LINestyle = "--"  # VBM/CBM虚线线型

# ---------------------- 13. 显示开关（核心配置） ----------------------
SHOW_VBM_LINE = True  # 是否显示VBM虚线
SHOW_CBM_LINE = True  # 是否显示CBM虚线
SHOW_VBM_MARKER = True  # 是否显示VBM标记点
SHOW_CBM_MARKER = True  # 是否显示CBM标记点
SHOW_FERMI_LINE = True  # 是否显示费米能级线
SHOW_KPOINT_LINE = True  # 是否显示k点竖线

# ---------------------- 14. VBM/CBM标记点专属配置 ----------------------
MARKER_SIZE = 100  # 标记点大小
MARKER_IS_FILLED = True  # 是否实心
MARKER_EDGE_WIDTH = 2.0  # 标记点轮廓粗细
MARKER_ZORDER = 5  # 标记点层级（最上层）

# ---------------------- 15. 画布&布局配置 ----------------------
FIGSIZE = (6, 8)  # 总画布尺寸（仅能带图）
WINDOW_SPACING = 0.1  # 能带窗口之间的间距

# ---------------------- 16. 偏移开关（核心参数） ----------------------
OFFSET_TO_VBM_CBM_CENTER = True  # 开启时让0eV对齐VBM和CBM的中心

# ==============================================================================
# ============================ 自动计算最终参数（无需修改） =============================
# ==============================================================================
# 主线条最终线宽
FINAL_LINEWIDTH_BAND = LINEWIDTH_BASE_BAND * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_SPINE = LINEWIDTH_BASE_SPINE * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_GRID = LINEWIDTH_BASE_GRID * GLOBAL_LINEWIDTH_SCALE if 'LINEWIDTH_BASE_GRID' in locals() else 0

# 刻度最终线宽
FINAL_LINEWIDTH_BAND_TICK_MAJOR = LINEWIDTH_BASE_BAND_TICK_MAJOR * GLOBAL_LINEWIDTH_SCALE

# 刻度最终长度
FINAL_TICKLENGTH_BAND_MAJOR = TICKLENGTH_BASE_BAND_MAJOR * GLOBAL_LINEWIDTH_SCALE

# 辅助线最终线宽
FINAL_LINEWIDTH_FERMI = LINEWIDTH_BASE_FERMI * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_KLINE = LINEWIDTH_BASE_KLINE * GLOBAL_LINEWIDTH_SCALE
FINAL_LINEWIDTH_VBM_CBM = LINEWIDTH_BASE_VBM_CBM * GLOBAL_LINEWIDTH_SCALE
FINAL_MARKER_EDGE_WIDTH = MARKER_EDGE_WIDTH * GLOBAL_LINEWIDTH_SCALE

# 字体最终大小
FINAL_FONTSIZE_TITLE = FONTSIZE_BASE_TITLE * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_BAND_X_TICK = FONTSIZE_BASE_BAND_X_TICK * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_BAND_Y_TICK = FONTSIZE_BASE_BAND_Y_TICK * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_BAND_Y_LABEL = FONTSIZE_BASE_BAND_Y_LABEL * GLOBAL_FONT_SIZE_SCALE
FINAL_FONTSIZE_ERROR_TEXT = FONTSIZE_BASE_ERROR_TEXT * GLOBAL_FONT_SIZE_SCALE

# ==============================================================================
# ============================ 基础样式全局设置（无需修改） =============================
# ==============================================================================
plt.rcParams["font.family"] = ["DejaVu Sans", "sans-serif", "Arial", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["text.usetex"] = False
plt.rcParams["figure.dpi"] = 100
plt.rcParams["savefig.bbox"] = "tight"
plt.rcParams["axes.grid"] = GRID_ON  # 按网格开关控制
plt.rcParams["grid.alpha"] = GRID_ALPHA
plt.rcParams["grid.linestyle"] = GRID_LINestyle


# ==============================================================================
# ============================ 工具函数 =============================
# ==============================================================================
def convert_subscript(text: str) -> str:
    """下划线转Unicode下标"""
    subscript_map = {'0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉'}
    return re.sub(r'_(\d)', lambda m: subscript_map[m.group(1)], text)


def convert_k_label(label: str) -> str:
    """k点标签转Unicode（希腊字母+下标）"""
    label = convert_subscript(label)
    greek_map = {"GAMMA": "Γ", "\\Gamma": "Γ", "gamma": "γ"}
    for k, v in greek_map.items():
        label = label.replace(k, v).replace("$", "").strip()
    return label


def parse_split_klabels(raw_labels: List[str], raw_coords: List[float]) -> Tuple[
    List[List[str]], List[List[float]], List[float]]:
    """解析k标签并拆分能带窗口"""
    converted_labels = [convert_k_label(lab) for lab in raw_labels]
    valid_pairs = list(zip(converted_labels, raw_coords))
    if not valid_pairs:
        raise ValueError("KLABELS无有效标签")

    split_pairs = [p for p in valid_pairs if "|" in p[0]]
    M = len(split_pairs)
    window_count = M + 1
    print(f"✅ 拆分{window_count}个能带窗口")

    window_klabels, window_kcoords, split_k = [], [], [p[1] for p in split_pairs]
    if M == 0:
        window_klabels.append([p[0] for p in valid_pairs])
        window_kcoords.append([p[1] for p in valid_pairs])
        return window_klabels, window_kcoords, split_k

    split_indices = [valid_pairs.index(p) for p in split_pairs]
    split_left = [p[0].split("|")[0].strip() for p in split_pairs]
    split_right = [p[0].split("|")[1].strip() for p in split_pairs]

    # 窗口0
    win0_labels = [p[0] for p in valid_pairs[:split_indices[0]]] + [split_left[0]]
    win0_coords = [p[1] for p in valid_pairs[:split_indices[0]]] + [split_pairs[0][1]]
    window_klabels.append(win0_labels)
    window_kcoords.append(win0_coords)

    # 中间窗口
    for i in range(1, M):
        win_labels = [split_right[i - 1]] + [p[0] for p in valid_pairs[split_indices[i - 1] + 1:split_indices[i]]] + [
            split_left[i]]
        win_coords = [split_pairs[i - 1][1]] + [p[1] for p in
                                                valid_pairs[split_indices[i - 1] + 1:split_indices[i]]] + [
                         split_pairs[i][1]]
        window_klabels.append(win_labels)
        window_kcoords.append(win_coords)

    # 最后窗口
    win_last_labels = [split_right[-1]] + [p[0] for p in valid_pairs[split_indices[-1] + 1:]]
    win_last_coords = [split_pairs[-1][1]] + [p[1] for p in valid_pairs[split_indices[-1] + 1:]]
    window_klabels.append(win_last_labels)
    window_kcoords.append(win_last_coords)

    return window_klabels, window_kcoords, split_k


def load_band_gap_data() -> Tuple[float, float, float, float]:
    """加载BAND_GAP数据"""
    vbm_e_raw, cbm_e_raw, band_gap, fermi_e = np.nan, np.nan, np.nan, np.nan
    try:
        with open(FILE_BAND_GAP, "r") as f:
            for line in f:
                line = line.strip()
                if "Eigenvalue of VBM" in line:
                    vbm_e_raw = float(re.search(r'(-?\d+\.?\d*)', line).group(1))
                if "Eigenvalue of CBM" in line:
                    cbm_e_raw = float(re.search(r'(-?\d+\.?\d*)', line).group(1))
                if "Band Gap" in line:
                    band_gap = float(re.search(r'(-?\d+\.?\d*)', line).group(1))
                if "Fermi Energy" in line:
                    fermi_e = float(re.search(r'(-?\d+\.?\d*)', line).group(1))
        vbm_e_raw -= fermi_e
        cbm_e_raw -= fermi_e
        print(f"\n✅ 带隙：{band_gap:.4f} eV | VBM：{vbm_e_raw:.4f} eV | CBM：{cbm_e_raw:.4f} eV")
    except Exception as e:
        print(f"⚠️  解析BAND_GAP失败：{e}")
    return vbm_e_raw, cbm_e_raw, band_gap, fermi_e


def load_band_data() -> Tuple[np.ndarray, np.ndarray, List[str], List[float]]:
    """加载能带数据和k标签"""
    k_points, band_energies = np.array([]), np.array([])
    raw_labels, raw_coords = [], []

    # 读取能带数据
    try:
        band_data = np.loadtxt(FILE_BAND, skiprows=1)
        k_points = band_data[:, 0]
        band_energies = band_data[:, 1:]
        print(f"✅ 读取能带：{len(k_points)}个k点 | {band_energies.shape[1]}条能带")
    except Exception as e:
        print(f"⚠️  读取BAND.dat失败：{e}")

    # 读取k标签
    try:
        with open(FILE_KLABELS, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith(("*", "#", "k-label")):
                    parts = line.split()
                    if len(parts) >= 2 and parts[1].replace(".", "").isdigit():
                        raw_labels.append(parts[0])
                        raw_coords.append(float(parts[1]))
        print(f"✅ 读取k标签：{len(raw_labels)}个")
    except Exception as e:
        print(f"⚠️  读取KLABELS失败：{e}")

    return k_points, band_energies, raw_labels, raw_coords


def split_band_data(k_points: np.ndarray, band_energies: np.ndarray, split_k: List[float]) -> Tuple[
    List[np.ndarray], List[np.ndarray]]:
    """拆分能带数据到窗口"""
    M = len(split_k)
    window_count = M + 1
    window_k, window_band = [], []
    split_k_sorted = sorted(split_k)

    if M == 0:
        window_k.append(k_points)
        window_band.append(band_energies)
        return window_k, window_band

    mask0 = k_points <= split_k_sorted[0]
    window_k.append(k_points[mask0])
    window_band.append(band_energies[mask0])

    for i in range(1, M):
        mask = (k_points >= split_k_sorted[i - 1]) & (k_points <= split_k_sorted[i])
        window_k.append(k_points[mask])
        window_band.append(band_energies[mask])

    mask_last = k_points >= split_k_sorted[-1]
    window_k.append(k_points[mask_last])
    window_band.append(band_energies[mask_last])

    return window_k, window_band


def get_window_index(k_val: float, split_k: List[float]) -> int:
    """判断k点所属窗口"""
    M = len(split_k)
    if M == 0:
        return 0
    split_k_sorted = sorted(split_k)
    if k_val <= split_k_sorted[0]:
        return 0
    for i in range(1, M):
        if split_k_sorted[i - 1] < k_val <= split_k_sorted[i]:
            return i
    return M


def get_tick_kwargs(axis: str) -> Dict[str, Any]:
    """生成刻度配置参数"""
    kwargs = {'direction': TICK_DIRECTION}
    # 刻度标签距离
    if axis == 'x':
        kwargs['pad'] = BAND_X_TICK_PAD
    else:
        kwargs['pad'] = BAND_Y_TICK_PAD
    # 字体大小
    kwargs['labelsize'] = FINAL_FONTSIZE_BAND_X_TICK if axis == 'x' else FINAL_FONTSIZE_BAND_Y_TICK
    return kwargs


def calculate_vbm_cbm_from_band(k_points: np.ndarray, band_energies: np.ndarray) -> Tuple[float, float, float, float]:
    """从能带数据自动计算VBM/CBM"""
    # 展平能带数据和对应的k点
    flattened_energies = band_energies.flatten()
    flattened_k = np.repeat(k_points, band_energies.shape[1])

    # 计算VBM：Y<0的最大能量点
    vbm_energy, vbm_k = np.nan, np.nan
    vbm_mask = flattened_energies < 0
    if np.any(vbm_mask):
        vbm_energy = np.max(flattened_energies[vbm_mask])
        vbm_indices = np.where(flattened_energies == vbm_energy)[0]
        vbm_k = flattened_k[vbm_indices[0]]
        print(f"✅ 计算VBM：能量={vbm_energy:.4f} eV，k坐标={vbm_k:.2f}")

    # 计算CBM：Y>0的最小能量点
    cbm_energy, cbm_k = np.nan, np.nan
    cbm_mask = flattened_energies > 0
    if np.any(cbm_mask):
        cbm_energy = np.min(flattened_energies[cbm_mask])
        cbm_indices = np.where(flattened_energies == cbm_energy)[0]
        cbm_k = flattened_k[cbm_indices[0]]
        print(f"✅ 计算CBM：能量={cbm_energy:.4f} eV，k坐标={cbm_k:.2f}")

    return vbm_energy, vbm_k, cbm_energy, cbm_k


def apply_energy_offset(
        vbm_energy: float,
        cbm_energy: float,
        band_energies: np.ndarray
) -> Tuple[float, float, np.ndarray]:
    """应用能量偏移，让0eV对齐VBM和CBM的中心"""
    if not OFFSET_TO_VBM_CBM_CENTER or np.isnan(vbm_energy) or np.isnan(cbm_energy):
        return vbm_energy, cbm_energy, band_energies

    # 计算偏移量：VBM和CBM中心对齐到0eV
    center_energy = (vbm_energy + cbm_energy) / 2
    offset = -center_energy
    print(f"✅ 应用能量偏移：中心能量={center_energy:.4f} eV，偏移量={offset:.4f} eV")

    # 应用偏移到所有能量数据
    vbm_energy_offset = vbm_energy + offset
    cbm_energy_offset = cbm_energy + offset
    band_energies_offset = band_energies + offset if band_energies.size > 0 else band_energies

    print(f"✅ 偏移后：VBM={vbm_energy_offset:.4f} eV，CBM={cbm_energy_offset:.4f} eV")
    return vbm_energy_offset, cbm_energy_offset, band_energies_offset


# ==============================================================================
# ============================ 绘图函数 =============================
# ==============================================================================
def plot_single_band_window(
        ax: plt.Axes,
        k_data: np.ndarray,
        band_data: np.ndarray,
        window_labels: List[str],
        window_coords: List[float],
        vbm_info: Tuple[float, float],
        cbm_info: Tuple[float, float],
        window_idx: int,
        split_k: List[float]
):
    """绘制单个能带窗口"""
    vbm_k, vbm_e = vbm_info
    cbm_k, cbm_e = cbm_info

    # 绘制能带曲线
    for band in band_data.T:
        ax.plot(k_data, band, color=COLOR_BAND, linewidth=FINAL_LINEWIDTH_BAND, zorder=1)

    # 费米能级线
    if SHOW_FERMI_LINE:
        ax.axhline(y=FERMI_LEVEL_Y, color=COLOR_FERMI_LEVEL,
                   linestyle=FERMI_LINE_LINestyle, linewidth=FINAL_LINEWIDTH_FERMI, zorder=2)

    # VBM/CBM线
    if SHOW_VBM_LINE and not np.isnan(vbm_e):
        ax.axhline(y=vbm_e, color=COLOR_VBM, linestyle=VBM_CBM_LINestyle,
                   alpha=VBM_CBM_ALPHA, linewidth=FINAL_LINEWIDTH_VBM_CBM, zorder=2)
    if SHOW_CBM_LINE and not np.isnan(cbm_e):
        ax.axhline(y=cbm_e, color=COLOR_CBM, linestyle=VBM_CBM_LINestyle,
                   alpha=VBM_CBM_ALPHA, linewidth=FINAL_LINEWIDTH_VBM_CBM, zorder=2)

    # k点竖线
    if SHOW_KPOINT_LINE:
        for coord in window_coords:
            ax.axvline(x=coord, color=COLOR_KLINE, linestyle=KLINE_LINestyle,
                       alpha=KLINE_ALPHA, linewidth=FINAL_LINEWIDTH_KLINE, zorder=2)

    # VBM/CBM标记点
    if MARKER_IS_FILLED:
        marker_facecolor = COLOR_VBM_CBM_MARKER
        marker_edgecolor = MARKER_EDGE_COLOR
    else:
        marker_facecolor = 'none'
        marker_edgecolor = COLOR_VBM_CBM_MARKER

    if SHOW_VBM_MARKER and not np.isnan(vbm_k) and get_window_index(vbm_k, split_k) == window_idx:
        ax.scatter(x=vbm_k, y=vbm_e, s=MARKER_SIZE, c=marker_facecolor,
                   edgecolor=marker_edgecolor, linewidths=FINAL_MARKER_EDGE_WIDTH,
                   marker="o", zorder=MARKER_ZORDER)

    if SHOW_CBM_MARKER and not np.isnan(cbm_k) and get_window_index(cbm_k, split_k) == window_idx:
        ax.scatter(x=cbm_k, y=cbm_e, s=MARKER_SIZE, c=marker_facecolor,
                   edgecolor=marker_edgecolor, linewidths=FINAL_MARKER_EDGE_WIDTH,
                   marker="o", zorder=MARKER_ZORDER)

    # 坐标轴配置
    ax.set_xticks(window_coords)
    ax.set_xticklabels(window_labels, fontsize=FINAL_FONTSIZE_BAND_X_TICK, ha='center')
    ax.set_xlim(min(window_coords), max(window_coords))
    ax.margins(x=0)

    # 刻度样式
    ax.tick_params(axis='x', which='major', length=FINAL_TICKLENGTH_BAND_MAJOR,
                   width=FINAL_LINEWIDTH_BAND_TICK_MAJOR, **get_tick_kwargs('x'))
    ax.tick_params(axis='y', which='major', length=FINAL_TICKLENGTH_BAND_MAJOR,
                   width=FINAL_LINEWIDTH_BAND_TICK_MAJOR, **get_tick_kwargs('y'))

    # 边框样式
    for spine in ax.spines.values():
        spine.set_linewidth(FINAL_LINEWIDTH_SPINE)
        spine.set_color(COLOR_SPINE)


# ==============================================================================
# ============================ 核心绘图函数 =============================
# ==============================================================================
def plot_band_structure():
    """绘制独立的能带图"""
    # 1. 加载所有数据
    vbm_e_raw, cbm_e_raw, band_gap, fermi_e = load_band_gap_data()
    k_points, band_energies, raw_labels, raw_coords = load_band_data()
    window_klabels, window_kcoords, split_k = parse_split_klabels(raw_labels, raw_coords)
    window_k, window_band = split_band_data(k_points, band_energies, split_k)
    band_window_count = len(window_klabels)

    # 2. 数据校验
    if len(k_points) == 0 or band_window_count != len(window_k):
        print("❌ 能带数据无效")
        return

    # 3. 计算全局VBM/CBM
    vbm_energy, vbm_k, cbm_energy, cbm_k = calculate_vbm_cbm_from_band(k_points, band_energies)

    # 4. 应用能量偏移
    vbm_energy_offset, cbm_energy_offset, band_energies_offset = apply_energy_offset(
        vbm_energy, cbm_energy, band_energies
    )

    # 更新拆分后的能带数据（应用偏移）
    window_band_offset = []
    for win_band in window_band:
        if win_band.size > 0:
            window_band_offset.append(
                win_band + (vbm_energy_offset - vbm_energy) if OFFSET_TO_VBM_CBM_CENTER else win_band)
        else:
            window_band_offset.append(win_band)

    # 5. 统一能量轴范围（基于偏移后的数据）
    energy_ranges = []
    if len(band_energies_offset) > 0:
        energy_ranges.extend([band_energies_offset.min(), band_energies_offset.max()])

    y_min, y_max = (-10, 10)
    if energy_ranges:
        y_min, y_max = (min(energy_ranges), max(energy_ranges)) if Y_RANGE is None else Y_RANGE

    # 6. 创建画布&布局（仅能带图）
    fig = plt.figure(figsize=FIGSIZE)

    # 7. 总标题
    if TITLE_TEXT:
        fig.suptitle(TITLE_TEXT, fontsize=FINAL_FONTSIZE_TITLE, pad=TITLE_PAD)

    # 8. 绘制能带窗口（占满整个画布）
    gs = GridSpec(1, band_window_count, wspace=WINDOW_SPACING)
    # 先创建第一个能带窗口（作为Y轴基准）
    band_axs = [fig.add_subplot(gs[0])]
    # 后续能带窗口共享第一个的Y轴
    for i in range(1, band_window_count):
        band_axs.append(fig.add_subplot(gs[i], sharey=band_axs[0]))

    # 仅最左侧能带窗口显示Y轴标签和刻度
    band_axs[0].set_ylabel(BAND_Y_LABEL, fontsize=FINAL_FONTSIZE_BAND_Y_LABEL,
                           labelpad=BAND_Y_LABEL_PAD, color=COLOR_SPINE)

    # 绘制每个能带窗口（使用偏移后的能量数据）
    for idx, (ax, k_data, band_data, labels, coords) in enumerate(
            zip(band_axs, window_k, window_band_offset, window_klabels, window_kcoords)):
        plot_single_band_window(
            ax=ax,
            k_data=k_data,
            band_data=band_data,
            window_labels=labels,
            window_coords=coords,
            vbm_info=(vbm_k, vbm_energy_offset),  # 使用偏移后的VBM能量
            cbm_info=(cbm_k, cbm_energy_offset),  # 使用偏移后的CBM能量
            window_idx=idx,
            split_k=split_k
        )
        ax.set_ylim(y_min, y_max)
        ax.yaxis.set_major_formatter(FormatStrFormatter(f"%.{Y_TICK_DECIMAL}f"))

        # 仅最左侧窗口显示Y轴刻度标签，其他能带窗口隐藏
        if idx != 0:
            ax.tick_params(axis='y', labelleft=False)

    # 核心修复：统一所有能带窗口的Y轴主刻度间隔（2.0eV）
    y_major_locator = MultipleLocator(Y_MAJOR_TICK)
    for ax in band_axs:
        ax.yaxis.set_major_locator(y_major_locator)
        ax.yaxis.set_major_formatter(FormatStrFormatter(f"%.{Y_TICK_DECIMAL}f"))

    # 9. 调整布局（增大左侧边距，确保Y轴标签完整显示）
    plt.subplots_adjust(left=0.18, right=0.98, top=0.95, bottom=0.07)
    plt.show()


# ==============================================================================
# ============================ 主程序入口 =============================
# ==============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("📌 独立能带图绘图配置")
    print("=" * 70)
    print(f"总画布：宽{FIGSIZE[0]} × 高{FIGSIZE[1]}")
    print(f"Y轴配置：仅最左侧能带窗口显示数值刻度 | 所有子图共用同一Y轴")
    print(f"Y轴主刻度间隔：{Y_MAJOR_TICK} eV（已生效）")  # 新增日志提示
    print(f"全局线宽倍率：{GLOBAL_LINEWIDTH_SCALE} | 全局字体倍率：{GLOBAL_FONT_SIZE_SCALE}")
    print(f"VBM/CBM中心对齐开关：{'开启' if OFFSET_TO_VBM_CBM_CENTER else '关闭'}")
    if OFFSET_TO_VBM_CBM_CENTER:
        print("⚠️  开启后0eV将对齐VBM和CBM的中心，所有能量数据将自动偏移")
    print("=" * 70 + "\n")

    try:
        plot_band_structure()
    except Exception as e:
        print(f"\n❌ 绘图失败：{str(e)}")