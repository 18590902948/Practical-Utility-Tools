#!/usr/bin/env python3
"""
=============================================================================
脚本:        train_xyz2model_xyzs.py
分类:        主动学习工作流脚本 (结构抽取/转换类)
功能:        从 NEP 训练目录的 train.xyz 中按指定帧号或随机抽取结构，每帧
             输出为 <outdir>/1_md<帧号>/model.xyz (主动学习 MD 初始结构)，
             并同步 nep.txt 与 sub_MD.sh 至所有 1_md* 文件夹。
使用方法:    python train_xyz2model_xyzs.py [选项] 帧号 [帧号 ...]
             python train_xyz2model_xyzs.py [选项] -ran <n>
参数:        -o/--outdir DIR   输出根目录 (默认: 当前目录的父目录 ..)
             -h/--help         显示帮助
模式参数:    --extract/-ext   固定抽帧（默认）：提取指定帧号 [帧号 ...]
             --random/-ran   随机抽帧：随机抽取 n 帧（用法：--random <n>）
             (模式互斥，同时指定多个时报错；选项位置随意)
输入文件:    train.xyz (extxyz 格式，从当前运行目录读取)
输出文件:
  model.xyz                  每个抽取帧输出到 <outdir>/1_md<帧号>/model.xyz
  extracted_model_xyz.txt    记录文件 (帧号/原子数/路径/事件/状态，追加模式)
输出路径:    默认当前目录的父目录 (..，保持训练目录整洁)；可用 -o/--outdir 指定
运行前提:    需在 NEP 训练目录 (含 nep.txt、nep.in、train.xyz) 中运行
约定:        帧号为 OVITO 0 起始索引 (0 = 第一帧)；已记录且输出完整的帧
             自动跳过，删除输出后下次自动重建；每次运行结束自动同步
             nep.txt 与 sub_MD.sh 到所有 1_md* 文件夹 (run.in 需自备)
示例:
  python train_xyz2model_xyzs.py 5 9 66        # 固定抽帧 (默认)
  python train_xyz2model_xyzs.py -ext 7        # 固定抽帧 (显式声明)
  python train_xyz2model_xyzs.py -ran 3        # 随机抽帧
  python train_xyz2model_xyzs.py -o /some/dir 2
作者:        Hongbo Sun
最后修改日期: 2026-08-24
=============================================================================
"""

import datetime
import os
import random
import shutil
import sys

# ============================== 参数配置区 =====================================
SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))   # 脚本所在目录 (不带点相对路径基准)
INPUT_PATH       = "."                # 输入文件寻找路径 (相对脚本所在目录；正常运行=当前运行目录)
DEFAULT_INPUT    = "train.xyz"        # 输入文件 (extxyz 格式，固定从 INPUT_PATH 读取)
OUTPUT_FILE      = "model.xyz"        # 输出文件 (每个抽取帧输出到 <outdir>/1_md<帧号>/ 下)
OUTPUT_PATH      = ".."               # 输出根目录 (相对脚本所在目录；默认父目录保持训练目录整洁；-o 命令行优先)
MD_FOLDER_PREFIX = "1_md"             # 输出文件夹前缀 (如 1_md5)
RECORD_FILE      = "extracted_model_xyz.txt"   # 记录文件 (帧号/原子数/路径/事件/状态，追加模式，脚本所在目录)
RECORD_HEADER    = "# " + f"{'帧号':<20}{'原子数':<8}{'路径':<60}{'事件':<16}状态\n"
# =============================================================================
# 提交脚本模板 (sub_MD.sh): 此变量的内容写入每个 MD 文件夹的 sub_MD.sh。
# 按你的超算环境调整: 作业名 / 队列分区 / 资源限制 / 模块加载 / 运行命令。
# 修改后重跑本脚本即可同步到所有 1_md* 文件夹 (内容一致)。
# 注意: 三引号后的空行在写入 sub_MD.sh 时会被自动去掉 (lstrip),
#       保证 #!/bin/bash 仍是文件第一行。
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

# ============================== 环境准备区 =====================================
# 超算 locale 可能非 UTF-8 (如 POSIX/C), 强制 stdout 用 UTF-8,
# 避免打印中文时抛 UnicodeEncodeError (Windows 终端显示乱码不影响功能)。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ASE 依赖检查: 缺少时给出明确的安装提示后退出
try:
    from ase.io import read, write
except ImportError:
    print("❌ 错误: 未找到 ASE (Python 库)。请在超算环境安装: pip install ase")
    sys.exit(1)
# =============================================================================


# ============================== 函数配置区 =====================================

def print_usage():
    print(__doc__)


