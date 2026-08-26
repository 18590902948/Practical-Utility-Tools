"""
=============================================================================
脚本:        check_dup_xyz.py
分类:        结构处理工具
功能:        严格检测 xyz / extxyz 文件内部及文件之间的重复结构帧
             (元素组成、晶胞、周期性边界下分数坐标一一对应, 兼容帧内
              原子顺序不同; 坐标须在容差内完全一致, 不做相似性匹配)
使用方法:    python check_dup_xyz.py <文件A.xyz> [<文件B.xyz> ...]
参数:        -h/--help     显示本帮助
输入文件:    <文件A.xyz>        待检测的 xyz/extxyz 文件, 支持任意数量
                            (1 个: 检测内部重复; 2+ 个: 先检测各文件
                            内部重复, 再检测文件间重复, 按顺序合并
                            去重; 相对路径先按当前运行目录探测, 不
                            存在再相对脚本所在目录解析)
输出文件:
  <名>_dedup.xyz          去重后的结构 (有内部重复时生成)
  merged_dedup.xyz        合并去重结构 (多文件模式: 第一个文件全部
                          保留 + 后续文件中去掉与前面重复的帧)
  duplicate_frames.xyz    检测到的重复结构帧 (有重复时生成)
  check_dup.txt           重复检测报告 (分节明细: 标题/时间戳/各阶段/
                          末尾汇总, 覆盖写, 仅写文件名不含路径)
输出路径:    脚本所在目录下的 check_dup/ 文件夹
帧号约定:    OVITO 0 起始索引 (0 = 第一帧, 编辑器中第 n+1 帧)
示例:
  python check_dup_xyz.py ./A.xyz                     # 单文件: 检测内部重复
  python check_dup_xyz.py ./A.xyz ./B.xyz             # 双文件: 内部+文件间重复
  python check_dup_xyz.py ./A.xyz ./B.xyz ./C.xyz     # 多文件: 按顺序合并去重
依赖:        ase, numpy
作者:        隼蝶.
最后修改:    2026-08-24
=============================================================================
"""
import datetime
import os
import sys

# ============================== 参数配置区 =====================================
QUANT_BITS   = 6                          # 指纹量化位数 (仅用于快速分组, 最终判定以严格验证为准)
MATCH_TOL    = 1e-4                       # 严格验证容差 (分数坐标单位, 约 0.003 Å @ 30 Å 晶胞)
CELL_TOL     = 1e-5                       # 晶胞比较容差 (Å)
OUT_DIR      = "check_dup"                # 输出文件夹 (相对脚本所在目录)
REPORT_FILE  = "check_dup.txt"            # 重复检测报告文件名 (覆盖写, 分节明细)
DUP_FRAMES_FILE = "duplicate_frames.xyz"  # 重复结构帧输出文件名
# =============================================================================

# ============================== 环境准备区 =====================================
# Windows 控制台默认 GBK 编码无法输出部分字符 (emoji 等), 统一切换 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 依赖检查: 缺少 ase/numpy 时给出明确的安装提示后退出
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # 脚本所在目录

try:
    import numpy as np
    from ase.io import read, write
except ImportError:
    print("❌ 错误: 未找到 ASE (Python 库)。请安装: pip install ase")
    sys.exit(1)
# =============================================================================


# ============================== 函数配置区 =====================================


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
    """读取多帧 xyz/extxyz, 返回 Atoms 列表。"""
    print(f"📦 正在读取: {os.path.abspath(path)}")
    frames = read(path, index=":")
    print(f"  ✅ 共 {len(frames)} 帧")
    return frames


