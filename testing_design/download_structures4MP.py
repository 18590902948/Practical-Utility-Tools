"""
=============================================================================
脚本:        download_structures4MP.py
分类:        数据下载脚本
功能:        从 Materials Project 数据库按化学式或元素组合批量检索下载
             材料结构（可筛选实验/理论/全部），输出 .vasp / .cif 文件，
             并生成合并 extxyz 文件与 MP ID 清单；下载失败自动重试
             （默认 3 次），重试仍失败则跳过并在终端与 download.log 记录原因。
使用方法:    python download_structures4MP.py                  # 使用配置区参数（默认）
             python download_structures4MP.py -for SiO2         # 化学式匹配
             python download_structures4MP.py -eoi Si O         # 仅包含设定元素
             python download_structures4MP.py -eal Si O         # 至少包含设定元素
             其余参数（模式、排除、下载等）与配置区默认值见下方说明，
             命令行参数优先于配置区（API_KEY 需在配置区设置）
参数:        -h/--help               显示脚本说明并退出（退出码 0）
             -exp/--experimental     仅下载实验结构（默认按配置区 DOWNLOAD_MODE）
             -exc/--exclude <化学式...>  排除指定化学式（约化式匹配）
模式参数:    -for/--formula <化学式>   化学式匹配（默认模式）
             -eoi/--elements-only-include <元素...>  仅包含设定元素
             -eal/--elements-at-least <元素...>      至少包含设定元素
             （模式互斥；不传时用配置区 MATCH_MODE，其余配置区参数
             如 ELEMENTS/EXCLUDE_FORMULAS/FORMAT/CELL_TYPE 等见脚本顶部）
输入文件:    无（结构数据通过 Materials Project API 在线检索下载）
输出文件:    xxx.vasp / xxx.cif   结构文件（按 MP ID 命名，vasp 第一行为 MP ID）
             xxx.xyz              合并 extxyz 文件（vasp 格式时生成，多帧，
                                 每帧属性行以 MP ID 开头，按 MP ID 升序）
             download.log         记录文件（MP ID 清单：首列帧序号 0 起对应
                                 ovito 帧索引，按 MP ID 升序，与 xyz 帧严格对应；
                                 末尾附重试后仍失败的 ID 及原因）
输出路径:    脚本所在目录下 <匹配标签>/ 子文件夹（for 模式为化学式如 SiO2；
             eoi/eal 模式为 "模式_元素" 如 eoi_Si-O、eal_Si-O）
作者:        Hongbo Sun
最后修改日期: 2026-08-26
=============================================================================
"""
"""
环境需求:
  - Python >= 3.11 (typing.NotRequired)
  - mp-api >= 0.44 (或 < 0.44 以兼容 Python 3.10)
  - pymatgen
  - ase（Structure.to_ase_atoms 转换依赖，生成合并的 extxyz 文件时使用）
"""
from mp_api.client import MPRester
from pymatgen.core import Element, Composition
from pymatgen.io.vasp import Poscar
from pymatgen.io.cif import CifWriter
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from tqdm import tqdm
import os
import sys

# ============ 环境准备 ============
# Windows 控制台默认 GBK 无法输出 Å/emoji 等字符，统一切换 UTF-8（参考脚本设计规范）
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
# ================================

# ============ 配置参数 ============
MATCH_MODE = "eoi"                        # 匹配模式三选一（值 = 英文缩写）:
                                          # "for" = formula，化学式匹配
                                          # "eoi" = elements only include，
                                          #        仅包含设定元素（元素集合恰好为设定元素）
                                          # "eal" = elements at least，
                                          #        至少包含设定元素
FORMULA = "Si"                            # 化学式（MATCH_MODE="for" 时生效）
ELEMENTS = ["Si", "O"]                    # 元素列表（元素匹配模式时生效）
EXCLUDE_FORMULAS = ["SiO2"]               # 需排除的化学式列表（按约化式匹配，如 ["SiO2"]
                                          # 会同时排除 Si2O4、Si3O6 等 SinO2n 组成），留空 [] 则不排除
DOWNLOAD_MODE = "all"                     # "all" / "experimental" / "theoretical"
RETRY_TIMES = 3                           # 单个结构下载失败自动重试次数（重试 3 次仍失败
                                          # 则跳过该结构，终端打印原因并写入 download.log）
