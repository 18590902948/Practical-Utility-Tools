#!/usr/bin/env python3
"""
=============================================================================
GPUMDkit: A User-Friendly Toolkit for GPUMD and NEP
Repository: https://github.com/zhyan0603/GPUMDkit
Citation: Z. Yan et al., GPUMDkit: A User-Friendly Toolkit for GPUMD and NEP,
          MGE Advances, 2026, e70074 (https://doi.org/10.1002/mgea.70074)
=============================================================================
脚本:        xyz2model_xyz.py  (train_xyz2model_xyz2.py 的通用化 fork 版)
分类:        结构处理工具
功能:        按 OVITO 帧号从 extxyz 轨迹中抽取指定/随机/全部帧，每帧输出
             为独立文件夹下的 model.xyz，并用记录文件自动去重审计。
使用方法:    python xyz2model_xyz.py [输入xyz文件名] [选项] [模式参数]
参数:        输入xyz文件名   输入 extxyz 文件 (不指定时用配置区 INPUT_FILES，
                           支持通配符；命令行相对当前运行目录解析)
             -o/--outdir     输出根目录 (默认: 配置区 OUTPUT_PATH，脚本所在目录)
             -h/--help       显示本帮助
模式参数:    --extract/-ext   固定抽帧（默认）：提取指定帧号 [帧号 ...]
             --random/-ran   随机抽帧：随机抽取 n 帧（用法：--random <n>）
             --all/-all      全帧抽取：抽取全部帧
             (模式互斥，同时指定多个时报错；选项位置随意)
输入文件:    配置区 INPUT_FILES (默认 train.xyz，支持通配符)
输出文件:    extracted_model_xyz.txt  (记录文件，表格形式，表头+5列，自动去重)
             0/model.xyz, 1/model.xyz  (每帧一个文件夹，文件夹名为 OVITO 帧号)
输出路径:    默认脚本所在目录 (OUTPUT_PATH)，可用 -o 指定 (相对/绝对路径均可)
帧号约定:    OVITO 0 起始索引 (0 = 第一帧，编辑器中第 n+1 帧)
示例:
  python xyz2model_xyz.py test.xyz --extract 5 9 66
  python xyz2model_xyz.py --extract 5 9 66   (不指定输入时用配置区 INPUT_FILES)
  python xyz2model_xyz.py --random 3
  python xyz2model_xyz.py --all
作者:        Zihan YAN (yanzihan@westlake.edu.cn) (fork 自 train_xyz2model_xyz2.py)
最后修改:    2026-08-24
=============================================================================
"""

import datetime
import glob
import os
import random
import sys

# ============================== 参数配置区 =====================================
INPUT_FILES  = ["train.xyz"]            # 输入文件列表 (支持通配符，相对 INPUT_PATH 展开；命令行参数优先)
OUTPUT_FILES = ["model.xyz"]            # 输出文件列表 (每帧输出为 <帧号>/<输出文件>，相对 OUTPUT_PATH)
RECORD_FILE  = "extracted_model_xyz.txt"  # 帧抽取记录文件 (脚本所在目录)
INPUT_PATH   = "./"                    # 输入文件寻找路径 (相对脚本所在目录)
OUTPUT_PATH  = "./"                    # 输出文件寻找路径 (相对脚本所在目录)
RECORD_PATH_COL = 60                    # 记录文件路径列最小宽度 (保证列间分隔)
RECORD_HEADER   = ("# " + f"{'帧号':<20}{'原子数':<8}"
                   f"{'路径':<{RECORD_PATH_COL}}{'事件':<16}状态\n")  # 记录文件表头
# =============================================================================

# ============================== 环境准备区 =====================================
# 终端 locale 可能非 UTF-8 (如 POSIX/C), 强制 stdout 用 UTF-8,
# 避免打印中文时抛 UnicodeEncodeError (Windows 终端显示乱码不影响功能)。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from ase.io import read, write
except ImportError:
    print("❌ 错误: 未找到 ASE (Python 库)。请安装: pip install ase")
    sys.exit(1)
# ===========================================================================


