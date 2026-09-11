"""
=============================================================================
脚本:        dedup_merge_xyz.py
分类:        结构处理工具
功能:        快捷合并多个 xyz/extxyz 文件并去重: 按量化指纹粗分组、组内
             严格验证判重, 保留每个重复结构的首帧, 一次完成合并与去重。
使用方法:    python dedup_merge_xyz.py <文件 ...> [-o 输出]
参数:        <文件 ...>     待合并去重的 xyz/extxyz 文件 (可选 -t/--target
                            标记, -t/--target 仅为明确声明、可省略, 位置
                            参数一律视为输入文件; 支持通配符; 相对路径先
                            按当前运行目录探测, 不存在再相对脚本所在目录
                            解析)
             -o/--output   输出路径 (以 .xyz/.extxyz 结尾视为输出文件完整
                            路径; 否则视为输出目录, 文件名用配置区
                            OUTPUT_FILE; 默认输出到脚本所在目录下
                            OUTPUT_FILE; ./ ../ 开头的相对路径相对当前运
                            行目录解析, 不带点开头的默认相对脚本所在目录
                            解析; --outdir 等价写法)
             -h/--help     显示本帮助
输入文件:    <文件 ...> (命令行指定, 按给定顺序合并)
输出文件:    merged_dedup.xyz   合并去重结果 (覆盖写, 统一 extxyz 格式,
                               保留晶胞/受力/能量等信息)
             merged_dedup.txt   记录文件 (追加写, 表头以 # 开头)
输出路径:    默认脚本所在目录 (可用 -o 指定输出文件或输出目录); 记录文件
             与输出文件同目录
示例:
  python dedup_merge_xyz.py ./100.xyz ./200.xyz
  python dedup_merge_xyz.py './*.xyz' -o ./merged_dedup.xyz
  python dedup_merge_xyz.py ./a.xyz ./b.xyz -o ./out/
依赖:        ase, numpy
作者:        隼蝶.
最后修改:    2026-09-11
=============================================================================
"""

import glob
import os
import sys
import time

# ============================== 参数配置区 =====================================
OUTPUT_FILE  = "merged_dedup.xyz"   # 默认输出文件名 (-o 未指定时, 相对 OUTPUT_PATH)
RECORD_FILE  = "merged_dedup.txt"   # 记录文件 (追加写入, 与输出文件同目录)
OUTPUT_PATH  = "./"                 # 默认输出路径 (相对脚本所在目录)
QUANT_BITS   = 6                    # 指纹量化位数 (仅用于快速粗分组)
MATCH_TOL    = 1e-4                 # 组内严格验证容差 (分数坐标)
CELL_TOL     = 1e-5                 # 晶胞比较容差 (Å)
# =============================================================================

# ============================== 环境准备区 =====================================
# Windows 控制台默认 GBK 编码无法输出部分字符 (emoji 等), 统一切换 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 依赖检查: 缺少 ase/numpy 时给出明确的安装提示后退出
try:
    import numpy as np
    from ase.io import read, write
except ImportError:
    print("❌ 错误: 未找到 ASE (Python 库)。请安装: pip install ase")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # 脚本所在目录
# =============================================================================


# ============================== 函数配置区 =====================================
def print_usage():
    """打印头部注释块 (脚本功能与完整使用方法)。"""
    print(__doc__)


def dw(s):
    """字符串显示宽度: 中文等宽字符按 2 列计。"""
    return sum(2 if ord(ch) > 127 else 1 for ch in str(s))


def pad(s, width, align="l"):
    """按显示宽度填充空格: l 左对齐 / r 右对齐。"""
    gap = width - dw(s)
    return s + " " * gap if align == "l" else " " * gap + str(s)


def fingerprint(atoms):
    """快速指纹: 原子数、元素组成、晶胞与分数坐标 (排序 + wrap 后量化)。"""
    return (len(atoms),
            tuple(sorted(atoms.get_chemical_symbols())),
            tuple(np.round(atoms.cell[:], QUANT_BITS).flatten()),
            tuple(sorted(map(tuple, np.round(atoms.get_scaled_positions(wrap=True), QUANT_BITS)))))


def is_duplicate(atoms1, atoms2, tol=MATCH_TOL):
    """严格判定两帧是否等价: 元素计数、晶胞、PBC 下分数坐标一一对应。"""
    if len(atoms1) != len(atoms2):
        return False
    sym1, sym2 = atoms1.get_chemical_symbols(), atoms2.get_chemical_symbols()
    if sorted(sym1) != sorted(sym2):
        return False
    if not np.allclose(atoms1.cell[:], atoms2.cell[:], rtol=0.0, atol=CELL_TOL):
        return False
    f1, f2 = atoms1.get_scaled_positions(wrap=True), atoms2.get_scaled_positions(wrap=True)
    used = [False] * len(atoms2)
    # 对 atoms1 每个原子, 贪心找未使用的同元素最近邻 (PBC 最小镜像距离)
    for i, s1 in enumerate(sym1):
        best, best_d = -1, np.inf
        for j, s2 in enumerate(sym2):
            if used[j] or s2 != s1:
                continue
            d = np.max(np.abs((f1[i] - f2[j]) - np.round(f1[i] - f2[j])))
            if d < best_d:
                best, best_d = j, d
        if best < 0 or best_d > tol:
            return False
        used[best] = True
    return True


