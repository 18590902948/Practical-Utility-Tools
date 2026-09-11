"""
=============================================================================
脚本:        add_atoms_ontop.py  (add_li_ontop.py 的通用化 fork)
分类:        结构处理脚本
功能:        在数字命名子文件夹内结构（model.xyz，extxyz 格式）的基底原子
             顶位单侧撒入指定元素原子（x/y 与基底原子相同，z = 基底原子的
             z + 吸附高度），支持随机与棋盘两种撒点模式，结果写出为
             model_<元素>.xyz 新文件（原结构不动）
使用方法:    python add_atoms_ontop.py [根目录] [-ran|-che] [-e 元素] [-sub 元素]
             [-cov 覆盖度] [-hei 高度] [-s 种子] [-y] [-h]
参数:        -e/--element     撒入元素符号 (默认: 配置区 ELEMENT)
             -sub/--substrate 基底元素符号 (顶位吸附对象，默认: 配置区 SUBSTRATE)
             -cov/--coverage  覆盖度 (0, 1]：撒入数 = ceil(基底原子数 × 覆盖度)
                              (默认: 配置区 COVERAGE)
             -hei/--height    吸附高度 (Å)：撒入原子 z = 基底原子 z + 该值
                              (默认: 配置区 HEIGHT)
             -s/--seed        随机模式种子 (整数，默认: 配置区 RANDOM_SEED)
             -y/--yes         跳过执行前确认（非交互终端自动跳过确认）
             -h/--help        显示本帮助（退出码 0）
             根目录           含数字命名子文件夹的根目录（每个子文件夹内有
                              model.xyz）；省略时用配置区 INPUT_PATH
                              解析规则：./ 开头相对当前运行目录，
                              不带点开头相对脚本所在目录，绝对路径照旧
模式参数:    -ran/--random    随机表面吸附（默认）：从基底原子中不放回随机
                              选取 ceil(基底数 × 覆盖度) 个顶位撒点
             -che/--checker   棋盘表面吸附：基底原子胞位 (i+j) 为偶数的顶位
                              撒点，需方形超胞（文件夹名 = 超胞倍数 n）
             (模式互斥，同时指定多个时报错；模式选项位置随意)
输入文件:    <根目录>/<数字文件夹>/model.xyz（extxyz 格式，需含晶胞）
输出文件:    <根目录>/<数字文件夹>/model_<元素>.xyz（新文件，不覆盖输入）
             add_atoms_ontop.txt（记录文件，表格形式，表头 # 开头 + 6 列，
             追加模式，位于脚本所在目录）
输出路径:    输出与输入同目录（各数字子文件夹内）；记录文件在脚本所在目录
示例:
  python add_atoms_ontop.py ./HLi1-30                        # 随机模式(默认)撒 Li
  python add_atoms_ontop.py ./HLi1-30 -che -e Na -cov 0.25   # 棋盘模式撒 Na (覆盖度 25%)
  python add_atoms_ontop.py ./HLi1-30 -sub Mo -hei 2.5 -s 42 # 自定义高度/种子 (随机模式)
注意:        撒点规则：撒入原子 x/y 与基底原子相同，z = 基底原子 z + 高度（单侧
             表面）；撒入原子追加在原子列表末尾；原结构不动、输出新文件；随机
             模式固定种子保证可复现；棋盘模式要求方形超胞（文件夹名 = 超胞倍数
             n，基底原子数须为 n×n）且棋盘格撒点数 = ceil(基底数 × 覆盖度)；
             已含撒入元素的子文件夹自动跳过（防止重复撒入）；原脚本
             add_li_ontop.py 保留不动
# 目录树示例:
# ============================================================================
# HLi1-30/                 # 根目录 (数字文件夹为超胞倍数)
# ├── 2/
# │   ├── model.xyz        # 输入: 原始结构 (不改动)
# │   └── model_Li.xyz     # 输出: 撒 Li 后的新结构
# ├── 3/
# │   ├── model.xyz
# │   └── model_Li.xyz
# └── ...
# ============================================================================
作者:        Qoder
最后修改日期: 2026-09-10
=============================================================================
"""

import datetime
import math
import os
import sys
import unicodedata