FORMAT = "vasp"                           # 输出格式: "vasp" / "cif"
CELL_TYPE = "primitive"                   # "primitive" / "conventional"，原胞或惯用胞
CIF_SYMPREC = 0.01                         # CIF 对称性检测精度（Å），None 则不分析对称性
API_KEY = "Q1BIVhNaF1pwiU4NUwqscSV2uO4S1W8V"  # Materials Project API Key，分享脚本时请删除/替换为自己的
# ================================


def print_usage():
    """打印命令行用法说明（参数用错时提示）"""
    print("用法: python download_structures4MP.py                    # 用法1: 使用配置区参数")
    print("      python download_structures4MP.py -for <化学式>       # 用法2: 化学式匹配，如: -for SiO2")
    print("      python download_structures4MP.py -eoi <元素...>      # 用法3: 仅包含设定元素，如: -eoi Si O")
    print("      python download_structures4MP.py -eal <元素...>      # 用法4: 至少包含设定元素，如: -eal Si O")
    print("      选项后可加 -exp 仅下载实验结构 / -exc <化学式...> 排除指定化学式，如:")
    print("      python download_structures4MP.py -for Si -exp")
    print("      python download_structures4MP.py -eoi Si O -exc SiO2")

# ============ 命令行参数（可选，覆盖上方配置区） ============
# 选项形式（-缩写/--全称 成对支持），模式选项互斥，不传时用配置区 MATCH_MODE；
# 命令行指定时忽略配置区对应参数（命令行参数 > 配置区默认值）
if len(sys.argv) > 1:
    argv = sys.argv[1:]
    mode_opt = None        # 模式选项（-for/-eoi/-eal），互斥
    mode_values = []       # 模式选项后跟的参数（化学式或元素列表）
    exclude_values = None  # -exc 后跟的排除化学式（None 表示未指定 -exc）

    def is_option(arg):
        """判断是否为选项（以 - 开头）"""
        return arg.startswith("-")

    def take_values(idx):
        """收集 argv[idx] 之后直到下一个选项的所有参数，返回 (值列表, 新索引)"""
        values = []
        while idx + 1 < len(argv) and not is_option(argv[idx + 1]):
            idx += 1
            values.append(argv[idx])
        return values, idx

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            # 帮助: 显示脚本说明（头部注释块内容），以退出码 0 结束
            print(__doc__)
            sys.exit(0)
        elif arg in ("-for", "--formula"):
            if mode_opt is not None:
                print(f"错误: 模式选项互斥，不能同时指定 {mode_opt} 与 {arg}")
                print_usage()
                sys.exit(1)
            mode_opt = arg
            mode_values, i = take_values(i)
            if len(mode_values) != 1:
                print(f"{arg} 后需指定一个化学式，如: -for SiO2")
                print_usage()
                sys.exit(1)
        elif arg in ("-eoi", "--elements-only-include",
                     "-eal", "--elements-at-least"):
            if mode_opt is not None:
                print(f"错误: 模式选项互斥，不能同时指定 {mode_opt} 与 {arg}")
                print_usage()
                sys.exit(1)
            mode_opt = arg
            mode_values, i = take_values(i)
            if not mode_values:
                print(f"{arg} 后需指定至少一个元素，如: {arg} Si O")
                print_usage()
                sys.exit(1)
        elif arg in ("-exp", "--experimental"):
            DOWNLOAD_MODE = "experimental"  # 仅下载实验结构（忽略配置区 DOWNLOAD_MODE）
        elif arg in ("-exc", "--exclude"):
            if exclude_values is not None:
                print(f"{arg} 只能指定一次")
                print_usage()
                sys.exit(1)
            exclude_values, i = take_values(i)
            if not exclude_values:
                print(f"{arg} 后需指定至少一个化学式，如: -eoi Si O -exc SiO2")
                print_usage()
                sys.exit(1)
        else:
            print(f"未知参数: {arg}")
            print_usage()
            sys.exit(1)
        i += 1

    # 应用命令行结果（忽略配置区对应参数）
    if mode_opt is not None:
        if mode_opt in ("-for", "--formula"):
            MATCH_MODE = "for"
            FORMULA = mode_values[0]
        elif mode_opt in ("-eoi", "--elements-only-include"):
            MATCH_MODE = "eoi"
            ELEMENTS = mode_values
        else:  # -eal/--elements-at-least
            MATCH_MODE = "eal"
            ELEMENTS = mode_values
    # 命令行模式下 EXCLUDE_FORMULAS 不读取配置区：-exc 指定时用之，否则置空
    EXCLUDE_FORMULAS = exclude_values if exclude_values is not None else []
