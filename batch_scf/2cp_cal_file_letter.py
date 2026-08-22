"""
=============================================================================
脚本:        2cp_cal_file_letter.py
分类:        文件批量处理脚本
功能:        遍历a/b/c…字母分组目录下所有数字命名的子文件夹，将Y_VASP_file
             目录下的INCAR、POTCAR、*.sh任务提交脚本批量复制到各子任务目录；
             自动检测源文件是否齐全（缺失INCAR时自动创建默认INCAR），
             并校验POTCAR与POSCAR的元素顺序是否一致。
使用方法:    python 2cp_cal_file_letter.py
参数:        无参数，依赖脚本所在目录下的Y_VASP_file源目录及a/b/c分组目录结构
输出:
  */*/INCAR         复制到各子目录的VASP输入文件
  */*/POTCAR        复制到各子目录的赝势文件
  */*/sub2.sh       复制到各子目录的作业提交脚本
作者:        Hongbo Sun
最后修改日期: 2026‑08‑21
=============================================================================
# 目录树示例:
# ============================================================================
# .
# ├── 1xyz2poscar_letter.py
# ├── 2cp_cal_file_letter.py
# ├── Y_VASP_file/
# │   ├── INCAR
# │   ├── POTCAR
# │   └── sub2.sh
# ├── a/
# │   ├── 1/
# │   │   ├── POSCAR
# │   │   ├── INCAR
# │   │   ├── POTCAR
# │   │   └── sub2.sh
# │   ├── 2/
# │   │   └── ...
# │   └── ...
# └── b/
#     ├── 501/
#     │   └── ...
#     └── ...
# ============================================================================
"""
import os
import re
import sys
import glob
import shutil
import string

# Windows 控制台默认 GBK 编码无法输出 emoji，统一改用 UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# ============ 配置区（可按需调整） ============
# 默认INCAR模板：Y_VASP_file下不存在INCAR时自动创建，如需自定义请直接修改此模板。
# 注意：INCAR写入时强制LF换行（\n）、UTF-8无BOM编码，符合Linux VASP格式要求。
DEFAULT_INCAR = """ISTART =  0            (Not read existing wavefunction)
ISPIN  =  1            (Non-spin-polarized DFT)

ICHARG =  2            (Initial guess from superposition of atomic charge density)
LREAL  =  Auto         (Projection operators: automatic)
ENCUT  =  500          (Plane-wave cutoff energy in eV)

IVDW   =  12           (Many-body dispersion correction enabled)

LWAVE  = .FALSE.       (Do not write WAVECAR)
LCHARG = .FALSE.       (Do not write CHGCAR)

PREC     =  Normal
KGAMMA   = .TRUE.      # Gamma point only
KSPACING = 0.2        # Automatic k-point generation
ALGO     = Normal

# Static calculation
NSW    =   0
IBRION =  -1

EDIFF  =  1E-05        (Energy convergence, eV)
NELM   =  150          (Maximum SCF steps)

NCORE = 2
"""

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(SCRIPT_DIR, "Y_VASP_file")


def find_task_folders():
    """收集所有子任务文件夹：a/b/c…字母分组目录下的数字命名字文件夹"""
    folders = []
    for g in string.ascii_lowercase:
        group_path = os.path.join(SCRIPT_DIR, g)
        if not os.path.isdir(group_path):
            continue
        for sub in os.listdir(group_path):
            sub_path = os.path.join(group_path, sub)
            if sub.isdigit() and os.path.isdir(sub_path):
                folders.append(sub_path)
    return folders


def find_first_poscar(folders):
    """在所有子任务文件夹中查找第一个POSCAR（各帧第6行元素顺序一致，检测一个即可）"""
    for folder in folders:
        poscar = os.path.join(folder, "POSCAR")
        if os.path.exists(poscar):
            return poscar
    return None


