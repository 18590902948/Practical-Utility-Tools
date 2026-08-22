"""







这是个失败的思想！！！！！！！！！！！！！！！！









=============================================================================
脚本:        orthocell_projection.py
功能:        按"投影法"将任意倾斜晶胞构造为一个同体积的正交盒子：
             1. 刚体旋转晶胞，使 A 轴与 X 轴对齐，B 落入 XY 平面
                （AoB 平面与 XoY 平面重合）；
             2. 盒子边长取 A2=|A|、B2=|B|·sinγ（B 在 Y 方向的投影长度）、
                C2=V/(A2·B2)（C 相对 AB 平面的垂高），满足 A2·B2·C2=V；
             3. 所有原子只做同样的刚体旋转，不做任何拉伸/变形；
             4. 用半开区间 [0,Lx)×[0,Ly)×[0,Lz) 框取盒子内的原子：
                左/下/前边界计入，右/上/后边界不计，避免重复计数。
             注意：这是几何投影盒，盒边一般不是原晶格矢量的整数组合，
             框出的是"切出来的原子团"，不是周期等价晶胞；如需周期等价
             的正交晶胞请使用 orthocell.py（整数组合搜索 + 周期复制）。
使用方法:    python orthocell_projection.py 输入文件 [输出文件]
             无参数运行时自动扫描脚本所在目录，仅当存在唯一 xyz 文件时使用
参数说明:    输入文件  任意 ASE 可读取的结构文件（xyz/extxyz/POSCAR/cif/cfg 等）
             输出文件  可选；默认输出为 输入名_proj.扩展名，格式由扩展名决定
输出:        正交投影盒子结构文件；终端打印盒边长、原子数与体积校验
算法参数:    见下方"配置区"
作者:        LINGMA
修改日期:    2026-08-22
=============================================================================
"""
import itertools
import os
import sys

import numpy as np

# ============================== 配置区 =====================================
IMAGE_RANGE = 2         # 周期镜像复制范围 [-N,N]，确保盒子附近原子都被考虑
TOL = 1e-6              # 边界比较容差（Angstrom）
DEDUP_TOL = 0.1         # 去重距离阈值（Angstrom），与 orthocell.py 一致
PBC = False             # 输出结构是否标记为周期性（几何切盒默认非周期）
# ===========================================================================

# 输出格式映射：扩展名 -> ASE 格式名
FORMAT_MAP = {
    ".xyz": "xyz", ".extxyz": "extxyz",
    ".vasp": "vasp", ".poscar": "vasp", ".contcar": "vasp",
    ".cif": "cif", ".cfg": "cfg",
    ".lmp": "lammps-data", ".data": "lammps-data",
}


def build_projection_frame(H):
    """构造投影正交坐标系。

    参数:
        H: 3x3 数组，行向量为盒向量 A,B,C
    返回:
        R: 3x3 旋转矩阵（行向量 e1,e2,e3 为旧坐标下的分量），
           新坐标 = 旧坐标 @ R.T
        H2: 旋转后的盒向量，H2[0]=(Lx,0,0)、H2[1]=(Bx,By,0)、H2[2]=(Cx,Cy,Cz)
        L: [Lx, Ly, Lz] 投影盒边长
    """
    A, B, C = H[0], H[1], H[2]
    A1 = np.linalg.norm(A)
    if A1 < 1e-10:
        raise RuntimeError("A 向量长度为零，无法作为对齐轴")
    e1 = A / A1
    # B 在垂直于 A 方向上的分量（即投影到 Y 的方向）
    B_perp = B - (B @ e1) * e1
    By = np.linalg.norm(B_perp)
    if By < 1e-10:
        raise RuntimeError("A、B 共线，无法构造 AoB 平面")
    e2 = B_perp / By
    e3 = np.cross(e1, e2)
    if C @ e3 < 0:
        e3 = -e3  # 保证盒高 C2 为正
    R = np.array([e1, e2, e3])
    H2 = H @ R.T
    L = np.array([H2[0, 0], H2[1, 1], H2[2, 2]])
    return R, H2, L


def collect_atoms_in_box(atoms, R, L, img_range=IMAGE_RANGE, tol=TOL):
    """刚体旋转所有原子（含周期镜像）并按半开区间 [0,Lx)x[0,Ly)x[0,Lz) 框取。

    返回:
        symbols: 保留原子的元素列表
        positions: 保留原子的新笛卡尔坐标 (N,3)
        n_candidates: 框取到的候选原子数（去重前）
    """
    H = np.array(atoms.cell[:], dtype=float)
    Lx, Ly, Lz = L
    symbols, positions = [], []
    for img in itertools.product(range(-img_range, img_range + 1), repeat=3):
        offset = img[0] * H[0] + img[1] * H[1] + img[2] * H[2]
        for sym, p in zip(atoms.symbols, atoms.positions):
            q = (p + offset) @ R.T
            if (-tol <= q[0] < Lx - tol
                    and -tol <= q[1] < Ly - tol
                    and -tol <= q[2] < Lz - tol):
                symbols.append(sym)
                positions.append(q)
    return symbols, np.array(positions), len(symbols)


