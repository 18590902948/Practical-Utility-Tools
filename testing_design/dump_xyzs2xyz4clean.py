#!/usr/bin/env python3
"""
=============================================================================
脚本:        dump_xyzs2xyz4clean.py
分类:        结构处理工具
功能:        合并多个目标文件夹下同名 dump/xyz 文件为单一文件，并清理
             注释行中非白名单标签 (默认只保留 Time/pbc/Lattice/Properties)；
             -s 可额外保留指定键值对 (如 energy=-39.25362674)，-n 指定
             输入文件名，-o 指定输出路径 (靶文件夹)，并统计帧数、记录
             合并日志。
使用方法:    python dump_xyzs2xyz4clean.py [-t] [目标文件夹 ...] [-n 文件名] [-s 键名] [-o 输出路径]
参数:        目标文件夹 ...  格式一致的输入文件夹 (可选 -t/--target 标记，
                           不输入也行；支持通配符描述，如 './1_md*'；
                           相对当前运行目录解析，不存在再相对脚本目录；
                           不传时用配置区 DEFAULT_DIRS)
             -t/--target   目标文件夹标记 (可选，不输入也行，仅用于明确
                           声明；位置参数一律视为目标文件夹)
             -n/--name     输入文件名 (不指定默认 dump.xyz，各目标文件夹下同名文件)
             -s/--save     保留键名 (可多次使用，如 -s energy -s virial；
                           指定后注释行中该键值对与白名单一起保留)
             -o/--output   输出路径 (两种形式: 以 .xyz/.extxyz 结尾视为
                           输出文件完整路径，如 -o ./A/a.xyz，否则视为
                           输出目录 (靶文件夹)，文件名用配置区
                           OUTPUT_FILES；不指定时输出到默认目录
                           OUTPUT_PATH；不带点开头的相对路径默认相对
                           脚本所在目录解析，./ 或 ../ 开头相对当前
                           运行目录)
             -h/--help     显示本帮助
输入文件:    配置区 DEFAULT_DIRS 下的 INPUT_FILE (默认 dump.xyz)
输出文件:    配置区 OUTPUT_FILES (默认 merge_clean.xyz，相对 OUTPUT_PATH)
输出路径:    默认脚本所在目录下的 merge_clean/ (OUTPUT_PATH)，可用 -o 指定
           (输出文件或输出目录，相对/绝对路径均可)；合并记录
           merge_clean.txt 位于输出目录
示例:
  python dump_xyzs2xyz4clean.py
  python dump_xyzs2xyz4clean.py -t ./dir1 ./dir2 -s energy -o ./A/a.xyz
  python dump_xyzs2xyz4clean.py './1_md*' -s energy -o ./A/a.xyz
作者:        Hongbo Sun
最后修改:    2026-08-24
=============================================================================
"""

import glob
import os
import re
import sys
import time

# ============================== 参数配置区 =====================================
INPUT_FILE   = "dump.xyz"                    # 输入文件名 (各目录下同名文件；-n 命令行优先)
DEFAULT_DIRS = ["1_md*"]  # 默认目标文件夹列表 (相对 INPUT_PATH，条目支持通配符；命令行目录参数优先)
# 原写法示例 (逐条列出，效果等价): ["1_md712", "1_md2379", "1_md2412", "1_md3494", "1_md3631"]
OUTPUT_FILES = ["merge_clean.xyz"]           # 输出文件列表 (相对 OUTPUT_PATH；-o 命令行优先)
OUTPUT_PATH  = "./merge_clean/"              # 输出文件寻找路径 (相对脚本所在目录)
RECORD_FILE  = "merge_clean.txt"             # 合并记录文件 (追加写入，不覆盖历史，输出目录)
INPUT_PATH   = "./"                          # 输入目录寻找路径 (相对脚本所在目录)
KEEP_KEYS    = {"Time", "pbc", "Lattice", "Properties"}  # 默认保留的注释键名白名单 (-s 追加)
MERGE_BUF    = 1024 * 1024                   # 合并读写缓冲区大小 (1 MB)
# =============================================================================

# ============================== 环境准备区 =====================================
# 终端 locale 可能非 UTF-8 (如 POSIX/C), 强制 stdout 用 UTF-8,
# 避免打印中文时抛 UnicodeEncodeError (Windows 终端显示乱码不影响功能)。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
# ===========================================================================