def extract_potcar_elements(potcar_path):
    """提取POTCAR元素顺序：按'VRHFIN ='字段出现的先后顺序"""
    elements = []
    with open(potcar_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = re.search(r"VRHFIN\s*=\s*([A-Za-z]+)", line)
            if m:
                elements.append(m.group(1))
    return elements


def extract_poscar_elements(poscar_path):
    """提取POSCAR元素顺序：第6行（元素符号行）"""
    with open(poscar_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    if len(lines) < 6:
        return []
    return lines[5].split()


def main():
    # 1. 确保 Y_VASP_file 源目录存在
    if not os.path.isdir(SOURCE_DIR):
        os.makedirs(SOURCE_DIR)
        print(f"ℹ️  未检测到源目录 Y_VASP_file，已自动创建：{SOURCE_DIR}")
        print("    请将 INCAR、POTCAR 及任务提交脚本（*.sh）放入该目录后重新运行本脚本。")

    # 2. 检查 INCAR：缺失则自动创建默认INCAR（LF换行、UTF-8无BOM，符合Linux VASP格式）
    incar_path = os.path.join(SOURCE_DIR, "INCAR")
    if not os.path.exists(incar_path):
        with open(incar_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(DEFAULT_INCAR)
        print(f"⚠️  未检测到 INCAR 文件，已自动创建默认 INCAR：{incar_path}")
        print("    该默认 INCAR 采用 LF 换行、UTF-8 无 BOM 编码，可直接用于 Linux 环境 VASP 计算。")
        print("    如需自定义计算参数，请编辑并覆盖该默认 INCAR 后重新运行本脚本。")

    # 3. 检查 POTCAR 与 *.sh 任务提交脚本
    potcar_path = os.path.join(SOURCE_DIR, "POTCAR")
    sh_files = sorted(glob.glob(os.path.join(SOURCE_DIR, "*.sh")))
    missing = []
    if not os.path.exists(potcar_path):
        missing.append("POTCAR")
    if len(sh_files) == 0:
        missing.append("任务提交脚本（*.sh，如 sub2.sh）")
    if missing:
        print(f"❌ 源目录 Y_VASP_file 缺少以下必需文件：{'、'.join(missing)}")
        print("   请补齐上述文件后重新运行本脚本。")
        exit(1)

    # 4. 收集子任务文件夹并校验元素顺序
    folders = find_task_folders()
    if len(folders) == 0:
        print("❌ 未找到任何数字命名的子任务文件夹，请先运行 1xyz2poscar 脚本生成 POSCAR。")
        exit(1)

    poscar_path = find_first_poscar(folders)
    if poscar_path is None:
        print("❌ 未找到任何 POSCAR 文件，请先运行 1xyz2poscar 脚本生成 POSCAR。")
        exit(1)

    potcar_elements = extract_potcar_elements(potcar_path)
    poscar_elements = extract_poscar_elements(poscar_path)
    if potcar_elements != poscar_elements:
        print(f"❌ POTCAR 元素顺序（{' '.join(potcar_elements)}）与 POSCAR 元素顺序（{' '.join(poscar_elements)}）不一致！")
        print("   请按照 POSCAR 第 6 行元素顺序重新拼接 POTCAR 后重试。")
        exit(1)
    print(f"✅ POTCAR 与 POSCAR 元素顺序校验一致：{' '.join(potcar_elements)}")

    # 5. 复制前检测 INCAR 是否为默认INCAR（比较时忽略换行符差异）
    with open(incar_path, "r", encoding="utf-8") as f:
        incar_content = f.read()
    if incar_content.strip().replace("\r\n", "\n") == DEFAULT_INCAR.strip():
        print("ℹ️  本次使用的 INCAR 为默认 INCAR（未自定义）。如需自定义，请编辑 Y_VASP_file/INCAR 后重新运行本脚本。")

    # 6. 批量复制 INCAR、POTCAR、*.sh 到所有子任务文件夹
    copy_items = ["INCAR", "POTCAR"] + [os.path.basename(s) for s in sh_files]
    total = 0
    for folder in folders:
        for f in copy_items:
            shutil.copy2(os.path.join(SOURCE_DIR, f), os.path.join(folder, f))
            total += 1
        print(f"📦 已复制到：{folder}")
    print(f"\n🎉 全部完成！共处理 {len(folders)} 个子任务文件夹，复制 {total} 个文件。")


if __name__ == "__main__":
    main()