# ================================

if MATCH_MODE not in ("for", "eoi", "eal"):
    print(f"不支持的匹配模式: {MATCH_MODE}")
    print_usage()
    sys.exit(1)
if FORMAT not in ("vasp", "cif"):
    print(f"不支持的输出格式: {FORMAT}（可选 \"vasp\" / \"cif\"）")
    sys.exit(1)
if CELL_TYPE not in ("primitive", "conventional"):
    print(f"不支持的胞类型: {CELL_TYPE}（可选 \"primitive\" / \"conventional\"）")
    sys.exit(1)
EXT = FORMAT  # 文件扩展名

if MATCH_MODE != "for":
    if not ELEMENTS:
        print(f"元素匹配模式（MATCH_MODE=\"{MATCH_MODE}\"）下 ELEMENTS 不能为空，请配置元素列表")
        sys.exit(1)
    try:
        # 规范化元素符号（如 "si" -> "Si"），同时校验元素名称有效性
        # 新版 pymatgen 的 Element 对大小写敏感，小写输入时再尝试首字母大写
        normalized = []
        for e in ELEMENTS:
            try:
                normalized.append(Element(e).symbol)
            except Exception:
                normalized.append(Element(str(e).capitalize()).symbol)
        ELEMENTS = normalized
    except Exception:
        print(f"ELEMENTS 中包含无效元素名称: {ELEMENTS}")
        sys.exit(1)

# 规范化排除化学式（统一转为约化式，如 "Si2O4" -> "SiO2"），并校验有效性
# 约化式匹配意味着 "SiO2" 自动覆盖 Si2O4、Si3O6 等所有 SinO2n 组成
if EXCLUDE_FORMULAS:
    try:
        EXCLUDE_FORMULAS = [Composition(f).reduced_formula for f in EXCLUDE_FORMULAS]
    except Exception:
        print(f"EXCLUDE_FORMULAS 中包含无效化学式: {EXCLUDE_FORMULAS}（需规范大小写，示例: \"SiO2\"）")
        sys.exit(1)

# 匹配标签与搜索描述：for 模式用化学式；eoi/eal 模式用 "模式_元素" 命名文件夹
if MATCH_MODE == "for":
    LABEL = FORMULA
    SEARCH_DESC = f"{FORMULA} 的化学式匹配"
elif MATCH_MODE == "eoi":
    # 文件夹命名: eoi_元素（元素用 "-" 连接），如 eoi_Si-O
    LABEL = f"eoi_{'-'.join(ELEMENTS)}"
    SEARCH_DESC = f"{'-'.join(ELEMENTS)} 的元素匹配（仅包含设定元素）"
else:  # eal
    # 文件夹命名: eal_元素（元素用 "-" 连接），如 eal_Si-O
    LABEL = f"eal_{'-'.join(ELEMENTS)}"
    SEARCH_DESC = f"{'-'.join(ELEMENTS)} 的元素匹配（至少包含设定元素）"

# 下载模式描述（写入 download.log 最后一行）
if MATCH_MODE == "for":
    MODE_DESC = f"下载模式: for（化学式匹配 {FORMULA}）"
elif MATCH_MODE == "eoi":
    MODE_DESC = f"下载模式: eoi（仅包含设定元素 {', '.join(ELEMENTS)}）"
else:  # eal
    MODE_DESC = f"下载模式: eal（至少包含设定元素 {', '.join(ELEMENTS)}）"

EXCLUDE_DESC = ""  # 排除化学式描述（启用排除过滤时填充，写入 download.log）

SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), LABEL)

os.makedirs(SAVE_DIR, exist_ok=True)

