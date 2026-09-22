#!/usr/bin/env python3
"""
=============================================================================
脚本:        check_min_distance.py
分类:        结构检查工具
功能:        检查 xyz/extxyz 文件各元素对 (含同种元素之间) 的最小间距:
             逐帧扫描 (按帧注释行 Lattice/pbc 做 PBC 最小镜像判定)，汇总
             每个元素对在全部帧中的最小间距及出现帧号，终端与记录文件按
             元素对输出一行汇总表格 (元素对/最小间距/帧序号)；终端运行时
             逐帧显示进度条
使用方法:    python check_min_distance.py [输入文件 ...] [-n 输入文件 ...]
             [-o 输出路径] [-h/--help]
参数:        输入文件 ...   待检查的 xyz/extxyz 文件 (可多个，支持通配符；
                         命令行参数先按当前运行目录解析，不存在再相对
                         脚本所在目录)
             -n/--name     指定输入文件 (可多个，支持通配符，与位置参数
                         等价，可混用；如 -n ./train.xyz)
             -o/--output   输出路径 (以 .txt 结尾视为记录文件完整路径，仅
                         单输入时可用；否则视为输出目录。不带点开头的相对
                         路径默认相对脚本所在目录解析，./ 或 ../ 开头相对
                         当前运行目录；不指定时输出到配置区 OUTPUT_PATH)
             -h/--help     显示本帮助
输入文件:    配置区 INPUT_FILES (默认 train.xyz，相对 INPUT_PATH)
输出文件:
  check_min_distance.txt  记录文件 (汇总表格: 元素对/最小间距/帧序号，覆盖
                          写；多输入时自动加 <原名>_ 前缀防覆盖)
输出路径:    默认脚本所在目录下 check_min_distance/ (OUTPUT_PATH)，可用 -o
             指定 (记录文件或输出目录，相对/绝对路径均可)
帧号约定:    表中帧号为对应元素对最小间距出现处的 OVITO 0 起始索引
             (0 = 第一帧，文本编辑器中第 n+1 帧；多帧同为最小值时取首次)
间距约定:    按帧注释行 Lattice 与 pbc 做 PBC 最小镜像距离判定 (三斜晶格
             支持)；无 Lattice 注释的帧按直接笛卡尔距离计算 (无周期处理)
             并计数提示；某元素对在全部帧中均无实测数据时该行显示 '-'
进度显示:    终端 (TTY) 运行时逐帧就地刷新进度条 (完成/总帧数 + 百分比，
             总帧数由预扫描得到)；输出重定向到文件/管道或配置区
             PROGRESS_BAR=False 时不显示
示例:
  python check_min_distance.py ./train.xyz
  python check_min_distance.py -n ./train.xyz
  python check_min_distance.py ./A/a.xyz ./B/b.xyz -o ./out/
  python check_min_distance.py ./train.xyz -o ./check_min_distance.txt
  (不指定输入文件时用配置区 INPUT_FILES，检查脚本所在目录下的文件)
作者:        隼蝶.
最后修改:    2026-09-14
=============================================================================
"""

import glob
import math
import os
import re
import sys
import time

# ============================== 参数配置区 =====================================
INPUT_FILES    = ["train.xyz"]             # 输入文件列表 (支持通配符，相对 INPUT_PATH 展开；命令行参数优先)
RECORD_FILE    = "check_min_distance.txt"  # 记录文件 (多输入时自动加 <原名>_ 前缀防覆盖)
USE_PBC        = True                      # 间距计算是否按帧注释行 pbc 键做周期取整 (False 则直接算笛卡尔距离)
PRECISION      = 3                         # 最小间距保留小数位数 (Å)
INPUT_ENCODING = "utf-8"                   # 输入文件编码 (Windows 默认 GBK 会误读 UTF-8 文件，故显式指定)
INPUT_PATH     = "./"                      # 输入文件寻找路径 (相对脚本所在目录)
OUTPUT_PATH    = "./check_min_distance/"   # 输出文件寻找路径 (相对脚本所在目录)
W_PAIR         = 6                         # 表格列宽 (显示宽度): 元素对
W_DIST         = 12                        # 表格列宽 (显示宽度): 最小间距
W_FRAME        = 8                         # 表格列宽 (显示宽度): 帧序号
PROGRESS_BAR   = True                      # 是否显示逐帧进度条 (仅终端 TTY 运行且预扫描出总帧数时生效)
BAR_WIDTH      = 24                        # 进度条宽度 (字符数)
# =============================================================================

