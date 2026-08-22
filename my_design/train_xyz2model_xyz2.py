#!/usr/bin/env python3
"""
=============================================================================
GPUMDkit: A User-Friendly Toolkit for GPUMD and NEP
Repository: https://github.com/zhyan0603/GPUMDkit
Citation: Z. Yan et al., GPUMDkit: A User-Friendly Toolkit for GPUMD and NEP,
          MGE Advances, 2026, e70074 (https://doi.org/10.1002/mgea.70074)
=============================================================================
脚本:       train_xyz2model_xyz.py  (pos2model_xyz.py 的 fork 版，改造为
            主动学习 MD 模拟的初始结构创建器)
分类:       主动学习工作流脚本
用途:       从 train.xyz (extxyz 格式) 中抽取指定帧，将每一帧保存为独立的
            model.xyz，作为主动学习 MD 模拟的初始结构。输入文件保持不变。

帧号约定 (重要):
  命令行传入的帧号为 OVITO 中显示的 0 起始索引 (0 = 第一帧)。
  抽取出的结构在文本编辑器中打开是第 (n+1) 帧 (1 起始)。
  输出文件夹命名为 1_md<n>，与 OVITO 帧号一致。
  每次抽取时脚本会同时打印两种视角，便于当场核对对应关系。

路径约定:
  脚本运行 (读写文件、创建文件夹) 时一律使用相对路径 (相对于当前运行
  目录); 而终端打印与 extracted_frames.txt 记录中显示的是绝对路径。
  输出根目录默认为当前目录的父目录 (相对路径 ..)。

帧记录与去重:
  每次成功抽取的帧会追加写入当前运行目录下的 extracted_model_xyz.txt，
  首行为表头，每行包含: 帧号、原子数、输出绝对路径、事件、状态。
    事件: 新建 (首次抽取) / 重建 (记录过但重新生成) / 已被移除 (检测到文件消失)。
    状态: 存在 (文件在) / 丢失 (文件不在)。
  旧格式记录 (无原子数列) 首次运行时自动迁移: 原子数从 model.xyz
  第一行补读，文件已丢失则记 '-'
  每次运行时先对比 txt 记录与磁盘上的实际文件，更新状态列:
    - 文件存在 → 状态保持"存在" (事件保留原值);
    - 文件缺失 → 该行更新为事件"已被移除"、状态"丢失"。
  然后按以下规则判断是否重复:
    - 有记录且文件夹与 model.xyz 都存在 → 跳过，不再重复生成;
    - 文件夹或 model.xyz 缺失 (例如被手动删除) → 重新生成。
  该规则同时适用于固定抽帧与随机抽帧模式 (随机模式中，
  已记录且输出完整的帧会从随机池中排除)。

输出文件夹:
  每一帧输出到 <outdir>/<MD_FOLDER_PREFIX><n>/model.xyz。
  文件夹前缀 (默认 1_md) 是脚本顶部的可配置参数。

自动同步 (每次运行结束都会执行):
  1) 若运行目录下存在 nep.txt，会复制 (覆盖) 到输出根目录下
     所有 1_md* 文件夹，保证势函数最新且 MD 目录自包含;
  2) 每个 1_md* 文件夹都会重新生成 sub_MD.sh，内容由脚本开头
     的 SUBMISSION_SCRIPT 变量定义 (修改该变量后重跑脚本即可
     全量同步)，所有文件夹内容一致。注意: 手动改过的 sub_MD.sh
     会被覆盖。
  注意: run.in 不在此脚本的同步范围内，需自行准备/同步。

超算 Linux 适配 (脚本主要运行环境):
  - stdout 强制 UTF-8, 避免超算 locale 非 UTF-8 时打印中文报错;
  - 生成 sub_MD.sh 统一写 LF 换行并赋予执行权限;
  - 缺少 ASE 库时给出明确的安装提示。

两种模式:
  1) 固定抽帧 (默认)
     python train_xyz2model_xyz.py [选项] 帧号 [帧号 ...]
     显式指定一个或多个 OVITO 帧号，重复帧号会忽略并给出警告。
  2) 随机抽帧
     python train_xyz2model_xyz.py [选项] random <n>
     随机抽取 <n> 个不重复的帧。未设置随机种子，每次运行结果不同;
     抽中的帧号会打印出来，便于记录复现。

选项:
  -i, --input FILE   输入 extxyz 文件 (默认: 当前目录下的 train.xyz)。
  -o, --outdir DIR   输出根目录 (默认: 当前目录的父目录，保持训练目录
                     如 1_train/ 整洁)。
输出:
  <outdir>/1_md<帧号>/model.xyz   (每个抽取帧一个文件夹)
示例:
  python train_xyz2model_xyz.py 5 9 66
      # OVITO 帧 5/9/66 (= 编辑器中第 6/10/67 帧)
      # -> ../1_md5/model.xyz, ../1_md9/model.xyz, ../1_md66/model.xyz
  python train_xyz2model_xyz.py 7
      # -> ../1_md7/model.xyz (编辑器中第 8 帧)
  python train_xyz2model_xyz.py random 3
      # 随机不重复抽 3 帧，例如 -> ../1_md12/model.xyz, ...
  python train_xyz2model_xyz.py -i test.xyz 0 1
      # 改用 test.xyz 作为输入，抽取前两帧
  python train_xyz2model_xyz.py -o /some/dir 2
      # 输出到 /some/dir/1_md2/model.xyz 而非默认父目录

去重 (两种模式通用):
  重复运行同一命令时，txt 中已记录且文件夹与 model.xyz 都存在的帧会被跳过:
    python train_xyz2model_xyz.py 5 9 66
    python train_xyz2model_xyz.py 5 9 66   # 第二次运行: 三帧全部跳过
  若手动删除了 1_md5/model.xyz (或整个文件夹)，下次运行会重新抽取帧 5。
作者:       Zihan YAN (yanzihan@westlake.edu.cn)
最后修改:   2026-08-21
=============================================================================
"""

