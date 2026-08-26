#!/usr/bin/env python3
"""
=============================================================================
脚本:        clean_xyz.py
分类:        结构处理工具
功能:        清除 xyz/extxyz 文件中的应力 (stress)、维里 (virial)、力
             (forces) 信息，只保留结构信息 (晶格、坐标及 energy 等其余键)
使用方法:    python clean_xyz.py [输入文件 ...] [-o 输出路径] [-h/--help]
参数:        输入文件 ...   待清洗的 xyz/extxyz 文件 (可多个，支持通配符；
                         命令行参数先按当前运行目录解析，不存在再相对
                         脚本所在目录)
             -o/--output   输出路径 (两种形式: 以 .xyz/.extxyz 结尾视为
                         输出文件完整路径，仅单输入时可用；否则视为输出
                         目录。不带点开头的相对路径默认相对脚本所在目录
                         解析，./ 或 ../ 开头相对当前运行目录；不指定时
                         输出到配置区 OUTPUT_PATH)
             -h/--help     显示本帮助
输入文件:    配置区 INPUT_FILES (默认 *.xyz/*.extxyz，相对 INPUT_PATH)
输出文件:    每个输入文件输出为 <原名去扩展名> + SUFFIX + <原扩展名>
             (默认 *_clean.xyz)，输出格式固定为 extxyz (保留晶格信息)
输出路径:    默认脚本所在目录下 clean_xyz/ (OUTPUT_PATH)，可用 -o 指定
             (输出文件或输出目录，相对/绝对路径均可)
示例:
  python clean_xyz.py ./train.xyz
  python clean_xyz.py ./A/a.xyz ./B/b.xyz -o ./C/
  python clean_xyz.py ./A/a.xyz -o ./D/e.xyz
  (不指定输入文件时用配置区 INPUT_FILES，清洗脚本所在目录下所有文件)
作者:        隼蝶. (fork 自 Zihan YAN 的 GPUMDkit clean_xyz.py)
最后修改:    2026-08-24
=============================================================================
"""

import glob
import os
import sys

# ============================== 参数配置区 =====================================
INPUT_FILES    = ["*.xyz", "*.extxyz"]  # 输入文件列表 (支持通配符，相对 INPUT_PATH 展开；命令行参数优先)
INPUT_ENCODING = "utf-8"                # 输入文件编码 (Windows 默认 GBK 会误读 UTF-8 文件，故显式指定)
SUFFIX         = "_clean"               # 输出文件名后缀: 原名去扩展名 + SUFFIX + 原扩展名
INPUT_PATH     = "./"                   # 输入文件寻找路径 (相对脚本所在目录)
OUTPUT_PATH    = "./clean_xyz/"         # 输出文件寻找路径 (相对脚本所在目录)
# =============================================================================

# ============================== 环境准备区 =====================================
# 终端 locale 可能非 UTF-8 (如 POSIX/C), 强制 stdout 用 UTF-8,
# 避免打印中文时抛 UnicodeEncodeError (Windows 终端显示乱码不影响功能)。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from ase.io import read, write
    from ase.io.extxyz import XYZError
except ImportError:
    print("❌ 错误: 未找到 ASE (Python 库)。请安装: pip install ase")
    sys.exit(1)
# ===========================================================================


# ============================== 函数配置区 =====================================
def print_usage():
    """打印头部注释块 (脚本功能与完整使用方法)。"""
    print(__doc__)


