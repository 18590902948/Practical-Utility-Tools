"""
=============================================================================
脚本:        orthocell.py
功能:        将任意晶胞（盒子）转换为等价的正交（直角）盒子。
             算法移植自 atomsk 的 -orthocell 选项
             （atomsk/src/options/opt_orthocell.f90, GPL v3, P. Hirel）：
             1. 沿 X/Y/Z 三个笛卡尔轴，搜索原盒向量 H1,H2,H3 的整数线性组合
                m*H1+n*H2+o*H3，使其与该轴对齐（保持晶格周期性）；
             2. 用这些新向量构成正交盒子，按周期复制原子填满新盒子；
             3. 已对齐但指向负方向的轴会被翻转（此时原子数不变）。
使用方法:    python orthocell.py 输入文件 [输出文件]
             无参数运行时自动扫描脚本所在目录，仅当存在唯一 xyz 文件时使用
参数说明:    输入文件  任意 ASE 可读取的结构文件（xyz/extxyz/POSCAR/cif/cfg 等）
             输出文件  可选；默认输出为 输入名_ortho.扩展名，格式由扩展名决定
输出:        正交盒子结构文件；终端打印新盒向量与原子数变化
算法参数:    见下方"配置区"，ACCURACY 对应 atomsk 的 orthocell accuracy
作者:        LINGMA
修改日期:    2026-08-22
=============================================================================
"""
import os
import sys

import numpy as np

# ============================== 配置区 =====================================
ACCURACY = 0.01        # 对齐精度阈值（Angstrom / 角度判据），atomsk 默认 0.01
MAX_N = 200            # 整数组合搜索范围上限（atomsk 会搜到 600，Python 内存受限）
DEDUP_TOL = 0.1        # 复制原子去重距离阈值（Angstrom），与 atomsk 一致
# ===========================================================================

# 输出格式映射：扩展名 -> ASE 格式名
FORMAT_MAP = {
    ".xyz": "xyz", ".extxyz": "extxyz",
    ".vasp": "vasp", ".poscar": "vasp", ".contcar": "vasp",
    ".cif": "cif", ".cfg": "cfg",
    ".lmp": "lammps-data", ".data": "lammps-data",
}


