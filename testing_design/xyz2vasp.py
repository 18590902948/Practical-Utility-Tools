#!/usr/bin/env python3
"""
=============================================================================
脚本:        xyz2vasp.py
分类:        格式转换脚本
功能:        将 xyz / extxyz 轨迹文件逐帧转换为 VASP POSCAR 文件 (每帧
             输出一个 POSCAR_<OVITO帧号>.vasp，帧号遵循 OVITO 0 起始
             约定)；写入前按元素对原子排序，保证 POSCAR 元素分组连续，
             便于直接配套 POTCAR 使用。
使用方法:    python xyz2vasp.py [输入文件 ...] [-o 输出目录] [-h]
参数:        输入文件    xyz / extxyz 格式输入文件，支持通配符与跨目录
                        路径，可多个 (位置参数前可加 -t/--target 标记，
                        仅为声明、可省略)；不指定时自动扫描脚本所在目录
                        (INPUT_PATH) 下全部 *.xyz / *.extxyz 文件
             -o/--output 输出目录 (也可写作 --outdir)：全部 POSCAR 与
                        记录文件输出到该目录；默认脚本所在目录
                        (OUTPUT_PATH)。每帧一个文件、无法合并，故 -o
                        仅支持目录形式
             -h/--help   显示本帮助
帧号约定:    输出文件按 OVITO 帧号命名 (0 = 第 1 帧)：文本第 n+1 帧
             输出为 POSCAR_<n>.vasp；头部注释与运行提示均写明该约定
输入文件:    *.xyz / *.extxyz  (xyz 或 extxyz 格式，多帧)
输出文件:    xyz2vasp.txt  (记录文件，表格形式，表头 #+多列，覆盖模式，
                        与输出文件同目录)
             <输出目录>/POSCAR_0.vasp、POSCAR_1.vasp ... (每帧一个)
             单个输入文件时各帧直接输出到输出目录；多个输入文件时各
             输入文件的帧输出到其同名子目录 (去扩展名，同名输入自动加
             _2/_3 后缀)，避免不同输入文件的帧文件相互覆盖
输出路径:    默认脚本所在目录 (OUTPUT_PATH)，可用 -o 指定；相对路径遵循
             "带 ./ 相对当前运行目录、不带点相对脚本目录" 规则
示例:
  python xyz2vasp.py ./train.xyz -o ./poscar/
  python xyz2vasp.py './*.xyz' './x/a.extxyz' -o ./out/
  python xyz2vasp.py                     (扫描脚本目录全部 xyz 文件)
# 目录树示例:
# ============================================================================
# .                        # 脚本所在目录 (含 xyz 轨迹文件)
# ├── train.xyz            # 输入: xyz/extxyz 轨迹 (3 帧)
# ├── POSCAR_0.vasp        # 输出: 第 1 帧 (OVITO 帧 0)
# ├── POSCAR_1.vasp        # 输出: 第 2 帧 (OVITO 帧 1)
# ├── POSCAR_2.vasp        # 输出: 第 3 帧 (OVITO 帧 2)
# └── xyz2vasp.txt         # 输出: 转换记录文件
# ============================================================================
作者:        隼蝶.
最后修改日期: 2026-09-07
=============================================================================
"""

import datetime
import glob
import os
import sys

# ============================== 参数配置区 =====================================
INPUT_PATTERNS = ["*.xyz", "*.extxyz"]  # 默认输入匹配模式 (通配符，相对 INPUT_PATH 展开；命令行参数优先)
# 输出文件为每帧一个 POSCAR_<OVITO帧号>.vasp (命名规则见头部注释)，无固定
# 输出文件名列表，故不设 OUTPUT_FILES 字段
RECORD_FILE  = "xyz2vasp.txt"           # 转换记录文件 (与输出文件同目录)
INPUT_PATH   = "./"                     # 输入文件寻找路径 (相对脚本所在目录)
OUTPUT_PATH  = "./"                     # 输出文件寻找路径 (相对脚本所在目录)
RECORD_PATH_COL = 60                    # 记录文件路径列最小宽度 (保证列间分隔)
RECORD_HEADER   = ("# " + f"{'输入文件':<{RECORD_PATH_COL}}{'总帧数':<8}{'原子数':<8}"
                  f"{'写出帧':<8}{'跳过帧':<8}状态\n")  # 记录文件表头