# ============================== 环境准备区 =====================================
# 终端 locale 可能非 UTF-8 (如 POSIX/C), 强制 stdout 用 UTF-8,
# 避免打印中文时抛 UnicodeEncodeError (Windows 终端显示乱码不影响功能)。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
# ===========================================================================


# ============================== 函数配置区 =====================================
LATTICE_RE = re.compile(r'Lattice="([^"]*)"')   # 帧注释行晶格 9 分量 (行向量堆叠顺序)
PBC_RE = re.compile(r'pbc="([^"]*)"')           # 帧注释行周期标记 (T/F)

ATOMIC_ORDER = {"H": 1, "He": 2, "Li": 3, "Be": 4, "B": 5, "C": 6, "N": 7,
                "O": 8, "F": 9, "Ne": 10, "Na": 11, "Mg": 12, "Al": 13,
                "Si": 14, "P": 15, "S": 16, "Cl": 17, "Ar": 18, "K": 19,
                "Ca": 20, "Ti": 22, "V": 23, "Cr": 24, "Mn": 25, "Fe": 26,
                "Co": 27, "Ni": 28, "Cu": 29, "Zn": 30, "Ga": 31, "Ge": 32,
                "Se": 34, "Br": 35, "Zr": 40, "Nb": 41, "Mo": 42, "Ag": 47,
                "Sn": 50, "Sb": 51, "Te": 52, "I": 53, "La": 57, "W": 74,
                "Pt": 78, "Au": 79, "Pb": 82, "Bi": 83}  # 原子序映射 (元素排序展示用)


def dw(s):
    """字符串显示宽度: 中文等宽字符按 2 列计，用于表格对齐。"""
    return sum(2 if ord(c) > 127 else 1 for c in str(s))


def pad(s, w, align="<"):
    """按显示宽度填充空格对齐: '<' 左对齐, '>' 右对齐。"""
    s = str(s)
    n = w - dw(s)
    return s + " " * n if align == "<" else " " * n + s


def col(s, w, align="<"):
    """单列: 按宽度对齐 + 列间 2 空格分隔。"""
    return pad(s, w, align) + "  "


def table_header():
    """表格表头行 (元素对/最小间距/帧序号, 右对齐)。"""
    return (col("元素对", W_PAIR, ">") + col("最小间距/Å", W_DIST, ">")
            + pad("帧序号", W_FRAME, ">"))


def table_row(pair, dist, frame):
    """表格数据行: 元素对/最小间距/帧序号 (右对齐, 与表头一致)。"""
    return (col(pair, W_PAIR, ">") + col(dist, W_DIST, ">")
            + pad(frame, W_FRAME, ">"))


_PROGRESS_W = 0        # 进度条行当前显示宽度 (0 = 未显示)


def progress_line(done, total):
    """进度条行: [进度格] 百分比 已完成/总帧数 (ASCII 进度格, 终端通用)。"""
    frac = min(done / total, 1.0) if total else 0.0
    fill = int(BAR_WIDTH * frac)
    return (f"  🔍 进度: [{'#' * fill}{'-' * (BAR_WIDTH - fill)}] "
            f"{frac * 100:5.1f}%  {done}/{total} 帧")


def draw_progress(done, total):
    """就地刷新进度条 (\r 覆盖同一行并立即 flush)；记录行宽供擦除。"""
    global _PROGRESS_W
    line = progress_line(done, total)
    sys.stdout.write("\r" + line)
    sys.stdout.flush()
    _PROGRESS_W = dw(line)


def clear_progress():
    """擦除进度条行 (输出表格或报错前调用; 无进度条时无操作)。"""
    global _PROGRESS_W
    if _PROGRESS_W:
        sys.stdout.write("\r" + " " * _PROGRESS_W + "\r")
        sys.stdout.flush()
        _PROGRESS_W = 0


def print_usage():
    """打印头部注释块 (脚本功能与完整使用方法)。"""
    print(__doc__)