def parse_args(argv):
    """解析命令行参数: -h/--help、-t/--target、-o/--output/--outdir 为选项,
    其余为输入文件列表; 选项位置随意。返回 (输入文件列表, 输出路径)。"""
    files, out_path, i = [], None, 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif arg in ("-t", "--target"):
            i += 1  # -t/--target 为可选标记 (不输入也行), 位置参数一律视为输入文件
        elif arg in ("-o", "--output", "--outdir"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -o/--output 需要一个输出路径。")
                sys.exit(1)
            out_path = argv[i + 1]
            i += 2
        else:
            files.append(arg)
            i += 1
    return files, out_path


def resolve_cmd_path(p, script_dir):
    """命令行路径解析: 绝对路径照旧; ./ ../ 或 . 开头的相对路径相对当前
    运行目录解析; 不带点开头的相对路径默认相对脚本所在目录解析。"""
    if os.path.isabs(p):
        return p
    if p in (".", "..") or p.startswith(("./", "../")):
        return os.path.abspath(p)
    return os.path.normpath(os.path.join(script_dir, p))


def resolve_input_file(f, script_dir):
    """输入文件路径解析: 绝对路径照旧; 相对路径先按当前运行目录探测,
    不存在再相对脚本所在目录解析。"""
    if os.path.isabs(f):
        return f
    return os.path.abspath(f) if os.path.isfile(f) else os.path.abspath(os.path.join(script_dir, f))


def write_record(record_path, table, out_file, n_total, n_kept):
    """追加写入记录文件: 表头以 # 开头, 含时间戳、各输入文件帧数/保留/去重
    与输出汇总 (输出展示绝对路径)。"""
    lines = ["# " + "=" * 40,
             f"# 合并去重时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"# [输入文件] ({len(table)} 个)",
             "# " + pad("文件名", 44) + " " + pad("帧数", 6, "r") + " "
             + pad("保留", 6, "r") + " " + pad("去重", 6, "r")]
    for name, n, kept, removed in table:
        lines.append("# " + pad(name, 44) + " " + pad(str(n), 6, "r") + " "
                     + pad(str(kept), 6, "r") + " " + pad(str(removed), 6, "r"))
    lines.append("# [输出文件]")
    lines.append(f"#   {pad(os.path.abspath(out_file), 44)} 输出 {n_kept} 帧 "
                 f"(读入 {n_total} 帧, 去重 {n_total - n_kept} 帧)")
    lines.append("# " + "=" * 40)
    with open(record_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ============================== 脚本工作区 =====================================
def main():
    args, out_path = parse_args(sys.argv[1:])
    if not args:
        print("❌ 错误: 未提供输入文件。用法: python dedup_merge_xyz.py <文件 ...> [-o 输出]")
        print("   (帮助请用 -h/--help)")
        sys.exit(1)

    # 输入文件解析: 支持通配符 (不带点的模式未匹配时再相对脚本目录展开一次);
    # 相对路径先按当前运行目录探测, 不存在再相对脚本所在目录解析
    files = []
    for a in args:
        if any(ch in a for ch in "*?["):
            matches = sorted(glob.glob(a))
            if not matches and not a.startswith(("./", "../")):
                matches = sorted(glob.glob(os.path.join(SCRIPT_DIR, a)))
            if not matches:
                print(f"⚠️ 警告: 模式 '{a}' 未匹配任何文件，已跳过。")
            files.extend(m for m in matches if os.path.isfile(m))
            continue
        f = resolve_input_file(a, SCRIPT_DIR)
        if not os.path.isfile(f):
            print(f"⚠️ 警告: 文件不存在，已跳过: {a}")
            continue
        files.append(f)
    if not files:
        print("❌ 错误: 未找到任何输入文件。")
        sys.exit(1)

    # 输出文件: -o 以 .xyz/.extxyz 结尾视为输出文件完整路径, 否则视为输出
    # 目录; 未指定时输出到默认目录 OUTPUT_PATH 下 (相对脚本所在目录)
    if out_path:
        out_base = resolve_cmd_path(out_path, SCRIPT_DIR)
        if os.path.splitext(out_base)[1].lower() in (".xyz", ".extxyz"):
            out_file = out_base
        else:
            out_file = os.path.join(out_base, OUTPUT_FILE)
    else:
        out_file = os.path.normpath(os.path.join(SCRIPT_DIR, OUTPUT_PATH, OUTPUT_FILE))

    # 合并去重: 指纹分组 + 组内严格验证, 保留每个重复结构的首帧
    print("📦 开始合并去重:")
    groups, keep = {}, []  # 指纹 -> 该组已保留的帧; keep = 全部保留帧 (按输入顺序)
    table = []             # (文件名, 帧数, 保留, 去重)
    n_total = 0
    for f in files:
        frames = read(f, index=":")
        n0 = len(keep)
        for at in frames:
            fp = fingerprint(at)
            if not any(is_duplicate(g, at) for g in groups.get(fp, ())):
                groups.setdefault(fp, []).append(at)
                keep.append(at)
        n_kept = len(keep) - n0
        table.append((os.path.basename(f), len(frames), n_kept, len(frames) - n_kept))
        n_total += len(frames)
        print(f"  📦 {os.path.basename(f)}: 读入 {len(frames)} 帧, "
              f"保留 {n_kept} 帧, 去重 {len(frames) - n_kept} 帧")

    # 写出结果 (覆盖) 与记录文件 (追加, 与输出文件同目录)
    os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
    write(out_file, keep, format="extxyz")
    record_path = os.path.join(os.path.dirname(os.path.abspath(out_file)), RECORD_FILE)
    write_record(record_path, table, out_file, n_total, len(keep))

    # 运行完毕总结关键信息 (数量统计、输出文件与路径)
    print("=" * 52)
    print("🎉 运行完成，总结:")
    print(f"  输入文件:  {len(table)} 个 (共 {n_total} 帧)")
    print(f"  去重统计:  去除 {n_total - len(keep)} 帧")
    print(f"  输出文件:  {os.path.abspath(out_file)} ({len(keep)} 帧)")
    print(f"  记录文件:  {os.path.abspath(record_path)} (追加)")
    print("=" * 52)


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