# =============================================================================

# ============================== 环境准备区 =====================================
# 终端 locale 可能非 UTF-8 (如 POSIX/C)，强制 stdout/stderr 用 UTF-8，
# 避免打印中文/emoji 时抛 UnicodeEncodeError (Windows 终端显示乱码不影响功能)。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

try:
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
    """解析命令行参数 (选项位置随意): 位置参数为输入文件 (可多个，支持
    通配符)，-h/--help、-o/--output/--outdir、-t/--target (仅声明标记)。
    返回 (输入文件列表, 输出目录或 None)。"""
    input_files = []
    output = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif arg in ("-o", "--output", "--outdir"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -o/--output 需要一个目录路径。")
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


def resolve_outdir(script_dir, output):
    """解析输出目录: -o/--output 指定的目录 (每帧一个文件、不可合并，
    仅目录形式)；省略 -o 时用配置区 OUTPUT_PATH。返回绝对路径。"""
    if output:
        return resolve_cmd_path(script_dir, output)
    return os.path.normpath(os.path.join(script_dir, OUTPUT_PATH))


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
    """扫描 INPUT_PATH 下匹配 INPUT_PATTERNS 的全部文件 (排除记录文件等
    非 xyz 输出)。返回绝对路径列表。"""
    base = os.path.normpath(os.path.join(script_dir, INPUT_PATH))
    files = []
    for pattern in INPUT_PATTERNS:
        files.extend(os.path.abspath(m) for m in sorted(glob.glob(os.path.join(base, pattern))))
    return sorted(set(files))


def has_cell(frame):
    """判断帧是否带有效晶格 (VASP 必需): ASE 中未设置晶格的 Atoms 其
    cell 为全零。返回 True/False。"""
    cell = frame.get_cell()
    return cell is not None and abs(cell.volume) > 1e-12


def write_frame(frame, frame_idx, outdir):
    """将单帧原子排序后写入 <outdir>/POSCAR_<OVITO帧号>.vasp (覆盖模式)。
    返回 True/False (False = 跳过，记录文件与终端用于统计)。"""
    if not has_cell(frame):
        return False
    atoms = frame.copy()
    # 按原子序分组排序 (ASE 3.28 已移除 Atoms.sort，改用索引重排)，保证
    # POSCAR 元素行连续、便于配 POTCAR
    atoms = atoms[sorted(range(len(atoms)), key=lambda i: atoms[i].number)]
    write(os.path.join(outdir, f"POSCAR_{frame_idx}.vasp"), atoms, format="vasp")
    return True


def process_file(src_path, outdir):
    """流式读取单个轨迹文件并逐帧写 POSCAR (iread 惰性迭代，内存占用
    恒定)。返回记录元组 (输入文件, 总帧数, 原子数, 写出帧, 跳过帧, 状态)，
    中途异常时保留已写帧并标记状态。"""
    natom, n_total, n_ok, n_skip = "-", 0, 0, 0
    status = "读取异常"
    try:
        for frame_idx, frame in enumerate(iread(src_path, index=":")):
            if frame_idx == 0:
                natom = len(frame)
            if write_frame(frame, frame_idx, outdir):
                n_ok += 1
            else:
                n_skip += 1
            n_total = frame_idx + 1
        status = "成功"
    except Exception as e:
        print(f"  ❌ 读取中断: {os.path.basename(src_path)} 第 {n_total + 1} 帧起 ({e})")
        status = f"部分转换" if n_ok else "读取异常"
    return (src_path, n_total, natom, n_ok, n_skip, status)


def write_record(record_path, records, outdir, detail_lines):
    """覆盖写记录文件: 表头 (# 开头) + 时间戳 + 每行一条记录
    (输入文件/总帧数/原子数/写出帧/跳过帧/状态，空格分隔)，末尾汇总
    输出目录与帧号约定说明。"""
    with open(record_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(RECORD_HEADER)
        f.write(f"# {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        for path, nframes, natom, n_ok, n_skip, status in records:
            path_col = max(RECORD_PATH_COL, len(path) + 1)
            f.write(f"{path:<{path_col}}{str(nframes):<8}{str(natom):<8}"
                    f"{str(n_ok):<8}{str(n_skip):<8}{status}\n")
        f.write("# 输出目录: " + os.path.abspath(outdir) + "\n")
        f.write("# " + detail_lines + "\n")


def print_summary(n_input, n_ok_file, n_total_f, n_ok_f, n_skip_f, outdir, record_path):
    """运行完毕后集中总结关键信息 (数量统计、输出与记录文件绝对路径)。"""
    print("=" * 52)
    print("🎉 运行完成，总结:")
    print(f"  输入:        {n_input} 个 xyz/extxyz 文件 ({n_ok_file} 成功)")
    print(f"  帧:          共 {n_total_f} 帧，写出 {n_ok_f} 个 POSCAR，"
          f"跳过 {n_skip_f} 帧 (无晶格)")
    print(f"  输出目录:    {os.path.abspath(outdir)}")
    print(f"  记录文件:    {os.path.abspath(record_path)}")
    print(f"  帧号说明:    OVITO 帧 0 = 第 1 帧 -> POSCAR_0.vasp (文本第 n+1 帧 = POSCAR_n.vasp)")
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
        for f in files:
            if not f.lower().endswith((".xyz", ".extxyz")):
                print(f"⚠️ 警告: '{f}' 不是 xyz/extxyz 文件，已忽略。")
        files = [f for f in files if f.lower().endswith((".xyz", ".extxyz"))]
    else:
        print(f"ℹ️ 未指定输入文件，自动扫描脚本所在目录 (INPUT_PATH) 下 "
              f"{'/'.join(INPUT_PATTERNS)} 文件 ...")
        files = scan_inputs(script_dir)

    if not files:
        print(f"❌ 错误: 未找到任何 xyz/extxyz 格式输入文件 "
              f"({'/'.join(INPUT_PATTERNS)})。")
        print("用法: python xyz2vasp.py [输入文件 ...] -o 输出目录")
        sys.exit(1)

    # 执行前展示来源清单
    print(f"📦 {len(files)} 个输入文件:")
    for f in files:
        print(f"    - {f}")

    # ---- 解析输出路径 ----
    outdir = resolve_outdir(script_dir, output)
    os.makedirs(outdir, exist_ok=True)
    record_path = os.path.join(outdir, RECORD_FILE)

    # ---- 多输入时分配同名子目录 (避免不同文件的 POSCAR 帧文件相互覆盖) ----
    multi = len(files) > 1
    seen_names = {}
    target_dirs = {}
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        if not multi:
            target_dirs[f] = outdir
        else:
            k = seen_names.get(name, 0)
            seen_names[name] = k + 1
            sub = name if k == 0 else f"{name}_{k + 1}"
            target_dirs[f] = os.path.join(outdir, sub)

    # ---- 逐文件流式转换 (覆盖模式) ----
    all_records, out_subdirs = [], []
    for f in files:
        d = target_dirs[f]
        if d != outdir:
            os.makedirs(d, exist_ok=True)
        path, n_total, natom, n_ok, n_skip, status = process_file(f, d)
        all_records.append((path, n_total, natom, n_ok, n_skip, status))
        out_subdirs.append(os.path.relpath(d, outdir))
        print(f"✅ 已转换 {n_ok} 帧 (跳过 {n_skip} 帧) -> {os.path.abspath(d)}"
              f"{'' if status == '成功' else ' [' + status + ']'}")

    # ---- 写记录文件并总结 ----
    detail = (f"帧号约定: 文本第 n+1 帧 -> POSCAR_n.vasp (OVITO 帧号 0 起始)；"
              f"无晶格帧跳过不输出")
    if multi:
        detail += "；各输入文件输出到同名子目录"
    write_record(record_path, all_records, outdir, detail)
    n_ok_file = sum(1 for r in all_records if r[5] == "成功")
    print_summary(len(all_records), n_ok_file,
                  sum(r[1] for r in all_records),
                  sum(r[3] for r in all_records),
                  sum(r[4] for r in all_records), outdir, record_path)


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