import datetime
import os
import random
import shutil
import sys

# 超算 locale 可能非 UTF-8 (如 POSIX/C), 强制 stdout 用 UTF-8,
# 避免打印中文时抛 UnicodeEncodeError (Windows 终端显示乱码不影响功能)。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from ase.io import read, write
except ImportError:
    print("错误: 未找到 ASE (Python 库)。请在超算环境安装: pip install ase")
    sys.exit(1)

OUTPUT_FILE = "model.xyz"
DEFAULT_INPUT = "train.xyz"
# 输出文件夹命名: <MD_FOLDER_PREFIX><ovito帧号>，例如 1_md5。
# 如需更换命名方案，修改此前缀即可。
MD_FOLDER_PREFIX = "1_md"
# 帧抽取记录文件 (位于当前运行目录)，每行记录: OVITO 帧号、输出绝对
# 路径、事件 (新建/重建/已被移除)、状态 (存在/丢失)，用于避免重复
# 使用同一结构并审计文件状态。
RECORD_FILE = "extracted_model_xyz.txt"
# 记录文件表头 (帧号 / 原子数 / 路径 / 事件 / 状态)，首次创建记录
# 文件时写入; 以 # 开头，不参与解析。
RECORD_HEADER = "# " + f"{'帧号':<20}{'原子数':<8}{'路径':<60}{'事件':<16}状态\n"

# =====================================================================
# 提交脚本模板 (sub_MD.sh): 此变量的内容写入每个 MD 文件夹的 sub_MD.sh。
# 按你的超算环境调整: 作业名 / 队列分区 / 资源限制 / 模块加载 / 运行命令。
# 修改后重跑本脚本即可同步到所有 1_md* 文件夹 (内容一致)。
# 注意: 三引号后的空行在写入 sub_MD.sh 时会被自动去掉 (lstrip),
#       保证 #!/bin/bash 仍是文件第一行。
# =====================================================================
SUBMISSION_SCRIPT = """
#!/bin/bash
#SBATCH --job-name=MoTe2_MD
#SBATCH --partition=4090
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --mem=16G
#SBATCH -o %j.log
#SBATCH -e %j.log

# 加载环境
module purge
module load GPUMD/5.6-cuda12.2.0

# 自动进入当前提交目录
cd $SLURM_SUBMIT_DIR

# 运行 GPUMD (执行 run.in 里的 MD 任务)
gpumd

exit
"""


