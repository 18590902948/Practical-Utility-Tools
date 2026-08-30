import numpy as np
import time
import pickle
import math
import os
from scipy import interpolate
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, AutoMinorLocator, FixedLocator

# ======================================================================
# ====================== 所有可配置参数（集中在这里！）======================
# ======================================================================

# ---------------------- 基础文件设置 ----------------------
cache_file1 = ".structure.XDATCAR_frame_0-9999"
cache_file2 = ".structure.XDATCAR_frame_40000-49999"
XDAT_name = "XDATCAR"

# ---------------------- 图例自定义设置 ----------------------
legend1_text = "NCS 300 K Al-O 0-10 ps"
legend2_text = "NCS 300 K Al-O 90-100 ps"
legend_location1 = 'upper right'
legend_location2 = 'upper right'

# ---------------------- 画幅设置 ----------------------
fig_size = (10, 6)

# ---------------------- 图表显示设置 ----------------------
grid_on = False
line_width_spine = 2.5  # 边框线宽（重叠后显示为一条线）
middle_line_color = 'black'

# 线宽控制
line_width_global = 2.5
line_width_rdf1 = 2.5
line_width_rdf2 = 2.5
line_width_grid = 0.6
line_width_tick = 2.5
line_width_tick_minor = 2.0

# 颜色控制
rdf_line_color1 = 'blue'
rdf_line_color2 = 'red'
auto_cut_line_color1 = 'darkblue'
auto_cut_line_color2 = 'darkred'
manual_cut_line_color = 'gray'

# 截断半径控制
manual_cutoff = 2.35
show_manual_line = False
show_auto_line1 = False
show_auto_line2 = False

# 坐标轴范围控制
x_range = [0, 8]
y_range1 = [-2, 32]  # 上子图Y轴范围
y_range2 = [-2, 32]  # 下子图Y轴范围（从0开始）

# 刻度控制
x_major_tick = 2.0
y_major_tick1 = 8.0
y_major_tick2 = 8.0
tick_length_major = 8.0
tick_length_minor = 6.0

# 字体大小控制
font_size_global = 28
font_size_x_tick = 24
font_size_x_label = 28
font_size_y_tick1 = 24
font_size_y_tick2 = 24
font_size_y_label = 28  # Y轴标签字体大小
font_size_legend1 = 22
font_size_legend2 = 22

# ======================================================================
# ====================== 以下代码无需修改（除非自定义功能）======================
# ======================================================================