def parse_args(argv):
    """解析命令行参数 (选项位置随意): 输入文件为位置参数 (可多个);
    -h/--help、-o/--output 为选项。返回 (输入文件列表, 输出路径)。"""
    inputs = []
    out_path = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif arg in ("-o", "--output", "--outdir"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -o/--output 需要一个输出路径。")
                sys.exit(1)
            out_path = argv[i + 1]
            i += 2
        else:
            inputs.append(arg)
            i += 1
    return inputs, out_path


def resolve_cmd_path(p, script_dir):
    """命令行路径解析: 绝对路径照旧；以 ./ ../ 或 . 开头的相对路径相对
    当前运行目录解析；不带点开头的相对路径默认相对脚本所在目录解析。"""
    if os.path.isabs(p):
        return p
    if p in (".", "..") or p.startswith(("./", "../")):
        return os.path.abspath(p)
    return os.path.normpath(os.path.join(script_dir, p))


def expand_cmd_inputs(args, script_dir):
    """展开命令行输入文件: 含通配符的 glob 展开 (先相对当前运行目录，未匹配
    且不带点开头再相对脚本目录兜底)；无通配符的字面路径先按当前运行目录
    探测，不存在再相对脚本目录解析。返回存在的文件完整路径列表。"""
    inputs = []
    for a in args:
        if any(ch in a for ch in "*?["):
            matches = sorted(glob.glob(a))
            if not matches and not a.startswith(("./", "../")):
                matches = sorted(glob.glob(os.path.join(script_dir, a)))
            if not matches:
                print(f"⚠️ 警告: 模式 '{a}' 未匹配任何文件，已跳过。")
            else:
                inputs.extend(os.path.normpath(m) for m in matches)
            continue
        p = a if os.path.isfile(a) else os.path.join(script_dir, a)
        if not os.path.isfile(p):
            print(f"❌ 错误: 输入文件不存在: {a}")
            sys.exit(1)
        inputs.append(os.path.normpath(p))
    return inputs


def expand_default_inputs(input_base):
    """按配置区 INPUT_FILES 展开默认输入文件 (相对 input_base，支持通配符)。"""
    files = []
    for p in INPUT_FILES:
        if any(ch in p for ch in "*?["):
            files.extend(sorted(glob.glob(os.path.join(input_base, p))))
        else:
            files.append(os.path.join(input_base, p))
    return [os.path.normpath(f) for f in files]


def clean_frame(atoms):
    """清除单帧中的应力/维里/力信息: info 中键名含 stress/virial 的条目、
    calc.results 中键名含 stress/forces 的条目、arrays 中的 forces；
    calc 中其余结果 (如 energy) 移入 info 保留，calc 置 None。
    返回 (清除键总数, 是否清除 forces)。"""
    n_info = 0
    for key in list(atoms.info.keys()):  # list() 避免遍历时修改字典报错
        if "stress" in key.lower() or "virial" in key.lower():
            del atoms.info[key]
            n_info += 1
    has_forces = False
    if "forces" in atoms.arrays:
        del atoms.arrays["forces"]
        has_forces = True
    if hasattr(atoms, "calc") and atoms.calc is not None:
        if hasattr(atoms.calc, "results"):
            for key, val in list(atoms.calc.results.items()):
                if "stress" in key.lower():
                    # ASE 读 extxyz 时 stress 在 calc.results 中
                    del atoms.calc.results[key]
                    n_info += 1
                elif "forces" in key.lower():
                    # ASE 读 extxyz 时 forces 也在 calc.results 中
                    del atoms.calc.results[key]
                    has_forces = True
                else:
                    # 其余结果 (如 energy) 移入 info 保留，避免 calc 置 None 后丢失
                    atoms.info.setdefault(key, val)
        atoms.calc = None
    return n_info, has_forces


def process_file(in_file, out_file):
    """读取输入文件全部帧 (按配置区 INPUT_ENCODING 打开，Windows 默认
    GBK 会误读 UTF-8 文件)，逐帧清除应力/维里/力信息后写入输出 (extxyz
    格式保留晶格，覆盖模式)。返回 (帧数, 清除键总数, 含 forces 帧数)。"""
    try:
        fin = open(in_file, encoding=INPUT_ENCODING)
    except OSError as e:
        print(f"❌ 错误: 无法打开输入文件: {in_file} ({e})")
        sys.exit(1)
    with fin:
        try:
            frames = read(fin, format="extxyz", index=":")
        except UnicodeDecodeError as e:
            print(f"❌ 错误: 输入文件解码失败 (编码 {INPUT_ENCODING}): {e}")
            print("  提示: 若文件为其他编码，请修改配置区 INPUT_ENCODING 后重试。")
            sys.exit(1)
        except XYZError as e:
            print(f"❌ 错误: 输入文件包含非 xyz 内容 (编码 {INPUT_ENCODING} 解码通过): {e}")
            print("  提示: 文件可能混入了记录文本等其他杂质 (如合并时误把 txt 拼入)，请检查文件后重试。")
            sys.exit(1)
    n_info = 0
    n_force = 0
    for atoms in frames:
        ni, has_forces = clean_frame(atoms)
        n_info += ni
        n_force += int(has_forces)
    with open(out_file, "w", encoding="utf-8") as fout:
        write(fout, frames, format="extxyz")
    return len(frames), n_info, n_force


def print_summary(results):
    """总结关键信息: 处理数量统计与输出文件绝对路径。"""
    total_frames = sum(r[1] for r in results)
    print("\n🎉 清洗完成:")
    print(f"  处理文件:  {len(results)} 个")
    print(f"  总帧数:    {total_frames}")
    print("  输出文件:  (覆盖模式)")
    for name, n, ni, nf, path in results:
        print(f"    - {path}  ({name}: {n} 帧"
              + (f", 清除 info 键 {ni} 个" if ni else ", 无 stress/virial 键")
              + (f", 清除 forces {nf} 帧" if nf else "") + ")")
# ===========================================================================


# ============================== 脚本工作区 =====================================
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    args, out_path = parse_args(sys.argv[1:])

    # 输入文件: 命令行参数先按当前运行目录探测，不存在再相对脚本目录；
    # 无参数时用配置区 INPUT_FILES (相对 INPUT_PATH 展开)
    if args:
        inputs = expand_cmd_inputs(args, script_dir)
    else:
        inputs = expand_default_inputs(os.path.join(script_dir, INPUT_PATH))
    if not inputs:
        print("❌ 错误: 未找到任何输入文件。请指定输入文件，或用 -h/--help 查看帮助。")
        sys.exit(1)
    for p in inputs:
        print(f"ℹ️ 输入文件: {os.path.abspath(p)}")

    # 输出路径: -o 命令行优先，否则默认输出目录 OUTPUT_PATH (相对脚本目录)
    out_file = None
    if out_path:
        out_base = resolve_cmd_path(out_path, script_dir)
        if os.path.splitext(out_base)[1].lower() in (".xyz", ".extxyz"):
            # -o 为输出文件完整路径: 仅单输入时可用
            if len(inputs) > 1:
                print("❌ 错误: 指定了多个输入文件时，-o 只能指定输出目录。")
                sys.exit(1)
            out_file = out_base
            output_dir = os.path.dirname(out_base)
        else:
            # -o 为输出目录: 文件名按输入名生成
            output_dir = out_base
    else:
        output_dir = os.path.normpath(os.path.join(script_dir, OUTPUT_PATH))
    os.makedirs(output_dir, exist_ok=True)

    # 逐个清洗 (覆盖模式，直接覆盖同名旧文件)
    print("\n📦 开始清洗:")
    results = []
    for in_file in inputs:
        name = os.path.basename(in_file)
        if out_file:
            target = out_file
        else:
            stem, ext = os.path.splitext(name)
            target = os.path.join(output_dir, stem + SUFFIX + ext)
        n_frames, n_info, n_force = process_file(in_file, target)
        results.append((name, n_frames, n_info, n_force, os.path.abspath(target)))
        print(f"  ✅ {name}: {n_frames} 帧"
              + (f", 清除 info 键 {n_info} 个" if n_info else ", 无 stress/virial 键")
              + (f", 清除 forces {n_force} 帧" if n_force else ""))
        print(f"     -> {os.path.abspath(target)}")

    print_summary(results)
# ===========================================================================


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
