#!/usr/bin/env python3
"""
=============================================================================
脚本:        active_xyzs2xyz.py
分类:        主动学习工具
功能:        合并多个目标文件夹下 active.xyz 中按不确定度筛选出的 top-N
             高价值结构为单一 extxyz 文件，供 DFT 单点批量标注；每帧原始
             属性 (uncertainty/energy/virial/stress/forces 等) 全部保留，
             并追加 source="文件夹名" 标注来源。
背景:        active 模式 MD 输出的 active.xyz 会保存所有"超阈值"帧，相邻
             帧高度冗余 (单个文件可达成千上万帧)，全部做 DFT 单点浪费机时；
             按帧级不确定度 (uncertainty 属性，单位 eV/Å) 降序取每目标
             文件夹 top-N，即可覆盖高价值结构。流式遍历 + 最小堆，大文件
             (几十万帧) 也不会全部驻留内存。
使用方法:    python active_xyzs2xyz.py [目标文件夹 ...] [-t] [-n 文件名] [-c N] [-m 值] [-o 输出路径]
参数:        目标文件夹 ...  格式一致的输入文件夹 (可选 -t/--target 标记，
                           不输入也行；支持通配符描述，如 './1_md*'；
                           相对当前运行目录解析，不存在再相对脚本目录；
                           不传时用配置区 DEFAULT_DIRS)
             -t/--target   目标文件夹标记 (可选，不输入也行，仅用于明确
                           声明；位置参数一律视为目标文件夹)
             -n/--name     输入文件名 (不指定默认 active.xyz，各目标文件夹
                           下同名文件)
             -c/--count N   每个目标文件夹取不确定度最高的前 N 帧
                           (默认 15，配置区 TOP_N)
             -m/--minimum 值  只保留 uncertainty >= 该值的帧 (可选，默认 0.3，
                           配置区 MIN_UNC)
             -o/--output   输出路径 (两种形式: 以 .xyz/.extxyz 结尾视为
                           输出文件完整路径，如 -o ./selected/f.xyz，否则
                           视为输出目录 (靶文件夹)，文件名用配置区
                           OUTPUT_FILES；--outdir 为输出目录形式别名；
                           不指定时输出到默认目录 OUTPUT_PATH；不带点
                           开头的相对路径默认相对脚本所在目录解析，
                           ./ 或 ../ 开头相对当前运行目录)
             -h/--help     显示本帮助
输入文件:    配置区 DEFAULT_DIRS 下的 INPUT_FILE (默认 active.xyz，extxyz
           格式，每帧属性含 uncertainty)
输出文件:    配置区 OUTPUT_FILES (默认 selected_active.xyz，相对
           OUTPUT_PATH，extxyz 格式)
输出路径:    默认脚本所在目录下的 selected_from_active/ (OUTPUT_PATH)，
           可用 -o 指定 (输出文件或输出目录，相对/绝对路径均可)；
           日志 selected_active.txt 位于输出目录 (内容=终端打印，覆盖写)
示例:
  python active_xyzs2xyz.py
  python active_xyzs2xyz.py -t ./1_md712 ./1_md2379 -c 20 -o ./selected/f.xyz
  python active_xyzs2xyz.py './1_md*' -m 0.2 -o ./selected_from_active/
作者:        Hongbo Sun
最后修改:    2026-08-24
=============================================================================
"""

import glob
import heapq
import os
import sys

# ============================== 参数配置区 =====================================
INPUT_FILE   = "active.xyz"                   # 输入文件名 (各目标文件夹下同名文件；-n 命令行优先)
DEFAULT_DIRS = ["1_md*"]                      # 默认目标文件夹列表 (相对 INPUT_PATH，条目支持通配符；命令行目录参数优先)
TOP_N        = 15                             # 每个目标文件夹默认取不确定度最高的前 N 帧 (-c/--count 命令行优先)
MIN_UNC      = 0.3                           # 只保留 uncertainty >= 该值的帧 (默认 0.3；-m/--minimum 命令行优先)
OUTPUT_FILES = ["selected_active.xyz"]        # 输出文件列表 (相对 OUTPUT_PATH；-o 命令行优先)
OUTPUT_PATH  = "./selected_from_active/"      # 输出文件寻找路径 (相对脚本所在目录)
RECORD_FILE  = "selected_active.txt"          # 运行日志文件 (内容=终端打印，覆盖写，输出目录)
INPUT_PATH   = "./"                           # 输入目录寻找路径 (相对脚本所在目录)
# =============================================================================

