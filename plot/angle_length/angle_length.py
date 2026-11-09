#!/usr/bin/env python3
"""
=============================================================================
脚本:        angle_length.py
分类:        结构分析工具 (plot/angle_length)
功能:        批量统计 VASP 结构中指定原子对 (默认 Al-O) 的平均键长，以及
             以两元素分别为中心的平均键角 (默认 Al-O-Al 与 O-Al-O)。
使用方法:    python angle_length.py [结构文件 ...] [选项]
参数:        结构文件 ............ VASP 结构文件 (POSCAR/CONTCAR/*.vasp)，可给
                               多个或用通配符；省略时用配置区 INPUT_FILES
             -c/--cutoff ........ 成键截断距离 (Å)，小于该值视为成键
             -e/--elements ...... 原子对两个元素符号 (如 -e Al O，也可 -e Al-O)
             -o/--output ........ 记录文件 (*.txt) 或输出目录 (等价 --outdir)
             -h/--help .......... 显示本帮助后退出
模式参数:    无 (单次全量统计，不做模式切换)
输入文件:    配置区 INPUT_FILES (默认 1layer.vasp、2layer.vasp，相对 INPUT_PATH)
输出文件:    angle_length.txt   记录文件 (汇总表，每次运行覆盖，表头以 # 开头)
输出路径:    默认脚本所在目录 (OUTPUT_PATH)，可用 -o 指定目录或完整文件名
键角定义:    同一中心原子上两个配位原子的夹角，取 0-180° 的正值 (不取反角)；
             键长与键角一律按周期性最小镜像 (PBC) 计算。
示例:
  python angle_length.py
  python angle_length.py ./1layer.vasp ./2layer.vasp
  python angle_length.py './*.vasp' -c 2.6
  python angle_length.py ./1layer.vasp -e Al O -o ./out/angle_length.txt
目录结构:
  plot/angle_length/
    ├── angle_length.py      (本脚本)
    ├── 1layer.vasp          (输入结构)
    ├── 2layer.vasp          (输入结构)
    └── angle_length.txt     (记录文件，运行后生成)
作者:        隼蝶.
最后修改日期: 2026-10-20
=============================================================================
"""

import datetime
import glob
import os
import re
import sys
from itertools import combinations

# ============================== 参数配置区 =====================================
INPUT_FILES  = ["1layer.vasp", "2layer.vasp"]   # 输入结构文件列表 (支持通配符，相对 INPUT_PATH，命令行优先)
OUTPUT_FILES = ["angle_length.txt"]             # 输出文件列表 (本脚本输出即汇总记录文件，相对 OUTPUT_PATH)
RECORD_FILE  = OUTPUT_FILES[0]                  # 记录文件 (汇总表，每次运行覆盖)
INPUT_PATH   = "./"                             # 输入文件寻找路径 (相对脚本所在目录)
OUTPUT_PATH  = "./"                             # 输出文件存放路径 (相对脚本所在目录)
ELEMENT_PAIR = ("Al", "O")                      # 原子对 (元素1, 元素2)：键长 E1-E2，键角 E1-E2-E1 与 E2-E1-E2
BOND_CUTOFF  = 2.60                             # 成键截断距离 (Å)，小于该值视为成键
NDIGITS      = 4                                # 终端与记录文件的数值小数位数
# =============================================================================

# ============================== 环境准备区 =====================================
# 终端 locale 可能非 UTF-8 (如 Windows GBK)，强制 stdout 用 UTF-8，
# 避免打印中文/emoji 时抛 UnicodeEncodeError。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    import numpy as np
except ImportError:
    print("❌ 错误: 未找到 numpy。请安装: pip install numpy")
    sys.exit(1)

try:
    from ase.data import chemical_symbols
    from ase.geometry import find_mic
    from ase.io import read
except ImportError:
    print("❌ 错误: 未找到 ASE (Python 库)。请安装: pip install ase")
    sys.exit(1)
# ===========================================================================


# ============================== 函数配置区 =====================================
def print_usage():
    """打印头部注释块 (脚本功能与完整使用方法)。"""
    print(__doc__)


def fail_option(option, need):
    """选项缺参或非法时打印用法提示并以错误码退出。"""
    print(f"❌ 错误: {option} 需要一个{need}。")
    print_usage()
    sys.exit(1)


