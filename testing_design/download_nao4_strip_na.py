"""
=============================================================================
脚本:        download_nao4_strip_na.py
分类:        数据下载脚本
功能:        从 Materials Project 检索含 Na 和 O 的四元化合物（带隙高于阈值、
             热力学稳定），剔除含黑名单元素（过渡金属/卤素/碱金属/放射性等）
             的化合物，下载剩余结构并去除 Na 后输出 VASP POSCAR 文件，
             同时生成 MP ID 清单记录文件；下载失败自动重试（默认 3 次）。
使用方法:    python download_nao4_strip_na.py                  # 使用配置区参数（默认）
             python download_nao4_strip_na.py -o ./my_dir      # 指定输出目录
参数:        -h/--help       显示脚本说明并退出（退出码 0）
             -o/--outdir     输出目录：以 ./、../ 或 . 开头的相对路径相对当前
                             运行目录解析；不带点开头的相对路径相对脚本所在目录
                             解析；绝对路径照旧。省略时输出到脚本所在目录下
                             nao4_strip_na/ 子文件夹
输入文件:    无（结构数据通过 Materials Project API 在线检索下载）
输出文件:    xxx.vasp        去除 Na 后的结构文件（按 MP ID 命名，第一行注释为 MP ID）
             download.log   记录文件（表格：帧序号 0 起、MP ID、化学式、去 Na 后
                            元素；末尾附查询条件、剔除与失败明细）
输出路径:    脚本所在目录下 nao4_strip_na/ 子文件夹（可用 -o 指定）
作者:        隼蝶.
最后修改日期: 2026-09-01
=============================================================================
"""
"""
环境需求:
  - mp-api
  - pymatgen
  - tqdm
"""
from mp_api.client import MPRester
from pymatgen.core import Element
from pymatgen.io.vasp import Poscar
from tqdm import tqdm
import os
import sys

# ============================== 参数配置区 =====================================
API_KEY = "phIhLdfYcgsRVUPsd2IPE3UYxLGPUxJM"  # Materials Project API Key，分享脚本时请删除/替换为自己的
ELEMENTS_INCLUDE = ["Na", "O"]                # 必须同时包含的元素（AND 语义）
NELEMENTS = 4                                 # 元素种类数（如 4 = 四元化合物）
BAND_GAP_MIN = 2.0                            # 带隙下限（eV），低于该值剔除
E_ABOVE_HULL_MAX = 0.1                        # 能量高于凸包上限（eV/原子），高于该值（不稳定）剔除
EXCLUDE_ELEMENTS = [                          # 黑名单元素：含任一元素的化合物剔除
    "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "H", "S", "F", "Cl", "Br", "I", "N",
    "Li", "K", "Ac", "Th", "U", "Pa", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es",
    "Fm", "Md", "No", "Lr", "Fr", "Po", "At", "Rn", "Tc", "Ra", "As", "Hg", "Be",
    "Tl",
]
STRIP_ELEMENT = "Na"                          # 输出前从结构中去除的元素
RETRY_TIMES = 3                               # 单个结构下载失败自动重试次数
SAVE_PATH = "./nao4_strip_na/"                # 输出目录（相对脚本所在目录；-o 命令行优先）
RECORD_FILE = "download.log"                  # 记录文件（输出目录内）
# ==============================================================================

# ============================== 环境准备区 =====================================
# Windows 控制台默认 GBK 无法输出 Å/emoji 等字符，统一切换 UTF-8（参考脚本设计规范）
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
# ==============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # 脚本所在目录（脚本自定位）


# ============================== 函数配置区 =====================================
def resolve_outdir(raw):
    """解析输出目录：绝对路径或 . 开头相对当前运行目录，其余相对脚本目录"""
    if raw is None:
        return os.path.join(SCRIPT_DIR, "nao4_strip_na")
    if os.path.isabs(raw) or raw.startswith("."):
        return raw
    return os.path.join(SCRIPT_DIR, raw)


def normalize_elements(elements):
    """规范化元素符号并校验有效性（如 "na" -> "Na"），无效时抛出异常"""
    result = []
    for e in elements:
        try:
            result.append(Element(e).symbol)
        except Exception:
            result.append(Element(str(e).capitalize()).symbol)
    return result


def doc_elements(doc):
    """提取检索结果文档的元素符号集合"""
    return {getattr(el, "symbol", str(el)) for el in (getattr(doc, "elements", None) or [])}


def search_docs(mpr, elements, num_elements, band_gap_min, e_above_hull_max):
    """按元素、元素数、带隙与凸包条件检索化合物文档列表"""
    return mpr.materials.summary.search(
        elements=elements,
        num_elements=(num_elements, num_elements),  # 元素种类数范围，相等即精确匹配
        band_gap=(band_gap_min, 100.0),             # 带隙区间，上限 100 eV 视为无上界
        energy_above_hull=(0.0, e_above_hull_max),  # 凸包能量区间，下限 0 为最低值
        fields=["material_id", "formula_pretty", "elements", "composition"],
    )


def download_and_strip(mpr, mp_id, strip_element, save_dir):
    """下载结构、去除指定元素并排序写入 POSCAR，返回剩余元素串"""
    structure = mpr.materials.get_structure_by_material_id(mp_id)
    structure.remove_species([strip_element])
    structure = structure.get_sorted_structure(reverse=True)
    Poscar(structure, comment=str(mp_id)).write_file(os.path.join(save_dir, f"{mp_id}.vasp"))
    return "-".join(el.symbol for el in structure.elements)
# ==============================================================================


