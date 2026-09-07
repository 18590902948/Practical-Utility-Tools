#!/usr/bin/env python3
"""
=============================================================================
脚本:        xyz_filter.py
分类:        结构处理工具
功能:        对 xyz/extxyz 多帧文件做多条件筛选:
             (1) 元素匹配 — 命令行 -eoi/-eal 指定元素 (帧元素集合恰好等于
             或至少包含设定元素)、-all 不限元素，或按配置区 KEEP_GROUPS
             多组并行 (恰好含);
             (2) 几何检查 — 剔除帧内任意两原子间距 (PBC 最小镜像) 小于
             阈值的帧 (默认 2.1 Å) 与原子数超过上限的帧 (默认 200)。
             文本级流式逐帧解析、原样输出命中帧 (energy/force/virial 等
             全部键值与坐标精度逐字保留，适合 GB 级训练文件)，并生成记录
             文件 (帧号/原子数/元素组成/最小间距/状态逐帧一行)
使用方法:    python xyz_filter.py [输入文件 ...] [-eoi/-eal <元素...>|-all]
             [-d <阈值>] [-n <上限>] [-o 输出路径] [-h/--help]
参数:        输入文件 ...   待筛选的 xyz/extxyz 文件 (可多个，支持通配符；
                         命令行参数先按当前运行目录解析，不存在再相对
                         脚本所在目录)
             -d/--min-dist  最小原子间距阈值 (Å，默认配置区 MIN_DIST；
                         0 关闭间距检查)
             -n/--max-atoms 帧原子数上限 (默认配置区 MAX_ATOMS；0 关闭)
             -o/--output   输出路径 (输出目录；不带点开头的相对路径默认
                         相对脚本所在目录解析，./ 或 ../ 开头相对当前
                         运行目录；单组单输入时也可指定输出文件完整路径
                         (以 .xyz/.extxyz 结尾)；不指定时输出到配置区
                         OUTPUT_PATH)
             -h/--help     显示本帮助
模式参数:    -eoi/--elements-only-include <元素...>  仅包含设定元素 (帧元素
                         集合恰好为设定元素，组名 = 元素拼接，如 MoLiTe)
             -eal/--elements-at-least <元素...>      至少包含设定元素 (帧可
                         含其他元素，组名 = eal_元素名-连接)
             -all/--all   全部元素: 不做元素匹配，全部帧直接进入几何检查
                          (原子数上限/最小间距)，通过者写入
                          <原名>_filtered.xyz (纯几何过滤)
             (模式互斥，同时指定时报错；不传模式时用配置区 KEEP_GROUPS
             多组并行，与旧版行为一致)
输入文件:    配置区 INPUT_FILES (默认 train.xyz，相对 INPUT_PATH)
输出文件:    每输入文件、每组组合各输出一个文件:
             <原名去扩展名>_<组名><原扩展名> (如 200_MoLiTe.xyz)；
             无命中帧的组不生成空文件。记录文件 <原名去扩展名>_filtered.txt
             与输出文件同目录，表格形式逐帧记录
输出路径:    默认脚本所在目录下 filtered_xyz/ (OUTPUT_PATH)，可用 -o 指定
             (输出目录，相对/绝对路径均可)
帧号约定:    记录文件中帧号为输入文件内的 OVITO 0 起始索引 (0 = 第一帧)
间距约定:    按帧注释行 Lattice 与 pbc 做 PBC 最小镜像距离判定 (三斜晶格
             支持)；无 Lattice 注释的帧无法检查，按通过处理并计数提示
示例:
  python xyz_filter.py ./train.xyz
  python xyz_filter.py -eoi Mo Li Te E:/Literature/NEP/474/200.xyz -o ./out/
  python xyz_filter.py -eal Mo Te ./A/a.xyz -d 2.1 -n 200 -o ./out/
  python xyz_filter.py -all E:/Literature/NEP/474/200.xyz -d 2.1 -n 200 -o E:/Literature/NEP/474/
  (目标组合配置区默认 KEEP_GROUPS: 每组为一种组合，元素顺序即组名，
   如 ["Mo","Te"] 组名为 MoTe；命令行 -eoi/-eal 给出时忽略 KEEP_GROUPS)
作者:        隼蝶.
最后修改:    2026-09-04
=============================================================================
"""