def resolve_cmd_path(p):
    """命令行路径解析: 绝对路径照旧; ./、../、. 开头相对当前运行目录;
    不带点开头相对脚本所在目录 (规范第八节)。"""
    if os.path.isabs(p):
        return p
    if p.startswith(("./", "../")) or p == ".":
        return os.path.abspath(p)
    return os.path.abspath(os.path.join(SCRIPT_DIR, p))


def parse_args(argv):
    """解析选项: -o/--outdir、-h/--help、-ext/--extract、-ran/--random。
    返回 (outdir, mode, rest)；mode: "extract"/"random"/None (默认固定抽帧)。
    输入文件固定 (DEFAULT_INPUT)，无 -i 选项。"""
    outdir = None
    mode = None
    rest = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-o", "--outdir"):
            if i + 1 >= len(argv):
                print(f"❌ 错误: 选项 {arg} 需要一个目录。")
                sys.exit(1)
            outdir = resolve_cmd_path(argv[i + 1])
            i += 2
        elif arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif arg in ("-ext", "--extract"):
            if mode is not None:
                print("❌ 错误: 模式选项互斥，只能指定一个模式 "
                      "(--extract/-ext 或 --random/-ran)。")
                sys.exit(1)
            mode = "extract"
            i += 1
        elif arg in ("-ran", "--random"):
            if mode is not None:
                print("❌ 错误: 模式选项互斥，只能指定一个模式 "
                      "(--extract/-ext 或 --random/-ran)。")
                sys.exit(1)
            mode = "random"
            i += 1
        else:
            rest.append(arg)
            i += 1
    return outdir, mode, rest