def find_orthogonal_vectors(H, accuracy=ACCURACY):
    """搜索与 X/Y/Z 轴对齐的最小正交盒向量。

    参数:
        H: 3x3 数组，行向量为盒向量 H1,H2,H3
        accuracy: 对齐精度（对应 atomsk 的 orthocell accuracy）
    返回:
        uv: 3 元素数组，新正交盒边长（沿 X/Y/Z 的正方向）
        mno: 3x3 整数数组，mno[i] = (m,n,o)，即新向量 i 是 m*H1+n*H2+o*H3
        aligned: 3 元素布尔数组，原盒向量是否已对齐对应坐标轴
        reversed_: 3 元素布尔数组，对齐的轴是否需要翻转方向
    """
    aligned = np.zeros(3, dtype=bool)
    reversed_ = np.zeros(3, dtype=bool)
    uv = np.zeros(3)
    mno = np.zeros((3, 3), dtype=int)

    # 检查原盒向量是否已对齐坐标轴（非对角分量约为 0）
    for i in range(3):
        if abs(np.linalg.norm(H[i]) - abs(H[i, i])) < 1e-6:
            aligned[i] = True
            uv[i] = np.linalg.norm(H[i])
            if H[i, i] < 0:
                reversed_[i] = True  # 对齐但指向负方向，需要翻转

    if aligned.all():
        # 全部已对齐（最多只需翻转负方向），无需搜索
        return uv, mno, aligned, reversed_

    axes = np.eye(3)
    # 逐级扩大搜索范围：先在 N=10 快速找，找不到再扩大（与 atomsk 策略一致）
    solved = aligned.copy()
    uv2, mno2 = uv.copy(), mno.copy()
    for N in (10, 50, MAX_N):
        # 生成 (2N+1)^3 个整数组合，分块向量化计算，避免内存爆炸
        width = 2 * N + 1
        total = width ** 3
        chunk = 2_000_000
        for i in range(3):
            if solved[i]:
                continue
            j, k = (i + 1) % 3, (i + 2) % 3
            best, best_key, best_mno = None, None, None
            for start in range(0, total, chunk):
                idx = np.arange(start, min(start + chunk, total))
                m = idx // (width * width) - N
                r = idx % (width * width)
                n = r // width - N
                o = r % width - N
                # 所有组合的向量 V = m*H1 + n*H2 + o*H3
                V = m[:, None] * H[0] + n[:, None] * H[1] + o[:, None] * H[2]
                vlen = np.linalg.norm(V, axis=1)
                valid = vlen > 1.0  # 排除零向量和过短向量（与 atomsk 一致）
                V, vlen, m, n, o = V[valid], vlen[valid], m[valid], n[valid], o[valid]
                if len(V) == 0:
                    continue
                # 向量与轴 i 的夹角（度）
                cosang = np.clip(V @ axes[i] / vlen, -1.0, 1.0)
                alpha = np.degrees(np.arccos(cosang))
                # 条件 1：足够对齐（角度或非对角分量判据），取最短向量
                cond1 = (alpha < accuracy / 10) | (
                    (np.abs(V[:, j]) < accuracy) & (np.abs(V[:, k]) < accuracy)
                )
                if cond1.any():
                    # 组内最短者与当前最优比较（atomsk：vlen < 已保存长度才替换）
                    i1 = np.argmin(vlen[cond1])
                    cand = V[cond1][i1]
                    if best is None or np.linalg.norm(cand) < best_key:
                        best, best_key = cand, np.linalg.norm(cand)
                        best_mno = (m[cond1][i1], n[cond1][i1], o[cond1][i1])
                else:
                    # 条件 2：更严格对齐（即使向量更长），取最对齐的
                    cond2 = (alpha < accuracy / 100) | (
                        (np.abs(V[:, j]) < 0.1 * accuracy)
                        & (np.abs(V[:, k]) < 0.1 * accuracy)
                    )
                    if not cond2.any():
                        continue
                    sel = V[cond2]
                    # 先按非对角分量和（对齐度）再按长度排序，取最对齐者
                    order = np.lexsort((vlen[cond2],
                                        np.abs(sel[:, j]) + np.abs(sel[:, k])))
                    cand = sel[order[0]]
                    if best is None or (
                        abs(cand[j]) < abs(best[j]) and abs(cand[k]) < abs(best[k])
                    ):
                        best = cand
                        best_key = np.linalg.norm(cand)
                        best_mno = (m[cond2][order[0]], n[cond2][order[0]], o[cond2][order[0]])
            if best is not None:
                solved[i] = True
                uv2[i] = abs(best[i])  # 与轴 i 对齐，第 i 分量即边长
                mno2[i] = best_mno
        if solved.all():
            break
    if not solved.all():
        raise RuntimeError(
            f"在搜索范围 N={MAX_N} 内未找到与坐标轴对齐的盒向量，"
            "该晶格取向可能无法用整数组合得到正交盒（atomsk 会搜索到 N=600）"
        )
    return uv2, mno2, aligned, reversed_


