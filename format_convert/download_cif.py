"""
=============================================================================
脚本:        download_cif.py
分类:        格式转换脚本（数据下载）
功能:        从 Materials Project 数据库按化学式批量检索并下载材料结构；
             可筛选实验结构/理论结构/全部，保存为 .vasp 文件；
             同时生成 MP ID 清单文件。
使用方法:    python download_cif.py
参数:        需在脚本顶部配置:
             FORMULA         化学式（如 "Si"）
             DOWNLOAD_MODE   "experimental" / "theoretical" / "all"
             API Key 从环境变量 MP_API_KEY 读取（或修改脚本内 API_KEY）
输出:
  xxx.vasp            下载的结构文件（VASP POSCAR 格式）
  xxx_mp_ids.txt      MP ID 清单（含实验/理论标记）
作者:        Hongbo Sun
最后修改日期: 2026-08-20
=============================================================================
# 目录树示例:
# ============================================================================
# .                       # 脚本所在目录（下载保存位置）
# ├── 1234567.vasp       # 输出：下载的结构文件（VASP POSCAR 格式）
# ├── 2345678.vasp       # 输出：按 MP ID 编号命名
# ├── ...
# └── Si_mp_ids.txt      # 输出：MP ID 清单（含实验/理论标记）
# ============================================================================
"""
"""
环境需求:
  - Python >= 3.11 (typing.NotRequired)
  - mp-api >= 0.44 (或 < 0.44 以兼容 Python 3.10)
  - pymatgen
"""
from mp_api.client import MPRester
from pymatgen.io.vasp import Poscar
from tqdm import tqdm
import os
import sys

# ============ 配置参数 ============
FORMULA = "Si"                          # 化学式
DOWNLOAD_MODE = "experimental"          # "all" / "experimental" / "theoretical"
API_KEY = os.environ.get("MP_API_KEY") or "Q1BIVhNaF1pwiU4NUwqscSV2uO4S1W8V"
# ================================

SAVE_DIR = os.path.dirname(os.path.abspath(__file__))

os.makedirs(SAVE_DIR, exist_ok=True)

with MPRester(API_KEY) as mpr:
    # 搜索所有匹配结构的 ID
    print(f"正在搜索 {FORMULA} 的结构...")
    docs = mpr.materials.summary.search(
        formula=FORMULA,
        fields=["material_id", "formula_pretty", "theoretical"],
        num_chunks=1,
    )

    total = len(docs)
    if total == 0:
        print(f"未找到 {FORMULA} 的任何结构")
        sys.exit(0)

    # 根据 DOWNLOAD_MODE 过滤
    if DOWNLOAD_MODE == "experimental":
        docs = [d for d in docs if not getattr(d, "theoretical", True)]
    elif DOWNLOAD_MODE == "theoretical":
        docs = [d for d in docs if getattr(d, "theoretical", True)]
    # "all" 不做过滤

    total = len(docs)
    if total == 0:
        print(f"当前模式 '{DOWNLOAD_MODE}' 下无可用结构")
        sys.exit(0)

    print(f"共检索到 {total} 个 {FORMULA} 结构（模式: {DOWNLOAD_MODE}），开始下载...\n")

    downloaded = []  # (mp_id, is_experimental)
    success = 0
    pbar = tqdm(total=total, desc="下载进度", unit="个")
    for doc in docs:
        mp_id = doc.material_id
        is_exp = not getattr(doc, "theoretical", True)  # theoretical=False 表示实验结构

        try:
            structure = mpr.materials.get_structure_by_material_id(mp_id)

            num_part = mp_id.split("-")[-1]
            vasp_filename = f"{num_part}.vasp"
            vasp_path = os.path.join(SAVE_DIR, vasp_filename)

            Poscar(structure).write_file(vasp_path)
            downloaded.append((mp_id, is_exp))
            success += 1
            pbar.set_postfix_str(mp_id)
        except Exception as e:
            pbar.set_postfix_str(f"{mp_id} 失败")
        finally:
            pbar.update(1)

    pbar.close()
    print(f"\n完成！成功下载 {success}/{total} 个 .vasp 文件到 {SAVE_DIR}")

    # 输出 MP ID 清单（第二列标注实验结构）
    list_path = os.path.join(SAVE_DIR, f"{FORMULA}_mp_ids.txt")
    with open(list_path, "w") as f:
        for mid, is_exp in downloaded:
            marker = "\t实验" if is_exp else ""
            f.write(f"{mid}{marker}\n")
    print(f"MP ID 清单已保存至 {list_path}")
