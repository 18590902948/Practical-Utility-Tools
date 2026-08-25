#!/usr/bin/env python3
"""
=============================================================================
脚本:        vasp2xyz.py
分类:        格式转换脚本
功能:        将 VASP 格式文件 (*.vasp / POSCAR* / CONTCAR*) 转换为标准 xyz
             格式 (第二行为 Lattice/Properties/pbc 属性行，与
             classic_data/xyz_format 标准格式一致，晶格信息完整保留)；
             -o 指定目录时按文件类型分类输出 vasp.xyz / pos.xyz /
             cont.xyz，-o 指定文件时全部合并为一个文件；记录文件审计
             每次转换。
使用方法:    python vasp2xyz.py [输入文件 ...] [-o 输出] [-h]
参数:        输入文件    VASP 格式输入文件 (*.vasp / POSCAR* / CONTCAR*)，
                        支持通配符与跨目录路径，可多个；不指定时自动扫描
                        脚本所在目录下全部 VASP 文件
                        (位置参数前可加 -t/--target 标记，仅为声明、可省略)
             -o/--output 输出文件或输出目录：以 .xyz/.extxyz 结尾视为输出
                        文件完整路径 (全部输入合并为一个文件)；否则视为
                        输出目录 (按文件类型分类输出 vasp.xyz / pos.xyz /
                        cont.xyz)；默认输出到脚本所在目录 (OUTPUT_PATH)
             -h/--help   显示本帮助
输入文件:    *.vasp / POSCAR* / CONTCAR* (VASP 格式)
输出文件:    vasp2xyz.txt  (记录文件，表格形式，表头#+多列，覆盖模式，
                        与输出文件同目录)
             <输出目录>/vasp.xyz    由 *.vasp 文件转换合并
             <输出目录>/pos.xyz     由 POSCAR* 文件转换合并
             <输出目录>/cont.xyz    由 CONTCAR* 文件转换合并
             (或 -o 指定的单个合并文件)
输出路径:    默认脚本所在目录 (OUTPUT_PATH)，可用 -o 指定；相对路径遵循
             "带 ./ 相对当前运行目录、不带点相对脚本目录" 规则
示例:
  python vasp2xyz.py ./A.vasp ./B.vasp ./POSCAR ./CONTCAR -o ./out/
  python vasp2xyz.py './POSCAR*' './CONTCAR*' -o ./pos.xyz
  python vasp2xyz.py ./A.vasp ./B.vasp -o ./D.xyz
  python vasp2xyz.py                     (扫描脚本目录全部 VASP 文件)
# 目录树示例:
# ============================================================================
# .                        # 脚本所在目录 (含 VASP 格式文件)
# ├── 1.vasp               # 输入: VASP 文件
# ├── 2.vasp               # 输入: VASP 文件
# ├── POSCAR               # 输入: POSCAR 文件
# ├── CONTCAR              # 输入: CONTCAR 文件
# ├── vasp.xyz             # 输出: 由 *.vasp 转换合并
# ├── pos.xyz              # 输出: 由 POSCAR* 转换合并
# ├── cont.xyz             # 输出: 由 CONTCAR* 转换合并
# └── vasp2xyz.txt         # 输出: 转换记录文件
# ============================================================================
作者:        Hongbo Sun
最后修改日期: 2026-08-24
=============================================================================
"""

import datetime
import glob
import os
import sys

# ============================== 参数配置区 =====================================
INPUT_FILES  = []                  # 输入文件列表 (空列表=扫描 INPUT_PATH 下全部 VASP 文件；支持通配符，相对 INPUT_PATH 展开；命令行参数优先)
OUTPUT_FILES = ["vasp.xyz", "pos.xyz", "cont.xyz"]  # 分类输出文件名 (对应 vasp/poscar/contcar 三组)
RECORD_FILE  = "vasp2xyz.txt"      # 转换记录文件 (与输出文件同目录)
INPUT_PATH   = "./"                # 输入文件寻找路径 (相对脚本所在目录)
OUTPUT_PATH  = "./"                # 输出文件寻找路径 (相对脚本所在目录)
RECORD_PATH_COL = 60               # 记录文件路径列最小宽度 (保证列间分隔)
RECORD_HEADER   = ("# " + f"{'输入文件':<{RECORD_PATH_COL}}{'帧数':<6}{'原子数':<8}"
                  f"{'事件':<8}状态\n")  # 记录文件表头
# =============================================================================