import glob
import math
import os
import re
import sys
from collections import Counter

# ============================== 参数配置区 =====================================
INPUT_FILES    = ["train.xyz"]        # 输入文件列表 (支持通配符，相对 INPUT_PATH 展开；命令行参数优先)
KEEP_GROUPS    = [["Mo", "Te"], ["Mo", "Te", "Li"]]  # 目标元素组合 (配置区默认, 仅当命令行未给 -eoi/-eal 模式时生效): 每组 = 帧须恰好含这些元素 (元素顺序即输出组名)
MIN_DIST       = 2.1                  # 最小原子间距阈值 (Å): 帧内任意两原子 PBC 最小镜像间距小于该值 → 剔除; 0 = 关闭间距检查
MAX_ATOMS      = 200                  # 帧原子数上限: 帧原子数大于该值 → 剔除; 0 = 关闭原子数检查
USE_PBC        = True                 # 间距计算是否按帧注释行 pbc 键做周期取整 (False 则直接算笛卡尔距离)
INPUT_ENCODING = "utf-8"              # 输入文件编码 (Windows 默认 GBK 会误读 UTF-8 文件，故显式指定)
RECORD_HEADER  = ("# " + f"{'帧号':<10}{'原子数':<8}{'元素组成':<18}"
                  f"{'最小间距/Å':>10}  状态\n")  # 记录文件表头
INPUT_PATH     = "./"                 # 输入文件寻找路径 (相对脚本所在目录)
OUTPUT_PATH    = "./filtered_xyz/"    # 输出文件寻找路径 (相对脚本所在目录)
BUFFER_N       = 50                   # 输出缓冲: 攒够 N 帧批量落盘 (内存友好)
# =============================================================================

# ============================== 环境准备区 =====================================
# 终端 locale 可能非 UTF-8 (如 POSIX/C), 强制 stdout 用 UTF-8,
# 避免打印中文时抛 UnicodeEncodeError (Windows 终端显示乱码不影响功能)。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
# ===========================================================================


# ============================== 函数配置区 =====================================
LATTICE_RE = re.compile(r'Lattice="([^"]*)"')   # 帧注释行晶格 9 分量 (行向量堆叠顺序)
PBC_RE = re.compile(r'pbc="([^"]*)"')            # 帧注释行周期标记 (T/F)


def print_usage():
    """打印头部注释块 (脚本功能与完整使用方法)。"""
    print(__doc__)