def _deduplicate(points, tol=DEDUP_TOL):
    """按距离阈值 tol 合并重复点（对应 atomsk 的 0.1 Angstrom 去重），
    返回每组保留第一个点（索引最小者）的索引数组。"""
    if len(points) < 2:
        return np.arange(len(points))
    from scipy.spatial import cKDTree

    tree = cKDTree(points)
    pairs = tree.query_pairs(tol)  # 距离 < tol 的点对
    if not pairs:
        return np.arange(len(points))
    # 并查集：合并所有相邻点，每组取索引最小者
    parent = list(range(len(points)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)  # 保留索引小者
    return np.array([i for i in range(len(points)) if find(i) == i])


def build_orthorhombic_cell(atoms):
    """将 Atoms 的任意盒子转换为等价的正交盒子，返回新的 Atoms。

    保持原子种类与周期性；已对齐的盒子（含负方向）原子数不变，
    一般斜盒子会按周期复制原子。
    """
    H = np.array(atoms.cell[:], dtype=float)
    uv, mno, aligned, reversed_ = find_orthogonal_vectors(H)

    # 特殊情况：三个盒向量原本就对齐坐标轴（至多翻转负方向）
    if aligned.all():
        pos = np.array(atoms.positions, dtype=float)
        for i in range(3):
            if reversed_[i]:
                pos[:, i] += uv[i]  # 原子整体平移该轴向量，保持周期性
        new = atoms.copy()
        new.cell = np.diag(uv)
        new.set_positions(pos)
        return new

    # 一般情况：按周期复制原子填满新正交盒子
    # 复制范围 = 2 * 对应系数最大值（与 atomsk 一致），至少为 1
    rm = max(1, 2 * int(np.abs(mno[:, 0]).max()))
    rn = max(1, 2 * int(np.abs(mno[:, 1]).max()))
    ro = max(1, 2 * int(np.abs(mno[:, 2]).max()))

    cands, owners = [], []  # 新盒内的复制位置及其所属原原子索引
    for ai, p in enumerate(atoms.positions):
        for m in range(-rm, rm + 1):
            for n in range(-rn, rn + 1):
                for o in range(-ro, ro + 1):
                    tp = p + m * H[0] + n * H[1] + o * H[2]
                    if (-1e-12 < tp[0] <= uv[0] - 1e-12
                            and -1e-12 < tp[1] <= uv[1] - 1e-12
                            and -1e-12 < tp[2] <= uv[2] - 1e-12):
                        cands.append(tp)
                        owners.append(ai)
    if not cands:
        raise RuntimeError("新正交盒内未收集到任何原子，请检查盒子设置")

    cands = np.array(cands)
    keep = _deduplicate(cands)
    # 组装新 Atoms：只保留元素与位置（与 atomsk 行为一致，不保留附加属性）
    from ase import Atoms
    new = Atoms(numbers=atoms.numbers[np.array(owners)[keep]],
                positions=cands[keep],
                cell=np.diag(uv),
                pbc=atoms.pbc)
    return new


def main():
    args = sys.argv[1:]
    script_dir = os.path.dirname(os.path.abspath(__file__))

    if args:
        in_file = args[0]
        if not os.path.isfile(in_file):
            print(f"错误：找不到输入文件 {in_file}")
            sys.exit(1)
    else:
        # 无参数：自动扫描脚本所在目录唯一的 xyz 文件
        xyz_files = [f for f in os.listdir(script_dir)
                     if f.endswith((".xyz", ".extxyz"))]
        if len(xyz_files) != 1:
            print("错误：请指定输入文件，或确保脚本目录下只有一个 xyz 文件")
            sys.exit(1)
        in_file = os.path.join(script_dir, xyz_files[0])

    from ase.io import read, write

    atoms = read(in_file)
    print(f"读取: {os.path.abspath(in_file)}")
    print(f"  盒向量:\n{np.array(atoms.cell[:])}")
    print(f"  原子数: {len(atoms)}")

    # 判断盒子是否已是正方向的对角正交盒
    cell = np.array(atoms.cell[:], dtype=float)
    if np.allclose(cell - np.diag(np.diag(cell)), 0, atol=1e-6) and np.all(np.diag(cell) > 0):
        print("\n盒子已是正方向的正交盒子，无需转换")
        return

    new_atoms = build_orthorhombic_cell(atoms)

    # 确定输出文件名与格式
    if len(args) >= 2:
        out_file = args[1]
    else:
        stem, ext = os.path.splitext(in_file)
        ext = ext.lower() if ext else ".xyz"
        out_file = f"{stem}_ortho{ext}"
    fmt = FORMAT_MAP.get(os.path.splitext(out_file)[1].lower(), "xyz")
    write(out_file, new_atoms, format=fmt)

    print("\n转换完成！")
    print(f"  新盒向量:\n{np.array(new_atoms.cell[:])}")
    print(f"  新原子数: {len(new_atoms)}（原 {len(atoms)}）")
    print(f"  输出: {os.path.abspath(out_file)}")


if __name__ == "__main__":
    main()