with MPRester(API_KEY, mute_progress_bars=True) as mpr:
    # mute_progress_bars=True: 禁用 mp-api 内部分页检索进度条（Retrieving ... documents），
    # 脚本自己的下载进度条（“下载进度”）不受影响
    # 搜索所有匹配结构的 ID
    print(f"正在搜索 {SEARCH_DESC} 的结构...")
    if MATCH_MODE == "for":
        docs = mpr.materials.summary.search(
            formula=FORMULA,
            fields=["material_id", "formula_pretty", "theoretical", "elements", "composition"],
        )
    else:
        # elements 参数为 AND 语义：返回同时包含所有设定元素的结构（可含其他元素），
        # 天然满足"至少包含"模式；"仅包含"模式在此基础上再本地过滤
        docs = mpr.materials.summary.search(
            elements=ELEMENTS,
            fields=["material_id", "formula_pretty", "theoretical", "elements", "composition"],
        )
        element_desc = "、".join(ELEMENTS)
        print(f"元素检索结果：MP 中同时含 {element_desc} 的结构共 {len(docs)} 个")
        if MATCH_MODE == "eoi":
            target = set(ELEMENTS)
            exact_docs = [
                d for d in docs
                if {getattr(el, "symbol", str(el)) for el in (getattr(d, "elements", None) or [])} == target
            ]
            print(f"其中仅包含设定元素（元素集合恰好为 {element_desc}）的结构 {len(exact_docs)} 个")
            docs = exact_docs

    # 排除指定化学式的结构（按约化式匹配，"SiO2" 自动覆盖 Si2O4、Si3O6 等 SinO2n 组成）
    if EXCLUDE_FORMULAS:
        exclude_set = set(EXCLUDE_FORMULAS)
        before = len(docs)
        docs = [d for d in docs if d.composition.reduced_formula not in exclude_set]
        excluded = before - len(docs)
        EXCLUDE_DESC = f"排除化学式: {'、'.join(sorted(exclude_set))}（共排除 {excluded} 个）"
        if excluded > 0:
            print(f"已排除化学式为 {'、'.join(sorted(exclude_set))} 的结构 {excluded} 个")

    total = len(docs)
    if total == 0:
        print(f"未找到 {SEARCH_DESC} 的任何结构")
        sys.exit(0)

    # 根据 DOWNLOAD_MODE 过滤（theoretical=False 表示实验结构，None 不参与过滤）
    if DOWNLOAD_MODE == "experimental":
        docs = [d for d in docs if getattr(d, "theoretical", None) is False]
    elif DOWNLOAD_MODE == "theoretical":
        docs = [d for d in docs if getattr(d, "theoretical", None) is True]
    # "all" 不做过滤

    total = len(docs)
    if total == 0:
        print(f"当前模式 '{DOWNLOAD_MODE}' 下无可用结构")
        sys.exit(0)

    print(f"共检索到 {total} 个 {SEARCH_DESC} 结构（模式: {DOWNLOAD_MODE}），开始下载...\n")

    def mp_id_sort_key(item):
        """按 MP ID 数字部分升序排序（如 mp-1000 排在 mp-999 之前）"""
        return int(item[0].split("-")[1])

    downloaded = []  # (mp_id, is_experimental)
    failed = []      # (mp_id, 错误信息)
    xyz_frames = []  # 收集 (mp_id, ase Atoms) 帧，用于生成合并的 extxyz 文件（FORMAT="vasp" 时）
    success = 0
    pbar = tqdm(total=total, desc="下载进度", unit="个")
    for doc in docs:
        mp_id = doc.material_id
        is_exp = getattr(doc, "theoretical", None) is False  # theoretical=False 表示实验结构

        # 下载失败自动重试: 每次失败在终端打印原因并提示重试，重试 RETRY_TIMES
        # 次仍失败则跳过该结构（不影响其余结构下载），原因同时写入 download.log
        structure = None
        last_err = ""
        for attempt in range(1, RETRY_TIMES + 1):
            try:
                structure = mpr.materials.get_structure_by_material_id(mp_id)
                break
            except Exception as e:
                last_err = repr(e)
                pbar.write(f"  ⚠️ {mp_id} 第 {attempt}/{RETRY_TIMES} 次下载失败: {last_err}")
                if attempt < RETRY_TIMES:
                    pbar.write(f"     自动重试中（第 {attempt + 1}/{RETRY_TIMES} 次）...")

        if structure is None:
            # 重试次数耗尽: 跳过该结构，终端明确说明
            failed.append((mp_id, last_err))
            pbar.write(f"  ❌ {mp_id} 重试 {RETRY_TIMES} 次仍失败，已跳过该结构。")
            pbar.set_postfix_str(f"{mp_id} 失败跳过")
        else:
            try:
                if CELL_TYPE == "conventional":
                    # 用 SpacegroupAnalyzer 在本地转换为惯用胞（兼容旧版 mp-api）
                    structure = SpacegroupAnalyzer(
                        structure, symprec=0.01
                    ).get_conventional_standard_structure()

                filename = f"{mp_id}.{EXT}"
                file_path = os.path.join(SAVE_DIR, filename)

                if FORMAT == "cif":
                    CifWriter(structure, symprec=CIF_SYMPREC).write_file(file_path)
                else:
                    # 第一行注释写 MP ID，便于分辨每个 .vasp 对应的 MP 结构
                    Poscar(structure, comment=str(mp_id)).write_file(file_path)
                    # 同时收集 (mp_id, 结构转 ase Atoms)，用于最后生成合并的 extxyz 文件
                    xyz_frames.append((mp_id, structure.to_ase_atoms()))

                downloaded.append((mp_id, is_exp))
                success += 1
                pbar.set_postfix_str(mp_id)
            except Exception as e:
                failed.append((mp_id, repr(e)))
                pbar.set_postfix_str(f"{mp_id} 失败")
        pbar.update(1)

    pbar.close()
    print(f"\n完成！成功下载 {success}/{total} 个 .{EXT} 文件到 {SAVE_DIR}")

    # 输出格式为 vasp 时，将所有成功下载的结构合并写入一个 extxyz 文件；
    # 帧按 MP ID 升序排列（与 download.log 帧序号严格对应），每帧属性行以 MP ID 开头
    if FORMAT == "vasp" and xyz_frames:
        xyz_frames.sort(key=mp_id_sort_key)
        xyz_path = os.path.join(SAVE_DIR, f"{LABEL}.xyz")
        # 按项目标准 extxyz 格式手写（参考 classic_data/xyz_format/example.extxyz）
        with open(xyz_path, "w", encoding="utf-8") as f:
            for mid, atoms in xyz_frames:
                cell = atoms.cell[:]
                lattice = " ".join(f"{v:.8f}" for row in cell for v in row)
                f.write(f"{len(atoms)}\n")
                f.write(f'{mid} Lattice="{lattice}" Properties=species:S:1:pos:R:3 pbc="T T T"\n')
                for sym, pos in zip(atoms.get_chemical_symbols(), atoms.positions):
                    f.write(f"{sym:<2} {pos[0]:.8f} {pos[1]:.8f} {pos[2]:.8f}\n")
        print(f"已将 {len(xyz_frames)} 个结构合并写入 {xyz_path}（帧按 MP ID 升序，属性行含 MP ID）")

    # 汇总下载失败的 ID 及原因（重试后仍失败），便于排查
    if failed:
        print(f"以下 {len(failed)} 个结构重试 {RETRY_TIMES} 次仍失败，已跳过:")
        for mid, err in failed:
            print(f"  {mid}: {err}")

    # 输出 MP ID 清单：首列为帧序号（0 起，对应 ovito 中 xyz 的帧索引），
    # 按 MP ID 升序排列（与 xyz 帧顺序严格对应），第二列标注实验结构；末尾附统计与下载模式
    list_path = os.path.join(SAVE_DIR, "download.log")
    downloaded.sort(key=mp_id_sort_key)
    exp_count = sum(1 for _, is_exp in downloaded if is_exp)
    theo_count = success - exp_count
    with open(list_path, "w", encoding="utf-8") as f:
        f.write(f"# {'帧':<5}{'MP ID':<15}{'类型':>8}\n")
        for frame_idx, (mid, is_exp) in enumerate(downloaded):
            marker = "实验" if is_exp else ""
            f.write(f"{frame_idx:<6}{mid:<15}{marker:>8}\n")
        f.write(f"\n共 {success} 个结构：理论 {theo_count} 个，实验 {exp_count} 个\n")
        if EXCLUDE_DESC:
            f.write(f"{EXCLUDE_DESC}\n")
        f.write(f"{MODE_DESC}\n")
        if failed:
            # 重试后仍失败的结构写入 log，与终端说明保持一致
            f.write(f"\n以下 {len(failed)} 个结构重试 {RETRY_TIMES} 次仍失败，已跳过:\n")
            for mid, err in failed:
                f.write(f"  {mid}: {err}\n")
    print(f"下载日志已保存至 {list_path}（帧序号与 xyz 帧严格对应）")
    print(f"共下载 {success} 个结构：理论 {theo_count} 个，实验 {exp_count} 个")