def parse_args(argv):
    """解析命令行参数 (选项位置随意): 输入文件用位置参数直接给出，或用
    -n/--name 指定 (两者等价，可混用)；-h/--help、-o/--output 为选项。
    返回 (输入文件列表, 输出路径)。"""
    inputs = []
    out_path = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif arg in ("-n", "--name"):
            n_before = len(inputs)
            i += 1
            # 收集选项后的输入文件直到下一个选项 (可多个，支持混用位置参数)
            while i < len(argv) and not argv[i].startswith("-"):
                inputs.append(argv[i])
                i += 1
            if len(inputs) == n_before:
                print("❌ 错误: 选项 -n/--name 后需指定至少一个输入文件。")
                sys.exit(1)
        elif arg in ("-o", "--output", "--outdir"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -o/--output 需要一个输出路径。")
                sys.exit(1)
            out_path = argv[i + 1]
            i += 2
        elif arg.startswith("-"):
            print(f"❌ 错误: 未知选项: {arg} (可用 -h/--help 查看帮助)")
            sys.exit(1)
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


def elem_key(sym):
    """元素排序键: 按原子序升序 (未知元素排最后，再按字母序)。"""
    return (ATOMIC_ORDER.get(sym, 1000), sym)


def parse_header_geo(header):
    """解析帧注释行的晶格与 pbc: 返回 (行向量矩阵, pbc 布尔三元组)；
    无 Lattice 键或分量不足时返回 (None, None)。"""
    m = LATTICE_RE.search(header)
    if not m:
        return None, None
    try:
        vals = [float(x) for x in m.group(1).split()]
    except ValueError:
        return None, None
    if len(vals) < 9:
        return None, None
    vecs = [vals[0:3], vals[3:6], vals[6:9]]
    pbc = [True, True, True]
    mp = PBC_RE.search(header)
    if mp:
        toks = mp.group(1).replace(",", " ").split()
        if len(toks) >= 3:
            pbc = [t.lower() == "t" for t in toks[:3]]
    return vecs, pbc


def invert3x3(m):
    """3×3 矩阵求逆 (行向量堆叠，标准伴随式)；奇异时返回 None。"""
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    A = e * i - f * h
    B = -(d * i - f * g)
    C = d * h - e * g
    D = -(b * i - c * h)
    E = a * i - c * g
    F = -(a * h - b * g)
    G = b * f - c * e
    H = -(a * f - c * d)
    I = a * e - b * d
    det = a * A + b * B + c * C
    if abs(det) < 1e-12:
        return None
    return [[A / det, D / det, G / det],
            [B / det, E / det, H / det],
            [C / det, F / det, I / det]]


def pair_min_dists(atom_lines, vecs, pbc):
    """帧内每对元素的最小间距 (Å): USE_PBC 且帧有晶格时按最小镜像计算
    (笛卡尔差转分数坐标就近取整回主胞再转回，三斜晶格适用)；无晶格或
    奇异晶格时退化为直接笛卡尔距离。返回 ({(元素A,元素B): 最小距离},
    是否实际按 PBC 计算)。元素对键按原子序排序规范化。"""
    syms = []
    pos = []
    for ln in atom_lines:
        p = ln.split()
        syms.append(p[0])
        pos.append((float(p[1]), float(p[2]), float(p[3])))
    pbc_on = USE_PBC and vecs is not None and any(pbc)
    inv = invert3x3(vecs) if pbc_on else None
    if pbc_on and inv is None:
        pbc_on = False        # 奇异晶格退化到直接笛卡尔距离
    best = {}
    n = len(pos)
    for i in range(n - 1):
        x0, y0, z0 = pos[i]
        s0 = syms[i]
        for j in range(i + 1, n):
            x1, y1, z1 = pos[j]
            dx, dy, dz = x0 - x1, y0 - y1, z0 - z1
            if pbc_on:
                # 分数差 = 笛卡尔差 × 逆矩阵 (行向量)，周期维就近取整
                f = [dx * inv[0][k] + dy * inv[1][k] + dz * inv[2][k]
                     for k in range(3)]
                for k in range(3):
                    if pbc[k]:
                        f[k] -= round(f[k])
                r = [f[0] * vecs[0][k] + f[1] * vecs[1][k] + f[2] * vecs[2][k]
                     for k in range(3)]
            else:
                r = [dx, dy, dz]
            d = math.sqrt(r[0] * r[0] + r[1] * r[1] + r[2] * r[2])
            s1 = syms[j]
            key = (s0, s1) if elem_key(s0) <= elem_key(s1) else (s1, s0)
            if key not in best or d < best[key]:
                best[key] = d
    return best, pbc_on


def count_frames(in_file):
    """预扫描统计文件总帧数 (逐帧快速跳过原子行, 不校验内容; 供进度条显示;
    解析异常时返回 None, 交给主扫描给出精确报错)。"""
    n = 0
    try:
        with open(in_file, encoding=INPUT_ENCODING, newline="") as fin:
            while True:
                line = fin.readline()
                if not line:
                    break
                parts = line.split()
                if not parts:
                    continue
                n_atoms = int(parts[0])
                if n_atoms < 0:
                    return None
                fin.readline()          # 注释行
                for _ in range(n_atoms):
                    fin.readline()      # 原子行
                n += 1
    except (ValueError, OSError):
        return None
    return n


def process_file(in_file, out_dir, multi_input, rec_override=None):
    """文本级流式检查单文件: 逐帧读取原子数行/注释行/原子行，逐元素对累积
    全文件最小间距及出现帧号 (同值取首次)；处理完按元素对输出一行汇总表格
    (元素对/最小间距/帧序号) 到终端并写记录文件。返回统计信息 dict
    (帧数/无晶格帧数/无可配对帧数/元素集合/无实测数据对数/记录路径)。"""
    stem = os.path.splitext(os.path.basename(in_file))[0]
    if rec_override:
        rec_path = rec_override
    elif multi_input:
        rec_path = os.path.join(out_dir, stem + "_" + RECORD_FILE)
    else:
        rec_path = os.path.join(out_dir, RECORD_FILE)

    n_frames = 0          # 总帧数
    n_no_lattice = 0      # 无 Lattice 注释 (按直接笛卡尔距离) 的帧数
    n_no_pair = 0         # 帧内原子不足 2 个 (无元素对数据) 的帧数
    elems_all = set()     # 全文件出现过的元素
    best = {}             # {(元素A,元素B): (最小间距, 出现帧号)} 保留首次最小

    # 预扫描总帧数供进度条显示 (重定向输出或预扫描失败时不显示)
    total_frames = count_frames(in_file)
    prog_on = bool(PROGRESS_BAR and total_frames and sys.stdout.isatty())
    prog_step = max(1, (total_frames or 1) // 200)   # 约 200 次刷新

    fin = open(in_file, encoding=INPUT_ENCODING, newline="")
    total_txt = f"共 {total_frames} 帧, " if total_frames is not None else ""
    print(f"\n📦 检查文件: {os.path.basename(in_file)} "
          f"({total_txt}帧号: 元素对最小间距出现处的 OVITO 0 起始索引, "
          f"编辑器第 n+1 帧)")
    try:
        while True:
            line = fin.readline()
            if not line:
                break
            parts = line.split()
            if not parts:
                continue
            try:
                n_atoms = int(parts[0])
            except ValueError:
                clear_progress()
                print(f"❌ 错误: 第 {n_frames + 1} 帧原子数行无法解析，文件可能损坏: "
                      f"{in_file} (行内容: {line.strip()[:60]})")
                sys.exit(1)
            header = fin.readline()
            if not header:
                clear_progress()
                print(f"❌ 错误: 第 {n_frames + 1} 帧缺少注释行，文件可能损坏: {in_file}")
                sys.exit(1)
            atom_lines = [fin.readline() for _ in range(n_atoms)]
            if any(not al for al in atom_lines):
                clear_progress()
                print(f"❌ 错误: 第 {n_frames + 1} 帧原子行不足，文件可能损坏: {in_file}")
                sys.exit(1)

            vecs, pbc = parse_header_geo(header)
            if USE_PBC and vecs is None:
                n_no_lattice += 1
            try:
                dists, _ = pair_min_dists(atom_lines, vecs, pbc)
            except (ValueError, IndexError):
                clear_progress()
                print(f"❌ 错误: 第 {n_frames + 1} 帧存在无法解析的原子行，"
                      f"文件可能损坏: {in_file}")
                sys.exit(1)

            elems_all.update(ln.split()[0] for ln in atom_lines if ln.split())
            if not dists:
                n_no_pair += 1
            for key, d in dists.items():
                if key not in best or d < best[key][0]:
                    best[key] = (d, n_frames)   # 同值保留首次出现的帧号
            n_frames += 1
            if prog_on and (n_frames % prog_step == 0
                            or n_frames >= total_frames):
                draw_progress(n_frames, total_frames)
    finally:
        fin.close()
        clear_progress()

    # 汇总表格: 文件元素并集的所有组合 (全文件均无实测数据的组合显示 '-')
    syms_all = sorted(elems_all, key=elem_key)
    rows = []
    n_missing = 0
    for i, a in enumerate(syms_all):
        for b in syms_all[i:]:
            key = (a, b)
            if key in best:
                d, fr = best[key]
                rows.append(table_row(f"{a}-{b}", f"{d:.{PRECISION}f}", fr))
            else:
                rows.append(table_row(f"{a}-{b}", "-", "-"))
                n_missing += 1

    # 记录文件: 注释头 + 汇总表格 (覆盖写；内容与终端一致)
    pbc_desc = ("PBC 最小镜像 (帧注释行 pbc 为 T 的维度周期取整)"
                if USE_PBC else "直接笛卡尔距离 (未做周期处理)")
    fout = open(rec_path, "w", encoding="utf-8", newline="")
    fout.write("# check_min_distance.py 记录 (覆盖写)\n")
    fout.write(f"# 检查时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    fout.write(f"# 输入文件: {os.path.abspath(in_file)}\n")
    fout.write("# 帧号约定: 元素对最小间距出现处的 OVITO 0 起始索引 (0 = 第一帧)\n")
    fout.write(f"# 间距约定: {pbc_desc}; 无 Lattice 帧按直接笛卡尔距离计算\n")
    fout.write("# " + table_header() + "\n")
    fout.write("\n".join(rows) + "\n")
    fout.close()

    # 终端输出汇总表格与单文件小结
    print(table_header())
    for r in rows:
        print(r)
    elems_show = " ".join(syms_all) if syms_all else "-"
    print(f"  ✅ 共 {n_frames} 帧, 元素: {elems_show}, 元素对: {len(rows)} 种"
          + (f" (其中 {n_missing} 种无实测数据)" if n_missing else ""))
    if n_no_lattice:
        print(f"  ⚠️ {n_no_lattice} 帧无 Lattice 注释，已按直接笛卡尔距离计算")
    if n_no_pair:
        print(f"  ⚠️ {n_no_pair} 帧内原子不足 2 个，无元素对数据")
    print(f"  -> {os.path.abspath(rec_path)} (记录文件)")

    return {"name": os.path.basename(in_file), "n_frames": n_frames,
            "n_no_lattice": n_no_lattice, "n_no_pair": n_no_pair,
            "rec_path": rec_path}
# ===========================================================================


# ============================== 脚本工作区 =====================================
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    args, out_path = parse_args(sys.argv[1:])

    # 输入文件: 命令行参数优先，无参数用配置区 INPUT_FILES (相对 INPUT_PATH)
    if args:
        inputs = expand_cmd_inputs(args, script_dir)
    else:
        inputs = expand_default_inputs(os.path.join(script_dir, INPUT_PATH))
    if not inputs:
        print("❌ 错误: 未找到任何输入文件。请指定输入文件，或用 -h/--help 查看帮助。")
        sys.exit(1)
    for p in inputs:
        print(f"ℹ️ 输入文件: {os.path.abspath(p)}")

    # 输出路径: -o 命令行优先 (以 .txt 结尾视为记录文件完整路径，仅单输入
    # 可用；否则视为输出目录)，未指定时用默认输出目录 OUTPUT_PATH
    rec_override = None
    if out_path:
        out_base = resolve_cmd_path(out_path, script_dir)
        if out_base.lower().endswith(".txt"):
            if len(inputs) > 1:
                print("❌ 错误: 多个输入文件时，-o 只能指定输出目录。")
                sys.exit(1)
            rec_override = out_base
            output_dir = os.path.dirname(out_base)
        else:
            output_dir = out_base
    else:
        output_dir = os.path.normpath(os.path.join(script_dir, OUTPUT_PATH))
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n📦 开始检查 (间距单位: Å, 间距约定: "
          f"{'PBC 最小镜像' if USE_PBC else '直接笛卡尔距离'}):")
    results = []
    for in_file in inputs:
        results.append(process_file(in_file, output_dir,
                                    multi_input=(len(inputs) > 1),
                                    rec_override=rec_override))

    # 运行完毕总结关键信息
    print("\n🎉 检查完成:")
    print(f"  处理文件:  {len(results)} 个")
    print(f"  总帧数:    {sum(r['n_frames'] for r in results)}")
    n_nl = sum(r["n_no_lattice"] for r in results)
    if n_nl:
        print(f"  ⚠️ 无 Lattice 帧: {n_nl} 个 (按直接笛卡尔距离计算)")
    print(f"  记录文件:  {len(results)} 个 (覆盖模式)")
    for r in results:
        print(f"    - {os.path.abspath(r['rec_path'])}  ({r['name']})")
# ===========================================================================


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