# ============================== 函数配置区 =====================================
def print_usage():
    """打印头部注释块 (脚本功能与完整使用方法)。"""
    print(__doc__)


def parse_args(argv):
    """解析命令行参数 (选项形式，位置随意): 输入文件为位置参数;
    -h/--help、-o/--outdir、--extract/-ext、--random/-ran、--all/-all
    为选项。返回 (输入文件名, 输出目录, 模式, 模式参数列表)。"""
    input_file = None
    outdir = None
    mode = None
    mode_args = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif arg in ("-o", "--outdir"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -o/--outdir 需要一个目录。")
                sys.exit(1)
            outdir = argv[i + 1]
            i += 2
        elif arg in ("--extract", "-ext"):
            if mode is not None:
                mode_conflict(mode, "extract")
            mode = "extract"
            i += 1
            # 收集模式选项后的帧号，直到下一个选项
            while i < len(argv) and argv[i].isdigit():
                mode_args.append(argv[i])
                i += 1
        elif arg in ("--random", "-ran"):
            if mode is not None:
                mode_conflict(mode, "random")
            if i + 1 >= len(argv) or not argv[i + 1].isdigit():
                print("❌ 错误: --random/-ran 需要一个正整数 n (随机抽取 n 帧)。")
                sys.exit(1)
            mode = "random"
            mode_args = [argv[i + 1]]
            i += 2
        elif arg in ("--all", "-all"):
            if mode is not None:
                mode_conflict(mode, "all")
            mode = "all"
            i += 1
        elif arg.isdigit():
            print(f"❌ 错误: '{arg}' 不是有效参数。帧号请用选项形式指定:")
            print("  用法: python xyz2model_xyz.py 输入xyz文件名 --extract 5 9")
            sys.exit(1)
        elif input_file is None:
            input_file = arg
            i += 1
        else:
            print(f"❌ 错误: 无法识别的参数 '{arg}'。")
            print_usage()
            sys.exit(1)
    return input_file, outdir, mode, mode_args


def mode_conflict(existing, new):
    """模式选项互斥校验: 同时指定多个模式时报错退出。"""
    names = {"extract": "--extract/-ext",
             "random": "--random/-ran",
             "all": "--all/-all"}
    print(f"❌ 错误: 模式选项互斥，只能指定一个 "
          f"({names[existing]} 与 {names[new]} 冲突)。")
    sys.exit(1)


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
            files.append(os.path.join(base_dir, p))
    return files


def resolve_input(script_dir, input_file):
    """解析输入文件: 命令行指定优先 (相对当前运行目录解析，不存在再相对
    脚本目录)；未指定时用配置区 INPUT_FILES 展开 (相对 INPUT_PATH)，
    多文件时仅使用第一个并警告。返回输入文件绝对路径。"""
    if input_file:
        f = (input_file if os.path.isfile(input_file)
             else os.path.join(script_dir, input_file))
        if os.path.isfile(f):
            return os.path.abspath(f)
        print(f"❌ 错误: 输入文件 '{os.path.abspath(input_file)}' 不存在。")
        print("请确认输入 xyz 文件与脚本同目录，用法:")
        print("  python xyz2model_xyz.py 输入xyz文件名 --extract 帧号 [帧号 ...]")
        sys.exit(1)
    base = os.path.normpath(os.path.join(script_dir, INPUT_PATH))
    files = [f for f in expand_patterns(INPUT_FILES, base, keep_unmatched=False)
             if os.path.isfile(f)]
    if not files:
        print("❌ 错误: 配置区 INPUT_FILES 未找到任何输入文件。")
        print("请在参数配置区设置 INPUT_FILES 或用命令行指定输入 xyz 文件。")
        sys.exit(1)
    if len(files) > 1:
        print(f"⚠️ 警告: 配置区 INPUT_FILES 匹配 {len(files)} 个文件，"
              f"仅使用第一个: {os.path.basename(files[0])}")
    return files[0]


def count_atoms(path):
    """读取 extxyz 文件第一行得到原子数; 读取失败返回 '-'。"""
    try:
        with open(path, encoding="utf-8") as f:
            first = f.readline().strip()
        return int(first) if first.isdigit() else "-"
    except OSError:
        return "-"


def load_record(record_path):
    """从记录文件读取已记录的 OVITO 帧号 (若存在)。"""
    if not os.path.exists(record_path):
        return set()
    recorded = set()
    with open(record_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            token = line.split()[0]
            if token.isdigit():
                recorded.add(int(token))
    return recorded


def update_record_status(record_path):
    """运行前对比记录文件与磁盘实际文件，更新每帧的状态列:
    文件存在 → 状态"存在" (事件保留); 文件缺失 → 事件"已被移除"、
    状态"丢失"。返回 (存在数, 丢失数)。"""
    if not os.path.exists(record_path):
        return 0, 0
    with open(record_path, encoding="utf-8") as f:
        lines = f.readlines()
    # 旧文件可能没有表头 (升级前生成)，重写时自动补到最顶部
    has_header = any(line.strip() == RECORD_HEADER.strip() for line in lines)
    lines_out = [RECORD_HEADER] if not has_header else []
    n_exist = n_lost = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            lines_out.append(line)
            continue
        parts = stripped.split()
        if not parts or not parts[0].isdigit() or len(parts) < 2:
            lines_out.append(line)
            continue
        idx = int(parts[0])
        if len(parts) > 1 and (parts[1].isdigit() or parts[1] == "-"):
            # 新格式: 第 2 列为原子数 ('-' 表示文件丢失时无法统计)
            natom = parts[1]
            path = parts[2]
            event = parts[3] if len(parts) > 3 else ""
            status = parts[4] if len(parts) > 4 else ""
        else:
            # 旧格式 (无原子数列): 第 2 列为路径，原子数从 model.xyz
            # 第一行补读; 文件已丢失则记 '-'
            natom = (str(count_atoms(parts[1]))
                     if os.path.isfile(parts[1]) else "-")
            path = parts[1]
            event = parts[2] if len(parts) > 2 else ""
            status = parts[3] if len(parts) > 3 else ""
        if os.path.isfile(path):
            n_exist += 1
            if status != "存在":
                status = "存在"
        else:
            n_lost += 1
            event, status = "已被移除", "丢失"
        # 路径列用动态宽度，保证路径后至少有 1 个分隔空格 (解析依赖)
        path_col = max(RECORD_PATH_COL, len(path) + 1)
        lines_out.append(
            f"{idx:<22}{natom:<8}{path:<{path_col}}{event:<16}{status}\n")
    with open(record_path, "w", encoding="utf-8") as f:
        f.writelines(lines_out)
    return n_exist, n_lost


def append_record(frames, indices, outdir, recorded, record_path):
    """将新抽取的帧追加到记录文件，带原子数、事件与状态列:
    从未记录过 → 事件"新建"; 记录过但重新抽取 → 事件"重建"。
    状态均为"存在"。首次创建记录文件时写入表头。"""
    if not indices:
        return
    new_file = not os.path.exists(record_path)
    with open(record_path, "a", encoding="utf-8") as f:
        if new_file:
            f.write(RECORD_HEADER)
        f.write(f"# {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        for idx in indices:
            natom = len(frames[idx])
            out_path = os.path.abspath(os.path.join(
                outdir, str(idx), OUTPUT_FILES[0]))
            event = "重建" if idx in recorded else "新建"
            # 路径列用动态宽度，保证路径后至少有 1 个分隔空格 (解析依赖)
            path_col = max(RECORD_PATH_COL, len(out_path) + 1)
            f.write(
                f"{idx:<22}{natom:<8}{out_path:<{path_col}}{event:<16}存在\n")
    print(f"✅ 已记录 {len(indices)} 个新帧到 {os.path.abspath(record_path)}。")


def output_complete(idx, outdir):
    """输出是否完整: 输出根目录下对应的文件夹与输出文件都存在。"""
    folder = os.path.join(outdir, str(idx))
    return os.path.isdir(folder) and os.path.isfile(
        os.path.join(folder, OUTPUT_FILES[0]))


def frame_available(idx, recorded, outdir):
    """帧可抽取的条件: 未记录，或已记录但输出不完整 (文件夹或
    model.xyz 缺失，例如被手动删除)。"""
    if idx not in recorded:
        return True
    return not output_complete(idx, outdir)


def extract_and_save(frames, ovito_index, outdir):
    """将 frames[ovito_index] 保存为 <outdir>/<ovito_index>/model.xyz。

    ovito_index 为 0 起始; 同一结构在文本编辑器中打开是第
    (ovito_index + 1) 帧。输出文件夹名为帧号本身。"""
    folder = os.path.join(outdir, str(ovito_index))
    os.makedirs(folder, exist_ok=True)
    out_path = os.path.join(folder, OUTPUT_FILES[0])
    if os.path.exists(out_path):
        print(f"ℹ️ 提示: {os.path.abspath(out_path)} 已存在，将被覆盖。")
    write(out_path, frames[ovito_index], format="extxyz")
    print(f"  ✅ OVITO 帧 {ovito_index} "
          f"(= 编辑器中第 {ovito_index + 1} 帧) "
          f"-> {os.path.abspath(out_path)}")


def print_summary(mode_name, n_extracted, n_skipped, outdir, record_path):
    """运行完毕后集中总结关键信息 (模式、数量统计、输出与记录文件绝对路径)。"""
    print("=" * 52)
    print("🎉 运行完成，总结:")
    print(f"  模式:       {mode_name}")
    print(f"  抽取:       {n_extracted} 帧")
    print(f"  跳过:       {n_skipped} 帧 (已抽取过且输出完整)")
    print(f"  输出根目录: {os.path.abspath(outdir)}")
    print(f"  记录文件:   {os.path.abspath(record_path)}")
    print("=" * 52)


# ============================== 脚本工作区 =====================================
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_file, outdir, mode, mode_args = parse_args(sys.argv[1:])
    record_path = os.path.join(script_dir, RECORD_FILE)

    input_path = resolve_input(script_dir, input_file)
    print(f"ℹ️ 输入文件: {input_path}")

    recorded = load_record(record_path)
    if recorded:
        print(f"ℹ️ 记录文件 {os.path.abspath(record_path)} "
              f"中的已用帧: {sorted(recorded)}")
    # 运行前对比磁盘文件，更新 txt 中每帧的状态列
    n_exist, n_lost = update_record_status(record_path)
    if recorded:
        print(f"ℹ️ 已更新记录状态: {n_exist} 帧存在, {n_lost} 帧丢失。")

    # 一次性读取全部帧 (index=":" 返回列表)
    frames = read(input_path, index=":")
    nframes = len(frames)
    print(f"ℹ️ 已从 {os.path.abspath(input_path)} 读取 {nframes} 帧。")

    # 输出根目录: -o 选项 > 配置区 OUTPUT_PATH (脚本所在目录)
    if outdir is None:
        outdir = os.path.normpath(os.path.join(script_dir, OUTPUT_PATH))
        print(f"ℹ️ 未指定输出根目录，使用脚本所在目录: {os.path.abspath(outdir)}")
    os.makedirs(outdir, exist_ok=True)

    # 未指定模式选项 → 默认固定抽帧 (--extract)
    if mode is None:
        print("ℹ️ 未指定模式，默认固定抽帧 (--extract/-ext)。")
        mode = "extract"

    mode_name = {"extract": "固定抽帧", "random": "随机抽帧",
                 "all": "全帧抽取"}[mode]
    n_extracted = 0
    n_skipped = 0

    if mode == "all":
        # 全帧模式: python xyz2model_xyz.py 输入xyz文件名 --all
        to_extract = [i for i in range(nframes)
                      if frame_available(i, recorded, outdir)]
        skipped = [i for i in range(nframes)
                   if not frame_available(i, recorded, outdir)]
        n_skipped = len(skipped)
        if skipped:
            print(f"⚠️ 已排除 {len(skipped)} 个抽取过的帧 "
                  f"(有记录且输出完整): {skipped}")
        if not to_extract:
            print("ℹ️ 无需抽取 (所有帧都已抽取过)。")
        else:
            print(f"📦 开始抽取全部 {len(to_extract)} 帧 (共 {nframes} 帧):")
            for idx in to_extract:
                extract_and_save(frames, idx, outdir)
            append_record(frames, to_extract, outdir, recorded, record_path)
        n_extracted = len(to_extract)
    elif mode == "random":
        # 随机模式: python xyz2model_xyz.py 输入xyz文件名 --random <n>
        n_pick = int(mode_args[0])
        if n_pick < 1:
            print("❌ 错误: 抽取帧数必须 >= 1。")
            sys.exit(1)
        if n_pick > nframes:
            print(f"❌ 错误: 无法抽取 {n_pick} 帧: "
                  f"{os.path.abspath(input_file)} 仅包含 {nframes} 帧。")
            sys.exit(1)
        # 排除已记录且输出完整的帧 (文件夹与 model.xyz 均存在)
        available = [i for i in range(nframes)
                     if frame_available(i, recorded, outdir)]
        skipped = [i for i in range(nframes)
                   if not frame_available(i, recorded, outdir)]
        n_skipped = len(skipped)
        if skipped:
            print(f"⚠️ 已排除 {len(skipped)} 个抽取过的帧 "
                  f"(有记录且输出完整): {skipped}")
        if len(available) < n_pick:
            print(f"❌ 错误: 仅有 {len(available)} 帧可用 "
                  f"(已排除有记录且输出完整的帧)，无法抽取 {n_pick} 帧。")
            sys.exit(1)
        picked = sorted(random.sample(available, n_pick))
        print(f"✅ 随机抽中 {n_pick} 帧: {picked} (OVITO 帧号)。")
        for idx in picked:
            extract_and_save(frames, idx, outdir)
        append_record(frames, picked, outdir, recorded, record_path)
        n_extracted = len(picked)
    else:
        # 固定抽帧模式 (默认): --extract 帧号 [帧号 ...]
        if not mode_args:
            print("❌ 错误: 固定抽帧模式需要至少一个帧号 "
                  "(用法: --extract 5 9)。")
            print_usage()
            sys.exit(1)
        ovito_indices = []
        seen = set()
        for token in mode_args:
            idx = int(token)
            if idx in seen:
                print(f"⚠️ 警告: 重复帧号 {idx} 已忽略。")
                continue
            seen.add(idx)
            ovito_indices.append(idx)

        for idx in ovito_indices:
            if idx < 0 or idx >= nframes:
                print(f"❌ 错误: 帧号 {idx} 超出范围 "
                      f"([0, {nframes - 1}]，共 {nframes} 帧)。")
                sys.exit(1)

        # 按记录文件去重: 有记录且输出完整 (文件夹与 model.xyz 均存在)
        # 才跳过; 缺文件夹或缺 model.xyz 则重新生成
        to_extract = []
        for idx in ovito_indices:
            if idx in recorded:
                folder = os.path.join(outdir, str(idx))
                model_path = os.path.join(folder, OUTPUT_FILES[0])
                if os.path.isdir(folder) and os.path.isfile(model_path):
                    print(f"⚠️ 跳过: 帧 {idx} 已抽取过 "
                          f"({os.path.abspath(model_path)} 存在)。")
                    continue
                if not os.path.isdir(folder):
                    print(f"ℹ️ 提示: 帧 {idx} 有记录，但文件夹 "
                          f"{os.path.abspath(folder)} 不存在，重新生成。")
                else:
                    print(f"ℹ️ 提示: 帧 {idx} 有记录，但 "
                          f"{os.path.abspath(model_path)} 不存在，"
                          "重新生成。")
            to_extract.append(idx)
        n_skipped = len(ovito_indices) - len(to_extract)

        if not to_extract:
            print("ℹ️ 无需抽取 (所有请求的帧都已抽取过)。")
        else:
            print(f"📦 开始抽取以下帧: {to_extract}")
            for idx in to_extract:
                extract_and_save(frames, idx, outdir)
            append_record(frames, to_extract, outdir, recorded, record_path)
        n_extracted = len(to_extract)

    print_summary(mode_name, n_extracted, n_skipped, outdir, record_path)


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
