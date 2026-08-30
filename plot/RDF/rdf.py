import numpy as np
import time
import pickle
import math
import os
from scipy import interpolate
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, AutoMinorLocator  # 刻度精细控制

# ======================================================================
# ====================== 所有可配置参数（集中在这里！）======================
# ======================================================================

# ---------------------- 基础文件与帧范围设置 ----------------------
fname = "XDATCAR"  # XDATCAR文件名
start_frame = 0  # 起始帧（从0开始，包含）
end_frame = 4999  # 结束帧（不包含，即实际到end_frame-1帧）
# end_frame = None          # 若设为None，则包含从start_frame到最后一帧
specify_cache = None  # 针对性读取缓存文件（例：".structure.XDATCAR_frame_100-300"）
# specify_cache = ".structure.XDATCAR_frame_50-250"  # 示例：直接读取已有缓存

# ---------------------- 图表显示设置 ----------------------
grid_on = False  # 网格线开关（True/False）

# 线宽控制
line_width_global = 2.5  # 全局基础线宽
line_width_rdf = 2.5  # RDF曲线线宽
line_width_spine = 2.5  # 图表边框线宽
line_width_grid = 0.6  # 网格线宽
line_width_tick = 2.5  # 主刻度线宽
line_width_tick_minor = 2.0  # 子刻度线宽（比主刻度略细但足够可见）

# 颜色控制（支持英文颜色名/十六进制码/RGB值）
rdf_line_color = 'blue'  # RDF函数曲线颜色（例：'blue'/'#0000FF'/(0,0,1)）
auto_cut_line_color = 'red'  # 自动截断半径线颜色（例：'green'/'#00FF00'/(0,1,0)）
manual_cut_line_color = 'gray'  # 手动截断半径线颜色

# 截断半径控制
manual_cutoff = 2.35  # 手动截断半径值（可自定义）
show_manual_line = False  # 手动截断线（灰色虚线）开关
show_auto_line = False  # 自动截断线（红色虚线）开关

# 坐标轴范围控制
x_range = [0, 8]  # X轴范围 [最小值, 最大值]
y_range = [-2, 32]  # Y轴范围 [最小值, 最大值]

# 刻度控制
x_major_tick = 2.0  # X轴主刻度间隔
y_major_tick = 8.0  # Y轴主刻度间隔
tick_length_major = 8.0  # 主刻度长度（像素）
tick_length_minor = 6.0  # 子刻度长度（像素）

# 字体大小控制
font_size_global = 28  # 全局基础字体大小
font_size_x_tick = 24  # X轴刻度字体大小
font_size_x_label = 28  # X轴标签字体大小
font_size_y_tick = 24  # Y轴刻度字体大小
font_size_y_label = 28  # Y轴标签字体大小
font_size_legend = 24  # 图例字体大小

# ======================================================================
# ====================== 以下代码无需修改（除非自定义功能）======================
# ======================================================================