def parse_args(argv):
    """解析命令行参数 (选项与位置参数顺序随意)。
    返回 (结构文件列表, 截断距离, 元素对, 输出路径)。"""
    inputs, cutoff, elements, out = [], None, None, None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif arg in ("-c", "--cutoff"):
            if i + 1 >= len(argv):
                fail_option("-c/--cutoff", "正数截断距离 (Å)")
            try:
                cutoff = float(argv[i + 1])
            except ValueError:
                fail_option("-c/--cutoff", "正数截断距离 (Å)")
            i += 2
        elif arg in ("-e", "--elements"):
            values = []
            i += 1
            while (i < len(argv) and len(values) < 2
                   and not argv[i].startswith("-")):
                values.extend(p for p in re.split(r"[-/,]", argv[i]) if p)
                i += 1
            if len(values) != 2:
                fail_option("-e/--elements", "两个元素符号 (如 -e Al O)")
            elements = (values[0], values[1])
        elif arg in ("-o", "--output", "--outdir"):
            if i + 1 >= len(argv):
                fail_option("-o/--output", "记录文件 (*.txt) 或输出目录")
            out = argv[i + 1]
            i += 2
        else:
            inputs.append(arg)
            i += 1
    return inputs, cutoff, elements, out


def normalize_symbol(symbol):
    """规范元素符号大小写 (o -> O、al -> Al)；非法符号报错退出。"""
    text = symbol.strip().capitalize()
    if text not in chemical_symbols:
        print(f"❌ 错误: '{symbol}' 不是有效的元素符号。")
        sys.exit(1)
    return text


def dw(text):
    """字符串显示宽度：中文等宽字符按 2 列计，用于表格对齐。"""
    return sum(2 if ord(ch) > 127 else 1 for ch in str(text))


def pad(text, width, align="<"):
    """按显示宽度填充空格对齐: '<' 左对齐, '>' 右对齐。"""
    text = str(text)
    space = " " * (width - dw(text))
    return text + space if align == "<" else space + text


def make_table(headers, rows, aligns):
    """生成按显示宽度对齐的表格文本: 返回 (表头行, 数据行列表)。"""
    widths = []
    for j, head in enumerate(headers):
        width = dw(head)
        for row in rows:
            width = max(width, dw(row[j]))
        widths.append(width)
    header = "  ".join(pad(head, widths[j], aligns[j])
                       for j, head in enumerate(headers))
    body = ["  ".join(pad(cell, widths[j], aligns[j])
                      for j, cell in enumerate(row)) for row in rows]
    return header, body


def fmt(value, digits=NDIGITS):
    """数值格式化 (nan 显示为 '-')。"""
    if value is None or value != value:
        return "-"
    return f"{value:.{digits}f}"


def expand_cli(pattern, script_dir):
    """展开命令行给出的结构文件: 当前运行目录优先，脚本目录兜底；
    含通配符 (* ? [) 的按 glob 展开并排序。"""
    wildcard = any(ch in pattern for ch in "*?[")
    for base in (os.getcwd(), script_dir):
        if wildcard:
            hits = sorted(glob.glob(os.path.join(base, pattern)))
            if hits:
                return [os.path.abspath(h) for h in hits]
        else:
            path = os.path.join(base, pattern)
            if os.path.isfile(path):
                return [os.path.abspath(path)]
    if wildcard:
        print(f"⚠️ 警告: 模式 '{pattern}' 未匹配任何文件，已忽略。")
        return []
    return [os.path.abspath(pattern)]  # 字面路径保留，读取时再报错


def resolve_config_inputs(script_dir):
    """展开参数配置区 INPUT_FILES (相对 INPUT_PATH，支持通配符)。"""
    base = os.path.normpath(os.path.join(script_dir, INPUT_PATH))
    files = []
    for pattern in INPUT_FILES:
        if any(ch in pattern for ch in "*?["):
            hits = sorted(glob.glob(os.path.join(base, pattern)))
            if not hits:
                print(f"⚠️ 警告: 模式 '{pattern}' 未匹配任何文件，已忽略。")
            files.extend(os.path.abspath(h) for h in hits)
        else:
            files.append(os.path.abspath(os.path.join(base, pattern)))
    return files


def resolve_record_path(script_dir, out):
    """解析记录文件路径: -o 以 .txt 结尾视为完整文件，否则视为目录并拼接
    RECORD_FILE；带 ./ ../ 前缀的相对路径相对当前运行目录，其余相对脚本目录。"""
    if out is None:
        return os.path.abspath(os.path.join(script_dir, OUTPUT_PATH,
                                            RECORD_FILE))
    if out.lower().endswith(".txt"):
        folder, name = os.path.split(out)
        if not os.path.isabs(folder):
            if folder.startswith("."):
                folder = os.path.abspath(folder or ".")
            else:
                folder = os.path.join(script_dir, folder)
        return os.path.abspath(os.path.join(folder, name))
    if not os.path.isabs(out) and not out.startswith((".", os.sep)):
        out = os.path.join(script_dir, out)
    return os.path.abspath(os.path.join(out, RECORD_FILE))