# ============================== 参数配置区 =====================================
INPUT_PATH   = "./"                # 根目录寻找路径 (相对脚本所在目录)：其下数字命名子文件夹为处理对象
INPUT_FILES  = ["model.xyz"]       # 输入文件 (各数字子文件夹内)
OUTPUT_FILES = ["model_{el}.xyz"]  # 输出文件 (新文件；{el} 替换为撒入元素，原结构不动)
RECORD_FILE  = "add_atoms_ontop.txt"  # 记录文件 (脚本所在目录；追加模式：首次创建写表头，后续运行追加)
DEFAULT_MODE = "random"            # 默认撒原子模式: random(随机) / checker(棋盘)
ELEMENT      = "Li"                # 撒入元素符号 (默认 Li)
SUBSTRATE    = "Mo"                # 基底元素符号 (顶位吸附对象，默认 Mo)
COVERAGE     = 0.5                 # 覆盖度：撒入数 = ceil(基底原子数 × COVERAGE)
HEIGHT       = 2.0                 # 吸附高度 (Å)：撒入原子 z = 基底原子 z + HEIGHT
RANDOM_SEED  = 0                   # 随机模式种子 (固定默认值保证可复现)
GRID_TOL     = 1e-3                # 棋盘模式胞位索引换算容差：|分数坐标 × 胞倍数 - 最近整数| 上限
# =============================================================================

# ============================== 环境准备区 =====================================
# 终端 locale 可能非 UTF-8 (如 POSIX/C)，强切 UTF-8，避免中文/emoji 输出报错
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

try:
    import numpy as np
    from ase import Atoms
    from ase.data import atomic_numbers
    from ase.io import read, write
except ImportError:
    print("❌ 错误: 未找到 ASE / numpy (Python 库)。请安装: pip install ase")
    sys.exit(1)
# ===========================================================================


# ============================== 函数配置区 =====================================
def resolve_cmd_path(script_dir, p):
    """解析命令行路径: 绝对路径照旧；./ 或 ../ 开头相对当前运行目录；
    不带点开头的相对路径相对脚本所在目录。返回绝对路径。"""
    if os.path.isabs(p):
        return os.path.abspath(p)
    if p.startswith(("./", "../")) or p in (".", ".."):
        return os.path.abspath(os.path.join(os.getcwd(), p))
    return os.path.normpath(os.path.join(script_dir, p))


