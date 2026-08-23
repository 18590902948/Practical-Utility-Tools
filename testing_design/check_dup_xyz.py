"""
=============================================================================
脚本:        check_dup_xyz.py
功能:        严格检测 xyz / extxyz 文件内部及文件之间的重复结构帧
             (元素组成、晶胞、周期性边界下分数坐标一一对应, 兼容帧内
              原子顺序不同; 坐标须在容差内完全一致, 不做相似性匹配)

双文件模式:  python check_dup_xyz.py <文件A.xyz> <文件B.xyz>
   1. 检测 A 内部重复帧 -> 有则生成 <A>_dedup.xyz
   2. 检测 B 内部重复帧 -> 有则生成 <B>_dedup.xyz
   3. 严格检测两个去重文件之间的重复帧 -> 生成 merged_dedup.xyz
      (A_dedup 全部保留 + B_dedup 中不与 A 重复的帧)
   各阶段发现重复均会在终端告知。

单文件模式:  python check_dup_xyz.py <文件A.xyz>
   检测 A 内部重复帧 -> 有则生成 <A>_dedup.xyz
   发现重复时终端报告: 第 x 和第 y 帧重复 (x<y), 已去除第 y 帧

帧号计数:    与 OVITO 一致, 从 0 开始 (文本编辑器中第一帧为第 0 帧)
输出位置:    全部输出到脚本运行目录下的 check_dup/ 文件夹:
             - <名>_dedup.xyz          去重后的结构 (有重复时生成)
             - merged_dedup.xyz        合并去重结构 (双文件模式)
             - duplicate_frames.xyz    检测到的重复结构帧 (有重复时生成)
             - check_dup.txt           重复检测报告 (仅写文件名, 不含路径)
依赖:        ase, numpy
=============================================================================
"""
import datetime
import os
import sys

import numpy as np
from ase.io import read, write

# Windows 控制台默认 GBK 编码无法输出部分字符, 统一改用 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 指纹量化位数 (仅用于快速分组, 最终判定以严格验证为准)
QUANT_BITS = 6
# 严格验证容差 (分数坐标单位, 约 0.003 Å @ 30 Å 晶胞)
MATCH_TOL = 1e-4
# 晶胞比较容差 (Å)
CELL_TOL = 1e-5
# 输出文件夹 (脚本运行目录下的 check_dup)
OUT_DIR = "check_dup"
# 重复检测报告文件名
REPORT_FILE = "check_dup.txt"
# 重复结构帧输出文件名
DUP_FRAMES_FILE = "duplicate_frames.xyz"


def fingerprint(atoms):
    """快速指纹: 原子数、元素组成、晶胞、分数坐标 (排序 + wrap 后量化)"""
    scaled = atoms.get_scaled_positions(wrap=True)
    return (
        len(atoms),
        tuple(sorted(atoms.get_chemical_symbols())),
        tuple(np.round(np.asarray(atoms.cell[:], dtype=float), QUANT_BITS).flatten()),
        tuple(sorted(tuple(np.round(p, QUANT_BITS)) for p in scaled)),
    )


def _frac_dist(a, b):
    """两个分数坐标之间的最小镜像距离 (PBC)"""
    d = a - b
    d -= np.round(d)
    return float(np.max(np.abs(d)))


def is_duplicate(atoms1, atoms2, tol=MATCH_TOL):
    """严格判定两帧是否等价: 元素计数、晶胞、PBC 下坐标一一对应"""
    if len(atoms1) != len(atoms2):
        return False
    if sorted(atoms1.get_chemical_symbols()) != sorted(atoms2.get_chemical_symbols()):
        return False
    if not np.allclose(
        np.asarray(atoms1.cell[:], dtype=float),
        np.asarray(atoms2.cell[:], dtype=float),
        rtol=0.0, atol=CELL_TOL,
    ):
        return False
    f1 = atoms1.get_scaled_positions(wrap=True)
    f2 = atoms2.get_scaled_positions(wrap=True)
    sym2 = atoms2.get_chemical_symbols()
    used = [False] * len(atoms2)
    # 对 atoms1 每个原子, 贪心找未使用的同元素最近邻
    for i, s1 in enumerate(atoms1.get_chemical_symbols()):
        best, best_d = -1, np.inf
        for j, s2 in enumerate(sym2):
            if used[j] or s2 != s1:
                continue
            d = _frac_dist(f1[i], f2[j])
            if d < best_d:
                best, best_d = j, d
        if best < 0 or best_d > tol:
            return False
        used[best] = True
    return True


