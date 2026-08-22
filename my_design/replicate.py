"""
=============================================================================
脚本:        replicate.py
功能:        对结构文件进行扩胞（supercell），输出统一的基础 xyz 格式。
             基础 xyz 格式参考 xyz_format_example/example.xyz：
             仅保留晶胞（Lattice）、元素与坐标（Properties=species:S:1:pos:R:3
             pbc="T T T"），删除能量、受力、应力等全部附加属性。
支持输入:    xyz / extxyz（单帧或多帧）、.vasp / POSCAR / CONTCAR
使用方法:    python replicate.py 输入文件 a b c [输出文件]      # 指定扩胞倍数
             python replicate.py 输入文件 目标原子数 [输出文件] # 自动搜索最近超胞
             python replicate.py                                # 扫描脚本所在目录
                                                                 # 唯一结构文件并交互输入
输出:        单帧输入 -> 输出文件 或 输入名_super.xyz
             多帧输入 -> 输入名_frame1.xyz / frame2.xyz ...（每帧一个文件；
                         若指定输出文件则以它为主名，如 out1.xyz、out2.xyz）
注意:        扩胞倍数基于第 1 帧原子数计算，所有帧共用同一倍数；
             原子顺序保持输入顺序，不做重排。
作者:        LINGMA
修改日期:    2026-08-22
=============================================================================
"""
import os
import sys
import math

import numpy as np
from ase.io import read, write
from ase.build import make_supercell
from ase import Atoms

# ============================== 配置区 =====================================
DEFAULT_SUFFIX = "_super"   # 单帧输入默认输出后缀（输出为 输入名_super.xyz）
FRAME_TAG = "_frame"        # 多帧输入输出文件名标签（输出为 输入名_frameN.xyz）
DIFF_TOLERANCE = 2.0        # 目标原子数模式：候选偏差容忍倍率（>=1）
                            # 偏差不超过 最小偏差*该值 的候选才参与正方体评选，
                            # 值越大越偏向正方体（可能牺牲原子数接近度）
MIN_DIFF_RATIO = 0.03       # 候选偏差保底下限：目标原子数的比例（默认 3%）
                            # 即使最小偏差为 0（完美匹配），也允许偏差 <= 目标*该值
                            # 的候选参与正方体评选，避免为了精确原子数选到扁盒子
# ===========================================================================

# 可自动识别为结构的文件名/扩展名（用于无参数自动扫描）
STRUCT_NAMES = ("poscar", "contcar")
STRUCT_EXTS = (".xyz", ".extxyz", ".vasp")


def find_nearest_supercell(atoms, target):
    """搜索最接近目标原子数的超胞倍数 (a, b, c)，并尽量使扩胞后盒子接近正方体。

    评选规则:
      1. 计算所有倍数组合的原子数偏差，取最小偏差 best_diff（最近的超胞）；
      2. 偏差不超过 best_diff * DIFF_TOLERANCE 的候选进入评选（容忍范围）；
      3. 入选者按扩胞后盒边长比（最长/最短，越接近 1 越正方）排序，最优者胜出。
    """
    n_atoms = len(atoms)
    if target < n_atoms:
        print("  警告: 目标原子数小于原原子数，返回 1x1x1")
        return (1, 1, 1)

    cell = atoms.cell.lengths()
    ratio = (target / n_atoms) ** (1 / 3)
    max_mult = max(1, int(math.ceil(ratio * 5)))

    # 收集全部候选: (a, b, c, 原子数偏差, 原子数, 盒边长比)
    candidates = []
    for a in range(1, max_mult + 1):
        for b in range(1, max_mult + 1):
            for c in range(1, max_mult + 1):
                n_new = n_atoms * a * b * c
                diff = abs(n_new - target)
                lengths = (cell[0] * a, cell[1] * b, cell[2] * c)
                shape = max(lengths) / min(lengths)  # 边长比，1 = 正方体
                candidates.append((a, b, c, diff, n_new, shape))

    best_diff = min(c[3] for c in candidates)
    # 候选偏差上限：最小偏差 * 容忍倍率，但至少允许 目标原子数*MIN_DIFF_RATIO 的偏差
    diff_limit = max(best_diff * DIFF_TOLERANCE, target * MIN_DIFF_RATIO)
    # 偏差在 diff_limit 内的候选进入正方体评选
    feasible = [c for c in candidates if c[3] <= diff_limit]
    feasible.sort(key=lambda c: (c[5], c[3]))  # 边长比优先，其次偏差
    best = feasible[0]

    # 终端展示评选过程（按偏差排序、偏差相同时按边长比排序的前 8 个候选）
    print(f"  候选评选（按原子数偏差排序，"
          f"偏差 <= {diff_limit:.0f} 参与正方体评选）:")
    print(f"    {'倍数':<10}{'原子数':>8}{'偏差':>8}{'边长比':>10}")
    for a, b, c, diff, n_new, shape in sorted(candidates, key=lambda x: (x[3], x[5]))[:8]:
        mark = "  <- 选中" if (a, b, c) == best[:3] else ""
        print(f"    {f'{a}x{b}x{c}':<10}{n_new:>8}{diff:>8}{shape:>10.2f}{mark}")
    print(f"  选中: {best[0]}x{best[1]}x{best[2]}（{best[4]} 原子, 偏差 {best[3]}, "
          f"边长比 {best[5]:.2f}）")
    return best[0], best[1], best[2]