# ============================== 脚本工作区 =====================================
def main():
    # 解析命令行参数（-h 显示帮助；-o 指定输出目录，命令行优先于配置区）
    outdir_arg = None
    if len(sys.argv) > 1:
        argv = sys.argv[1:]
        i = 0
        while i < len(argv):
            arg = argv[i]
            if arg in ("-h", "--help"):
                print(__doc__)  # 脚本说明只通过 -h/--help 展示
                sys.exit(0)
            elif arg in ("-o", "--outdir"):
                if i + 1 >= len(argv) or argv[i + 1].startswith("-"):
                    print("错误: -o/--outdir 后需指定输出目录，如: -o ./my_dir")
                    sys.exit(1)
                outdir_arg = argv[i + 1]
                i += 1
            else:
                print(f"未知参数: {arg}（可用 -h/--help 查看脚本说明）")
                sys.exit(1)
            i += 1

    # 元素规范化与有效性校验（配置区元素先规范化再用于查询/去除）
    try:
        elements_include = normalize_elements(ELEMENTS_INCLUDE)
        strip_element = normalize_elements([STRIP_ELEMENT])[0]
        exclude_set = {Element(e).symbol for e in EXCLUDE_ELEMENTS}
    except Exception as e:
        print(f"❌ 配置区元素名称无效: {e}")
        sys.exit(1)

    # 输出目录（-o 命令行优先，默认脚本目录下 nao4_strip_na/），覆盖模式直接写
    save_dir = resolve_outdir(outdir_arg)
    os.makedirs(save_dir, exist_ok=True)

    desc = (f"含 {'、'.join(elements_include)} 的 {NELEMENTS} 元化合物"
            f"（带隙 ≥ {BAND_GAP_MIN} eV、e_above_hull ≤ {E_ABOVE_HULL_MAX} eV/原子）")
    print(f"ℹ️ 正在检索 {desc} ...")
    with MPRester(API_KEY, mute_progress_bars=True) as mpr:
        docs = search_docs(mpr, elements_include, NELEMENTS, BAND_GAP_MIN, E_ABOVE_HULL_MAX)
        total = len(docs)
        print(f"ℹ️ 共检索到 {total} 个化合物")
        if total == 0:
            print("❌ 未找到符合条件的化合物，请调整配置区查询条件")
            sys.exit(0)

        # 剔除含黑名单元素的化合物（保持原有筛选逻辑）
        docs = [d for d in docs if not (doc_elements(d) & exclude_set)]
        excluded = total - len(docs)
        if excluded:
            print(f"⚠️ 已剔除含黑名单元素（{len(exclude_set)} 种）的化合物 {excluded} 个，剩余 {len(docs)} 个")
        if not docs:
            print("❌ 剔除黑名单后无剩余化合物")
            sys.exit(0)

        # 逐个下载结构 → 去除 Na → 排序写 POSCAR（失败自动重试，重试仍失败跳过）
        downloaded = []  # (mp_id, 化学式, 去Na后元素)
        failed = []      # (mp_id, 错误信息)
        success = 0
        pbar = tqdm(total=len(docs), desc="下载进度", unit="个")
        for doc in docs:
            mp_id = doc.material_id
            formula = getattr(doc, "formula_pretty", "")
            remain = None
            last_err = ""
            for attempt in range(1, RETRY_TIMES + 1):
                try:
                    remain = download_and_strip(mpr, mp_id, strip_element, save_dir)
                    break
                except Exception as e:
                    last_err = repr(e)
                    pbar.write(f"  ⚠️ {mp_id} 第 {attempt}/{RETRY_TIMES} 次下载失败: {last_err}")
            if remain is None:
                failed.append((mp_id, last_err))
                pbar.write(f"  ❌ {mp_id} 重试 {RETRY_TIMES} 次仍失败，已跳过该结构。")
            else:
                downloaded.append((mp_id, formula, remain))
                success += 1
            pbar.update(1)
        pbar.close()

        # 记录文件：表格形式（表头 # 开头，帧号 0 起），末尾附查询条件与失败明细
        downloaded.sort(key=lambda x: int(x[0].split("-")[1]))  # 按 MP ID 数字升序
        record_path = os.path.join(save_dir, RECORD_FILE)
        with open(record_path, "w", encoding="utf-8") as f:
            f.write(f"# {'帧':<6}{'MP ID':<16}{'化学式':<20}{'去Na后元素':>10}\n")
            for frame_idx, (mid, formula, remain) in enumerate(downloaded):
                f.write(f"{frame_idx:<7}{mid:<16}{formula:<20}{remain:>10}\n")
            f.write(f"\n检索条件: {desc}，共 {total} 个\n")
            f.write(f"剔除含黑名单元素 {len(exclude_set)} 种，剔除 {excluded} 个，剩余 {len(docs)} 个\n")
            f.write(f"成功下载并去除 {strip_element} 的结构 {success} 个，失败 {len(failed)} 个\n")
            if failed:
                f.write(f"\n以下 {len(failed)} 个结构重试 {RETRY_TIMES} 次仍失败，已跳过:\n")
                for mid, err in failed:
                    f.write(f"  {mid}: {err}\n")

        # 运行完毕总结关键信息（数量统计、输出路径绝对路径）
        print(f"\n🎉 完成！成功下载 {success}/{len(docs)} 个结构（去除 {strip_element} 后）")
        print(f"📦 输出目录: {os.path.abspath(save_dir)}")
        print(f"📄 记录文件: {os.path.abspath(record_path)}")
        if failed:
            print(f"❌ 失败 {len(failed)} 个: " + ", ".join(mid for mid, _ in failed))
# ==============================================================================


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
# ==============================================================================