def check_nep_training_dir():
    """检查当前目录是否为 NEP 训练目录: 必须同时存在 nep.txt、
    DEFAULT_INPUT、nep.in 三个文件，否则提示并退出脚本。"""
    required = ("nep.txt", DEFAULT_INPUT, "nep.in")
    missing = [name for name in required
               if not os.path.isfile(os.path.join(INPUT_PATH, name))]
    if missing:
        print("❌ 错误: 当前目录不是有效的 NEP 训练目录。")
        print("   本脚本必须在同时包含以下三个文件的目录中运行:")
        print("   " + "、".join(required))
        print(f"   当前目录: {os.path.abspath(os.getcwd())}")
        print(f"   缺少文件: {'、'.join(missing)}")
        sys.exit(1)
    print("✅ 已确认当前目录为 NEP 训练目录 "
          f"({os.path.abspath(os.getcwd())})，"
          f"检测到 nep.txt、{DEFAULT_INPUT}、nep.in。")


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
    print(f"✅ 已记录 {len(indices)} 个新帧到 "
          f"{os.path.abspath(RECORD_FILE)}。")


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
        print(f"  ℹ️ 提示: {os.path.abspath(out_path)} 已存在，将被覆盖。")
    write(out_path, frames[ovito_index], format="extxyz")
    print(f"  📦 OVITO 帧 {ovito_index} "
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
        print("ℹ️ 提示: 输出根目录下未发现任何 1_md* 文件夹，跳过同步。")
        return
    if os.path.isfile(os.path.join(INPUT_PATH, "nep.txt")):
        for name in folders:
            dest = os.path.join(outdir, name, "nep.txt")
            shutil.copy2(os.path.join(INPUT_PATH, "nep.txt"), dest)
            print(f"  📦 已复制 nep.txt -> {os.path.abspath(dest)}")
    else:
        print("ℹ️ 提示: 运行目录未发现 nep.txt，未复制势文件到 MD 文件夹。")
    for name in folders:
        dest = os.path.join(outdir, name, "sub_MD.sh")
        with open(dest, "w", encoding="utf-8", newline="\n") as f:
            # lstrip: 去掉模板开头的空行, 保证 #!/bin/bash 是第一行
            f.write(SUBMISSION_SCRIPT.lstrip("\n"))
        os.chmod(dest, 0o755)  # 赋予执行权限, 便于直接 ./sub_MD.sh
        print(f"  📦 已生成 sub_MD.sh -> {os.path.abspath(dest)}")


def main():
    outdir, mode, rest = parse_args(sys.argv[1:])

    # 脚本默认在 NEP 训练目录中运行，先确认当前目录合法再继续
    check_nep_training_dir()

    if not rest and mode is None:
        print_usage()
        sys.exit(0)
    if not rest and mode == "extract":
        print("❌ 用法: python train_xyz2model_xyzs.py -ext 帧号 [帧号 ...]")
        sys.exit(1)

    # 旧写法兼容: 位置参数 random 视为随机抽帧模式 (推荐改用 -ran/--random)
    if rest and rest[0] == "random":
        if mode == "extract":
            print("❌ 错误: 模式选项互斥，不能同时使用 --extract/-ext "
                  "与位置参数 random。")
            sys.exit(1)
        if mode is None:
            print("ℹ️ 提示: 位置参数 random 是旧写法，建议改用 "
                  "--random/-ran 选项。")
            mode = "random"
        rest = rest[1:]

    recorded = load_record()
    if recorded:
        print(f"ℹ️ 记录文件 {os.path.abspath(RECORD_FILE)} "
              f"中的已用帧: {sorted(recorded)}")
    # 运行前对比磁盘文件，更新 txt 中每帧的状态列
    n_exist, n_lost = update_record_status()
    if recorded:
        print(f"ℹ️ 已更新记录状态: {n_exist} 帧存在, {n_lost} 帧丢失。")

    # 一次性读取全部帧 (index=":" 返回列表)
    input_path = os.path.join(INPUT_PATH, DEFAULT_INPUT)
    frames = read(input_path, index=":")
    nframes = len(frames)
    print(f"✅ 已从 {os.path.abspath(input_path)} 读取 {nframes} 帧。")

    # 输出根目录: -o 选项 > 配置区 OUTPUT_PATH (相对脚本所在目录)
    if outdir is None:
        outdir = os.path.abspath(os.path.join(SCRIPT_DIR, OUTPUT_PATH))
        print(f"ℹ️ 未指定输出根目录，使用父目录: {outdir}")
    os.makedirs(outdir, exist_ok=True)

    extracted = []  # 本次实际抽取的 OVITO 帧号 (用于结尾总结)
    if mode == "random":
        # 随机模式: --random/-ran <n> (旧写法 random <n> 兼容)
        if len(rest) != 1 or not rest[0].isdigit():
            print("❌ 用法: python train_xyz2model_xyzs.py -ran <n> "
                  "(随机抽取 n 帧)")
            sys.exit(1)
        n_pick = int(rest[0])
        if n_pick < 1:
            print("❌ 错误: 抽取帧数必须 >= 1。")
            sys.exit(1)
        if n_pick > nframes:
            print(f"❌ 错误: 无法抽取 {n_pick} 帧: "
                  f"{os.path.abspath(input_path)} "
                  f"仅包含 {nframes} 帧。")
            sys.exit(1)
        # 排除已记录且输出完整的帧 (文件夹与 model.xyz 均存在)
        available = [i for i in range(nframes)
                     if frame_available(i, recorded, outdir)]
        skipped = [i for i in range(nframes)
                   if not frame_available(i, recorded, outdir)]
        if skipped:
            print(f"ℹ️ 已排除 {len(skipped)} 个抽取过的帧 "
                  f"(有记录且输出完整): {skipped}")
        if len(available) < n_pick:
            print(f"❌ 错误: 仅有 {len(available)} 帧可用 "
                  f"(已排除有记录且输出完整的帧)，无法抽取 {n_pick} 帧。")
            sys.exit(1)
        picked = sorted(random.sample(available, n_pick))
        print(f"✅ 随机抽中 {n_pick} 帧: {picked} (OVITO 帧号)。")
        for idx in picked:
            extract_and_save(frames, idx, outdir)
        append_record(frames, picked, outdir, recorded)
        extracted = picked
    else:
        # 固定抽帧模式 (默认): -ext/--extract 可省略
        ovito_indices = []
        seen = set()
        for token in rest:
            if not token.isdigit():
                print(f"❌ 错误: '{token}' 不是有效的帧号。"
                      "用法: python train_xyz2model_xyzs.py [帧号 ...] "
                      "或 python train_xyz2model_xyzs.py -ran <n>")
                sys.exit(1)
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
                folder = os.path.join(outdir, f"{MD_FOLDER_PREFIX}{idx}")
                model_path = os.path.join(folder, OUTPUT_FILE)
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

        if not to_extract:
            print("ℹ️ 无需抽取 (所有请求的帧都已抽取过)。")
        else:
            print("📦 开始抽取以下帧:")
            for idx in to_extract:
                extract_and_save(frames, idx, outdir)
            append_record(frames, to_extract, outdir, recorded)
            extracted = to_extract

    # 同步势文件与提交脚本到所有 1_md* 文件夹 (含本次新抽取的)
    sync_md_folder_files(outdir)

    # 运行结束集中总结关键信息 (规范: 处理数量/输出文件/记录文件)
    summary = (f"🎉 全部完成！本次抽取 {len(extracted)} 帧"
               + (f" (OVITO 帧号: {extracted})" if extracted else "") + "。")
    print(f"\n{summary}")
    print(f"   输出根目录: {outdir}")
    print(f"   记录文件: {os.path.abspath(RECORD_FILE)}")


# ============================== 脚本运行区 =====================================

if __name__ == "__main__":
    main()
