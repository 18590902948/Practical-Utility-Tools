#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
脚本:        xsd2xyz.py
分类:        格式转换脚本
功能:        将 Materials Studio 导出的 XSD 结构文件转换为标准 extxyz 格式
             (model.xyz)，支持批量转换；元素按元素周期表顺序排序
             (Mo 在 Te 之前)，与后续扩胞/势函数训练流程兼容。
使用方法:    python xsd2xyz.py [输入xsd文件 ...] [选项]
参数:        输入xsd文件   输入 XSD 文件 (可多个，支持通配符；不指定时用配置区
                         INPUT_FILES；先按当前运行目录探测，不存在再相对脚本目录)
             -o/--output  输出文件完整路径或输出目录
                         (以 .xyz/.extxyz 结尾视为输出文件，否则视为输出目录；
                         默认: 配置区 OUTPUT_FILES/OUTPUT_PATH)
             -h/--help   显示本帮助
输入文件:    配置区 INPUT_FILES (默认 *.xsd，支持通配符)
输出文件:
  model.xyz            单个输入时默认输出名 (可 -o 自定义)
  <basename>.xyz       多个输入时自动按输入名输出，避免同名冲突
  xsd2xyz.txt          记录文件 (表格形式，表头#开头+5列，每次运行追加)
输出路径:    默认脚本所在目录 (OUTPUT_PATH)，可用 -o 指定 (相对/绝对路径均可)
示例:
  python xsd2xyz.py ./H/H.xsd
  python xsd2xyz.py ./H/H.xsd -o ./out/model.xyz
  python xsd2xyz.py *.xsd -o ./out
作者:        隼蝶.
最后修改日期: 2026-08-26
=============================================================================
# 目录树示例:
# ============================================================================
# .                       # 运行: python xsd2xyz.py A.xsd
# ├── A.xsd              # 输入：Materials Studio 结构文件
# ├── model.xyz          # 输出：extxyz 结构文件 (默认名，可 -o 自定义)
# └── xsd2xyz.txt        # 记录文件 (转换清单)
# ============================================================================
"""

import datetime
import glob
import math
import os
import re
import sys

# ============================== 参数配置区 =====================================
INPUT_FILES  = ["*.xsd"]                # 输入文件列表 (支持通配符，相对 INPUT_PATH 展开；命令行参数优先)
OUTPUT_FILES = ["model.xyz"]            # 输出文件列表 (单个输入时默认输出名，-o 可自定义；相对 OUTPUT_PATH)
RECORD_FILE  = "xsd2xyz.txt"            # 转换记录文件 (脚本所在目录，表格形式，每次运行追加)
INPUT_PATH   = "./"                     # 输入文件寻找路径 (相对脚本所在目录)
OUTPUT_PATH  = "./"                     # 输出文件寻找路径 (相对脚本所在目录)
RECORD_PATH_COL = 64                    # 记录文件路径列最小宽度 (保证列间分隔)
RECORD_HEADER   = ("# " + f"{'输入文件':<30}{'原子数':<8}"
                  f"{'输出路径':<{RECORD_PATH_COL}}{'事件':<8}状态\n")  # 记录文件表头
# =============================================================================

# ============================== 环境准备区 =====================================
# 终端 locale 可能非 UTF-8, 强制 stdout 用 UTF-8, 避免打印中文报错。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

try:
    from ase import Atoms
    from ase.io import write
except ImportError:
    print("❌ 错误: 未找到 ASE (Python 库)。请安装: pip install ase")
    sys.exit(1)
# ===========================================================================

# ============================== 函数配置区 =====================================
# 元素周期表顺序 (原子序数映射)，元素与原子块按此排序 (Mo 在 Te 之前)
ELEMENT_ORDER = {
    'H':1,'He':2,'Li':3,'Be':4,'B':5,'C':6,'N':7,'O':8,'F':9,'Ne':10,
    'Na':11,'Mg':12,'Al':13,'Si':14,'P':15,'S':16,'Cl':17,'Ar':18,
    'K':19,'Ca':20,'Sc':21,'Ti':22,'V':23,'Cr':24,'Mn':25,'Fe':26,'Co':27,
    'Ni':28,'Cu':29,'Zn':30,'Ga':31,'Ge':32,'As':33,'Se':34,'Br':35,'Kr':36,
    'Rb':37,'Sr':38,'Y':39,'Zr':40,'Nb':41,'Mo':42,'Tc':43,'Ru':44,'Rh':45,
    'Pd':46,'Ag':47,'Cd':48,'In':49,'Sn':50,'Sb':51,'Te':52,'I':53,'Xe':54,
    'Cs':55,'Ba':56,'La':57,'Ce':58,'Pr':59,'Nd':60,'Pm':61,'Sm':62,'Eu':63,
    'Gd':64,'Tb':65,'Dy':66,'Ho':67,'Er':68,'Tm':69,'Yb':70,'Lu':71,'Hf':72,
    'Ta':73,'W':74,'Re':75,'Os':76,'Ir':77,'Pt':78,'Au':79,'Hg':80,'Tl':81,
    'Pb':82,'Bi':83,'Po':84,'At':85,'Rn':86,'Fr':87,'Ra':88,'Ac':89,'Th':90,
    'Pa':91,'U':92,'Np':93,'Pu':94,'Am':95,'Cm':96,'Bk':97,'Cf':98,'Es':99,
    'Fm':100,'Md':101,'No':102,'Lr':103
}


def print_usage():
    """打印头部注释块 (脚本功能与完整使用方法)。"""
    print(__doc__)


def parse_args(argv):
    """解析命令行参数: 位置参数为输入 xsd 文件 (可多个)，-h/--help 显示帮助，
    -o/--output 指定输出文件完整路径或输出目录。返回 (输入文件列表, 输出参数)。"""
    inputs = []
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
        else:
            inputs.append(arg)
            i += 1
    return inputs, output


def expand_patterns(patterns, base_dir):
    """将文件模式列表展开为完整路径: 含通配符 (* ? [) 的按 glob 展开
    (相对 base_dir，结果排序)，无通配符的字面路径原样保留。"""
    files = []
    for p in patterns:
        if any(ch in p for ch in "*?["):
            files.extend(sorted(os.path.normpath(m)
                                for m in glob.glob(os.path.join(base_dir, p))))
        else:
            files.append(os.path.normpath(os.path.join(base_dir, p)))
    return files


def resolve_inputs(script_dir, cli_inputs):
    """解析输入文件列表: 命令行指定优先 (通配符先按当前运行目录展开，
    无匹配再相对脚本目录；字面路径先探测当前运行目录，不存在再相对脚本目录)；
    未指定时用配置区 INPUT_FILES 相对 INPUT_PATH 展开。
    返回存在的输入文件绝对路径列表。"""
    if cli_inputs:
        files = []
        for p in cli_inputs:
            if any(ch in p for ch in "*?["):
                matched = (sorted(glob.glob(p))
                           or sorted(glob.glob(os.path.join(script_dir, p))))
                files.extend(os.path.normpath(m) for m in matched)
            else:
                f = p if os.path.isfile(p) else os.path.join(script_dir, p)
                files.append(os.path.normpath(f))
        files = [f for f in files if os.path.isfile(f)]
        if not files:
            print(f"❌ 错误: 命令行指定的输入文件均不存在: {cli_inputs}")
            print("请确认输入 xsd 文件路径，或查看 -h/--help。")
            sys.exit(1)
        return [os.path.abspath(f) for f in files]
    base = os.path.normpath(os.path.join(script_dir, INPUT_PATH))
    files = [f for f in expand_patterns(INPUT_FILES, base) if os.path.isfile(f)]
    if not files:
        print(f"❌ 错误: 配置区 INPUT_FILES 未找到任何输入文件 "
              f"({INPUT_FILES}，路径 {base})。")
        print("请用命令行指定输入 xsd 文件，或查看 -h/--help。")
        sys.exit(1)
    return [os.path.abspath(f) for f in files]


def resolve_path(script_dir, p):
    """路径解析 (相对优先): 绝对路径照旧；带 ./、../ 或 . 开头的相对路径相对
    当前运行目录；不带点开头的相对路径默认相对脚本所在目录。返回绝对路径。"""
    if os.path.isabs(p):
        return os.path.abspath(p)
    if p.startswith("."):
        return os.path.abspath(os.path.join(os.getcwd(), p))
    return os.path.abspath(os.path.join(script_dir, p))


def resolve_outputs(script_dir, output, inputs):
    """解析输出路径并生成每个输入对应的输出文件绝对路径:
    -o 以 .xyz/.extxyz 结尾 → 单个输入时作为输出文件，多个输入时报错；
    -o 其他 / 省略 → 输出目录 (默认配置区 OUTPUT_PATH)，单个输入用配置区
    OUTPUT_FILES[0] 文件名，多个输入用 <basename>.xyz 避免同名冲突。
    返回 (输出目录绝对路径, 输出文件绝对路径列表)。"""
    n = len(inputs)
    if output is not None:
        out = resolve_path(script_dir, output)
        if out.lower().endswith((".xyz", ".extxyz")):
            if n > 1:
                print("❌ 错误: 多个输入文件不能指定单个输出文件 "
                      f"(-o {output})。")
                print("   请指定输出目录，如: -o ./out")
                sys.exit(1)
            return os.path.dirname(out), [out]
        outdir = out
    else:
        outdir = os.path.normpath(os.path.join(script_dir, OUTPUT_PATH))
    os.makedirs(outdir, exist_ok=True)
    out_files = []
    for src in inputs:
        if n == 1:
            name = OUTPUT_FILES[0]
        else:
            name = os.path.splitext(os.path.basename(src))[0] + ".xyz"
        out_files.append(os.path.join(outdir, name))
    return outdir, out_files


def parse_xsd(xsd_path):
    """解析 Materials Studio XSD 文件 (要求 P1 对称性，无对称操作)，
    返回 (晶格矩阵, 元素列表, 分数坐标列表)；元素按周期表顺序排序
    (Mo 在 Te 之前)。"""
    lattice_raw = []
    atominfo = []
    spacegroup = False
    with open(xsd_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "AVector" in line or "BVector" in line or "CVector" in line:
                for item in re.findall(r'Vector="(.*?)"', line, re.S):
                    lattice_raw.append([float(j) for j in item.split(",")])
            elif "Components" in line:
                atominfo.append(line)
            if '"P1"' in line:
                spacegroup = True
    if not spacegroup:
        raise ValueError("不支持带对称性的体系 "
                         "(请先在 Materials Studio 中 Build->Symmetry->Make P1)")
    if len(lattice_raw) != 3:
        raise ValueError("未读取到完整晶格信息 (AVector/BVector/CVector)")

    # 三斜晶格 → 笛卡尔行向量矩阵 (与 xsd2pos.py 一致)
    l1 = math.sqrt(lattice_raw[0][0]**2 + lattice_raw[0][1]**2 + lattice_raw[0][2]**2)
    l2 = math.sqrt(lattice_raw[1][0]**2 + lattice_raw[1][1]**2 + lattice_raw[1][2]**2)
    l3 = math.sqrt(lattice_raw[2][0]**2 + lattice_raw[2][1]**2 + lattice_raw[2][2]**2)
    alpha = math.acos((lattice_raw[1][0] * lattice_raw[2][0] +
                       lattice_raw[1][1] * lattice_raw[2][1] +
                       lattice_raw[1][2] * lattice_raw[2][2]) / (l2 * l3))
    beta = math.acos((lattice_raw[0][0] * lattice_raw[2][0] +
                      lattice_raw[0][1] * lattice_raw[2][1] +
                      lattice_raw[0][2] * lattice_raw[2][2]) / (l1 * l3))
    gamma = math.acos((lattice_raw[0][0] * lattice_raw[1][0] +
                       lattice_raw[0][1] * lattice_raw[1][1] +
                       lattice_raw[0][2] * lattice_raw[1][2]) / (l1 * l2))
    bc2 = l2**2 + l3**2 - 2 * l2 * l3 * math.cos(alpha)
    h1 = l1
    h2 = l2 * math.cos(gamma)
    h3 = l2 * math.sin(gamma)
    h4 = l3 * math.cos(beta)
    h5 = ((h2 - h4)**2 + h3**2 + l3**2 - h4**2 - bc2) / (2 * h3)
    h6 = math.sqrt(l3**2 - h4**2 - h5**2)
    lattice = [[h1, 0., 0.], [h2, h3, 0.], [h4, h5, h6]]

    elements = []
    frac = []
    for line in atominfo:
        comp = re.findall(r'Components="(.*?)"', line, re.S)
        if not comp:
            continue
        elements.append(comp[0])
        xyz = re.findall(r'XYZ="(.*?)"', line, re.S)
        coord = [float(j) for j in xyz[0].split(",")] if xyz else [0.0, 0.0, 0.0]
        if len(coord) != 3:
            raise ValueError(f"原子 {comp[0]} 坐标列数异常: {coord}")
        frac.append(coord)
    if not elements:
        raise ValueError("未读取到原子信息 (Components/XYZ 缺失)")

    # 元素与坐标按周期表顺序整体排序 (Mo 在 Te 之前)
    pairs = sorted(zip(elements, frac), key=lambda p: ELEMENT_ORDER.get(p[0], 999))
    elements = [p[0] for p in pairs]
    frac = [p[1] for p in pairs]
    return lattice, elements, frac


def convert_xsd_to_xyz(xsd_path, out_path):
    """转换单个 XSD 文件为 extxyz 格式并写入 out_path (覆盖模式)。
    返回原子数。"""
    lattice, elements, frac = parse_xsd(xsd_path)
    atoms = Atoms(symbols=elements, scaled_positions=frac,
                  cell=lattice, pbc=True)
    write(out_path, atoms, format="extxyz")
    return len(atoms)


def append_record(record_path, records):
    """将转换记录追加到记录文件 (表格形式，表头#开头): 首次创建时写表头，
    每次运行先写时间戳行，其后每行一条记录
    (输入文件/原子数/输出路径/事件/状态，空格分隔)。"""
    new_file = not os.path.exists(record_path)
    with open(record_path, "a", encoding="utf-8") as f:
        if new_file:
            f.write(RECORD_HEADER)
        f.write(f"# {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        for src, natom, out, event, status in records:
            # 输入文件/路径列用动态宽度，保证列间至少有 1 个分隔空格 (解析依赖)
            src_col = max(30, len(src) + 1)
            path_col = max(RECORD_PATH_COL, len(out) + 1)
            f.write(f"{src:<{src_col}}{natom:<8}{out:<{path_col}}"
                    f"{event:<8}{status}\n")
    print(f"✅ 已追加 {len(records)} 条记录到 {os.path.abspath(record_path)}。")


def print_summary(n_ok, n_fail, outdir, record_path):
    """运行完毕后集中总结关键信息 (成功/失败统计、输出与记录文件绝对路径)。"""
    print("=" * 52)
    print("🎉 运行完成，总结:")
    print(f"  成功:       {n_ok} 个")
    print(f"  失败:       {n_fail} 个")
    print(f"  输出目录:   {os.path.abspath(outdir)}")
    print(f"  记录文件:   {os.path.abspath(record_path)}")
    print("=" * 52)


# ============================== 脚本工作区 =====================================
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cli_inputs, output = parse_args(sys.argv[1:])
    record_path = os.path.join(script_dir, RECORD_FILE)

    inputs = resolve_inputs(script_dir, cli_inputs)
    print(f"ℹ️ 输入文件 {len(inputs)} 个:")
    for f in inputs:
        print(f"    {f}")

    outdir, outputs = resolve_outputs(script_dir, output, inputs)
    print(f"ℹ️ 输出目录: {os.path.abspath(outdir)}")

    print(f"📦 开始转换 {len(inputs)} 个 XSD 文件:")
    records = []
    n_ok = n_fail = 0
    for i, (src, dst) in enumerate(zip(inputs, outputs), 1):
        try:
            existed = os.path.exists(dst)
            if existed:
                print(f"  ℹ️ 提示: {dst} 已存在，将被覆盖。")
            natom = convert_xsd_to_xyz(src, dst)
            event = "覆盖" if existed else "新建"
            n_ok += 1
            print(f"  ✅ [{i}/{len(inputs)}] {os.path.basename(src)} "
                  f"-> {os.path.abspath(dst)} ({natom} 原子)")
            records.append((os.path.abspath(src), natom,
                            os.path.abspath(dst), event, "成功"))
        except Exception as e:
            n_fail += 1
            print(f"  ❌ [{i}/{len(inputs)}] {os.path.abspath(src)} "
                  f"转换失败: {e}")
            records.append((os.path.abspath(src), "-",
                            os.path.abspath(dst), "-", "失败"))

    append_record(record_path, records)
    print_summary(n_ok, n_fail, outdir, record_path)


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