def neighbor_table(atoms, centers, others, cutoff):
    """求每个中心原子的配位原子: 返回 [(中心, 邻居索引, 最小镜像位移, 距离)]，
    仅保留距离小于截断值的邻居 (PBC 最小镜像)。"""
    if len(centers) == 0 or len(others) == 0:
        return []
    positions, cell, pbc = atoms.positions, atoms.cell, atoms.pbc
    table = []
    for center in centers:
        dvec = positions[others] - positions[center]
        dvec, dist = find_mic(dvec, cell, pbc=pbc)
        mask = dist < cutoff
        if mask.any():
            table.append((center, others[mask], dvec[mask], dist[mask]))
    return table


def angles_at_centers(table):
    """枚举同一中心原子上两两配位原子的夹角 (0-180°，每对只计一次)。"""
    chunks = []
    for _, _, dvec, _ in table:
        if len(dvec) < 2:
            continue
        norms = np.linalg.norm(dvec, axis=1)
        pair = np.array(list(combinations(range(len(dvec)), 2)))
        cos = np.einsum("ij,ij->i", dvec[pair[:, 0]], dvec[pair[:, 1]])
        cos = cos / (norms[pair[:, 0]] * norms[pair[:, 1]])
        chunks.append(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))
    return np.concatenate(chunks) if chunks else np.array([])


def describe(values):
    """统计样本: 返回 (个数, 平均值, 样本标准差)；空样本返回 (0, nan, nan)。"""
    if len(values) == 0:
        return 0, float("nan"), float("nan")
    std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    return len(values), float(np.mean(values)), std


def analyze_structure(path, elem1, elem2, cutoff):
    """读取并统计单个结构 (多帧文件仅取第 1 帧)；缺元素或没有成键则返回 None。"""
    atoms = read(path, index=0)
    symbols = np.array(atoms.get_chemical_symbols())
    idx1 = np.where(symbols == elem1)[0]
    idx2 = np.where(symbols == elem2)[0]
    if len(idx1) == 0 or len(idx2) == 0:
        print(f"  ⚠️ 缺少元素 {elem1} 或 {elem2}，已跳过。")
        return None
    # elem2 中心 -> elem1 邻居 (同时给出全部键长)；elem1 中心 -> elem2 邻居
    table2 = neighbor_table(atoms, idx2, idx1, cutoff)
    table1 = neighbor_table(atoms, idx1, idx2, cutoff)
    if not table2:
        print(f"  ⚠️ 截断 {cutoff:.2f} Å 下没有 {elem1}-{elem2} 成键，已跳过。")
        return None
    bonds = np.concatenate([entry[3] for entry in table2])
    return {
        "path" : path,
        "natom": len(atoms),
        "n1"   : len(idx1),
        "n2"   : len(idx2),
        "bond" : describe(bonds),                     # 键长 E1-E2
        "ang1" : describe(angles_at_centers(table2)),  # 键角 E1-E2-E1 (中心 E2)
        "ang2" : describe(angles_at_centers(table1)),  # 键角 E2-E1-E2 (中心 E1)
    }


def print_result_table(results, elem1, elem2):
    """终端打印各结构的平均键长与平均键角表格。"""
    ang1, ang2 = f"{elem1}-{elem2}-{elem1}", f"{elem2}-{elem1}-{elem2}"
    headers = ["结构", "原子数", f"N({elem1}-{elem2})", f"d({elem1}-{elem2})/Å",
               f"N({ang1})", f"θ({ang1})/°", f"N({ang2})", f"θ({ang2})/°"]
    aligns = ["<"] + [">"] * (len(headers) - 1)
    rows = [[os.path.basename(r["path"]), str(r["natom"]),
             str(r["bond"][0]), fmt(r["bond"][1]),
             str(r["ang1"][0]), fmt(r["ang1"][1]),
             str(r["ang2"][0]), fmt(r["ang2"][1])] for r in results]
    header, body = make_table(headers, rows, aligns)
    print("📊 平均键长与平均键角 (键角取 0-180° 正值):")
    print(header)
    for line in body:
        print(line)


