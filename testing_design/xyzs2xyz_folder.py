#!/usr/bin/env python3
"""
=============================================================================
脚本:        xyzs2xyz_folder.py
分类:        结构处理工具
功能:        合并多个文件夹中的 xyz/extxyz 文件：不传参数时自动检测脚本
             所在目录下的所有子文件夹 (按文件夹名排序合并)，传参数时按
             命令行参数指定的文件夹顺序合并 (支持通配符)；可用 -n 指定
             只合并某名称的 xyz/extxyz 文件，按格式分组合并，支持 -o
             指定输出路径，并统计帧数、记录合并日志。
使用方法:    python xyzs2xyz_folder.py [文件夹 ...] [-n 文件名] [-o 输出路径]
参数:        目标文件夹 ...  待合并的文件夹 (可选 -t/--target 标记，不输入
                           也行；命令行相对当前运行目录解析，不存在再相对
                           脚本目录；支持通配符；不传时自动扫描脚本目录
                           下的所有子文件夹，按文件夹名排序，排除输出目录)
             -t/--target   目标文件夹标记 (可选，不输入也行，仅用于明确
                           声明；位置参数一律视为目标文件夹)
             -n/--name     指定文件名 (可多次使用，如 -n a.xyz -n b.xyz；
                           支持通配符，如 -n 'a.*'；指定后只合并各目标文件夹中
                           名称匹配的 xyz/extxyz 文件)
             -o/--output   输出路径 (两种形式: 以 .xyz/.extxyz 结尾视为
                           输出文件完整路径，如 -o ./C/c.xyz，扩展名决定
                           合并格式；否则视为输出目录 (靶文件夹)，如
                           -o .，文件名用配置区 OUTPUT_FILES；不指定时
                           输出到默认目录 OUTPUT_PATH，文件名同样用默认
                           名；不带点开头的相对路径默认相对脚本所在目录
                           解析，./ 或 ../ 开头相对当前运行目录)
             -h/--help     显示本帮助
输入文件:    配置区 INPUT_PATH 下的子文件夹 (默认扫描脚本目录的所有子文件夹)
输出文件:    配置区 OUTPUT_FILES (默认 merged.xyz / merged.extxyz，相对
           OUTPUT_PATH)
输出路径:    默认脚本所在目录下的 merge/ (OUTPUT_PATH)，可用 -o 指定
           (输出文件或输出目录，相对/绝对路径均可)；合并记录 merged.txt
           位于输出目录
示例:
  python xyzs2xyz_folder.py
  python xyzs2xyz_folder.py ./文件夹1 ./文件夹2 ./文件夹3
  python xyzs2xyz_folder.py -n a.xyz ./A ./B ./C -o ./D/E/f.xyz
  python xyzs2xyz_folder.py -t ./A ./B ./C -n a.xyz -o ./D/E/f.xyz
  python xyzs2xyz_folder.py './1_md*' -o ./D/E/f.xyz
  python xyzs2xyz_folder.py ./A ./B -o ./C/c.xyz
作者:        隼蝶.
最后修改:    2026-08-24
=============================================================================
"""

import fnmatch
import glob
import os
import sys
import time

# ============================== 参数配置区 =====================================
INPUT_PATH   = "./"                           # 输入文件夹寻找路径 (相对脚本所在目录；不传参数时扫描其所有子文件夹)
OUTPUT_FILES = ["merged.xyz", "merged.extxyz"]  # 输出文件列表 (按输入实际格式生成对应扩展名的输出；-o 命令行优先)
OUTPUT_PATH  = "./merge/"                     # 输出文件寻找路径 (相对脚本所在目录)
RECORD_FILE  = "merged.txt"                   # 合并记录文件 (追加写入，不覆盖历史，输出目录)
MERGE_BUF    = 1024 * 1024                    # 合并读写缓冲区大小 (1 MB)
# =============================================================================

# ============================== 环境准备区 =====================================
# 终端 locale 可能非 UTF-8 (如 POSIX/C), 强制 stdout 用 UTF-8,
# 避免打印中文时抛 UnicodeEncodeError (Windows 终端显示乱码不影响功能)。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
# ===========================================================================