def parse_args(argv):
    """解析命令行参数 (选项位置随意)：位置参数为根目录 (至多一个)；
    模式选项 -ran/--random 与 -che/--checker 互斥；-e/--element、
    -sub/--substrate、-cov/--coverage、-hei/--height、-s/--seed 为撒原子
    参数；-y/--yes 跳过确认，-h/--help 显示帮助。
    返回 (根目录或 None, 模式或 None, 选项字典, 是否跳过确认)。"""
    root, mode, yes = None, None, False
    opts = {"element": None, "substrate": None, "coverage": None,
            "height": None, "seed": None}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        elif arg in ("-ran", "--random", "-che", "--checker"):
            new_mode = "random" if arg in ("-ran", "--random") else "checker"
            if mode is not None and mode != new_mode:
                print("❌ 错误: 模式选项互斥，-ran/--random 与 -che/--checker "
                      "只能指定一个。")
                sys.exit(1)
            mode = new_mode
            i += 1
        elif arg in ("-e", "--element", "-sub", "--substrate"):
            key = "element" if arg in ("-e", "--element") else "substrate"
            label = "-e/--element" if key == "element" else "-sub/--substrate"
            if i + 1 >= len(argv):
                print(f"❌ 错误: 选项 {label} 需要一个元素符号。")
                sys.exit(1)
            value = argv[i + 1].strip()
            if value not in atomic_numbers:
                print(f"❌ 错误: {label} 收到无效元素符号: '{value}'")
                sys.exit(1)
            opts[key] = value
            i += 2
        elif arg in ("-cov", "--coverage"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -cov/--coverage 需要一个数值 (0, 1]。")
                sys.exit(1)
            try:
                coverage = float(argv[i + 1])
            except ValueError:
                print(f"❌ 错误: -cov/--coverage 需要数值，收到: {argv[i + 1]}")
                sys.exit(1)
            if not 0 < coverage <= 1:
                print(f"❌ 错误: 覆盖度须在 (0, 1] 内，收到: {coverage}")
                sys.exit(1)
            opts["coverage"] = coverage
            i += 2
        elif arg in ("-hei", "--height"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -hei/--height 需要一个数值 (Å)。")
                sys.exit(1)
            try:
                height = float(argv[i + 1])
            except ValueError:
                print(f"❌ 错误: -hei/--height 需要数值，收到: {argv[i + 1]}")
                sys.exit(1)
            if height <= 0:
                print(f"❌ 错误: 吸附高度须为正数，收到: {height}")
                sys.exit(1)
            opts["height"] = height
            i += 2
        elif arg in ("-s", "--seed"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -s/--seed 需要一个整数。")
                sys.exit(1)
            try:
                seed = int(argv[i + 1])
            except ValueError:
                print(f"❌ 错误: -s/--seed 需要整数，收到: {argv[i + 1]}")
                sys.exit(1)
            opts["seed"] = seed
            i += 2
        elif arg in ("-y", "--yes"):
            yes = True
            i += 1
        elif arg.startswith("-"):
            print(f"❌ 错误: 无法识别的选项 '{arg}'。")
            print("用法: python add_atoms_ontop.py [根目录] [-ran|-che] "
                  "[-e 元素] [-sub 元素] [-cov 覆盖度] [-hei 高度] [-s 种子] [-y] [-h]")
            sys.exit(1)
        else:
            if root is not None:
                print(f"❌ 错误: 根目录参数只能有一个，收到: '{root}' 与 '{arg}'")
                sys.exit(1)
            root = arg
            i += 1
    return root, mode, opts, yes


def dw(text):
    """返回字符串的终端显示宽度 (东亚全角字符按 2 列计)。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def pad(text, width, align="<"):
    """按显示宽度补齐字符串 (中文按 2 列计)，用于终端表格对齐。"""
    space = " " * max(0, width - dw(text))
    return text + space if align == "<" else space + text


def random_top_sites(atoms, substrate, count, seed):
    """随机模式: 从全部基底原子中不放回随机选取 count 个索引 (升序返回)，
    作为撒点顶位。设定种子保证结果可复现。"""
    sites = [i for i, s in enumerate(atoms.get_chemical_symbols())
             if s == substrate]
    rng = np.random.default_rng(seed)
    picked = rng.choice(sites, size=count, replace=False)
    return sorted(int(i) for i in picked)


def checker_top_sites(atoms, substrate, n):
    """棋盘模式: 将每个基底原子的分数坐标换算为超胞胞位索引
    (u, v) = round(frac × n) mod n (浮点误差在胞边界回绕到 ≈1.0 时取模 n
    归一为 0)，取 (u+v) 为偶数的基底原子作顶位。换算超出容差或胞位重复时
    报错。返回顶位索引列表。"""
    frac = atoms.get_scaled_positions()
    symbols = atoms.get_chemical_symbols()
    sites, seen = [], set()
    for idx, sym in enumerate(symbols):
        if sym != substrate:
            continue
        fu = frac[idx][0] * n
        fv = frac[idx][1] * n
        ru = round(fu)
        rv = round(fv)
        if abs(fu - ru) > GRID_TOL or abs(fv - rv) > GRID_TOL:
            raise RuntimeError(f"{substrate}#{idx} 分数坐标不属于 {n}×{n} 规则胞位")
        u = ru % n
        v = rv % n
        if (u, v) in seen:
            raise RuntimeError(f"胞位 ({u}, {v}) 出现多个 {substrate}，无法确定撒点")
        seen.add((u, v))
        if (u + v) % 2 == 0:
            sites.append(idx)
    return sites


def sprinkle_ontop(atoms, sites, element, height):
    """在给定顶位 (基底原子索引) 正上方 height 处追加 element 原子：
    x/y 与基底原子相同，z = 基底原子 z + height，撒入原子追加在原子列表
    末尾。返回新 Atoms (原结构不动)。"""
    numbers = atoms.numbers.tolist()
    positions = atoms.get_positions().tolist()
    znum = atomic_numbers[element]
    for idx in sites:
        x, y, z = atoms.positions[idx]
        positions.append([x, y, z + height])
        numbers.append(znum)
    return Atoms(numbers=numbers, positions=positions,
                 cell=atoms.cell, pbc=atoms.pbc)


def process_folder(dirpath, n, in_name, out_name, mode, element, substrate,
                   coverage, height, seed):
    """处理单个数字子文件夹: 读取 model.xyz -> 按模式在基底原子顶位撒入
    element -> 写出新文件 (原结构不动)。返回 (状态, 基底数, 撒入数,
    总原子数, 说明)；状态为 ok/skip，结构异常抛 RuntimeError 归为失败。"""
    fpath = os.path.join(dirpath, in_name)
    if not os.path.isfile(fpath):
        return "skip", 0, 0, 0, f"缺少 {in_name}"
    atoms = read(fpath, format="extxyz")
    symbols = atoms.get_chemical_symbols()
    if element in symbols:
        return "skip", 0, 0, 0, f"已含 {element}（防止重复撒入）"
    if np.allclose(atoms.cell[:], 0):
        raise RuntimeError("无有效晶胞 (Lattice)")
    n_sub = symbols.count(substrate)
    if n_sub == 0:
        raise RuntimeError(f"结构中无基底元素 {substrate}")
    n_add = math.ceil(n_sub * coverage)     # 预期撒入数 (由覆盖度决定)
    if mode == "random":
        sites = random_top_sites(atoms, substrate, n_add, seed)
    else:                                   # checker (扩展点: 新撒点模式在此追加分支)
        if n_sub != n * n:
            raise RuntimeError(f"{substrate} 数 {n_sub} != {n}×{n}，非预期方形超胞")
        sites = checker_top_sites(atoms, substrate, n)
        if len(sites) != n_add:
            raise RuntimeError(
                f"棋盘格撒点数 {len(sites)} != 期望 ceil({n_sub}×{coverage})={n_add}")
    sub_z_max = max(atoms.positions[i][2]
                    for i, s in enumerate(symbols) if s == substrate)
    if min(atoms.positions[i][2] for i in sites) + height <= sub_z_max:
        raise RuntimeError(f"{element} 的 z 未严格大于 {substrate} 的 z")
    new = sprinkle_ontop(atoms, sites, element, height)
    write(os.path.join(dirpath, out_name), new, format="extxyz")
    return "ok", n_sub, len(sites), len(new), ""


def write_record(record_path, records, meta_line, root, out_name, element,
                 stats, total_add):
    """追加写记录文件 (表格形式): 文件首次创建时先写表头 (# 开头，列同终端
    表格)；随后追加本次运行参数行 (含时间戳)、根目录行、逐文件夹记录行
    (文件夹/基底数/撒入数/总原子/覆盖率/状态) 与末尾汇总行，空格分隔。"""
    first = not os.path.exists(record_path)
    header = ("# " + pad("文件夹", 8) + pad("基底数", 8, ">") + pad("撒入数", 8, ">")
              + pad("总原子", 10, ">") + pad("覆盖率", 10, ">") + "  状态")
    with open(record_path, "a", encoding="utf-8", newline="\n") as f:
        if first:
            f.write(header + "\n")
        f.write(f"# {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
                f"{meta_line}\n")
        f.write(f"# 根目录: {os.path.abspath(root)}\n")
        for name, n_sub, n_add, n_tot, status, note in records:
            row = (pad(name, 8) + pad(str(n_sub) if n_sub else "-", 8, ">")
                   + pad(str(n_add) if n_add else "-", 8, ">")
                   + pad(str(n_tot) if n_tot else "-", 10, ">")
                   + pad(f"{n_add / n_sub:.1%}" if n_sub else "-", 10, ">")
                   + f"  {status}" + (f" ({note})" if note else ""))
            f.write(row + "\n")
        f.write(f"# 汇总: 成功 {stats['ok']} 个 (共撒入 {element} {total_add} 个) | "
                f"跳过 {stats['skip']} 个 | 失败 {stats['fail']} 个\n")
        f.write(f"# 输出: 各子文件夹内 {out_name} (新文件，原结构不动)\n")


# ============================== 脚本工作区 =====================================
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cli_root, cli_mode, opts, yes = parse_args(sys.argv[1:])

    root = (resolve_cmd_path(script_dir, cli_root) if cli_root
            else os.path.normpath(os.path.join(script_dir, INPUT_PATH)))
    mode = cli_mode if cli_mode else DEFAULT_MODE
    element = opts["element"] if opts["element"] else ELEMENT
    substrate = opts["substrate"] if opts["substrate"] else SUBSTRATE
    coverage = opts["coverage"] if opts["coverage"] is not None else COVERAGE
    height = opts["height"] if opts["height"] is not None else HEIGHT
    seed = opts["seed"] if opts["seed"] is not None else RANDOM_SEED
    in_name = INPUT_FILES[0]
    out_name = OUTPUT_FILES[0].format(el=element)
    mode_name = {"random": "随机表面吸附", "checker": "棋盘表面吸附"}[mode]

    if not os.path.isdir(root):
        print(f"❌ 错误: 根目录不存在: {root}")
        sys.exit(1)

    folders = sorted([d for d in os.listdir(root)
                      if d.isdigit() and os.path.isdir(os.path.join(root, d))], key=int)
    print("=" * 70)
    print(f"📦 根目录: {os.path.abspath(root)}")
    if not folders:
        print("⚠️ 警告: 未找到数字命名的子文件夹，无需处理。")
        sys.exit(0)
    print(f"📦 数字子文件夹: {len(folders)} 个 ({folders[0]} ~ {folders[-1]})")
    print(f"ℹ️ 模式: {mode_name}，撒入 {element} @ 基底 {substrate} 顶位，"
          f"覆盖度 {coverage:.0%}，高度 {height:.2f} Å (单侧)")

    # 执行前确认（交互终端）；非交互终端或 -y 自动跳过
    if not yes:
        try:
            interactive = sys.stdin is not None and sys.stdin.isatty()
        except Exception:
            interactive = False
        if interactive:
            try:
                ans = input(f"共 {len(folders)} 个子文件夹将生成 {out_name} "
                            f"(撒 {element})，确认执行？[y/N/q] ").strip().lower()
            except EOFError:
                print("\n⚠️ 无法读取确认输入 (EOF)，已取消执行；"
                      "非交互执行请加 -y 跳过确认。")
                sys.exit(0)
            if ans == "q":
                print("ℹ️ 已取消。")
                sys.exit(0)
            if ans != "y":
                print("ℹ️ 已取消（未输入 y）。")
                sys.exit(0)
        else:
            print("ℹ️ 非交互终端，自动跳过执行前确认。")

    # 逐文件夹撒原子（新文件模式）
    header = (pad("文件夹", 8) + pad("基底数", 8, ">") + pad("撒入数", 8, ">")
              + pad("总原子", 10, ">") + pad("覆盖率", 10, ">") + "  状态")
    print("-" * 70)
    print(header)
    stats = {"ok": 0, "skip": 0, "fail": 0}
    total_add = 0
    records = []
    for name in folders:
        try:
            status, n_sub, n_add, n_tot, note = process_folder(
                os.path.join(root, name), int(name), in_name, out_name,
                mode, element, substrate, coverage, height, seed)
        except Exception as e:
            status, n_sub, n_add, n_tot, note = "fail", 0, 0, 0, str(e)
        stats[status] += 1
        tag = {"ok": "✅ 成功", "skip": "⚠️ 跳过", "fail": "❌ 失败"}[status]
        records.append((name, n_sub, n_add, n_tot,
                        {"ok": "成功", "skip": "跳过", "fail": "失败"}[status], note))
        if status == "ok":
            total_add += n_add
        row = (pad(name, 8) + pad(str(n_sub) if n_sub else "-", 8, ">")
               + pad(str(n_add) if n_add else "-", 8, ">")
               + pad(str(n_tot) if n_tot else "-", 10, ">")
               + pad(f"{n_add / n_sub:.1%}" if n_sub else "-", 10, ">")
               + f"  {tag}")
        print(row + (f" ({note})" if status != "ok" else ""))

    # 写记录文件 (脚本所在目录；追加模式) 并集中总结关键信息
    record_path = os.path.join(script_dir, RECORD_FILE)
    meta = (f"模式={mode_name} | 撒入={element} @ 基底={substrate} 顶位 | "
            f"覆盖度={coverage:.0%} | 高度={height:.2f} Å | 种子={seed}")
    write_record(record_path, records, meta, root, out_name, element,
                 stats, total_add)
    print("-" * 70)
    print("🎉 运行完成，总结:")
    print(f"  模式: {mode_name}，撒入 {element} @ 基底 {substrate} 顶位，"
          f"高度 {height:.2f} Å")
    print(f"  成功: {stats['ok']} 个文件夹 (共撒入 {element} {total_add} 个)")
    print(f"  跳过: {stats['skip']} 个  失败: {stats['fail']} 个")
    print(f"  输出: 各子文件夹内 {out_name} (新文件，原结构不动)")
    print(f"  记录文件: {os.path.abspath(record_path)} (追加模式)")
    print(f"  根目录: {os.path.abspath(root)}")
    print("=" * 70)
    sys.exit(1 if stats["fail"] else 0)


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