def read_frames(infile):
    """读取输入文件的所有帧，返回 Atoms 列表。

    xyz/extxyz 支持多帧；.vasp/POSCAR/CONTCAR 为单帧。
    """
    base = os.path.basename(infile).lower()
    ext = os.path.splitext(infile)[1].lower()
    if ext in (".xyz", ".extxyz"):
        frames = read(infile, index=":")
    elif ext == ".vasp" or base in STRUCT_NAMES:
        frames = [read(infile, format="vasp")]
    else:
        frames = read(infile, index=":")  # 其他格式交给 ASE 自动识别
        if not isinstance(frames, list):
            frames = [frames]
    if not frames:
        raise RuntimeError(f"文件 {infile} 未读取到任何原子结构")
    return frames


def clean_to_basic(atoms):
    """只保留元素、坐标、晶胞与周期性，删除全部附加属性
    （能量、受力、应力、电荷、速度等 info 与 arrays）。"""
    return Atoms(numbers=atoms.numbers.copy(),
                 positions=atoms.positions.copy(),
                 cell=atoms.cell.copy(),
                 pbc=atoms.pbc.copy())


def check_periodic(atoms):
    """校验晶胞是否有效（扩胞必须依赖周期性盒子）"""
    if np.allclose(atoms.cell[:], 0):
        raise RuntimeError(
            "未检测到有效晶胞（Lattice），无法扩胞；"
            "请确认输入文件包含盒子信息（如 extxyz 的 Lattice 行）"
        )


def build_out_names(in_file, out_file, n_frames):
    """根据帧数生成输出文件名列表。

    单帧: 使用指定输出文件，否则 输入名_super.xyz
    多帧: 每帧一个文件 输入名_frame1.xyz / frame2.xyz ...
          （指定输出文件时以它的主名作为前缀）
    """
    stem = os.path.splitext(in_file)[0]
    if n_frames == 1:
        return [out_file or f"{stem}{DEFAULT_SUFFIX}.xyz"]
    prefix = stem + FRAME_TAG
    if out_file:
        prefix = os.path.splitext(out_file)[0]
    return [f"{prefix}{i}.xyz" for i in range(1, n_frames + 1)]


def print_structure_info(frames, infile):
    """终端打印输入结构信息"""
    first = frames[0]
    symbols = []
    for s in first.get_chemical_symbols():
        if s not in symbols:
            symbols.append(s)
    print("=" * 70)
    print(f"输入文件: {os.path.abspath(infile)}")
    print(f"  帧数: {len(frames)}，每帧原子数: {len(frames[0])}"
          + (f"（第 {len(frames[0])} 帧起原子数不同）"
             if any(len(f) != len(frames[0]) for f in frames) else ""))
    print(f"  元素种类: {' '.join(symbols)}")
    print(f"  盒向量(第1帧):\n{np.array(first.cell[:])}")


