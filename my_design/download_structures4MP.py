"""
=============================================================================
脚本:        download_structures4MP.py
分类:        格式转换脚本（数据下载）
功能:        从 Materials Project 数据库按化学式或元素组合批量检索并下载
             材料结构；支持三种匹配模式：化学式匹配、元素匹配（仅包含设
             定元素）、元素匹配（至少包含设定元素）；可按约化式排除指定
             化学式（如 SiO2，同时覆盖 Si2O4、Si3O6 等 SinO2n 组成）；
             可筛选实验结构/理论结构/全部，支持 .vasp / .cif 两种输出格
             式；输出 vasp 格式时同时将所有结构合并生成一个 extxyz 文件；
             并生成 MP ID 清单。
使用方法:    python download_structures4MP.py                   # 用法1: 使用配置区参数
             python download_structures4MP.py for <化学式>       # 用法2: 化学式匹配（命令行指定）
             python download_structures4MP.py eoi <元素...>      # 用法3: 仅包含设定元素（命令行指定）
             python download_structures4MP.py eal <元素...>      # 用法3: 至少包含设定元素（命令行指定）
             模式参数后可加 exclude <化学式...> 排除指定化学式（约化式匹配）
             示例: for SiO2 / eoi Si O / eal Si O / eoi Si O exclude SiO2
             命令行指定时忽略配置区 MATCH_MODE/FORMULA/ELEMENTS/EXCLUDE_FORMULAS
参数:        需在脚本顶部配置:
             MATCH_MODE      匹配模式三选一:
                             "for"  化学式匹配（formula）
                             "eoi"  元素匹配（elements only include，
                                    仅包含设定元素，结构元素恰好为设定元素）
                             "eal"  元素匹配（elements at least，
                                    至少包含设定元素）
             FORMULA         化学式（MATCH_MODE="for" 时生效，如 "Si"）
             ELEMENTS        元素列表（元素匹配模式时生效，如 ["Si", "O"]）
             EXCLUDE_FORMULAS 需排除的化学式列表（按约化式匹配，如 ["SiO2"]
                             同时排除 Si2O4、Si3O6 等 SinO2n 组成），
                             留空 [] 则不排除
             DOWNLOAD_MODE   "experimental" / "theoretical" / "all"
             FORMAT          输出格式 "vasp" / "cif"
             CELL_TYPE       "primitive" / "conventional"，原胞或惯用胞
             CIF_SYMPREC     CIF 对称性检测精度（Å），None 则不分析对称性
             API_KEY         需在顶部配置 API Key（分享脚本时请删除/替换为自己的）
输出:
  所有文件保存在 <匹配标签>/ 子文件夹中（命名规则: for 模式为化学式如
  SiO2，eoi/eal 模式为 "模式_元素" 如 eoi_Si-O、eal_Si-O）:
  xxx.vasp / xxx.cif   下载的结构文件（按 MP ID 命名）
  xxx.xyz              合并的 extxyz 文件（FORMAT="vasp" 时生成，多帧）
  download.log         下载日志（MP ID 清单，末行含统计与下载模式）
作者:        Hongbo Sun
最后修改日期: 2026-08-22
=============================================================================
# 目录树示例:
# ============================================================================
# .                       # 脚本所在目录
# └── eoi_Si-O/           # 输出目录（按匹配标签命名：for 模式为化学式如 SiO2；
#                         # eoi/eal 模式为 "模式_元素"，如 eoi_Si-O、eal_Si-O；
#                         # 所有文件都在此）
#     ├── mp-1234567.vasp # 输出：下载的结构文件（按 MP ID 命名）
#     ├── mp-2345678.vasp # 输出：格式由 FORMAT 决定（vasp / cif）
#     ├── ...
#     ├── eoi_Si-O.xyz    # 输出：合并的 extxyz 文件（FORMAT="vasp" 时生成）
#     └── download.log    # 输出：下载日志（MP ID 清单 + 统计 + 下载模式）
# ============================================================================
"""
"""
环境需求:
  - Python >= 3.11 (typing.NotRequired)
  - mp-api >= 0.44 (或 < 0.44 以兼容 Python 3.10)
  - pymatgen
  - ase（生成合并的 extxyz 文件时使用）
"""
from mp_api.client import MPRester
from pymatgen.core import Element, Composition
from pymatgen.io.vasp import Poscar
from pymatgen.io.cif import CifWriter
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from ase.io import write as ase_write
from tqdm import tqdm
import os
import sys

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
FORMAT = "vasp"                           # 输出格式: "vasp" / "cif"
CELL_TYPE = "primitive"                   # "primitive" / "conventional"，原胞或惯用胞
CIF_SYMPREC = 0.01                         # CIF 对称性检测精度（Å），None 则不分析对称性
API_KEY = "Q1BIVhNaF1pwiU4NUwqscSV2uO4S1W8V"  # Materials Project API Key，分享脚本时请删除/替换为自己的
# ================================