plt.rcParams["font.family"] = ["DejaVu Sans", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.autolayout"] = False  # 禁用自动布局

Defaultdr = 0.05


def r_min(rs, gs, scale=10, s=1):
    x = np.linspace(0, rs[-1], rs.shape[-1] * scale)
    soft = interpolate.UnivariateSpline(rs, gs, s=s)
    y = soft(x)
    start = y.argmax()
    return x[np.where(y[start + 1:] - y[start:-1] > 0)[0][0] + start]


class structure():
    def __init__(self, **kwag):
        if 'cell_parameter' in kwag:
            self.cell_parameter = kwag['cell_parameter']
        else:
            self.cell_parameter = []
        if 'atmnamelist' in kwag:
            self.atmnamelist = kwag['atmnamelist']
        else:
            self.atmnamelist = []
        if 'atmnumlist' in kwag:
            self.atmnumlist = kwag['atmnumlist']
        else:
            self.atmnumlist = []
        if 'frames' in kwag:
            self.frames = kwag['frames']
        else:
            self.frames = []
        if 'dis' in kwag:
            self.dis = kwag['dis']
        else:
            self.dis = False

    def readXDATCAR(self, filename):
        fp = open(filename)
        line = fp.readline()
        line = fp.readline()
        scale = float(line.strip())
        cell_parameter = np.empty((3, 3), dtype=float)
        for i in range(0, 3):
            line = fp.readline()
            j = 0
            for m in line.strip().split():
                cell_parameter[i, j] = float(m)
                j += 1
        self.cell_parameter = cell_parameter * scale
        line = fp.readline()
        self.atmnamelist = line.strip().split()
        line = fp.readline()
        self.atmnumlist = np.array([int(x) for x in line.strip().split()], dtype=int)
        AtomNum = self.atmnumlist.sum()
        while True:
            frame = np.empty((AtomNum, 3), dtype=float)
            try:
                line = fp.readline()
            except:
                break
            if line == "":
                fp.close()
                break
            for i in range(0, AtomNum):
                line = fp.readline()
                j = 0
                for m in line.strip().split():
                    num = float(m)
                    frame[i, j] = num - math.floor(num)
                    j += 1
            self.frames.append(frame)

    def normed(self):
        try:
            return self.is_normed
        except AttributeError:
            i, j = np.nonzero(self.cell_parameter)
            is_normed = np.all(i == j)
            self.is_normed = is_normed
            return is_normed

    def get_absolutepos(self):
        try:
            return self.absolutepos
        except AttributeError:
            self.absolutepos = np.empty((len(self.frames), self.atmnumlist.sum(), 3))
            for f in range(0, len(self.frames)):
                self.absolutepos[f, :, :] = self.frames[f].dot(self.cell_parameter)
            return self.absolutepos

    def min_diss(self, A, B, cp=False, normed=-1):
        if type(cp) == bool and cp == False:
            cp = self.cell_parameter
        if normed == -1:
            normed = self.normed()
        if normed:
            dis_v = np.abs(A - B)
            dis_v = np.where(dis_v < 0.5, dis_v, 1 - dis_v)
            return np.linalg.norm(dis_v.dot(cp))
        diss = np.empty(27, dtype=float)
        di = 0
        for mx in (-1, 0, 1):
            for my in (-1, 0, 1):
                for mz in (-1, 0, 1):
                    dis_v = (A - (B + np.array([mx, my, mz]))).dot(cp)
                    diss[di] = np.linalg.norm(dis_v)
                    if diss[di] == 0:
                        return 0.0
                    di += 1
        return diss.min()

    def _distance_normed(self):
        cp = self.cell_parameter
        AtomNum = self.atmnumlist.sum()
        FrameNum = len(self.frames)
        self.dis = np.zeros((FrameNum, AtomNum, AtomNum), dtype=float)
        for f in range(0, FrameNum):
            AMatrix = self.frames[f]
            for j in range(1, AtomNum):
                dis_v = abs(AMatrix[j:, :] - AMatrix[:AtomNum - j, :])
                dis_v = np.where(dis_v < 0.5, dis_v, 1 - dis_v)
                dis_diag = np.linalg.norm(dis_v.dot(cp), axis=1)
                np.fill_diagonal(self.dis[f, j:, 0:AtomNum - j], dis_diag)
            self.dis[f, :, :] += self.dis[f, :, :].T

    def _distance_any(self):
        cp = self.cell_parameter
        AtomNum = self.atmnumlist.sum()
        FrameNum = len(self.frames)
        self.dis = np.zeros((FrameNum, AtomNum, AtomNum), dtype=float)
        AabPos = self.get_absolutepos()
        shiftpos = np.empty((27, 3), dtype=float)
        shiftindex = 0
        for mx in (-1, 0, 1):
            for my in (-1, 0, 1):
                for mz in (-1, 0, 1):
                    shiftpos[shiftindex, :] = np.array([mx, my, mz]).dot(cp)
                    shiftindex += 1
        for f in range(0, FrameNum):
            AabMatrix = AabPos[f, :, :]
            for j in range(1, AtomNum):
                dis_value = np.empty((27, AtomNum - j), dtype=float)
                dis_ab = AabMatrix[j:, :] - AabMatrix[:AtomNum - j, :]
                for m in range(0, 27):
                    dis_value[m, :] = np.linalg.norm(dis_ab - shiftpos[m, :], axis=1)
                dis_diag = dis_value.min(axis=0)
                np.fill_diagonal(self.dis[f, j:, 0:AtomNum - j], dis_diag)
            self.dis[f, :, :] += self.dis[f, :, :].T

    def distances(self):
        normed = self.normed()
        print(f"start calculating distance for {len(self.frames)} frames...")
        if normed:
            self._distance_normed()
        else:
            self._distance_any()

    def get_cellV(self):
        try:
            return self.cellV
        except AttributeError:
            self.cellV = abs(np.linalg.det(self.cell_parameter))
            return self.cellV

    def _atm_range(self, I):
        Start = self.atmnumlist[0:I].sum()
        End = self.atmnumlist[0:I + 1].sum()
        return Start, End

    def get_rdf(self, alphaI, betaI, dr=False):
        try:
            rdfdict = self.rdf
        except AttributeError:
            self.rdf = dict()
        try:
            Ndict = self.N
        except AttributeError:
            self.N = dict()
        if dr == False:
            for rdf in self.rdf:
                if rdf[0:2] == (alphaI, betaI) or rdf[0:2] == (betaI, alphaI):
                    return self.rdf[rdf]
            dr = Defaultdr
        if (alphaI, betaI, dr) in self.rdf or (betaI, alphaI, dr) in self.rdf:
            if (alphaI, betaI, dr) in self.rdf:
                return self.rdf[(alphaI, betaI, dr)]
            else:
                return self.rdf[(betaI, alphaI, dr)]
        else:
            print("calculating rdf of %s and %s, dr=%s" % (self.atmnamelist[alphaI], self.atmnamelist[betaI], dr))
        V = self.get_cellV()
        rho = self.atmnumlist[betaI] / V
        alphaStart, alphaEnd = self._atm_range(alphaI)
        betaStart, betaEnd = self._atm_range(betaI)
        RelatedDis = self.dis[:, alphaStart:alphaEnd, betaStart:betaEnd].copy().flatten()
        RelatedDis.sort(kind="mergesort")
        maxr = RelatedDis.max()
        r_bin = np.array(range(0, math.floor(maxr / dr) + 1)) * dr
        N, edge = np.histogram(RelatedDis, r_bin)
        Frames = len(self.frames)
        g = N / (4 * math.pi * r_bin[1:] * r_bin[1:] * dr * rho * Frames * self.atmnumlist[alphaI])
        self.rdf[(alphaI, betaI, dr)] = [r_bin[1:], g]
        self.N[(alphaI, betaI, dr)] = [r_bin[1:], N]
        return self.rdf[(alphaI, betaI, dr)]

    def someDis(self, alphaI, betaI):
        alphaStart, alphaEnd = self._atm_range(alphaI)
        betaStart, betaEnd = self._atm_range(betaI)
        return self.dis[:, alphaStart:alphaEnd, betaStart:betaEnd]

    def getN(self, alphaI, betaI, dr=False):
        try:
            self.N
        except AttributeError:
            self.N = dict()
        try:
            self.rdf
        except AttributeError:
            self.rdf = dict()
        if dr == False:
            for n in self.N:
                if n[0:2] == (alphaI, betaI) or n[0:2] == (betaI, alphaI):
                    return self.N[n]
            dr = Defaultdr
        if (alphaI, betaI, dr) in self.N or (betaI, alphaI, dr) in self.N:
            if (alphaI, betaI, dr) in self.N:
                return self.N[(alphaI, betaI, dr)]
            else:
                return self.N[(betaI, alphaI, dr)]
        else:
            self.get_rdf(alphaI, betaI, dr)
            return self.N[(alphaI, betaI, dr)]

    def averageCN(self, alphaI, betaI, r_cut=False):
        FrameNum = len(self.frames)
        if r_cut == False:
            rdf = self.get_rdf(alphaI, betaI)
            r_cut = r_min(*rdf)
        N = self.getN(alphaI, betaI)
        Index = np.searchsorted(N[0], r_cut, side='right')
        return N[1][:Index].sum() / FrameNum / self.atmnumlist[alphaI]

    def averageBondLength(self, alphaI, betaI, r_cut=False):
        if r_cut == False:
            rdf = self.get_rdf(alphaI, betaI)
            r_cut = r_min(*rdf)
        rdf = self.get_rdf(alphaI, betaI)
        r = rdf[0]
        g = rdf[1]
        dr = r[2] - r[1]
        Index = np.searchsorted(r, r_cut, side='left')
        r_new = r[:Index + 1]
        g_new = g[:Index + 1]
        return ((r_new - dr / 2) * g_new).sum() / g_new.sum()

    def CN(self, alphaI, betaI, r_cut=False):
        FrameNum = len(self.frames)
        if r_cut == False:
            rdf = self.get_rdf(alphaI, betaI)
            r_cut = r_min(*rdf)
        ABDis = self.someDis(alphaI, betaI).view()
        isBond = np.where(ABDis < r_cut, 1, 0)
        NumAlpha = self.atmnumlist[alphaI]
        Numbeta = self.atmnumlist[betaI]
        return isBond.reshape((FrameNum, NumAlpha * Numbeta)).sum(axis=1) / NumAlpha

    def BondLength(self, alphaI, betaI, r_cut=False):
        FrameNum = len(self.frames)
        if r_cut == False:
            rdf = self.get_rdf(alphaI, betaI)
            r_cut = r_min(*rdf)
        ABDis = self.someDis(alphaI, betaI).view()
        NumAlpha = self.atmnumlist[alphaI]
        Numbeta = self.atmnumlist[betaI]
        isBond = np.where(ABDis < r_cut, 1, 0)
        Bondlength = np.where(isBond == 1, ABDis, 0.0)
        NBond = isBond.reshape((FrameNum, NumAlpha * Numbeta)).sum(axis=1)
        return Bondlength.reshape((FrameNum, NumAlpha * Numbeta)).sum(axis=1) / NBond


class XDAT():
    def __init__(self, XDATName, cache_file, **kwargs):
        self.name = XDATName
        self.cachename = cache_file
        self.timecheck = kwargs.get('time', False)

        if self.timecheck:
            StartTime = time.time()

        cache_exists = os.path.isfile(self.cachename) and os.access(self.cachename, os.R_OK)
        if cache_exists:
            print(f"找到缓存文件: {self.cachename}")
            cachefp = open(self.cachename, 'rb')
            newstrc = pickle.load(cachefp)
            cachefp.close()
            print(f"缓存文件包含 {len(newstrc.frames)} 帧")
        else:
            raise FileNotFoundError(f"未找到缓存文件: {self.cachename}")

        self.structure = newstrc

        if self.timecheck:
            EndTime = time.time()
            print(f"读取耗时: {EndTime - StartTime:.2f} s")

        try:
            self.structure.rdf
            self.rdf_calced = True
        except AttributeError:
            self.rdf_calced = False

    def save(self, silence=False):
        if not silence:
            print(f"保存数据到缓存文件：{self.cachename}")
        sfp = open(self.cachename, 'wb')
        pickle.dump(self.structure, sfp)
        sfp.close()
        if not silence:
            print("数据保存完成")

    def SomeDistance(self, alphaI, betaI, copy=True):
        if copy:
            return self.structure.someDis(alphaI, betaI).copy()
        else:
            return self.structure.someDis(alphaI, betaI)

    def all_rdf(self):
        for i in range(0, len(self.structure.atmnamelist)):
            for j in range(0, len(self.structure.atmnamelist)):
                if not i == j:
                    self.structure.get_rdf(i, j)
        self.save(silence=True)
        self.rdf_calced = True


def testjob():
    print("=" * 60)
    print("正在读取第一个缓存文件...")
    xdat1 = XDAT(XDAT_name, cache_file1, time=True)

    print("\n" + "=" * 60)
    print("正在读取第二个缓存文件...")
    xdat2 = XDAT(XDAT_name, cache_file2, time=True)

    if not xdat1.rdf_calced:
        print("\n正在计算第一个数据集的RDF...")
        xdat1.all_rdf()

    if not xdat2.rdf_calced:
        print("\n正在计算第二个数据集的RDF...")
        xdat2.all_rdf()

    AlO1 = xdat1.structure.get_rdf(0, 1)
    AlO2 = xdat2.structure.get_rdf(0, 1)

    rcut_auto1 = r_min(*AlO1)
    rcut_auto2 = r_min(*AlO2)

    print("\n" + "=" * 60)
    print("计算结果汇总")
    print("=" * 60)
    print(f"1. {cache_file1}:")
    print(f"   - 帧数: {len(xdat1.structure.frames)}")
    print(f"   - Al-O RDF第一最小值（自动截断）: {rcut_auto1:.3f} Å")
    print(f"   - Al-O平均配位数（自动截断）: {xdat1.structure.averageCN(0, 1):.3f}")
    print(f"   - Al-O平均配位数（手动截断 {manual_cutoff}Å）: {xdat1.structure.averageCN(0, 1, r_cut=manual_cutoff):.3f}")
    print(f"   - Al-O平均键长: {xdat1.structure.averageBondLength(0, 1):.3f} Å")

    print(f"\n2. {cache_file2}:")
    print(f"   - 帧数: {len(xdat2.structure.frames)}")
    print(f"   - Al-O RDF第一最小值（自动截断）: {rcut_auto2:.3f} Å")
    print(f"   - Al-O平均配位数（自动截断）: {xdat2.structure.averageCN(0, 1):.3f}")
    print(f"   - Al-O平均配位数（手动截断 {manual_cutoff}Å）: {xdat2.structure.averageCN(0, 1, r_cut=manual_cutoff):.3f}")
    print(f"   - Al-O平均键长: {xdat2.structure.averageBondLength(0, 1):.3f} Å")
    print("=" * 60)

    # 创建图形，子图间距设为0，让中间框线重叠
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=fig_size, sharex=True,
                                   gridspec_kw={'hspace': 0, 'height_ratios': [1, 1]})

    # ---------------------- 上半部分图 ----------------------
    ax1.plot(AlO1[0], AlO1[1], color=rdf_line_color1, linewidth=line_width_rdf1,
             label=legend1_text)

    if show_auto_line1:
        ax1.axvline(rcut_auto1, color=auto_cut_line_color1, linestyle='--',
                    linewidth=line_width_global,
                    label=f'Auto cut-off: {rcut_auto1:.2f} Å')

    if show_manual_line:
        ax1.axvline(manual_cutoff, color=manual_cut_line_color, linestyle='--',
                    linewidth=line_width_global,
                    label=f'Manual cut-off: {manual_cutoff} Å')

    # 保留所有框线，统一线宽
    for spine in ax1.spines.values():
        spine.set_linewidth(line_width_spine)
        spine.set_visible(True)  # 强制显示所有框线

    if grid_on:
        ax1.grid(True, alpha=0.3, linewidth=line_width_grid)

    ax1.set_xlim(x_range)
    ax1.set_ylim(y_range1)

    # 关键修改1：上子图Y轴显示0、8、16、24、32（全部显示）
    ax1.yaxis.set_major_locator(FixedLocator([0, 8, 16, 24, 32]))
    ax1.yaxis.set_minor_locator(AutoMinorLocator(2))
    ax1.xaxis.set_minor_locator(AutoMinorLocator(2))

    # 只显示左侧和下侧刻度（隐藏右侧、上侧刻度）
    ax1.tick_params(
        which='major',
        direction='in',
        width=line_width_tick,
        length=tick_length_major,
        labelsize=font_size_global,
        tick1On=True,   # 显示左侧、下侧刻度
        tick2On=False   # 隐藏右侧、上侧刻度
    )
    ax1.tick_params(
        which='minor',
        direction='in',
        width=line_width_tick_minor,
        length=tick_length_minor,
        tick1On=True,   # 显示左侧、下侧小刻度
        tick2On=False   # 隐藏右侧、上侧小刻度
    )
    ax1.tick_params(axis='y', labelsize=font_size_y_tick1)
    ax1.tick_params(axis='x', labelbottom=False)  # 隐藏上子图X轴标签

    ax1.legend(frameon=False, fontsize=font_size_legend1, loc=legend_location1)
    ax1.set_ylabel('')

    # ---------------------- 下半部分图 ----------------------
    ax2.plot(AlO2[0], AlO2[1], color=rdf_line_color2, linewidth=line_width_rdf2,
             label=legend2_text)

    if show_auto_line2:
        ax2.axvline(rcut_auto2, color=auto_cut_line_color2, linestyle='--',
                    linewidth=line_width_global,
                    label=f'Auto cut-off: {rcut_auto2:.2f} Å')

    if show_manual_line:
        ax2.axvline(manual_cutoff, color=manual_cut_line_color, linestyle='--',
                    linewidth=line_width_global,
                    label=f'Manual cut-off: {manual_cutoff} Å')

    # 保留所有框线，统一线宽
    for spine in ax2.spines.values():
        spine.set_linewidth(line_width_spine)
        spine.set_visible(True)  # 强制显示所有框线

    if grid_on:
        ax2.grid(True, alpha=0.3, linewidth=line_width_grid)

    ax2.set_xlim(x_range)
    ax2.set_ylim(y_range2)

    # 关键修改2：下子图Y轴只显示0、8、16、24（隐藏32）
    ax2.yaxis.set_major_locator(FixedLocator([0, 8, 16, 24]))
    ax2.yaxis.set_minor_locator(AutoMinorLocator(2))

    # 只显示左侧和下侧刻度（隐藏右侧、上侧刻度）
    ax2.tick_params(
        which='major',
        direction='in',
        width=line_width_tick,
        length=tick_length_major,
        labelsize=font_size_global,
        tick1On=True,   # 显示左侧、下侧刻度
        tick2On=False   # 隐藏右侧、上侧刻度
    )
    ax2.tick_params(
        which='minor',
        direction='in',
        width=line_width_tick_minor,
        length=tick_length_minor,
        tick1On=True,   # 显示左侧、下侧小刻度
        tick2On=False   # 隐藏右侧、上侧小刻度
    )
    ax2.tick_params(axis='x', labelsize=font_size_x_tick)
    ax2.tick_params(axis='y', labelsize=font_size_y_tick2)

    ax2.xaxis.set_major_locator(MultipleLocator(x_major_tick))
    ax2.xaxis.set_minor_locator(AutoMinorLocator(2))

    ax2.legend(frameon=False, fontsize=font_size_legend2, loc=legend_location2)
    ax2.set_xlabel('Distance r (Å)', fontsize=font_size_x_label)

    # 添加居中Y轴标签
    fig.text(0.06, 0.5, 'RDF g (r)', fontsize=font_size_y_label,
             rotation='vertical', va='center', ha='center')

    # 手动调整边距，避免标签截断
    plt.subplots_adjust(
        left=0.14,
        right=0.98,
        top=0.95,
        bottom=0.15,
        hspace=0
    )

    fig.canvas.draw()
    plt.show()


if __name__ == '__main__':
    testjob()
else:
    print("你正在使用 结构派 后处理脚本")
    print("https://gitee.com/xczics/structure-py")