# 字体配置（按要求修改）
plt.rcParams["font.family"] = ["DejaVu Sans", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False  # 正常显示负号

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
        # 读取cell_parameter
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
        # 读取每一帧的位置（仅Direct坐标系）
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
    def __init__(self, XDATName, **kwargs):
        self.name = XDATName

        # 帧范围参数（从外部传入）
        self.start_frame = kwargs.get('start_frame', 0)
        self.end_frame = kwargs.get('end_frame', None)

        # 针对性读取缓存参数
        self.specify_cache = kwargs.get('cache_file', None)

        # 生成带帧范围的缓存文件名
        if self.specify_cache is None:
            end_frame_str = "end" if self.end_frame is None else str(self.end_frame)
            self.cachename = f".structure.{XDATName}_frame_{self.start_frame}-{end_frame_str}"
        else:
            self.cachename = self.specify_cache

        self.timecheck = kwargs.get('time', False)

        if self.timecheck:
            StartTime = time.time()

        # 读取缓存或XDATCAR
        cache_exists = os.path.isfile(self.cachename) and os.access(self.cachename, os.R_OK)
        if cache_exists:
            print(f"找到指定缓存文件: {self.cachename}")
            print("注意：如果缓存文件对应的帧范围与当前设置不一致，可能导致错误！")
            print(f"当前设置的帧范围：start={self.start_frame}, end={self.end_frame}")
            cachefp = open(self.cachename, 'rb')
            newstrc = pickle.load(cachefp)
            cachefp.close()

            # 验证缓存中的帧数量是否与范围匹配（仅警告，不强制）
            cache_frame_count = len(newstrc.frames)
            expected_end = self.end_frame if self.end_frame is not None else cache_frame_count
            expected_frame_count = expected_end - self.start_frame
            if cache_frame_count != expected_frame_count:
                print(f"警告：缓存文件包含 {cache_frame_count} 帧，但当前设置期望 {expected_frame_count} 帧")
                print("可能是缓存文件对应的帧范围与当前设置不一致，请检查！")

        else:
            print(f"未找到缓存文件 {self.cachename}")
            print(f"从XDATCAR文件读取数据，帧范围：start={self.start_frame}, end={self.end_frame}")
            newstrc = structure()
            newstrc.readXDATCAR(XDATName)

            # 应用帧范围筛选
            total_frames = len(newstrc.frames)
            print(f"XDATCAR文件共包含 {total_frames} 帧")

            # 处理end_frame超出范围的情况
            if self.end_frame is None or self.end_frame > total_frames:
                self.end_frame = total_frames
                print(f"结束帧超出范围，自动调整为最后一帧：{self.end_frame}")

            # 处理start_frame超出范围的情况
            if self.start_frame < 0:
                self.start_frame = 0
                print("起始帧不能为负，自动调整为0")

            if self.start_frame >= self.end_frame:
                raise ValueError(f"起始帧 {self.start_frame} 必须小于结束帧 {self.end_frame}")

            # 筛选帧
            newstrc.frames = newstrc.frames[self.start_frame:self.end_frame]
            selected_frames = len(newstrc.frames)
            print(f"筛选后实际使用的帧数：{selected_frames} 帧（{self.start_frame}到{self.end_frame - 1}）")

            # 重新计算距离
            newstrc.distances()

            # 保存带范围的缓存
            sfp = open(self.cachename, 'wb')
            pickle.dump(newstrc, sfp)
            sfp.close()
            print(f"缓存文件已保存为：{self.cachename}")

        self.structure = newstrc

        if self.timecheck:
            EndTime = time.time()
            print(f"预处理耗时: {EndTime - StartTime:.2f} s")

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
    # 读取数据（传入配置好的参数）
    xdat = XDAT(
        fname,
        time=True,
        start_frame=start_frame,
        end_frame=end_frame,
        cache_file=specify_cache
    )

    if not xdat.rdf_calced:
        xdat.all_rdf()

    # 计算Al-O RDF
    AlO = xdat.structure.get_rdf(0, 1)
    rcut_auto = r_min(*AlO)

    # 打印结果（包含帧范围信息）
    print("=" * 50)
    print(f"计算配置：Al-O RDF，帧范围 {start_frame}-{end_frame}（共{len(xdat.structure.frames)}帧）")
    print(f"Al-O RDF第一最小值（自动截断）: {rcut_auto:.3f} Å")
    print(f"Al-O平均配位数（自动截断）: {xdat.structure.averageCN(0, 1):.3f}")
    print(f"Al-O平均配位数（手动截断 {manual_cutoff}Å）: {xdat.structure.averageCN(0, 1, r_cut=manual_cutoff):.3f}")
    print(f"Al-O平均键长: {xdat.structure.averageBondLength(0, 1):.3f} Å")
    print("=" * 50)

    # 绘图设置
    fig, ax = plt.subplots(figsize=(10, 6))

    # 绘制RDF曲线
    ax.plot(AlO[0], AlO[1], color=rdf_line_color, linewidth=line_width_rdf,
            label=f'Al-O g(r) 0-10 ps')
    #             label=f'Al-O g(r) (frames {start_frame}-{end_frame})')

    # 绘制自动截断线
    if show_auto_line:
        ax.axvline(rcut_auto, color=auto_cut_line_color, linestyle='--', linewidth=line_width_global,
                   label=f'Auto cut-off {rcut_auto:.2f} Å')

    # 绘制手动截断线
    if show_manual_line:
        ax.axvline(manual_cutoff, color=manual_cut_line_color, linestyle='--', linewidth=line_width_global,
                   label=f'Manual cut-off {manual_cutoff} Å')

    # 边框线宽设置
    for spine in ax.spines.values():
        spine.set_linewidth(line_width_spine)

    # 网格线设置
    if grid_on:
        ax.grid(True, alpha=0.3, linewidth=line_width_grid)

    # 坐标轴范围设置
    ax.set_xlim(x_range)
    ax.set_ylim(y_range)

    # 刻度设置 - 主刻度
    ax.tick_params(
        which='major',
        direction='in',
        width=line_width_tick,
        length=tick_length_major,
        labelsize=font_size_global,
        tick1On=True
    )

    # 刻度设置 - 子刻度
    ax.tick_params(
        which='minor',
        direction='in',
        width=line_width_tick_minor,
        length=tick_length_minor,
        tick1On=True
    )

    # 单独覆盖X/Y轴刻度标签字体大小
    ax.tick_params(axis='x', labelsize=font_size_x_tick)
    ax.tick_params(axis='y', labelsize=font_size_y_tick)

    # 主刻度间隔设置
    ax.xaxis.set_major_locator(MultipleLocator(x_major_tick))
    ax.yaxis.set_major_locator(MultipleLocator(y_major_tick))

    # 子刻度设置
    ax.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))

    # 强制刷新刻度布局
    fig.canvas.draw()

    # 图例设置
    ax.legend(frameon=False, fontsize=font_size_legend)

    # 坐标轴标签
    ax.set_xlabel('Distance r (Å)', fontsize=font_size_x_label)
    ax.set_ylabel('RDF g (r)', fontsize=font_size_y_label)

    # 显示图表
    plt.tight_layout()
    plt.show()


if __name__ == '__main__':
    testjob()
else:
    print("你正在使用 结构派 后处理脚本")
    print("https://gitee.com/xczics/structure-py")