# ============================== 环境准备区 =====================================
# 终端 locale 可能非 UTF-8 (如 POSIX/C), 强制 stdout 用 UTF-8,
# 避免打印中文时抛 UnicodeEncodeError (Windows 终端显示乱码不影响功能)。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
# ASE 依赖检查: 读取/写入 extxyz 需要 ASE (ase.io.iread/write) 与 numpy
try:
    import numpy as np
    from ase.io import iread, write
except ImportError:
    print("❌ 错误: 未找到 ASE (Python 库)。请安装: pip install ase")
    sys.exit(1)
# ===========================================================================


# ============================== 函数配置区 =====================================
def print_usage():
    """打印头部注释块 (脚本功能与完整使用方法)。"""
    print(__doc__)


def parse_args(argv):
    """解析命令行参数: -h/--help、-t/--target、-n/--name、-c/--count、
    -m/--minimum、-o/--output/--outdir 为选项，其余为目标文件夹列表。
    返回 (目标文件夹列表, 输入文件名, top_n, min_unc, 输出路径)。选项位置随意。"""
    dirs = []
    name = None
    top_n = TOP_N
    min_unc = MIN_UNC
    out_path = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif arg in ("-t", "--target"):
            # -t/--target 为可选标记 (不输入也行)，无值；位置参数一律视为目标文件夹
            i += 1
        elif arg in ("-n", "--name"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -n/--name 需要一个输入文件名。")
                sys.exit(1)
            name = argv[i + 1]
            i += 2
        elif arg in ("-c", "--count"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -c/--count 需要一个正整数 N。")
                sys.exit(1)
            try:
                top_n = int(argv[i + 1])
            except ValueError:
                print("❌ 错误: -c/--count 的值必须是整数。")
                sys.exit(1)
            if top_n < 1:
                print("❌ 错误: -c/--count 必须 >= 1。")
                sys.exit(1)
            i += 2
        elif arg in ("-m", "--minimum"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -m/--minimum 需要一个数值。")
                sys.exit(1)
            try:
                min_unc = float(argv[i + 1])
            except ValueError:
                print("❌ 错误: -m/--minimum 的值必须是数值。")
                sys.exit(1)
            i += 2
        elif arg in ("-o", "--output", "--outdir"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -o/--output 需要一个输出路径。")
                sys.exit(1)
            out_path = argv[i + 1]
            i += 2
        else:
            dirs.append(arg)
            i += 1
    return dirs, name, top_n, min_unc, out_path


def resolve_cmd_path(p, script_dir):
    """命令行路径解析: 绝对路径照旧；以 ./ ../ 或 . 开头的相对路径相对
    当前运行目录解析；不带点开头的相对路径默认相对脚本所在目录解析。"""
    if os.path.isabs(p):
        return p
    if p in (".", "..") or p.startswith(("./", "../")):
        return os.path.abspath(p)
    return os.path.normpath(os.path.join(script_dir, p))


def dw(s):
    """字符串显示宽度: 中文等宽字符按 2 列计。"""
    return sum(2 if ord(ch) > 127 else 1 for ch in str(s))


def pad(s, width, align="l"):
    """按显示宽度填充空格: l 左对齐 / r 右对齐。"""
    gap = width - dw(s)
    return s + " " * gap if align == "l" else " " * gap + str(s)


def expand_dirs(pattern, base_dir):
    """将目录模式展开为目录列表: 含通配符 (* ? [) 的按 glob 展开 (相对
    base_dir，结果排序，仅保留目录)，无通配符的字面路径保留。"""
    if any(ch in pattern for ch in "*?["):
        matches = sorted(glob.glob(os.path.join(base_dir, pattern)))
        return [m for m in matches if os.path.isdir(m)]
    return [os.path.normpath(os.path.join(base_dir, pattern))]


def resolve_dirs(script_dir, args, input_base):
    """解析待合并的目标文件夹列表: 无参数用配置区 DEFAULT_DIRS (相对
    input_base，条目支持通配符)；有参数按顺序解析，含通配符的 glob 展开
    (先相对当前运行目录，不带点开头的模式未匹配时再相对脚本目录兜底，
    仅保留目录)，参数为已存在目录则直接使用，否则相对脚本目录解析。"""
    if not args:
        dirs = []
        for d in DEFAULT_DIRS:
            dirs.extend(expand_dirs(d, input_base))
        return dirs
    dirs = []
    for a in args:
        if any(ch in a for ch in "*?["):
            # 命令行通配符: 先相对当前运行目录 glob 展开 (bash 自动展开时
            # 参数已是具体目录，不经过此分支)；不带点开头的模式未匹配时
            # 再相对脚本目录兜底，与"不带点默认脚本目录"规则一致
            matches = sorted(glob.glob(a))
            if not matches and not a.startswith(("./", "../")):
                matches = sorted(glob.glob(os.path.join(script_dir, a)))
            if not matches:
                print(f"⚠️ 警告: 模式 '{a}' 未匹配任何文件夹，已跳过。")
            dirs.extend(m for m in matches if os.path.isdir(m))
            continue
        d = a if os.path.isdir(a) else os.path.join(script_dir, a)
        if not os.path.isdir(d):
            print(f"⚠️ 警告: 文件夹不存在，已跳过: {a}")
            continue
        dirs.append(d)
    return dirs


def select_top_from(folder, input_name, top_n, min_unc):
    """读取 <folder>/<input_name>，返回不确定度最高的 top_n 帧 (降序) 与统计。

    流式遍历 + 最小堆: 堆中只保留 top-N 帧对象，大文件 (几十万帧) 也不会
    全部驻留内存。堆元素 (uncertainty, 全局帧序号, atoms) 中帧序号全局
    唯一，保证元组比较不会落到 atoms 对象上。
    """
    path = os.path.join(folder, input_name)
    if not os.path.isfile(path):
        return None, None, None

    heap = []
    n_frames = 0      # 读取的总帧数
    n_skipped = 0     # 被过滤的帧数 (无 uncertainty 属性 或 低于 min_unc)
    for atoms in iread(path):
        n_frames += 1
        u = atoms.info.get("uncertainty", None)
        if u is None or (min_unc is not None and u < min_unc):
            n_skipped += 1
            continue
        item = (u, n_frames, atoms)
        if len(heap) < top_n:
            heapq.heappush(heap, item)
        elif u > heap[0][0]:
            heapq.heapreplace(heap, item)

    selected = sorted(heap, key=lambda x: -x[0])  # 按 uncertainty 降序
    return selected, n_frames, n_skipped


def sanitize_info(atoms):
    """把 info 中字符串形式的 virial/stress 转成 9 元素 float 数组。

    GPUMD active.xyz 中 virial/stress 是引号包裹的字符串, ASE 读入后
    info['virial']/['stress'] 为 str; 而 ASE 写 extxyz 时会访问
    info['stress'].shape (extxyz.py write_xyz), 字符串直接崩溃。
    转成 9 元素数组后, ASE 会按 SPECIAL_3_3_KEYS 处理, 序列化回
    与 GPUMD 相同的 "virial=\"...\"" 格式。
    """
    for key in ("virial", "stress"):
        val = atoms.info.get(key)
        if isinstance(val, str):
            try:
                atoms.info[key] = np.array([float(x) for x in val.split()])
            except ValueError:
                pass  # 解析失败则保留原字符串, 不影响主流程
    return atoms


def write_outputs(atoms_list, out_file):
    """把筛选结果写为 extxyz (覆盖写)；自动创建输出目录。"""
    out_dir = os.path.dirname(os.path.abspath(out_file))
    os.makedirs(out_dir, exist_ok=True)
    write(out_file, atoms_list, format="extxyz")


def write_record(log_lines, record_path):
    """覆盖写运行日志 (内容=终端打印全部行)，自动创建输出目录。"""
    os.makedirs(os.path.dirname(os.path.abspath(record_path)), exist_ok=True)
    with open(record_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")


# ============================== 脚本工作区 =====================================
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    args, name, top_n, min_unc, out_path = parse_args(sys.argv[1:])
    input_name = name or INPUT_FILE
    print(f"ℹ️ 脚本所在目录: {script_dir}")
    print(f"ℹ️ 输入文件名: {input_name} | 取帧数: {top_n}"
          + (f" | 最小不确定度: {min_unc}" if min_unc is not None else ""))

    # 输出文件: -o 命令行优先，否则配置区 OUTPUT_FILES (相对 OUTPUT_PATH)
    if out_path:
        out_base = resolve_cmd_path(out_path, script_dir)
        ext = os.path.splitext(out_base)[1].lower().lstrip(".")
        if ext in ("xyz", "extxyz"):
            # -o 为输出文件完整路径: 扩展名决定输出格式
            out_file = out_base
            output_dir = os.path.dirname(out_base)
        else:
            # -o 为输出目录: 文件名用配置区 OUTPUT_FILES
            output_dir = out_base
            out_file = os.path.join(output_dir, OUTPUT_FILES[0])
    else:
        output_dir = os.path.normpath(os.path.join(script_dir, OUTPUT_PATH))
        out_file = os.path.join(output_dir, OUTPUT_FILES[0])

    # 解析目标文件夹 (无参数用配置区 DEFAULT_DIRS，有参数按指定顺序)
    input_base = os.path.normpath(os.path.join(script_dir, INPUT_PATH))
    dirs = resolve_dirs(script_dir, args, input_base)
    if not dirs:
        print("❌ 错误: 未找到任何目标文件夹。")
        sys.exit(1)

    # 所有输出同时进终端和日志列表, 最后整体写入日志 (覆盖写, 不追加)
    log_lines = []

    def emit(msg=""):
        print(msg)
        log_lines.append(msg)

    emit(f"📋 检测到 {len(dirs)} 个目标文件夹: "
         + ", ".join(os.path.basename(d) for d in dirs))

    all_selected = []
    all_u = []          # 全部选中帧的 uncertainty, 用于末尾总统计
    n_total = len(dirs)
    table = []          # (文件夹名, 总帧数, 过滤帧数, 筛选数, uncertainty 范围)
    for i, folder in enumerate(dirs, start=1):
        selected, n_frames, n_skipped = select_top_from(
            folder, input_name, top_n, min_unc)
        if selected is None:
            emit(f"  ⚠️ [跳过] {os.path.basename(folder)}: 无 {input_name}, "
                 "该文件夹未跑 active 模式?")
            continue
        u_vals = [u for u, _, _ in selected]
        u_min = min(u_vals) if u_vals else 0.0
        u_max = max(u_vals) if u_vals else 0.0
        u_mean = sum(u_vals) / len(u_vals) if u_vals else 0.0
        table.append((os.path.basename(folder), n_frames, n_skipped,
                      len(selected), f"{u_min:.4f} ~ {u_max:.4f}"))
        emit(f"  ✅ [完成] {os.path.basename(folder)}: 共 {n_frames} 帧"
             + (f" (过滤 {n_skipped} 帧)" if n_skipped else "")
             + f", 取 top {len(selected)}, uncertainty {u_min:.4f} ~ {u_max:.4f}"
             + f" eV/Å (平均 {u_mean:.4f}), {i}/{n_total}")
        for u, _, atoms in selected:
            atoms.info["source"] = os.path.basename(folder)  # 标注来源, 便于追溯
            sanitize_info(atoms)          # 修复 virial/stress 字符串写回崩溃
            all_selected.append(atoms)
            all_u.append(u)

    if not all_selected:
        emit("❌ 错误: 所有目标文件夹都没有筛选出任何帧, 请检查 active.xyz "
             "是否为空或 -m/--minimum 是否过高。")
        sys.exit(1)

    # 终端表格: 文件夹名、总帧数、过滤帧数、筛选数、uncertainty 范围
    emit("")
    emit("# " + pad("文件夹名", 16) + pad("总帧数", 8, "r") + pad("过滤帧", 8, "r")
         + pad("筛选帧", 8, "r") + " " + pad("uncertainty 范围 (eV/Å)", 28))
    for row in table:
        emit("# " + pad(row[0], 16) + pad(str(row[1]), 8, "r")
             + pad(str(row[2]), 8, "r") + pad(str(row[3]), 8, "r")
             + " " + pad(row[4], 28))

    # 全部选中帧的总统计
    u_min_all = min(all_u)
    u_max_all = max(all_u)
    u_mean_all = sum(all_u) / len(all_u)
    emit(f"完成: 共 {len(all_selected)} 帧, uncertainty 范围 "
         f"{u_min_all:.4f} ~ {u_max_all:.4f} eV/Å, "
         f"平均 uncertainty = {u_mean_all:.4f}")

    # 写结构文件 (覆盖写, 不追加)
    write_outputs(all_selected, out_file)
    emit(f"结构已写入: {os.path.abspath(out_file)}")

    # 写日志 (内容 = 终端打印的全部, 覆盖写, 不追加)
    record_path = os.path.join(output_dir, RECORD_FILE)
    write_record(log_lines, record_path)
    emit(f"日志已写入: {os.path.abspath(record_path)}")

    # 运行完毕总结关键信息
    print("=" * 52)
    print("🎉 运行完成，总结:")
    print(f"  输入目标文件夹:  {len(dirs)} 个")
    print(f"  输出文件:  {os.path.abspath(out_file)}  ({len(all_selected)} 帧)")
    print(f"  日志文件:  {os.path.abspath(record_path)} (覆盖)")
    print("=" * 52)


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