def report_internal(name, removed):
    """终端报告内部重复: OVITO 帧号 0 起始, 同时提示编辑器中第 n+1 帧
    (规范第六条: 两种视角提示, 便于当场核对)。"""
    if not removed:
        print(f"  ✅ {name} 内部无重复帧。")
        return
    print(f"  ⚠️ {name} 内部发现 {len(removed)} 处重复:")
    for kept, dropped in sorted(removed, key=lambda r: (r[1], r[0])):
        print(f"  📦 OVITO 帧 {kept} 与 {dropped} 重复 (编辑器中第 "
              f"{kept + 1}/{dropped + 1} 帧, {kept}<{dropped})，"
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
        print(f"  ✅ 已保存去重文件: {os.path.abspath(out_path)} ({len(keep)} 帧)")
    return frames, keep, removed, mapping, out_path, dup_frames


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
    print(f"  📄 已保存检测报告: {os.path.abspath(path)}")


def print_usage():
    """打印头部注释块 (脚本功能与完整使用方法)。"""
    print(__doc__)


# ============================== 脚本工作区 =====================================
def parse_args(argv):
    """解析命令行参数: -h/--help 为选项, 其余为输入文件 (任意数量, 至少 1 个)。
    无参数时提示缺少必要参数 (帮助一律通过 -h/--help 获取)。"""
    files = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        files.append(arg)
        i += 1
    return files


def resolve_input_file(f, script_dir):
    """输入文件路径解析: 绝对路径照旧; 相对路径先按当前运行目录探测,
    不存在再相对脚本所在目录解析 (规范第八节路径约定)。"""
    if os.path.isabs(f):
        return f
    if os.path.isfile(f):
        return os.path.abspath(f)
    return os.path.abspath(os.path.join(script_dir, f))


def print_summary(infos, n_cross, merged_n, out_dir):
    """运行完毕后集中总结关键信息 (输入/重复统计/输出文件绝对路径)。
    infos: [(名字, 原始帧, keep, removed, 去重输出路径, 内部重复帧)]。"""
    n_internal = sum(len(info[3]) for info in infos)
    n_total = sum(len(info[1]) for info in infos)
    print("=" * 52)
    print("🎉 运行完成，总结:")
    if len(infos) == 1:
        print(f"  输入文件:  {infos[0][0]} ({n_total} 帧)")
    else:
        print(f"  输入文件:  {infos[0][0]} 等 {len(infos)} 个文件 (共 {n_total} 帧)")
    print(f"  重复统计:  内部 {n_internal} 处"
          + (f", 文件间 {n_cross} 处" if len(infos) > 1 else "")
          + f", 去除 {n_internal + n_cross} 帧")
    if merged_n is not None:
        print(f"  合并输出:  {merged_n} 帧 (merged_dedup.xyz)")
    print(f"  输出目录:  {os.path.abspath(out_dir)}")
    print(f"  报告文件:  {os.path.abspath(os.path.join(out_dir, REPORT_FILE))}")
    print("=" * 52)


def main():
    files = parse_args(sys.argv[1:])
    if not files:
        print("❌ 错误: 未提供输入文件。用法: python check_dup_xyz.py <文件A.xyz> [<文件B.xyz> ...]")
        print("   (帮助请用 -h/--help)")
        sys.exit(1)

    # 输入文件: 先按当前运行目录探测, 不存在再相对脚本所在目录解析
    paths = [resolve_input_file(f, SCRIPT_DIR) for f in files]
    for f, p in zip(files, paths):
        if not os.path.isfile(p):
            print(f"❌ 错误: 文件不存在: {f}")
            sys.exit(1)
        print(f"ℹ️ 输入文件: {os.path.abspath(p)}")

    # 输出文件夹: 脚本所在目录下的 check_dup (从任意目录调用结果稳定)
    out_dir = os.path.join(SCRIPT_DIR, OUT_DIR)
    os.makedirs(out_dir, exist_ok=True)

    # 1. 各文件内部去重: (名字, 原始帧, keep, removed, 去重输出路径, 内部重复帧)
    infos = []
    for i, p in enumerate(paths):
        name = os.path.basename(p)
        frames, keep, removed, _, out_path, dup_frames = process_file(p, out_dir)
        infos.append((name, frames, keep, removed, out_path, dup_frames))
        if i < len(paths) - 1:
            print()

    # 2. 文件间严格检测 (基于各文件去重后的帧): 后续文件与前面已保留帧比较
    pool = {}   # 指纹 -> [(文件序号, 去重后帧号)] 已保留帧池
    cross = []  # (被剔除: 文件序号, 去重后帧号, 与哪个文件的序号, 帧号)
    for i, info in enumerate(infos):
        keep_i = info[2]
        if i == 0:
            for di in range(len(keep_i)):
                pool.setdefault(fingerprint(keep_i[di][1]), []).append((i, di))
            continue
        for di in range(len(keep_i)):
            at = keep_i[di][1]
            dup = next(((fi, ddi) for fi, ddi in pool.get(fingerprint(at), [])
                        if is_duplicate(infos[fi][2][ddi][1], at)), None)
            if dup is None:
                pool.setdefault(fingerprint(at), []).append((i, di))
            else:
                cross.append((i, di, dup[0], dup[1]))

    if len(infos) > 1:
        print(f"🔍 严格检测 {len(infos)} 个文件去重后的帧之间是否重复 ...")
        if not cross:
            print("  ✅ 各文件去重后无帧间重复。")
        else:
            print(f"  ⚠️ 发现 {len(cross)} 处文件间重复 (OVITO 帧号, 0 起始):")
            for i, di, fi, ddi in cross:
                print(f"  📦 {infos[i][0]} 帧 {infos[i][2][di][0]} <-> "
                      f"{infos[fi][0]} 帧 {infos[fi][2][ddi][0]} 重复 "
                      f"(剔除 {infos[i][0]} 帧 {infos[i][2][di][0]})")
            print(f"  ℹ️ 合并时已剔除后续文件中与前面文件重复的 {len(cross)} 帧 "
                  f"(保留第一个文件 {infos[0][0]} 的帧)。")

    # 3. 生成合并去重文件: 第一个文件全部 + 后续文件中不与前面重复的帧
    merged = [at for _, at in infos[0][2]]
    merged_n = None
    if len(infos) > 1:
        for i in range(1, len(infos)):
            dropped = {di for (fi, di, _, _) in cross if fi == i}
            merged += [at for di, (_, at) in enumerate(infos[i][2]) if di not in dropped]
        merged_path = os.path.join(out_dir, "merged_dedup.xyz")
        write(merged_path, merged, format="extxyz")
        merged_n = len(merged)
        print(f"  ✅ 已保存合并去重文件: {os.path.abspath(merged_path)} ({merged_n} 帧)")

    # 4. 收集所有重复结构帧: 各文件内部被去除 + 跨文件被剔除
    dup_frames = []
    for info in infos:
        dup_frames += info[5]
    dup_frames += [infos[i][2][di][1] for i, di, _, _ in cross]
    dup_path = None
    if dup_frames:
        dup_path = os.path.join(out_dir, DUP_FRAMES_FILE)
        write(dup_path, dup_frames, format="extxyz")
        print(f"  📦 已保存重复结构帧: {os.path.abspath(dup_path)} ({len(dup_frames)} 帧)")

    # 5. 检测报告 txt (仅写文件名, 不含路径)
    lines = [
        "=" * 50,
        "重复检测报告",
        "=" * 50,
        f"检测时间: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
    ]
    for i, info in enumerate(infos):
        label = f"文件: {info[0]}" if len(infos) == 1 else f"文件{chr(65 + i)}: {info[0]}"
        lines.append(f"{label} ({len(info[1])} 帧)")
    for info in infos:
        lines.append("")
        lines.append(f"[{info[0]} 内部重复]")
        append_internal_lines(lines, info[3])
    lines.append("")
    lines.append("[文件间重复 (去重后)]")
    if len(infos) == 1:
        lines.append("  单文件模式, 无文件间比较。")
    elif not cross:
        lines.append("  无重复帧。")
    else:
        for i, di, fi, ddi in cross:
            lines.append(f"  {infos[i][0]} 帧 {infos[i][2][di][0]} <-> "
                         f"{infos[fi][0]} 帧 {infos[fi][2][ddi][0]}")
        lines.append(f"  合并时剔除后续文件中与前面文件重复的 {len(cross)} 帧 "
                     f"(保留 {infos[0][0]} 的全部帧)")
    lines.append("")
    lines.append("[输出文件]")
    for info in infos:
        if info[4]:
            lines.append(f"  - {os.path.basename(info[4])} : {info[0]} 去重后结构 ({len(info[2])} 帧)")
    if merged_n is not None:
        lines.append(f"  - merged_dedup.xyz : {len(infos)} 个文件合并去重 ({merged_n} 帧)")
    if dup_path:
        lines.append(f"  - {DUP_FRAMES_FILE} : 重复结构帧 ({len(dup_frames)} 帧)")
    # 末尾汇总统计 (报告文件分节结构的收尾)
    n_internal = sum(len(info[3]) for info in infos)
    lines.append("")
    lines.append("=" * 50)
    lines.append(f"汇总: 共检测 {sum(len(info[1]) for info in infos)} 帧, "
                 f"内部重复 {n_internal} 处, 文件间重复 {len(cross)} 处, "
                 f"合并输出 {merged_n if merged_n is not None else len(infos[0][2])} 帧")
    lines.append("=" * 50)
    save_report(out_dir, lines)
    print_summary(infos, len(cross), merged_n, out_dir)


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