# ============================== 函数配置区 =====================================
def print_usage():
    """打印头部注释块 (脚本功能与完整使用方法)。"""
    print(__doc__)


def parse_args(argv):
    """解析命令行参数: -h/--help、-o/--output、-n/--name、-t/--target 为
    选项，其余为目标文件夹列表。返回 (目标文件夹列表, 输出路径, 文件名
    模式列表)。选项位置随意。"""
    folders = []
    out_path = None
    name_patterns = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif arg in ("-t", "--target"):
            # -t/--target 为可选标记 (不输入也行)，无值；位置参数一律视为目标文件夹
            i += 1
        elif arg in ("-o", "--output"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -o/--output 需要一个输出文件路径。")
                sys.exit(1)
            out_path = argv[i + 1]
            i += 2
        elif arg in ("-n", "--name"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -n/--name 需要一个 xyz/extxyz 文件名。")
                sys.exit(1)
            name_patterns.append(argv[i + 1])
            i += 2
        else:
            folders.append(arg)
            i += 1
    return folders, out_path, name_patterns


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


def expand_patterns(patterns, base_dir, keep_unmatched=True):
    """将文件列表展开为完整路径: 含通配符 (* ? [) 的按 glob 展开 (相对
    base_dir，结果排序并规范化)，无通配符的字面路径原样保留；glob 无匹配
    时警告: keep_unmatched=True 按字面使用 (输出场景，可能是新文件)，
    False 则忽略 (输入场景)。"""
    files = []
    for p in patterns:
        if any(ch in p for ch in "*?["):
            matches = sorted(glob.glob(os.path.join(base_dir, p)))
            if matches:
                files.extend(os.path.normpath(m) for m in matches)
            elif keep_unmatched:
                print(f"⚠️ 警告: 模式 '{p}' 未匹配任何文件，按字面使用: "
                      f"{os.path.join(base_dir, p)}")
                files.append(os.path.join(base_dir, p))
            else:
                print(f"⚠️ 警告: 模式 '{p}' 未匹配任何文件，已忽略。")
        else:
            files.append(os.path.normpath(os.path.join(base_dir, p)))
    return files


def match_names(name, patterns):
    """判断文件名是否命中任一名称模式: 含通配符的按 fnmatch 匹配，
    否则精确匹配文件名。"""
    for p in patterns:
        if any(ch in p for ch in "*?["):
            if fnmatch.fnmatch(name, p):
                return True
        elif name == p:
            return True
    return False


def collect_files(folder, exclude_names, name_patterns=None):
    """返回文件夹内直接存放的 (xyz 文件列表, extxyz 文件列表)，均按文件名
    排序，排除指定的输出文件 (避免重复合并)；指定 name_patterns 时仅保留
    名称匹配的 xyz/extxyz 文件。"""
    xyz_files, extxyz_files = [], []
    for name in sorted(os.listdir(folder)):
        full = os.path.join(folder, name)
        if not os.path.isfile(full) or name in exclude_names:
            continue
        if name_patterns and not match_names(name, name_patterns):
            continue
        if name.endswith(".extxyz"):
            extxyz_files.append(full)
        elif name.endswith(".xyz"):
            xyz_files.append(full)
    return xyz_files, extxyz_files


def count_frames(path):
    """统计 xyz/extxyz 文件中的帧数 (每帧首行第一列为正整数原子数)。"""
    n = 0
    with open(path, "r", encoding="utf-8") as fin:
        for line in fin:
            parts = line.split()
            if parts:
                try:
                    if int(parts[0]) > 0:
                        n += 1
                except ValueError:
                    pass
    return n


def resolve_folders(script_dir, args, output_dir, input_base):
    """解析待合并的文件夹列表，返回按合并顺序排列的目录路径。
    无参数: 自动扫描 input_base 下所有子文件夹 (按文件夹名排序)，排除输出目录；
    有参数: 按参数顺序解析，支持通配符，参数为已存在目录则直接使用，否则
    相对脚本目录解析。"""
    if not args:
        return [os.path.join(input_base, d)
                for d in sorted(os.listdir(input_base))
                if os.path.isdir(os.path.join(input_base, d))
                and os.path.normpath(os.path.join(input_base, d)) != output_dir]
    folders = []
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
            folders.extend(m for m in matches if os.path.isdir(m))
            continue
        folder = a if os.path.isdir(a) else os.path.join(script_dir, a)
        if not os.path.isdir(folder):
            print(f"⚠️ 警告: 文件夹不存在，已跳过: {a}")
            continue
        folders.append(folder)
    return folders


def merge_files(file_list, out_file):
    """将多个文件按顺序拼接为一个文件 (覆盖写，行为等价 cat)，统一 LF
    换行；自动检查每个文件末尾，缺换行符则补一个，防止帧粘连。"""
    out_dir = os.path.dirname(os.path.abspath(out_file))
    os.makedirs(out_dir, exist_ok=True)
    with open(out_file, "w", encoding="utf-8", newline="\n") as fout:
        for f in file_list:
            print(f"  📦 合并 {os.path.basename(f)} ...", end=" ")
            last_chunk = ""
            with open(f, "r", encoding="utf-8", newline="\n") as fin:
                while True:
                    chunk = fin.read(MERGE_BUF)
                    if not chunk:
                        break
                    fout.write(chunk)
                    last_chunk = chunk
            if last_chunk and not last_chunk.endswith("\n"):
                fout.write("\n")
            print("✅")
    print(f"  ✅ 已输出: {os.path.abspath(out_file)}")


def write_record(records, record_path):
    """追加写入合并记录 (merged.txt)，每次运行一个分节块，全部行以 # 开头，
    含表头、时间戳、输入清单与输出清单。"""
    lines = ["# " + "=" * 40,
             f"# 合并时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"]
    inputs = records["inputs"]
    lines.append(f"# [输入文件] ({len(inputs)} 个)")
    lines.append("# " + pad("文件夹名", 44) + " " + pad("格式", 8)
                 + " " + pad("帧数", 6, "r"))
    for _, name, fmt, n in inputs:
        lines.append("# " + pad(name, 44) + " " + pad(fmt, 8)
                     + " " + pad(str(n), 6, "r"))
    lines.append("# [输出文件]")
    for out, total in records["outputs"]:
        lines.append(f"#   {pad(out, 44)} 总 {total} 帧")
    lines.append("# " + "=" * 40)
    with open(record_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def print_summary(n_folders, outputs, record_path):
    """运行完毕后集中总结关键信息 (输入文件夹数量、输出文件与绝对路径、记录文件)。"""
    print("=" * 52)
    print("🎉 运行完成，总结:")
    print(f"  输入文件夹:  {n_folders} 个")
    print(f"  输出文件:  {len(outputs)} 个")
    for out, total in outputs:
        print(f"    {os.path.abspath(out)}  (总 {total} 帧)")
    print(f"  记录文件:  {os.path.abspath(record_path)} (追加)")
    print("=" * 52)


# ============================== 脚本工作区 =====================================
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    args, out_path, name_patterns = parse_args(sys.argv[1:])
    print(f"ℹ️ 脚本所在目录: {script_dir}")

    # 输出文件: -o 命令行优先，否则配置区 OUTPUT_FILES (相对 OUTPUT_PATH)
    outputs_by_fmt = {}  # 格式 -> 输出文件路径
    if out_path:
        out_base = resolve_cmd_path(out_path, script_dir)
        ext = os.path.splitext(out_base)[1].lower().lstrip(".")
        if ext in ("xyz", "extxyz"):
            # -o 为输出文件完整路径: 扩展名决定合并格式
            outputs_by_fmt[ext] = out_base
            output_dir = os.path.dirname(out_base)
        else:
            # -o 为输出目录: 文件名用配置区 OUTPUT_FILES 对应格式
            output_dir = out_base
            for f in expand_patterns(OUTPUT_FILES, out_base):
                fmt = os.path.splitext(f)[1].lower().lstrip(".")
                if fmt in ("xyz", "extxyz"):
                    outputs_by_fmt[fmt] = f
            if not outputs_by_fmt:
                print("❌ 错误: 配置区 OUTPUT_FILES 中没有 .xyz/.extxyz 文件名。")
                sys.exit(1)
    else:
        output_dir = os.path.normpath(os.path.join(script_dir, OUTPUT_PATH))
        for f in expand_patterns(OUTPUT_FILES, output_dir):
            fmt = os.path.splitext(f)[1].lower().lstrip(".")
            if fmt in ("xyz", "extxyz"):
                outputs_by_fmt[fmt] = f
            else:
                print(f"⚠️ 警告: 输出文件扩展名非 .xyz/.extxyz，已忽略: {f}")
    if not outputs_by_fmt:
        print("❌ 错误: 未配置输出文件 (配置区 OUTPUT_FILES 为空且未指定 -o)。")
        sys.exit(1)

    # 解析待合并的文件夹 (无参数自动扫描子文件夹并排除输出目录，有参数按指定顺序)
    input_base = os.path.normpath(os.path.join(script_dir, INPUT_PATH))
    folders = resolve_folders(script_dir, args, output_dir, input_base)
    if not folders:
        print("❌ 错误: 未找到任何文件夹。")
        sys.exit(1)

    # 按指定顺序收集各文件夹中的 xyz/extxyz 文件，并统计各文件帧数
    groups = {"xyz": [], "extxyz": []}  # 格式 -> 文件路径列表
    table = []  # (路径, 文件夹名, 格式, 帧数)，用于终端展示与记录
    exclude_names = {os.path.basename(f) for f in outputs_by_fmt.values()}
    for folder in folders:
        xyz_files, extxyz_files = collect_files(folder, exclude_names, name_patterns)
        d = os.path.basename(os.path.normpath(folder))
        for f in xyz_files:
            n = count_frames(f)
            if n == 0:
                # 帧数为 0 说明不是有效的 xyz 文件 (如误传 txt/记录文件)，
                # 直接拼入会污染输出，跳过并警告
                print(f"⚠️ 警告: 文件不含有效 xyz 帧 (可能不是 xyz 文件)，已跳过: {f}")
                continue
            groups["xyz"].append(f)
            table.append((f, d, "xyz", n))
        for f in extxyz_files:
            n = count_frames(f)
            if n == 0:
                print(f"⚠️ 警告: 文件不含有效 xyz 帧 (可能不是 xyz 文件)，已跳过: {f}")
                continue
            groups["extxyz"].append(f)
            table.append((f, d, "extxyz", n))

    if not table:
        print("❌ 错误: 未找到含 xyz/extxyz 文件的文件夹。")
        sys.exit(1)

    # 终端展示: 文件夹名、格式、帧数 (中文宽度对齐，格式/帧数右对齐)
    print("\n📋 检测到含 xyz/extxyz 文件的文件夹:")
    print(f"  {pad('文件夹名', 44)}{pad('格式', 8)}{pad('帧数', 6, 'r')}")
    for _, d, fmt, n in table:
        print(f"  {pad(d, 44)}{pad(fmt, 8)}{pad(str(n), 6, 'r')}")

    # 按格式分别合并 (仅生成输入中存在的格式对应的输出文件)
    outputs = []
    for fmt in ("xyz", "extxyz"):
        f_list = groups[fmt]
        if not f_list:
            continue
        out = outputs_by_fmt[fmt]
        total = sum(n for _, _, fm, n in table if fm == fmt)
        print(f"\n📦 合并 {len(f_list)} 个 .{fmt} 文件 -> {os.path.abspath(out)}")
        merge_files(f_list, out)
        outputs.append((out, total))

    # 追加写入合并记录 (多次运行不覆盖历史，位于输出目录)
    record_path = os.path.join(output_dir, RECORD_FILE)
    if outputs:
        write_record({"inputs": table, "outputs": outputs}, record_path)
        print(f"ℹ️ 合并记录已追加: {os.path.abspath(record_path)}")

    # 总结: 统计实际包含匹配文件的文件夹数 (扫描到的空文件夹不计入)
    n_folders = len({d for _, d, _, _ in table})
    print_summary(n_folders, outputs, record_path)


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