def _deduplicate(points, tol=DEDUP_TOL):
    """按距离阈值 tol 合并重复点，返回保留点索引（每组取索引最小者）。"""
    if len(points) < 2:
        return np.arange(len(points))
    from scipy.spatial import cKDTree

    tree = cKDTree(points)
    pairs = tree.query_pairs(tol)
    if not pairs:
        return np.arange(len(points))
    parent = list(range(len(points)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return np.array([i for i in range(len(points)) if find(i) == i])


def build_projection_cell(atoms):
    """按投影法构造正交盒子并框取原子，返回新 Atoms 与统计信息。"""
    H = np.array(atoms.cell[:], dtype=float)
    R, H2, L = build_projection_frame(H)

    symbols, pos, n_cand = collect_atoms_in_box(atoms, R, L)
    if n_cand == 0:
        raise RuntimeError("盒子内未框取到任何原子，请检查晶胞设置")

    keep = _deduplicate(pos)
    n_dup = n_cand - len(keep)

    from ase import Atoms
    new = Atoms(symbols=[symbols[i] for i in keep],
                positions=pos[keep],
                cell=np.diag(L),
                pbc=(PBC, PBC, PBC))
    info = {"H2": H2, "L": L, "n_candidates": n_cand, "n_dup": n_dup}
    return new, info


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
    H = np.array(atoms.cell[:], dtype=float)
    print(f"读取: {os.path.abspath(in_file)}")
    print(f"  盒向量:\n{H}")
    print(f"  原子数: {len(atoms)}")

    # 几何信息：边长、夹角与体积
    a = np.linalg.norm(H[0])
    b = np.linalg.norm(H[1])
    c = np.linalg.norm(H[2])
    alpha = np.degrees(np.arccos(np.clip(H[1] @ H[2] / (b * c), -1, 1)))
    beta = np.degrees(np.arccos(np.clip(H[0] @ H[2] / (a * c), -1, 1)))
    gamma = np.degrees(np.arccos(np.clip(H[0] @ H[1] / (a * b), -1, 1)))
    V = abs(np.linalg.det(H))
    print(f"  边长: a={a:.4f}  b={b:.4f}  c={c:.4f}")
    print(f"  夹角: alpha={alpha:.4f}  beta={beta:.4f}  gamma={gamma:.4f}")
    print(f"  体积: V={V:.4f}")

    new, info = build_projection_cell(atoms)
    Lx, Ly, Lz = info["L"]
    Vbox = Lx * Ly * Lz
    print("\n投影正交盒：")
    print(f"  Lx=|A|={Lx:.4f}")
    print(f"  Ly=|B|·sin(gamma)={Ly:.4f}")
    print(f"  Lz=V/(Lx·Ly)={Lz:.4f}")
    print(f"  体积校验: Lx·Ly·Lz={Vbox:.4f}（原体积 {V:.4f}，"
          f"差值 {abs(Vbox - V):.2e}）")
    if abs(Vbox - V) > 1e-4:
        print("  警告: 体积不守恒，请检查输入结构")
    print(f"  旋转后盒向量（非对角分量为剪切量）:\n{info['H2']}")

    print("\n原子框取：")
    print(f"  候选原子（含周期镜像）: {info['n_candidates']}")
    print(f"  去重合并: {info['n_dup']} 个")
    print(f"  保留原子: {len(new)}（原 {len(atoms)}）")
    if len(new) != len(atoms):
        print("  提示: 保留原子数与原胞不同，说明盒子边界切到了原子，"
              "这是投影盒的固有行为")

    # 确定输出文件名与格式
    if len(args) >= 2:
        out_file = args[1]
    else:
        stem, ext = os.path.splitext(in_file)
        ext = ext.lower() if ext else ".xyz"
        out_file = f"{stem}_proj{ext}"
    fmt = FORMAT_MAP.get(os.path.splitext(out_file)[1].lower(), "xyz")
    write(out_file, new, format=fmt)

    print(f"\n输出: {os.path.abspath(out_file)}")
    print("注意: 此投影盒是几何切盒，不是周期等价晶胞；"
          "如需周期等价的正交晶胞请用 orthocell.py")


if __name__ == "__main__":
    main()
