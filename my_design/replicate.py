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
             python replicate.py 输入文件 -f 目标原子数        # 多帧 frame 模式
             python replicate.py 输入文件 目标原子数 -g        # 多帧 global 模式
             python replicate.py                                # 扫描脚本所在目录
                                                                 # 唯一结构文件并交互输入
参数说明:    -f / -g 指定多帧扩胞模式（可放在任意位置）；不指定时多帧输入会交互询问
输出:        所有输出默认放入输入文件所在目录的 replicate/ 子文件夹
             单帧输入 -> 输出文件 或 输入名_super.xyz
             多帧输入 frame 模式 -> frame0.xyz / frame1.xyz / frame2.xyz ...
                                  （每帧一个文件）
             多帧输入 global 模式 -> 输入名_global.xyz（单个多帧文件，
                                  每帧为原始对应帧扩胞后的结构）
             replicate/replicate.txt -> 每帧扩胞记录日志（多次运行追加）
注意:        目标原子数模式对每一帧按自身原子数单独计算扩胞倍数；
             指定倍数模式所有帧共用同一倍数；
             处理按 10 帧一批进行（分批打印/写日志/写文件，降低内存占用）；
             原子顺序保持输入顺序，不做重排。
作者:        LINGMA
修改日期:    2026-08-22
=============================================================================
"""
import os
import sys
import math
import time

import numpy as np
from ase.io import read, write
from ase.build import make_supercell
from ase import Atoms

# ============================== 配置区 =====================================
DEFAULT_SUFFIX = "_super"   # 单帧输入默认输出后缀（输出为 输入名_super.xyz）
FRAME_PREFIX = "frame"       # 多帧输入 frame 模式文件名前缀（frame0.xyz、frame1.xyz ...）
GLOBAL_SUFFIX = "_global"   # 多帧输入 global 模式输出后缀（输入名_global.xyz）
OUTPUT_DIR = "replicate"    # 默认输出子文件夹名（位于输入文件所在目录下）
LOG_FILE = "replicate.txt"  # 每帧扩胞记录日志文件名（追加模式，放输出目录下）
BATCH_SIZE = 10             # 每攒够多少帧统一输出一次（终端打印 + 日志 + 写文件，
                            # 分批释放内存）
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


def build_out_names(in_file, out_file, out_dir, mode, n_frames):
    """生成输出文件名列表（默认放在 out_dir 目录下）。

    单帧: 使用指定输出文件，否则 输入名_super.xyz
    多帧 frame 模式: 每帧一个文件 frame0.xyz / frame1.xyz / frame2.xyz ...
    多帧 global 模式: 输入名_global.xyz（单个多帧文件）
    （指定输出文件时以它作为文件名或主名）
    """
    stem = os.path.splitext(os.path.basename(in_file))[0]
    if n_frames == 1:
        return [os.path.join(out_dir, out_file or f"{stem}{DEFAULT_SUFFIX}.xyz")]
    if mode == "global":
        return [os.path.join(out_dir, out_file or f"{stem}{GLOBAL_SUFFIX}.xyz")]
    prefix = os.path.splitext(out_file)[0] if out_file else FRAME_PREFIX
    return [os.path.join(out_dir, f"{prefix}{i}.xyz") for i in range(n_frames)]


def print_structure_info(frames, infile):
    """终端打印输入结构信息（支持各帧原子数/元素不同的多帧文件）"""
    # 元素种类：全部帧的并集（保持出现顺序）
    symbols = []
    for f in frames:
        for s in f.get_chemical_symbols():
            if s not in symbols:
                symbols.append(s)
    n_atoms_list = sorted({len(f) for f in frames})

    print("=" * 70)
    print(f"输入文件: {os.path.abspath(infile)}")
    print(f"  帧数: {len(frames)}")
    if len(n_atoms_list) == 1:
        print(f"  原子数: {n_atoms_list[0]}，元素: {' '.join(symbols)}")
    else:
        print(f"  原子数: {n_atoms_list[0]} ~ {n_atoms_list[-1]}（各帧不同）")
        print(f"  元素种类: {' '.join(symbols)}")


def main():
    # 提取模式参数 -f/-g（可出现在任意位置），其余参数按原逻辑解析
    mode_arg = None
    args = []
    for a in sys.argv[1:]:
        if a in ("-f", "--frame"):
            mode_arg = "frame"
        elif a in ("-g", "--global"):
            mode_arg = "global"
        else:
            args.append(a)
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
    else:
        if any(x <= 0 for x in (a, b, c)):
            print("错误: a b c 必须为正整数")
            sys.exit(1)
        print(f"  扩胞倍数: {a} x {b} x {c}"
              f"（单帧 {n0} -> {n0 * a * b * c} 原子）")

    # ---------- 多帧模式选择（单帧无需选择；命令行 -f/-g 优先） ----------
    mode = "frame"
    if len(frames) > 1:
        if mode_arg:
            mode = mode_arg
            print("多帧扩胞模式: " + ("帧模式（每帧一个文件）" if mode == "frame"
                                      else "全局模式（一个多帧文件）"))
        else:
            mode = input("多帧扩胞模式 (f=帧模式, 每帧一个文件; "
                         "g=全局模式, 一个多帧文件) [默认 f]: ").strip().lower()
            mode = "frame" if mode != "g" else "global"

    # ---------- 确定输出目录（默认 输入文件所在目录/replicate） ----------
    if out_file and os.path.dirname(out_file):
        out_dir = os.path.dirname(os.path.abspath(out_file))  # 显式指定输出路径
        out_file = os.path.basename(out_file)
    else:
        out_dir = os.path.join(os.path.dirname(os.path.abspath(in_file)), OUTPUT_DIR)
    os.makedirs(out_dir, exist_ok=True)

    # ---------- 扩胞与输出（逐帧计算倍数，攒够 BATCH_SIZE 帧统一输出） ----------
    out_names = build_out_names(in_file, out_file, out_dir, mode, len(frames))
    mode_display = "帧模式" if mode == "frame" else "全局模式"
    if mode == "frame":
        prefix = os.path.splitext(out_file)[0] if out_file else FRAME_PREFIX
        out_display = prefix + "*.xyz"    # 帧模式文件模板（如 frame*.xyz）
    else:
        out_display = os.path.basename(out_names[0])
    print("=" * 70)
    print(f"  {'输出文件（基础 xyz 格式）':<24}{out_display:>44}")
    print(f"  {'帧扩胞模式':<24}{mode_display:>44}")
    print("帧扩胞明细")
    header = (f"{'帧号':>6}{'输入原子数':>16}{'扩胞向量':>14}"
              f"{'扩胞倍数':>12}{'输出原子数':>14}{'输出文件':>34}")
    print(header)

    # 日志先写头部（时间/输入/概要/表头），数据行随批次追加
    log_file = os.path.join(out_dir, LOG_FILE)
    with open(log_file, "a") as fout:
        fout.write("=" * 60 + "\n")
        fout.write(f"扩胞时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        fout.write(f"输入文件: {os.path.abspath(in_file)}\n")
        fout.write(f"  {'输出文件（基础 xyz 格式）':<24}{out_display:>44}\n")
        fout.write(f"  {'帧扩胞模式':<24}{mode_display:>44}\n")
        fout.write("帧扩胞明细\n")
        fout.write(header + "\n")

    # 全局模式: 输出文件从头重写，分批追加，避免一次性占满内存
    if mode == "global" and os.path.exists(out_names[0]):
        os.remove(out_names[0])

    batch_lines = []                      # 攒够一批的行（终端打印 + 写日志）
    batch_atoms = []                      # 全局模式: 攒够一批的结构
    for i, f in enumerate(frames, 1):
        # 目标原子数模式: 每一帧按自身原子数单独计算最接近的超胞倍数
        if target_num is not None:
            fa, fb, fc = find_nearest_supercell(f, target_num)
        else:
            fa, fb, fc = a, b, c
        new = clean_to_basic(make_supercell(f, np.diag([fa, fb, fc])))
        if mode == "frame":
            write(out_names[i - 1], new, format="extxyz")
            out_name = os.path.basename(out_names[i - 1])
        else:
            batch_atoms.append(new)
            out_name = os.path.basename(out_names[0])
            # 攒够一批（或最后一批）时写入输出文件，分批释放内存
            if len(batch_atoms) == BATCH_SIZE or i == len(frames):
                write(out_names[0], batch_atoms, format="extxyz", append=True)
                batch_atoms = []
        line = (f"{i:>6}{len(f):>16}{f'{fa}*{fb}*{fc}':>14}{fa * fb * fc:>12}"
                f"{len(new):>14}{out_name:>34}")
        batch_lines.append(line)
        # 攒够一批（或最后一批）时统一终端打印 + 追加日志
        if len(batch_lines) == BATCH_SIZE or i == len(frames):
            for l in batch_lines:
                print(l)
            with open(log_file, "a") as fout:
                for l in batch_lines:
                    fout.write(l + "\n")
            batch_lines = []

    # 提示 ASE 格式误判的坑：文件名含 POSCAR/CONTCAR 字样时会被当 vasp 读
    if any(any(k in os.path.basename(n).upper() for k in ("POSCAR", "CONTCAR"))
           for n in out_names):
        print("\n提示: 输出文件名含 POSCAR/CONTCAR 字样，ASE 自动识别会误判为 VASP 格式；")
        print("      用 ASE 读取时请显式指定格式: read(文件名, format=\"extxyz\")")

    with open(log_file, "a") as fout:
        fout.write("=" * 60 + "\n")
    print(f"扩胞记录已追加: {os.path.abspath(log_file)}")

    print("=" * 70)
    print("扩胞完成！")


if __name__ == "__main__":
    main()