def print_usage():
    print(__doc__)


def parse_args(argv):
    """解析选项 (-i/--input, -o/--outdir, -h/--help)，返回剩余位置参数。"""
    input_file = DEFAULT_INPUT
    outdir = None
    rest = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-i", "--input"):
            if i + 1 >= len(argv):
                print(f"错误: 选项 {arg} 需要一个文件名。")
                sys.exit(1)
            input_file = argv[i + 1]
            i += 2
        elif arg in ("-o", "--outdir"):
            if i + 1 >= len(argv):
                print(f"错误: 选项 {arg} 需要一个目录。")
                sys.exit(1)
            outdir = argv[i + 1]
            i += 2
        elif arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        else:
            rest.append(arg)
            i += 1
    return input_file, outdir, rest


def check_input(input_file):
    if not os.path.exists(input_file):
        print(f"错误: 输入文件 '{os.path.abspath(input_file)}' 不存在。")
        print(f"请确认当前目录下有 {DEFAULT_INPUT}，或使用 -i 指定输入文件。")
        sys.exit(1)


def count_atoms(path):
    """读取 extxyz 文件第一行得到原子数; 读取失败返回 '-'。"""
    try:
        with open(path, encoding="utf-8") as f:
            first = f.readline().strip()
        return int(first) if first.isdigit() else "-"
    except OSError:
        return "-"