def dedup_frames(frames):
    """按指纹分组, 组内严格验证; 每组保留最早帧。

    返回:
      keep    : [(原始帧号, Atoms)], 去重后按原顺序排列
      removed : [(保留帧原始号, 被去除帧原始号)] 记录
      mapping : 原始帧号 -> 去重后帧号 (-1 表示被去除)
    """
    table = {}
    for i, at in enumerate(frames):
        table.setdefault(fingerprint(at), []).append(i)

    keep, removed, mapping = [], [], {}
    for idxs in table.values():
        idxs.sort()
        group_keep = []   # 组内已保留的原始帧号
        for i in idxs:
            dup_of = next((k for k in group_keep if is_duplicate(frames[k], frames[i])), None)
            if dup_of is None:
                group_keep.append(i)
                mapping[i] = len(keep)
                keep.append((i, frames[i]))
            else:
                removed.append((dup_of, i))
                mapping[i] = -1
    return keep, removed, mapping


def load_frames(path):
    """读取多帧 xyz/extxyz, 返回 Atoms 列表"""
    print(f"正在读取: {os.path.abspath(path)}")
    frames = read(path, index=":")
    print(f"  共 {len(frames)} 帧")
    return frames


def report_internal(name, removed):
    """终端报告内部重复: 第 x 和第 y 帧重复 (x<y), 已去除第 y 帧"""
    if not removed:
        print(f"  {name} 内部无重复帧。")
        return
    print(f"  {name} 内部发现 {len(removed)} 处重复:")
    for kept, dropped in sorted(removed, key=lambda r: (r[1], r[0])):
        print(f"  第 {kept} 和第 {dropped} 帧重复 ({kept}<{dropped})，"
              f"已去除第 {dropped} 帧")


def process_file(path, out_dir):
    """单文件流程: 内部去重 -> 有重复则生成 <名>_dedup.xyz。

    返回 (frames, keep, removed, mapping, out_path, dup_frames)
    """
    frames = load_frames(path)
    name = os.path.basename(path)
    print(f"检测 {name} 内部重复 ...")
    keep, removed, mapping = dedup_frames(frames)
    report_internal(name, removed)

    out_path = None
    dup_frames = []
    if removed:
        base = os.path.splitext(name)[0]
        out_path = os.path.join(out_dir, f"{base}_dedup.xyz")
        write(out_path, [at for _, at in keep], format="extxyz")
        # 被去除的重复帧, 按被去除帧号排序
        dup_frames = [frames[d] for _, d in sorted(removed, key=lambda r: (r[1], r[0]))]
        print(f"  已保存去重文件: {os.path.abspath(out_path)} ({len(keep)} 帧)")
    return frames, keep, removed, mapping, out_path, dup_frames


def find_cross_duplicates(keep_a, keep_b):
    """严格检测两个去重列表之间的重复帧。

    keep 元素为 (原始帧号, Atoms)。返回 [(A去重后帧号, B去重后帧号)]。
    """
    table = {}
    for bi, (_, at) in enumerate(keep_b):
        table.setdefault(fingerprint(at), []).append(bi)
    pairs = []
    for ai, (_, ata) in enumerate(keep_a):
        for bi in table.get(fingerprint(ata), []):
            if is_duplicate(ata, keep_b[bi][1]):
                pairs.append((ai, bi))
    return pairs


def append_internal_lines(lines, removed):
    """向报告追加内部重复明细"""
    if not removed:
        lines.append("  无重复帧。")
    else:
        for kept, dropped in sorted(removed, key=lambda r: (r[1], r[0])):
            lines.append(f"  第 {kept} 和第 {dropped} 帧重复, 已去除第 {dropped} 帧")


def save_report(out_dir, lines):
    """写入 check_dup.txt 报告文件"""
    path = os.path.join(out_dir, REPORT_FILE)
    with open(path, "w", encoding="utf-8") as fout:
        fout.write("\n".join(lines) + "\n")
    print(f"已保存检测报告: {os.path.abspath(path)}")