# ============================== 函数配置区 =====================================
# 匹配注释行中的键值对: key=value 或 key="value with space"
TAG_RE = re.compile(r'(\w+)=("[^"]*"|\S+)')


def print_usage():
    """打印头部注释块 (脚本功能与完整使用方法)。"""
    print(__doc__)


def parse_args(argv):
    """解析命令行参数: -h/--help、-n/--name、-s/--save、-o/--output、
    -t/--target 为选项，其余为目标文件夹列表。返回 (目标文件夹列表, 输入
    文件名, 保留键集合, 输出路径)。选项位置随意。"""
    dirs = []
    name = None
    save_keys = set()
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
        elif arg in ("-s", "--save"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -s/--save 需要一个保留键名。")
                sys.exit(1)
            save_keys.add(argv[i + 1])
            i += 2
        elif arg in ("-o", "--output"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -o/--output 需要一个输出路径。")
                sys.exit(1)
            out_path = argv[i + 1]
            i += 2
        else:
            dirs.append(arg)
            i += 1
    return dirs, name, save_keys, out_path


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
    (相对当前运行目录，仅保留目录)，参数为已存在目录则直接使用，否则
    相对脚本目录解析。"""
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


def clean_comment(line, save_keys):
    """删除注释行中不在白名单里的标签: 只保留 KEEP_KEYS 与 -s 指定的键"""
    tags = TAG_RE.findall(line)
    kept = [f"{k}={v}" for k, v in tags if k in KEEP_KEYS or k in save_keys]
    return " ".join(kept) + "\n"



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


def merge_clean_files(file_list, out_file, save_keys):
    """按帧读取合并文件，清理注释行标签后写入输出 (覆盖写，行为等价 cat)，
    统一 LF 换行；自动检查每个文件末尾，缺换行符则补一个，防止帧粘连。
    返回各输入文件的帧数列表。"""
    out_dir = os.path.dirname(os.path.abspath(out_file))
    os.makedirs(out_dir, exist_ok=True)
    frame_counts = []
    with open(out_file, "w", encoding="utf-8", newline="\n") as fout:
        for f in file_list:
            print(f"  📦 处理 {os.path.basename(f)} ...", end=" ")
            n_frames = 0
            last_line = ""
            with open(f, "r", encoding="utf-8", newline="\n") as fin:
                while True:
                    nline = fin.readline()
                    if not nline:
                        break
                    parts = nline.split()
                    try:
                        # 首列必须是正整数原子数；记录文件/总结信息等污染行会在此失败
                        n = int(parts[0]) if parts else -1
                        if n <= 0:
                            raise ValueError
                    except (ValueError, IndexError):
                        print(f"⚠️ 警告: {os.path.basename(f)} 含非 xyz 内容"
                              "(可能被记录文件污染)，已跳过该文件")
                        return None
                    fout.write(nline)
                    fout.write(clean_comment(fin.readline(), save_keys))
                    for _ in range(n):
                        line = fin.readline()
                        fout.write(line)
                        last_line = line
                    n_frames += 1
            if last_line and not last_line.endswith("\n"):
                fout.write("\n")
            print(f"✅ ({n_frames} 帧)")
            frame_counts.append(n_frames)
    print(f"  ✅ 已输出: {os.path.abspath(out_file)}")
    return frame_counts


def write_record(records, record_path):
    """追加写入合并记录 (merge_clean.txt)，每次运行一个分节块，全部行以
    # 开头，含表头、时间戳、输入清单与输出清单。"""
    lines = ["# " + "=" * 40,
             f"# 合并时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"]
    inputs = records["inputs"]
    lines.append(f"# [输入文件] ({len(inputs)} 个)")
    lines.append("# " + pad("目录名", 20) + " " + pad("文件名", 30)
                 + " " + pad("帧数", 6, "r"))
    for _, d, fname, n in inputs:
        lines.append("# " + pad(d, 20) + " " + pad(fname, 30)
                     + " " + pad(str(n), 6, "r"))
    lines.append("# [输出文件]")
    for out, total in records["outputs"]:
        lines.append(f"#   {pad(out, 44)} 总 {total} 帧")
    lines.append("# " + "=" * 40)
    with open(record_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def print_summary(n_inputs, outputs, record_path, save_keys):
    """运行完毕后集中总结关键信息 (输入文件数、保留键、输出文件与绝对路径、记录文件)。"""
    print("=" * 52)
    print("🎉 运行完成，总结:")
    print(f"  输入文件:  {n_inputs} 个")
    print(f"  保留键:  {', '.join(sorted(KEEP_KEYS | save_keys))}")
    print(f"  输出文件:  {len(outputs)} 个")
    for out, total in outputs:
        print(f"    {os.path.abspath(out)}  (总 {total} 帧)")
    print(f"  记录文件:  {os.path.abspath(record_path)} (追加)")
    print("=" * 52)


# ============================== 脚本工作区 =====================================
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    args, name, save_keys, out_path = parse_args(sys.argv[1:])
    input_name = name or INPUT_FILE
    print(f"ℹ️ 脚本所在目录: {script_dir}")
    print(f"ℹ️ 输入文件名: {input_name} | 保留键: {', '.join(sorted(KEEP_KEYS | save_keys))}")

    # 输出文件: -o 命令行优先，否则配置区 OUTPUT_FILES (相对 OUTPUT_PATH)
    if out_path:
        out_base = resolve_cmd_path(out_path, script_dir)
        ext = os.path.splitext(out_base)[1].lower().lstrip(".")
        if ext in ("xyz", "extxyz"):
            # -o 为输出文件完整路径: 扩展名决定输出格式
            out_file = out_base
            output_dir = os.path.dirname(out_base)
        else:
            # -o 为输出目录: 文件名用配置区 OUTPUT_FILES 对应格式
            output_dir = out_base
            out_file = os.path.join(output_dir, OUTPUT_FILES[0])
    else:
        output_dir = os.path.normpath(os.path.join(script_dir, OUTPUT_PATH))
        out_file = os.path.join(output_dir, OUTPUT_FILES[0])

    # 解析待合并的目录 (无参数用配置区 DEFAULT_DIRS，有参数按指定顺序)
    input_base = os.path.normpath(os.path.join(script_dir, INPUT_PATH))
    dirs = resolve_dirs(script_dir, args, input_base)
    if not dirs:
        print("❌ 错误: 未找到任何目录。")
        sys.exit(1)

    # 收集各目录下的输入文件，排除输出文件 (避免重复合并)，校验含有效帧
    files = []
    for d in dirs:
        full = os.path.join(d, input_name)
        if not os.path.isfile(full):
            print(f"⚠️ 警告: 文件不存在，已跳过: {full}")
            continue
        if os.path.basename(full) == os.path.basename(out_file):
            print(f"⚠️ 警告: 与输出文件同名，已跳过: {full}")
            continue
        if count_frames(full) == 0:
            # 帧数为 0 说明不是有效的 xyz 文件 (如误传 txt/记录文件)，
            # 直接拼入会污染输出，跳过并警告
            print(f"⚠️ 警告: 文件不含有效 xyz 帧 (可能不是 xyz 文件)，已跳过: {full}")
            continue
        files.append(full)
    if not files:
        print("❌ 错误: 未找到任何输入文件。")
        sys.exit(1)

    # 合并清理并统计各文件帧数
    frame_counts = merge_clean_files(files, out_file, save_keys)
    if frame_counts is None:
        # 输入含非 xyz 内容 (如被记录文件污染)，输出不完整，终止并提示
        print("❌ 错误: 存在被污染的输入文件，已终止，请检查输入文件后重试。")
        sys.exit(1)
    total = sum(frame_counts)
    table = [(f, os.path.basename(os.path.dirname(f)), input_name, n)
             for f, n in zip(files, frame_counts)]

    # 终端展示: 目录名、文件名、帧数 (中文宽度对齐，帧数右对齐)
    print("\n📋 检测到输入文件:")
    print(f"  {pad('目录名', 20)}{pad('文件名', 30)}{pad('帧数', 6, 'r')}")
    for _, d, fname, n in table:
        print(f"  {pad(d, 20)}{pad(fname, 30)}{pad(str(n), 6, 'r')}")

    # 追加写入合并记录 (多次运行不覆盖历史，位于输出目录)
    record_path = os.path.join(output_dir, RECORD_FILE)
    outputs = [(out_file, total)]
    write_record({"inputs": table, "outputs": outputs}, record_path)
    print(f"ℹ️ 合并记录已追加: {os.path.abspath(record_path)}")

    print_summary(len(files), outputs, record_path, save_keys)


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