# ============================== 环境准备区 =====================================
# 终端 locale 可能非 UTF-8 (如 POSIX/C)，强制 stdout/stderr 用 UTF-8，
# 避免打印中文/emoji 时抛 UnicodeEncodeError (Windows 终端显示乱码不影响功能)。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

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
    """解析命令行参数 (选项位置随意): 位置参数为输入文件 (可多个，支持
    通配符)，-h/--help、-o/--output、-t/--target (仅声明标记)。
    返回 (输入文件列表, 输出路径或 None)。"""
    input_files = []
    output = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif arg in ("-o", "--output"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -o/--output 需要一个路径。")
                sys.exit(1)
            output = argv[i + 1]
            i += 2
        elif arg in ("-t", "--target"):
            i += 1  # 仅声明标记，位置参数一律视为输入文件
        elif arg.startswith("-"):
            print(f"❌ 错误: 无法识别的选项 '{arg}'。")
            print_usage()
            sys.exit(1)
        else:
            input_files.append(arg)
            i += 1
    return input_files, output


def resolve_cmd_path(script_dir, p):
    """解析命令行路径: 绝对路径照旧；./ 或 ../ 开头相对当前运行目录；
    不带点开头的相对路径相对脚本所在目录。返回绝对路径。"""
    if os.path.isabs(p):
        return os.path.abspath(p)
    if p.startswith(("./", "../")) or p in (".", ".."):
        return os.path.abspath(os.path.join(os.getcwd(), p))
    return os.path.normpath(os.path.join(script_dir, p))


def resolve_output(script_dir, output):
    """解析输出: -o 以 .xyz/.extxyz 结尾视为输出文件完整路径 (全部输入
    合并为一个文件)，否则视为输出目录 (按类型分类输出)；省略 -o 时用
    配置区 OUTPUT_PATH。返回 (输出目录绝对路径, 合并输出文件路径或 None)。"""
    if output:
        path = resolve_cmd_path(script_dir, output)
        if output.lower().endswith((".xyz", ".extxyz")):
            return os.path.dirname(path), path
        return path, None
    outdir = os.path.normpath(os.path.join(script_dir, OUTPUT_PATH))
    return outdir, None


def classify_vasp_file(name):
    """按文件名将 VASP 文件归类: *.vasp -> vasp, POSCAR* -> poscar,
    CONTCAR* -> contcar；非 VASP 文件 (含 xyz 输出文件) 返回 None。"""
    lower = name.lower()
    if lower.endswith((".xyz", ".extxyz")):
        return None  # 排除 xyz 输出文件，避免把上次输出当输入
    if lower.endswith(".vasp"):
        return "vasp"
    if lower.startswith("poscar"):
        return "poscar"
    if lower.startswith("contcar"):
        return "contcar"
    return None


def expand_input(patterns, script_dir):
    """将命令行输入文件列表展开为绝对路径: 含通配符 (* ? [) 的先相对当前
    运行目录 glob，无匹配再相对脚本目录展开；无通配符的先探测当前运行目录，
    不存在再相对脚本目录。返回 (路径列表, 未找到的原始模式列表)。"""
    files, missing = [], []
    for p in patterns:
        if any(ch in p for ch in "*?["):
            matches = sorted(glob.glob(p))
            if not matches:
                matches = sorted(glob.glob(os.path.join(script_dir, p)))
            if matches:
                files.extend(os.path.abspath(m) for m in matches)
            else:
                missing.append(p)
        else:
            if os.path.isfile(p):
                files.append(os.path.abspath(p))
            else:
                cand = os.path.join(script_dir, p)
                if os.path.isfile(cand):
                    files.append(os.path.abspath(cand))
                else:
                    missing.append(p)
    return files, missing


def scan_inputs(script_dir):
    """扫描 INPUT_PATH 下全部文件，按 VASP 类型归类。返回 {组名: [绝对路径]}。"""
    base = os.path.normpath(os.path.join(script_dir, INPUT_PATH))
    groups = {}
    for name in sorted(os.listdir(base)):
        full = os.path.join(base, name)
        if not os.path.isfile(full):
            continue
        group = classify_vasp_file(name)
        if group:
            groups.setdefault(group, []).append(os.path.abspath(full))
    return groups


def classify_inputs(files):
    """将命令行输入文件列表按 VASP 类型归类。返回 ({组名: [绝对路径]},
    非 VASP 文件列表)。"""
    groups, skipped = {}, []
    for f in files:
        group = classify_vasp_file(os.path.basename(f))
        if group:
            groups.setdefault(group, []).append(f)
        else:
            skipped.append(f)
    return groups, skipped


def read_group(filenames):
    """读取一组 VASP 文件的所有帧。返回 (帧列表, 逐文件记录列表)，
    记录项为 (输入文件, 帧数, 原子数, 事件, 状态)，读取失败的文件
    记录为 (跳过, 读取异常)。"""
    frames, records = [], []
    for f in filenames:
        try:
            fr = read(f, format="vasp", index=":")
            if not isinstance(fr, list):
                fr = [fr]
            natom = len(fr[0]) if fr else "-"
            frames.extend(fr)
            records.append((f, len(fr), natom, "转换", "成功"))
        except Exception as e:
            print(f"  ❌ 读取失败: {os.path.basename(f)} ({e})")
            records.append((f, "-", "-", "跳过", "读取异常"))
    return frames, records


def buffer_write(frames, out_path, chunk=50):
    """将帧列表分批写入输出文件 (覆盖模式): 攒够 chunk 帧批量落盘一次
    (首次覆盖、后续追加)，写完清空缓冲区，避免海量帧内存爆炸。
    返回实际写入帧数。"""
    if not frames:
        return 0
    for start in range(0, len(frames), chunk):
        batch = frames[start:start + chunk]
        write(out_path, batch, format="extxyz", append=start > 0)
    return len(frames)


def write_record(record_path, records, out_files):
    """覆盖写记录文件: 表头 (# 开头) + 时间戳 + 每行一条记录
    (输入文件/帧数/原子数/事件/状态，空格分隔)，末尾汇总输出文件清单。"""
    with open(record_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(RECORD_HEADER)
        f.write(f"# {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        for path, nframes, natom, event, status in records:
            path_col = max(RECORD_PATH_COL, len(path) + 1)
            f.write(f"{path:<{path_col}}{str(nframes):<6}{str(natom):<8}"
                    f"{event:<8}{status}\n")
        if out_files:
            f.write("# 输出文件: " + ", ".join(out_files) + "\n")


def print_summary(n_input, n_ok, outdir, out_files, record_path):
    """运行完毕后集中总结关键信息 (数量统计、输出与记录文件绝对路径)。"""
    print("=" * 52)
    print("🎉 运行完成，总结:")
    print(f"  输入:        {n_input} 个 VASP 文件 ({n_ok} 成功, "
          f"{n_input - n_ok} 失败/跳过)")
    print(f"  输出目录:    {os.path.abspath(outdir)}")
    for of in out_files:
        print(f"  输出文件:    {of}")
    print(f"  记录文件:    {os.path.abspath(record_path)}")
    print("=" * 52)


# ============================== 脚本工作区 =====================================
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_files, output = parse_args(sys.argv[1:])

    # ---- 收集输入文件并分类 ----
    if input_files:
        files, missing = expand_input(input_files, script_dir)
        for m in missing:
            print(f"⚠️ 警告: 输入 '{m}' 未找到，已忽略。")
        groups, skipped = classify_inputs(files)
        for s in skipped:
            print(f"⚠️ 警告: '{s}' 不是 VASP 文件 "
                  f"(*.vasp / POSCAR* / CONTCAR*)，已忽略。")
    else:
        print("ℹ️ 未指定输入文件，自动扫描脚本所在目录下全部 VASP 文件 ...")
        groups = scan_inputs(script_dir)

    n_total = sum(len(v) for v in groups.values())
    if n_total == 0:
        print("❌ 错误: 未找到任何 VASP 格式输入文件 "
              "(*.vasp / POSCAR* / CONTCAR*)。")
        print("用法: python vasp2xyz.py [输入文件 ...] -o 输出")
        sys.exit(1)

    # 执行前展示来源清单 (按 vasp/poscar/contcar 分组)
    for gname in ("vasp", "poscar", "contcar"):
        if gname in groups:
            print(f"📦 [{gname}] {len(groups[gname])} 个文件:")
            for f in groups[gname]:
                print(f"    - {f}")

    # ---- 解析输出路径 ----
    outdir, out_file = resolve_output(script_dir, output)
    os.makedirs(outdir, exist_ok=True)
    record_path = os.path.join(outdir, RECORD_FILE)

    # ---- 执行转换 (覆盖模式) ----
    all_records, out_files = [], []
    if out_file:
        # 合并模式: -o 指定文件，全部组按 vasp -> poscar -> contcar 顺序合并
        frames_all = []
        for gname in ("vasp", "poscar", "contcar"):
            if gname not in groups:
                continue
            frames_g, records = read_group(groups[gname])
            all_records.extend(records)
            frames_all.extend(frames_g)
        n = buffer_write(frames_all, out_file)
        if n:
            print(f"✅ 已写入 {n} 帧 -> {os.path.abspath(out_file)}")
            out_files.append(os.path.abspath(out_file))
    else:
        # 分类模式: -o 为目录或省略，每组输出一个文件
        for gname, outname in zip(("vasp", "poscar", "contcar"), OUTPUT_FILES):
            if gname not in groups:
                continue
            frames_g, records = read_group(groups[gname])
            all_records.extend(records)
            out_path = os.path.join(outdir, outname)
            n = buffer_write(frames_g, out_path)
            if n:
                print(f"✅ [{gname}] 已写入 {n} 帧 -> {os.path.abspath(out_path)}")
                out_files.append(os.path.abspath(out_path))

    # ---- 写记录文件并总结 ----
    write_record(record_path, all_records, out_files)
    n_ok = sum(1 for r in all_records if r[4] == "成功")
    print_summary(n_total, n_ok, outdir, out_files, record_path)


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