def main():
    args = sys.argv[1:]
    if len(args) == 1:
        file_a = args[0]
    elif len(args) == 2:
        file_a, file_b = args
    else:
        print("用法: python check_dup_xyz.py <文件A.xyz> [<文件B.xyz>]")
        print("  单文件: 检测 A 内部重复帧并去重")
        print("  双文件: 检测 A/B 内部重复并去重, 再检测两文件之间重复")
        sys.exit(1)

    for f in (file_a,) if len(args) == 1 else (file_a, file_b):
        if not os.path.isfile(f):
            print(f"错误: 文件不存在: {f}")
            sys.exit(1)

    # 输出文件夹: 脚本运行目录下的 check_dup
    out_dir = os.path.join(os.getcwd(), OUT_DIR)
    os.makedirs(out_dir, exist_ok=True)

    if len(args) == 1:
        # ================= 单文件模式 =================
        frames_a, keep, removed, mapping, out_path, dup_frames = process_file(file_a, out_dir)
        if removed:
            print(f"  共去除 {len(removed)} 帧, 剩余 {len(keep)} 帧。")

        lines = [
            "=" * 50,
            "重复检测报告",
            "=" * 50,
            f"检测时间: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
            f"文件: {os.path.basename(file_a)} ({len(frames_a)} 帧)",
            "",
            "[内部重复]",
        ]
        append_internal_lines(lines, removed)
        lines.append("")
        lines.append("[输出文件]")
        if out_path:
            lines.append(f"  - {os.path.basename(out_path)} : 去重后结构 ({len(keep)} 帧)")
        else:
            lines.append("  - 无内部重复, 未生成去重文件")
        if dup_frames:
            dup_path = os.path.join(out_dir, DUP_FRAMES_FILE)
            write(dup_path, dup_frames, format="extxyz")
            lines.append(f"  - {DUP_FRAMES_FILE} : 重复结构帧 ({len(dup_frames)} 帧)")
            print(f"已保存重复结构帧: {os.path.abspath(dup_path)} ({len(dup_frames)} 帧)")
        save_report(out_dir, lines)
        return

    # ================= 双文件模式 =================
    name_a = os.path.basename(file_a)
    name_b = os.path.basename(file_b)
    frames_a, keep_a, removed_a, map_a, out_a, dup_a = process_file(file_a, out_dir)
    print()
    frames_b, keep_b, removed_b, map_b, out_b, dup_b = process_file(file_b, out_dir)

    # 文件之间严格检测 (基于各自去重后的帧)
    print(f"\n严格检测 {name_a} 与 {name_b} 去重后的帧之间是否重复 ...")
    pairs = find_cross_duplicates(keep_a, keep_b)
    dup_b_set = set()
    if not pairs:
        print("  两个文件去重后无重复帧。")
    else:
        print(f"  发现 {len(pairs)} 处文件间重复:")
        for ai, bi in pairs:
            orig_a = keep_a[ai][0]
            orig_b = keep_b[bi][0]
            print(f"  {name_a} 帧 {orig_a} <-> {name_b} 帧 {orig_b} 重复")
            dup_b_set.add(bi)
        print(f"  合并时已剔除 {name_b} 中与 {name_a} 重复的 "
              f"{len(dup_b_set)} 帧 (保留 {name_a} 的帧)。")

    # 生成合并去重文件: A 全部 + B 中不与 A 重复的帧
    merged = [at for _, at in keep_a]
    merged += [at for bi, (_, at) in enumerate(keep_b) if bi not in dup_b_set]
    merged_path = os.path.join(out_dir, "merged_dedup.xyz")
    write(merged_path, merged, format="extxyz")
    print(f"已保存合并去重文件: {os.path.abspath(merged_path)} ({len(merged)} 帧)")

    # 收集所有重复结构帧: A 内部被去除 + B 内部被去除 + B 中与 A 重复被剔除
    dup_frames = list(dup_a) + list(dup_b)
    dup_frames += [keep_b[bi][1] for _, bi in pairs]
    dup_path = None
    if dup_frames:
        dup_path = os.path.join(out_dir, DUP_FRAMES_FILE)
        write(dup_path, dup_frames, format="extxyz")
        print(f"已保存重复结构帧: {os.path.abspath(dup_path)} ({len(dup_frames)} 帧)")

    # 检测报告 txt (仅写文件名, 不含路径)
    lines = [
        "=" * 50,
        "重复检测报告",
        "=" * 50,
        f"检测时间: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
        f"文件A: {name_a} ({len(frames_a)} 帧)",
        f"文件B: {name_b} ({len(frames_b)} 帧)",
        "",
        f"[{name_a} 内部重复]",
    ]
    append_internal_lines(lines, removed_a)
    lines.append("")
    lines.append(f"[{name_b} 内部重复]")
    append_internal_lines(lines, removed_b)
    lines.append("")
    lines.append("[文件间重复 (去重后)]")
    if not pairs:
        lines.append("  无重复帧。")
    else:
        for ai, bi in pairs:
            orig_a = keep_a[ai][0]
            orig_b = keep_b[bi][0]
            lines.append(f"  {name_a} 帧 {orig_a} <-> {name_b} 帧 {orig_b}")
        lines.append(f"  合并时剔除 {name_b} 中与 {name_a} 重复的 "
                     f"{len(dup_b_set)} 帧 (保留 {name_a} 的帧)")
    lines.append("")
    lines.append("[输出文件]")
    if out_a:
        lines.append(f"  - {os.path.basename(out_a)} : {name_a} 去重后结构 ({len(keep_a)} 帧)")
    if out_b:
        lines.append(f"  - {os.path.basename(out_b)} : {name_b} 去重后结构 ({len(keep_b)} 帧)")
    lines.append(f"  - merged_dedup.xyz : {name_a}+{name_b} 合并去重 ({len(merged)} 帧)")
    if dup_path:
        lines.append(f"  - {DUP_FRAMES_FILE} : 重复结构帧 ({len(dup_frames)} 帧)")
    save_report(out_dir, lines)


if __name__ == "__main__":
    main()