def print_usage():
    """打印命令行用法说明（参数用错时提示）"""
    print("用法: python download_structures4MP.py                   # 用法1: 使用配置区参数")
    print("      python download_structures4MP.py for <化学式>       # 用法2: 化学式匹配，如: for SiO2")
    print("      python download_structures4MP.py eoi <元素...>      # 用法3: 仅包含设定元素，如: eoi Si O")
    print("      python download_structures4MP.py eal <元素...>      # 用法3: 至少包含设定元素，如: eal Si O")
    print("      模式参数后可加 exclude <化学式...> 排除指定化学式，如: python download_structures4MP.py eoi Si O exclude SiO2 SiO3")

# ============ 命令行参数（可选，覆盖上方配置区） ============
# 用法2/3: python 脚本名 模式 [化学式/元素...] [exclude 化学式...]
# 命令行指定时忽略配置区参数；含 exclude 时忽略配置区 EXCLUDE_FORMULAS，
# 不含 exclude 时 EXCLUDE_FORMULAS 置空（命令行模式下不读取配置区）
if len(sys.argv) > 1:
    argv = sys.argv[1:]
    if "exclude" in argv:
        # exclude 关键字之后的所有参数为需排除的化学式（约化式匹配）
        idx = argv.index("exclude")
        EXCLUDE_FORMULAS = argv[idx + 1:]
        if not EXCLUDE_FORMULAS:
            print("exclude 后需指定至少一个化学式，如: eoi Si O exclude SiO2")
            print_usage()
            sys.exit(1)
        argv = argv[:idx]
    else:
        EXCLUDE_FORMULAS = []
    if not argv:
        # exclude 位于首位（如 "exclude SiO2"）时 argv 会被切空，此时无匹配模式，视为用法错误
        print_usage()
        sys.exit(1)
    MATCH_MODE = argv[0]
    if MATCH_MODE == "for":
        if len(argv) != 2:
            print_usage()
            sys.exit(1)
        FORMULA = argv[1]
    elif MATCH_MODE in ("eoi", "eal"):
        if len(argv) < 2:
            print_usage()
            sys.exit(1)
        ELEMENTS = argv[1:]
    else:
        print_usage()
        sys.exit(1)
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

    downloaded = []  # (mp_id, is_experimental)
    failed = []      # (mp_id, 错误信息)
    xyz_frames = []  # 收集 ase Atoms，用于生成合并的 extxyz 文件（FORMAT="vasp" 时）
    success = 0
    pbar = tqdm(total=total, desc="下载进度", unit="个")
    for doc in docs:
        mp_id = doc.material_id
        is_exp = getattr(doc, "theoretical", None) is False  # theoretical=False 表示实验结构

        try:
            structure = mpr.materials.get_structure_by_material_id(mp_id)
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
                Poscar(structure).write_file(file_path)
                # 同时收集结构（转 ase Atoms），用于最后生成合并的 extxyz 文件
                xyz_frames.append(structure.to_ase_atoms())

            downloaded.append((mp_id, is_exp))
            success += 1
            pbar.set_postfix_str(mp_id)
        except Exception as e:
            failed.append((mp_id, repr(e)))
            pbar.set_postfix_str(f"{mp_id} 失败")
        finally:
            pbar.update(1)

    pbar.close()
    print(f"\n完成！成功下载 {success}/{total} 个 .{EXT} 文件到 {SAVE_DIR}")

    # 输出格式为 vasp 时，将所有成功下载的结构合并写入一个 extxyz 文件（参考 pos2exyz.py）
    if FORMAT == "vasp" and xyz_frames:
        xyz_path = os.path.join(SAVE_DIR, f"{LABEL}.xyz")
        ase_write(xyz_path, xyz_frames, format="extxyz")
        print(f"已将 {len(xyz_frames)} 个结构合并写入 {xyz_path}")

    # 汇总下载失败的 ID 及原因，便于排查
    if failed:
        print(f"以下 {len(failed)} 个结构下载失败:")
        for mid, err in failed:
            print(f"  {mid}: {err}")

    # 输出 MP ID 清单（第二列标注实验结构，右对齐并拉开间距；末尾附统计与下载模式）
    list_path = os.path.join(SAVE_DIR, "download.log")
    exp_count = sum(1 for _, is_exp in downloaded if is_exp)
    theo_count = success - exp_count
    with open(list_path, "w", encoding="utf-8") as f:
        for mid, is_exp in downloaded:
            marker = "实验" if is_exp else ""
            f.write(f"{mid:<15}{marker:>8}\n")
        f.write(f"\n共 {success} 个结构：理论 {theo_count} 个，实验 {exp_count} 个\n")
        if EXCLUDE_DESC:
            f.write(f"{EXCLUDE_DESC}\n")
        f.write(f"{MODE_DESC}\n")
    print(f"下载日志已保存至 {list_path}")
    print(f"共下载 {success} 个结构：理论 {theo_count} 个，实验 {exp_count} 个")