def parse_args(argv):
    """解析命令行参数 (选项位置随意): 输入文件为位置参数 (可多个);
    -h/--help、-o/--output、-d/--min-dist、-n/--max-atoms 为选项，
    -eoi/--elements-only-include、-eal/--elements-at-least、-all/--all
    为互斥模式选项 (eoi/eal 后跟元素列表，收集到下一个选项为止)。
    返回 (输入文件列表, 输出路径, 模式, 元素列表, 最小间距, 原子数上限)。"""
    inputs = []
    out_path = None
    mode = None           # 模式: "eoi" / "eal" / "all" (None = 用配置区 KEEP_GROUPS)
    elems = []            # 模式选项后收集的元素符号
    min_dist = None       # -d/--min-dist (None = 用配置区 MIN_DIST)
    max_atoms = None      # -n/--max-atoms (None = 用配置区 MAX_ATOMS)
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
        elif arg in ("-eoi", "--elements-only-include",
                     "-eal", "--elements-at-least"):
            if mode is not None:
                print(f"❌ 错误: 模式选项互斥，不能同时指定 {mode} 与 {arg}。")
                sys.exit(1)
            mode = "eoi" if arg in ("-eoi", "--elements-only-include") else "eal"
            i += 1
            # 收集模式选项后的元素符号 (1-2 位字母) 直到下一个选项/其他参数;
            # 输入文件跟在模式元素后时不误吞 (如 -eoi Mo Li Te 200.xyz)
            while i < len(argv) and not argv[i].startswith("-") \
                    and norm_elem(argv[i]) is not None:
                elems.append(argv[i])
                i += 1
            if not elems:
                print(f"❌ 错误: {arg} 后需指定至少一个元素，如: {arg} Mo Li Te")
                sys.exit(1)
        elif arg in ("-all", "--all"):
            if mode is not None:
                print(f"❌ 错误: 模式选项互斥，不能同时指定 {mode} 与 {arg}。")
                sys.exit(1)
            mode = "all"
            i += 1
        elif arg in ("-d", "--min-dist"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -d/--min-dist 需要一个距离阈值 (Å)。")
                sys.exit(1)
            try:
                min_dist = float(argv[i + 1])
            except ValueError:
                print(f"❌ 错误: -d/--min-dist 需要数值阈值，收到: {argv[i + 1]}")
                sys.exit(1)
            i += 2
        elif arg in ("-n", "--max-atoms"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -n/--max-atoms 需要一个正整数上限。")
                sys.exit(1)
            try:
                max_atoms = int(argv[i + 1])
            except ValueError:
                print(f"❌ 错误: -n/--max-atoms 需要整数上限，收到: {argv[i + 1]}")
                sys.exit(1)
            i += 2
        elif arg.startswith("-"):
            print(f"❌ 错误: 未知选项: {arg} (可用 -h/--help 查看帮助)")
            sys.exit(1)
        else:
            inputs.append(arg)
            i += 1
    return inputs, out_path, mode, elems, min_dist, max_atoms


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


def norm_elem(e):
    """元素符号规范化 (首字母大写其余小写，如 'mo'/'Mo' 均 → 'Mo'；
    限 1-2 位字母，避免把路径等参数误当元素)。"""
    e = e.strip()
    if not e:
        return None
    n = e[:1].upper() + e[1:].lower()
    return n if (len(n) <= 2 and n.isalpha()) else None


def build_groups(mode, elems):
    """构造匹配组列表: 每组为 (元素集合, 组名, 模式)。命令行 -eoi/-eal
    给出时为单组 (元素顺序即组名；eal 模式组名加 eal_ 前缀防与 eoi 输出
    混淆)；-all 为纯几何模式 (集合 None，组名 保留，不做元素匹配)；
    否则用配置区 KEEP_GROUPS (全部按 eoi 判定)。返回 (组列表, 匹配描述)。"""
    if mode:
        if mode == "all":
            return [(None, "保留", "all")], "全部元素 (仅几何过滤)"
        normed = []
        for e in elems:
            n = norm_elem(e)
            if not n:
                print(f"❌ 错误: 无效元素符号: {e}")
                sys.exit(1)
            if n not in normed:
                normed.append(n)
        name = "".join(normed) if mode == "eoi" else "eal_" + "-".join(normed)
        desc = ("仅包含 " if mode == "eoi" else "至少包含 ") + " ".join(normed)
        return [(set(normed), name, mode)], desc
    groups = [(set(g), "".join(g), "eoi") for g in KEEP_GROUPS]
    if not groups:
        print("❌ 错误: 配置区 KEEP_GROUPS 为空。请配置目标组合或用命令行 -eoi/-eal 模式。")
        sys.exit(1)
    desc = "仅包含 " + "、".join("".join(g) for g in KEEP_GROUPS)
    return groups, desc


def frame_sym_counts(lines):
    """从帧的原子行列表统计元素计数 (取每行第一列)，返回 Counter。"""
    counts = Counter()
    for line in lines:
        parts = line.split()
        if parts:
            counts[parts[0]] += 1
    return counts


ATOMIC_ORDER = {"H": 1, "He": 2, "Li": 3, "Be": 4, "B": 5, "C": 6, "N": 7,
                "O": 8, "F": 9, "Ne": 10, "Na": 11, "Mg": 12, "Al": 13,
                "Si": 14, "P": 15, "S": 16, "Cl": 17, "Ar": 18, "K": 19,
                "Ca": 20, "Ti": 22, "V": 23, "Cr": 24, "Mn": 25, "Fe": 26,
                "Co": 27, "Ni": 28, "Cu": 29, "Zn": 30, "Ga": 31, "Ge": 32,
                "Se": 34, "Br": 35, "Zr": 40, "Nb": 41, "Mo": 42, "Ag": 47,
                "Sn": 50, "Sb": 51, "Te": 52, "I": 53, "La": 57, "W": 74,
                "Pt": 78, "Au": 79, "Pb": 82, "Bi": 83}  # 原子序映射 (元素组成串展示排序用)


def compose_symbols(counts):
    """元素组成串: 按原子序数升序拼成 Mo2Te4 形式 (记录文件用)。"""
    syms = sorted(counts, key=lambda s: ATOMIC_ORDER.get(s, 1000))
    return "".join(f"{s}{counts[s]}" for s in syms)


def drop_reason(counts, groups):
    """未命中任何组的剔除原因 (返回状态标签与描述): 单组 eal 帧缺设定元素
    → 缺 X；其余相对全部组元素并集判断 (含杂质元素/缺元素)。"""
    syms = set(counts)
    if len(groups) == 1 and groups[0][2] == "eal":
        missing = sorted(groups[0][0] - syms)
        return "剔-缺" + "".join(missing), "缺 " + ",".join(missing)
    union = set()
    for gset, _, _ in groups:
        if gset is not None:
            union.update(gset)
    extra = sorted(syms - union)
    if extra:
        return "剔-杂质" + "".join(extra), "含杂质元素 " + ",".join(extra)
    missing = sorted(union - syms)
    return "剔-缺" + "".join(missing), "缺 " + ",".join(missing)


# ---------- 几何检查 (PBC 最小镜像间距/原子数上限) ----------
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


def min_pair_dist(atom_lines, vecs, pbc):
    """帧内任意两原子最小间距 (Å): USE_PBC 时按最小镜像计算 (笛卡尔差转
    分数坐标就近取整回主胞再转回，三斜晶格适用)；返回最小距离。"""
    pos = []
    for ln in atom_lines:
        p = ln.split()
        pos.append((float(p[1]), float(p[2]), float(p[3])))
    pbc_on = USE_PBC and any(pbc)
    inv = invert3x3(vecs) if pbc_on else None
    if pbc_on and inv is None:
        pbc_on = False        # 奇异晶格退化到直接笛卡尔距离
    best = float("inf")
    n = len(pos)
    for i in range(n - 1):
        x0, y0, z0 = pos[i]
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
            if d < best:
                best = d
    return best


def geo_check(n_atoms, header, atom_lines, min_dist, max_atoms):
    """几何二次过滤 (元素组命中后调用): 先查原子数上限再算最小间距。返回
    (最小间距显示串或 None, 剔除标签, 剔除描述)。三项检查全部通过时返回
    (显示串, None, None)；无 Lattice 注释无法检查时返回 (None, None, None)。"""
    if max_atoms > 0 and n_atoms > max_atoms:
        return None, "剔-超限", f"原子数 {n_atoms}>{max_atoms}"
    if min_dist <= 0:
        return None, None, None
    vecs, pbc = parse_header_geo(header)
    if vecs is None:
        return None, None, None
    dmin = min_pair_dist(atom_lines, vecs, pbc)
    # 1e-9 容差: 避免 dmin 恰等于阈值时浮点误差导致的误剔除
    if dmin < min_dist - 1e-9:
        return f"{dmin:.3f}", "剔-间距", f"间距 {dmin:.3f}Å<{min_dist}Å"
    return f"{dmin:.3f}", None, None


def group_out_name(stem, ext, group):
    """组输出文件名: all 纯几何模式用 <原名>_filtered.<原扩展名>，
    元素组用 <原名>_<组名>.<原扩展名>。"""
    _, gname, gmode = group
    if gmode == "all":
        return stem + "_filtered" + ext
    return stem + "_" + gname + ext


def process_file(in_file, out_dir, groups, min_dist, max_atoms, out_file=None):
    """文本级流式筛选单文件: 逐帧读取原子数行/注释行/原子行；元素匹配命中
    且通过几何检查 (原子数上限/最小间距) 的帧原文写入对应输出 (缓冲区批量
    落盘)；每帧一行写入记录文件。返回 (总帧数, 组命中数列表, 剔除原因
    计数, 组输出路径列表, 记录文件路径, 无晶格跳过数)。out_file 提供时
    (单组 -o 文件形式) 输出到该文件。"""
    gnames = [g[1] for g in groups]
    kept_count = [0] * len(groups)
    reasons = Counter()
    no_lattice = 0
    out_streams = []
    out_paths = []
    buf_lines = [[] for _ in groups]
    buf_frames = [0] * len(groups)

    stem, ext = os.path.splitext(os.path.basename(in_file))
    if out_file:
        record_path = os.path.splitext(out_file)[0] + ".txt"
    else:
        record_path = os.path.join(out_dir, stem + "_filtered.txt")
    rec_buf = []

    # newline="" 关闭换行翻译: 原子行原文 (含行尾) 逐字保留
    fin = open(in_file, encoding=INPUT_ENCODING, newline="")
    fout_rec = open(record_path, "w", encoding="utf-8", newline="")
    fout_rec.write(RECORD_HEADER)

    def flush_stream(k):
        """将第 k 组的缓冲行写入其输出文件 (首次调用创建文件)。
        输出流按组索引存放，中间未命中的组补 None 占位。"""
        if not buf_lines[k]:
            return
        while len(out_streams) <= k:
            out_streams.append(None)
            out_paths.append(None)
        if out_streams[k] is None:
            if out_file:
                p = out_file
            else:
                p = os.path.join(out_dir, group_out_name(stem, ext, groups[k]))
            out_streams[k] = open(p, "w", encoding="utf-8", newline="")
            out_paths[k] = p
        out_streams[k].writelines(buf_lines[k])
        buf_lines[k].clear()
        buf_frames[k] = 0

    try:
        n_total = 0
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
                print(f"❌ 错误: 第 {n_total + 1} 帧原子数行无法解析，文件可能损坏: "
                      f"{in_file} (行内容: {line.strip()[:60]})")
                sys.exit(1)
            header = fin.readline()
            if not header:
                print(f"❌ 错误: 第 {n_total + 1} 帧缺少注释行，文件可能损坏: {in_file}")
                sys.exit(1)
            atom_lines = [fin.readline() for _ in range(n_atoms)]
            if any(not al for al in atom_lines):
                print(f"❌ 错误: 第 {n_total + 1} 帧原子行不足，文件可能损坏: {in_file}")
                sys.exit(1)

            counts = frame_sym_counts(atom_lines)
            comp = compose_symbols(counts)
            syms = set(counts)
            hit = None
            for k, (gset, _, gmode) in enumerate(groups):
                if gmode == "all":
                    matched = True          # 纯几何模式: 元素不设限
                elif gmode == "eoi":
                    matched = (syms == gset)
                else:
                    matched = gset.issubset(syms)
                if matched:
                    hit = k
                    break

            if hit is None:
                # 元素未命中: 无需几何检查，直接剔除
                tag, desc = drop_reason(counts, groups)
                reasons[desc] += 1
                status = tag
                min_d = "-"
            else:
                # 元素命中后的几何二次过滤 (原子数上限 → 最小间距)
                min_d, tag, desc = geo_check(n_atoms, header, atom_lines,
                                             min_dist, max_atoms)
                if tag is None and min_d is None:
                    # 无 Lattice 注释的帧无法做间距检查: 按通过处理并计数提示
                    # (间距检查关闭时 geo_check 同样返回 None，不计入)
                    if min_dist > 0:
                        no_lattice += 1
                    min_d = "-"
                if tag is None:
                    buf_lines[hit].append(line)
                    buf_lines[hit].append(header)
                    buf_lines[hit].extend(atom_lines)
                    kept_count[hit] += 1
                    buf_frames[hit] += 1
                    if buf_frames[hit] >= BUFFER_N:
                        flush_stream(hit)
                    status = gnames[hit]
                else:
                    if min_d is None:
                        min_d = "-"   # 原子数超限帧未算间距
                    reasons[desc] += 1
                    status = tag

            rec_buf.append(f"{n_total:<10}{n_atoms:<8}{comp:<18}"
                           f"{min_d:>10}  {status}\n")
            if len(rec_buf) >= BUFFER_N:
                fout_rec.writelines(rec_buf)
                rec_buf.clear()
            n_total += 1
    finally:
        fin.close()
        for k in range(len(groups)):
            flush_stream(k)
        fout_rec.writelines(rec_buf)
        fout_rec.close()
        for s in out_streams:
            if s is not None:
                s.close()

    return n_total, kept_count, reasons, out_paths, record_path, no_lattice
# ===========================================================================


# ============================== 脚本工作区 =====================================
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    args, out_path, mode, elems, min_dist, max_atoms = parse_args(sys.argv[1:])

    # 匹配组: 命令行 -eoi/-eal/-all 模式 (单组) 优先，否则配置区 KEEP_GROUPS
    groups, mode_desc = build_groups(mode, elems)
    # 几何阈值: 命令行优先，否则配置区默认值 (0 = 关闭对应检查)
    min_dist = MIN_DIST if min_dist is None else min_dist
    max_atoms = MAX_ATOMS if max_atoms is None else max_atoms

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

    # 输出路径: -o 命令行优先，否则默认输出目录 OUTPUT_PATH (相对脚本目录)
    # 多组组合时 -o 仅支持目录形式；单组单输入时支持 -o 输出文件完整路径
    out_file = None
    if out_path:
        out_base = resolve_cmd_path(out_path, script_dir)
        if os.path.splitext(out_base)[1].lower() in (".xyz", ".extxyz"):
            if len(groups) > 1 or len(inputs) > 1:
                print("❌ 错误: 多组组合或多个输入文件时，-o 只能指定输出目录。")
                sys.exit(1)
            out_file = out_base
            output_dir = os.path.dirname(out_base)
        else:
            output_dir = out_base
    else:
        output_dir = os.path.normpath(os.path.join(script_dir, OUTPUT_PATH))
    os.makedirs(output_dir, exist_ok=True)

    # 逐个筛选 (覆盖模式，直接覆盖同名旧文件)
    gnames = [g[1] for g in groups]
    print("\n📦 开始筛选 (元素匹配: " + mode_desc + "):")
    geo_desc = []
    if min_dist > 0:
        geo_desc.append(f"间距 < {min_dist} Å")
    if max_atoms > 0:
        geo_desc.append(f"原子数 > {max_atoms}")
    print("  🔍 几何检查: " + ("、".join(geo_desc) if geo_desc else "关闭"))
    results = []
    for in_file in inputs:
        n_total, kept_count, reasons, out_paths, record_path, no_lattice = \
            process_file(in_file, output_dir, groups, min_dist, max_atoms,
                         out_file=out_file)
        name = os.path.basename(in_file)
        results.append((name, n_total, kept_count, os.path.abspath(record_path)))
        line = f"  ✅ {name}: 共 {n_total} 帧"
        for i, n in enumerate(kept_count):
            line += f", {gnames[i]} {n} 帧" + (" ⚠️" if n == 0 else "")
        print(line)
        for p in out_paths:
            if p:
                print(f"     -> {os.path.abspath(p)}")
        print(f"     -> {os.path.abspath(record_path)} (记录文件)")
        if no_lattice:
            print(f"     ⚠️ {no_lattice} 帧无 Lattice 注释，已跳过间距检查")
        if reasons:
            detail = "; ".join(f"{r} {n} 帧" for r, n in reasons.items())
            print(f"     ⚠️ 剔除原因: {detail}")

    # 运行完毕总结关键信息
    print("\n🎉 筛选完成:")
    print(f"  处理文件:  {len(results)} 个")
    total = sum(r[1] for r in results)
    print(f"  总帧数:    {total}")
    for i, g in enumerate(gnames):
        n_g = sum(r[2][i] for r in results)
        print(f"  {g} 类合计:  {n_g} 帧" + (" ⚠️ 无命中帧" if n_g == 0 else ""))
    print("  输出文件:  (覆盖模式, 原文逐字保留)")
    if out_file:
        print(f"    - {os.path.abspath(out_file)}")
    else:
        for name, n, kc, rec in results:
            for i, g in enumerate(gnames):
                if kc[i]:
                    stem = os.path.splitext(os.path.basename(name))[0]
                    ext = os.path.splitext(name)[1]
                    p = os.path.join(output_dir,
                                     group_out_name(stem, ext, groups[i]))
                    print(f"    - {os.path.abspath(p)}  ({name}: {g} {kc[i]} 帧)")
    print(f"  记录文件:  {len(results)} 个")
# ===========================================================================


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