def load_record():
    """从 RECORD_FILE 读取已记录的 OVITO 帧号 (若存在)。"""
    if not os.path.exists(RECORD_FILE):
        return set()
    recorded = set()
    with open(RECORD_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            token = line.split()[0]
            if token.isdigit():
                recorded.add(int(token))
    return recorded


def update_record_status():
    """运行前对比 RECORD_FILE 记录与磁盘实际文件，更新每帧的状态列:
    文件存在 → 状态"存在" (事件保留); 文件缺失 → 事件"已被移除"、
    状态"丢失"。返回 (存在数, 丢失数)。"""
    if not os.path.exists(RECORD_FILE):
        return 0, 0
    with open(RECORD_FILE, encoding="utf-8") as f:
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
        path_col = max(60, len(path) + 1)
        lines_out.append(
            f"{idx:<22}{natom:<8}{path:<{path_col}}{event:<16}{status}\n")
    with open(RECORD_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines_out)
    return n_exist, n_lost


def append_record(frames, indices, outdir, recorded):
    """将新抽取的帧追加到 RECORD_FILE，带原子数、事件与状态列:
    从未记录过 → 事件"新建"; 记录过但重新抽取 → 事件"重建"。
    状态均为"存在"。首次创建记录文件时写入表头。"""
    if not indices:
        return
    new_file = not os.path.exists(RECORD_FILE)
    with open(RECORD_FILE, "a", encoding="utf-8") as f:
        if new_file:
            f.write(RECORD_HEADER)
        f.write(f"# {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        for idx in indices:
            natom = len(frames[idx])
            out_path = os.path.abspath(os.path.join(
                outdir, f"{MD_FOLDER_PREFIX}{idx}", OUTPUT_FILE))
            event = "重建" if idx in recorded else "新建"
            # 路径列用动态宽度，保证路径后至少有 1 个分隔空格 (解析依赖)
            path_col = max(60, len(out_path) + 1)
            f.write(
                f"{idx:<22}{natom:<8}{out_path:<{path_col}}{event:<16}存在\n")
    print(f"已记录 {len(indices)} 个新帧到 {os.path.abspath(RECORD_FILE)}。")


def output_complete(idx, outdir):
    """输出是否完整: 输出根目录下对应的文件夹与 model.xyz 都存在。"""
    folder = os.path.join(outdir, f"{MD_FOLDER_PREFIX}{idx}")
    return os.path.isdir(folder) and os.path.isfile(
        os.path.join(folder, OUTPUT_FILE))


def frame_available(idx, recorded, outdir):
    """帧可抽取的条件: 未记录，或已记录但输出不完整 (文件夹或
    model.xyz 缺失，例如被手动删除)。"""
    if idx not in recorded:
        return True
    return not output_complete(idx, outdir)


def extract_and_save(frames, ovito_index, outdir):
    """将 frames[ovito_index] 保存为
    <outdir>/<MD_FOLDER_PREFIX><ovito_index>/model.xyz。

    ovito_index 为 0 起始; 同一结构在文本编辑器中打开是第
    (ovito_index + 1) 帧。"""
    folder = os.path.join(outdir, f"{MD_FOLDER_PREFIX}{ovito_index}")
    os.makedirs(folder, exist_ok=True)
    out_path = os.path.join(folder, OUTPUT_FILE)
    if os.path.exists(out_path):
        print(f"  提示: {os.path.abspath(out_path)} 已存在，将被覆盖。")
    write(out_path, frames[ovito_index], format="extxyz")
    print(f"  OVITO 帧 {ovito_index} "
          f"(= 编辑器中第 {ovito_index + 1} 帧) "
          f"-> {os.path.abspath(out_path)}")


def sync_md_folder_files(outdir):
    """抽取完成后同步输出根目录下所有 1_md* 文件夹:
    1) 运行目录有 nep.txt 时复制进去 (覆盖旧版，保持势函数最新);
    2) 重新生成 sub_MD.sh (内容由脚本开头的 SUBMISSION_SCRIPT 变量定义)。
    用 newline="\n" 写 sub_MD.sh，避免 Windows 下写出 CRLF 导致
    超算上 #!/bin/bash 解析失败; 生成后赋予执行权限 (Linux)。"""
    if not os.path.isdir(outdir):
        return
    folders = sorted(
        name for name in os.listdir(outdir)
        if name.startswith(MD_FOLDER_PREFIX)
        and os.path.isdir(os.path.join(outdir, name)))
    if not folders:
        print("输出根目录下未发现任何 1_md* 文件夹，跳过同步。")
        return
    if os.path.isfile("nep.txt"):
        for name in folders:
            dest = os.path.join(outdir, name, "nep.txt")
            shutil.copy2("nep.txt", dest)
            print(f"  已复制 nep.txt -> {os.path.abspath(dest)}")
    else:
        print("提示: 运行目录未发现 nep.txt，未复制势文件到 MD 文件夹。")
    for name in folders:
        dest = os.path.join(outdir, name, "sub_MD.sh")
        with open(dest, "w", encoding="utf-8", newline="\n") as f:
            # lstrip: 去掉模板开头的空行, 保证 #!/bin/bash 是第一行
            f.write(SUBMISSION_SCRIPT.lstrip("\n"))
        os.chmod(dest, 0o755)  # 赋予执行权限, 便于直接 ./sub_MD.sh
        print(f"  已生成 sub_MD.sh -> {os.path.abspath(dest)}")


def main():
    input_file, outdir, rest = parse_args(sys.argv[1:])

    if not rest:
        print_usage()
        sys.exit(0)

    check_input(input_file)

    recorded = load_record()
    if recorded:
        print(f"记录文件 {os.path.abspath(RECORD_FILE)} "
              f"中的已用帧: {sorted(recorded)}")
    # 运行前对比磁盘文件，更新 txt 中每帧的状态列
    n_exist, n_lost = update_record_status()
    if recorded:
        print(f"已更新记录状态: {n_exist} 帧存在, {n_lost} 帧丢失。")

    # 一次性读取全部帧 (index=":" 返回列表)
    frames = read(input_file, index=":")
    nframes = len(frames)
    print(f"已从 {os.path.abspath(input_file)} 读取 {nframes} 帧。")

    # 输出根目录: -o 选项 > 当前目录的父目录 (运行用相对路径 ..，
    # 打印时显示绝对路径)
    if outdir is None:
        outdir = ".."
        print(f"未指定输出根目录，使用父目录: {os.path.abspath(outdir)}")
    os.makedirs(outdir, exist_ok=True)

    if rest[0] == "random":
        # 随机模式: python a.py random <n>
        if len(rest) != 2:
            print("用法: python a.py random <n>")
            sys.exit(1)
        if not rest[1].isdigit():
            print(f"错误: '{rest[1]}' 不是有效的正整数。")
            sys.exit(1)
        n_pick = int(rest[1])
        if n_pick < 1:
            print("错误: 抽取帧数必须 >= 1。")
            sys.exit(1)
        if n_pick > nframes:
            print(f"错误: 无法抽取 {n_pick} 帧: {os.path.abspath(input_file)} "
                  f"仅包含 {nframes} 帧。")
            sys.exit(1)
        # 排除已记录且输出完整的帧 (文件夹与 model.xyz 均存在)
        available = [i for i in range(nframes)
                     if frame_available(i, recorded, outdir)]
        skipped = [i for i in range(nframes)
                   if not frame_available(i, recorded, outdir)]
        if skipped:
            print(f"已排除 {len(skipped)} 个抽取过的帧 "
                  f"(有记录且输出完整): {skipped}")
        if len(available) < n_pick:
            print(f"错误: 仅有 {len(available)} 帧可用 "
                  f"(已排除有记录且输出完整的帧)，无法抽取 {n_pick} 帧。")
            sys.exit(1)
        picked = sorted(random.sample(available, n_pick))
        print(f"随机抽中 {n_pick} 帧: {picked} (OVITO 帧号)。")
        for idx in picked:
            extract_and_save(frames, idx, outdir)
        append_record(frames, picked, outdir, recorded)
    else:
        # 固定抽帧模式 (默认)
        ovito_indices = []
        seen = set()
        for token in rest:
            if not token.isdigit():
                print(f"错误: '{token}' 不是有效的帧号。"
                      "用法: python a.py [帧号 ...] "
                      "或 python a.py random <n>")
                sys.exit(1)
            idx = int(token)
            if idx in seen:
                print(f"警告: 重复帧号 {idx} 已忽略。")
                continue
            seen.add(idx)
            ovito_indices.append(idx)

        for idx in ovito_indices:
            if idx < 0 or idx >= nframes:
                print(f"错误: 帧号 {idx} 超出范围 "
                      f"([0, {nframes - 1}]，共 {nframes} 帧)。")
                sys.exit(1)

        # 按记录文件去重: 有记录且输出完整 (文件夹与 model.xyz 均存在)
        # 才跳过; 缺文件夹或缺 model.xyz 则重新生成
        to_extract = []
        for idx in ovito_indices:
            if idx in recorded:
                folder = os.path.join(outdir, f"{MD_FOLDER_PREFIX}{idx}")
                model_path = os.path.join(folder, OUTPUT_FILE)
                if os.path.isdir(folder) and os.path.isfile(model_path):
                    print(f"  跳过: 帧 {idx} 已抽取过 "
                          f"({os.path.abspath(model_path)} 存在)。")
                    continue
                if not os.path.isdir(folder):
                    print(f"  提示: 帧 {idx} 有记录，但文件夹 "
                          f"{os.path.abspath(folder)} 不存在，重新生成。")
                else:
                    print(f"  提示: 帧 {idx} 有记录，但 "
                          f"{os.path.abspath(model_path)} 不存在，"
                          "重新生成。")
            to_extract.append(idx)

        if not to_extract:
            print("无需抽取 (所有请求的帧都已抽取过)。")
        else:
            print("开始抽取以下帧:")
            for idx in to_extract:
                extract_and_save(frames, idx, outdir)
            append_record(frames, to_extract, outdir, recorded)

    # 同步势文件与提交脚本到所有 1_md* 文件夹 (含本次新抽取的)
    sync_md_folder_files(outdir)

    print("全部完成。")


if __name__ == "__main__":
    main()