def write_record(record_path, results, elem1, elem2, cutoff):
    """写汇总记录文件 (覆盖模式，UTF-8 + LF)，表头以 # 开头，附输入绝对路径。"""
    ang1, ang2 = f"{elem1}-{elem2}-{elem1}", f"{elem2}-{elem1}-{elem2}"
    headers = ["结构", f"N({elem1})", f"N({elem2})",
               f"N({elem1}-{elem2})", f"d({elem1}-{elem2})/Å", "sd(d)/Å",
               f"N({ang1})", f"θ({ang1})/°", "sd(θ)/°",
               f"N({ang2})", f"θ({ang2})/°", "sd(θ)/°"]
    aligns = ["<"] + [">"] * (len(headers) - 1)
    rows = [[os.path.basename(r["path"]), str(r["n1"]), str(r["n2"]),
             str(r["bond"][0]), fmt(r["bond"][1]), fmt(r["bond"][2]),
             str(r["ang1"][0]), fmt(r["ang1"][1]), fmt(r["ang1"][2]),
             str(r["ang2"][0]), fmt(r["ang2"][1]), fmt(r["ang2"][2])]
            for r in results]
    header, body = make_table(headers, rows, aligns)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = ["# angle_length.py 键长键角汇总\n",
             f"# 生成时间: {stamp}\n",
             f"# 原子对: {elem1}-{elem2} | 成键截断: {cutoff:.2f} Å | "
             "键角范围: 0-180° | PBC 最小镜像计算\n",
             f"# {header}\n"]
    lines += ["  " + line + "\n" for line in body]
    lines.append("#\n# 输入文件 (绝对路径):\n")
    lines += [f"#   [{n}] {r['path']}\n" for n, r in enumerate(results, 1)]
    os.makedirs(os.path.dirname(record_path), exist_ok=True)
    with open(record_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.writelines(lines)


def print_summary(results, skipped, failed, record_path, elem1, elem2):
    """运行完毕后集中总结关键信息 (数量统计、记录文件绝对路径)。"""
    print("=" * 62)
    print("🎉 运行完成，总结:")
    print(f"  原子对:     {elem1}-{elem2}")
    print(f"  成功:       {len(results)} 个结构")
    print(f"  跳过:       {len(skipped)} 个结构")
    print(f"  失败:       {len(failed)} 个结构")
    for path, reason in failed:
        print(f"    ❌ {os.path.basename(path)}: {reason}")
    if record_path:
        print(f"  记录文件:   {record_path}")
    else:
        print("  记录文件:   未生成 (无成功统计的结构)")
    print("=" * 62)


# ============================== 脚本工作区 =====================================
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cli_inputs, cutoff, elements, out = parse_args(sys.argv[1:])

    elem1, elem2 = ELEMENT_PAIR if elements is None else elements
    elem1, elem2 = normalize_symbol(elem1), normalize_symbol(elem2)
    cutoff = BOND_CUTOFF if cutoff is None else cutoff
    if cutoff <= 0:
        print(f"❌ 错误: 成键截断必须为正数，当前为 {cutoff}。")
        sys.exit(1)

    if cli_inputs:
        files = []
        for pattern in cli_inputs:
            files.extend(expand_cli(pattern, script_dir))
    else:
        files = resolve_config_inputs(script_dir)
    files = list(dict.fromkeys(files))  # 去重并保持顺序
    if not files:
        print("❌ 错误: 未找到任何输入结构文件。")
        print("请在参数配置区设置 INPUT_FILES，或用命令行指定，如:")
        print("  python angle_length.py ./1layer.vasp ./2layer.vasp")
        sys.exit(1)

    record_path = resolve_record_path(script_dir, out)
    print(f"ℹ️ 原子对: {elem1}-{elem2} | 成键截断: {cutoff:.2f} Å")
    print(f"ℹ️ 待统计结构: {len(files)} 个")

    results, skipped, failed = [], [], []
    for n, path in enumerate(files, 1):
        print(f"📦 [{n}/{len(files)}] {path}")
        try:
            res = analyze_structure(path, elem1, elem2, cutoff)
        except Exception as exc:  # 读取/解析失败不中断其余结构
            print(f"  ❌ 读取失败: {exc}")
            failed.append((path, str(exc)))
            continue
        if res is None:
            skipped.append(path)
            continue
        results.append(res)
        print(f"  ✅ {os.path.basename(path)}: "
              f"d({elem1}-{elem2}) = {fmt(res['bond'][1])} Å "
              f"({res['bond'][0]} 键), "
              f"θ({elem1}-{elem2}-{elem1}) = {fmt(res['ang1'][1])}°, "
              f"θ({elem2}-{elem1}-{elem2}) = {fmt(res['ang2'][1])}°")

    if results:
        print()
        print_result_table(results, elem1, elem2)
        write_record(record_path, results, elem1, elem2, cutoff)
        print(f"✅ 已写入记录文件: {record_path}")
    else:
        print("⚠️ 警告: 没有成功统计的结构，未生成记录文件。")
        record_path = None
    print_summary(results, skipped, failed, record_path, elem1, elem2)


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