def main():
    args = sys.argv[1:]
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # ---------- 参数解析 ----------
    def is_int(s):
        try:
            int(s)
            return True
        except ValueError:
            return False

    if not args:
        # 无参数：扫描脚本目录唯一结构文件，交互输入扩胞参数
        candidates = []
        for name in sorted(os.listdir(script_dir)):
            full = os.path.join(script_dir, name)
            if not os.path.isfile(full):
                continue
            base, ext = os.path.splitext(name)
            if ext.lower() in STRUCT_EXTS or base.lower() in STRUCT_NAMES:
                candidates.append(full)
        if len(candidates) != 1:
            print(f"错误: 脚本目录下结构文件数为 {len(candidates)}，"
                  "请指定输入文件，或确保目录下只有一个结构文件")
            sys.exit(1)
        in_file = candidates[0]
        print(f"自动扫描到: {os.path.abspath(in_file)}")
        mode = input("扩胞方式 (1=指定倍数 a b c, 2=目标原子数): ").strip()
        if mode == "1":
            a, b, c = map(int, input("输入扩胞倍数 a b c（空格分隔）: ").split())
        elif mode == "2":
            a = b = c = None
            target_num = int(input("输入目标原子数: "))
        else:
            print("错误: 无效选择")
            sys.exit(1)
        out_file = None
    elif len(args) >= 4:
        # 用法 1: 输入 a b c [输出]
        in_file = args[0]
        a, b, c = map(int, args[1:4])
        out_file = args[4] if len(args) >= 5 else None
        target_num = None
    elif len(args) == 3 and is_int(args[1]) and is_int(args[2]):
        # 用法 1 简写: 输入 a b c
        in_file = args[0]
        a, b, c = map(int, args[1:4])
        out_file = None
        target_num = None
    elif len(args) in (2, 3):
        # 用法 2: 输入 目标原子数 [输出]
        in_file = args[0]
        a = b = c = None
        target_num = int(args[1])
        out_file = args[2] if len(args) == 3 else None
    else:
        print("使用方法:")
        print("  python replicate.py 输入文件 a b c [输出文件]")
        print("  python replicate.py 输入文件 目标原子数 [输出文件]")
        sys.exit(1)

    if not os.path.isfile(in_file):
        print(f"错误: 找不到输入文件 {in_file}")
        sys.exit(1)

    # ---------- 读取与信息打印 ----------
    try:
        frames = read_frames(in_file)
    except Exception as e:
        print(f"错误: 读取输入文件失败 - {e}")
        sys.exit(1)

    print_structure_info(frames, in_file)
    for f in frames:
        check_periodic(f)

    # ---------- 计算扩胞倍数 ----------
    n0 = len(frames[0])
    if target_num is not None:
        a, b, c = find_nearest_supercell(frames[0], target_num)
        print(f"  目标原子数: {target_num}，搜索得到 {a} x {b} x {c}"
              f"（单帧 {n0} -> {n0 * a * b * c} 原子）")
    else:
        if any(x <= 0 for x in (a, b, c)):
            print("错误: a b c 必须为正整数")
            sys.exit(1)
        print(f"  扩胞倍数: {a} x {b} x {c}"
              f"（单帧 {n0} -> {n0 * a * b * c} 原子）")

    # ---------- 扩胞与输出 ----------
    P = np.diag([a, b, c])
    out_names = build_out_names(in_file, out_file, len(frames))
    print("=" * 70)
    print("输出文件（基础 xyz 格式，已删除多余属性）:")
    for f, out_name in zip(frames, out_names):
        new = clean_to_basic(make_supercell(f, P))
        write(out_name, new, format="extxyz")
        print(f"  {os.path.abspath(out_name)}  ({len(new)} 原子)")

    # 提示 ASE 格式误判的坑：文件名含 POSCAR/CONTCAR 字样时会被当 vasp 读
    if any(any(k in os.path.basename(n).upper() for k in ("POSCAR", "CONTCAR"))
           for n in out_names):
        print("\n提示: 输出文件名含 POSCAR/CONTCAR 字样，ASE 自动识别会误判为 VASP 格式；")
        print("      用 ASE 读取时请显式指定格式: read(文件名, format=\"extxyz\")")

    print("=" * 70)
    print("扩胞完成！")


if __name__ == "__main__":
    main()
