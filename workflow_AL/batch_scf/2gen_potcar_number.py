"""
脚本:        2gen_potcar_number.py
功能:        对脚本所在目录下所有数字文件夹：
             1) 在各文件夹直接生成默认 INCAR 与任务提交脚本 sub_<编号>.sh
                （如 1/sub_1.sh、52/sub_52.sh；模板中的 {name} 替换为所在
                文件夹编号，同时用作 Slurm 作业名；已有则覆盖；LF 换行、
                UTF-8 无 BOM，提交脚本补可执行位，保证 Linux 下可直接使用）；
             2) 按 POSCAR 第 6 行元素顺序分组，每组用 vaspkit -task 103 生成一次
                POTCAR 并复制到组内其余文件夹（生成前统一删除旧 POTCAR，
                失败/中断只会留下"缺失"，不会留下元素错配的旧文件）；
             3) 全量校验各文件夹 POTCAR (VRHFIN 序列) 与 POSCAR 元素顺序一致，
                不一致的 POTCAR 直接删除（宁可缺失，绝不残留错配）；
                并输出记录文件 potcar_gen.txt（覆盖模式）。
使用方法:    python3 2gen_potcar_number.py
运行环境:    超算登录节点（PATH 中有 vaspkit）；仅用 Python 3 标准库
作者:        隼蝶.
最后修改日期: 2026-09-11
"""
import os
import re
import sys
import shutil
import subprocess
from datetime import datetime

# Windows 控制台默认 GBK 编码无法输出 emoji，统一改用 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ============ 配置区（可按需调整） ============
VASPKIT_CMD = ["vaspkit"]       # vaspkit 调用命令（需完整路径/包装时可改）
VASPKIT_TASK = "103"            # vaspkit 任务号（103=默认设置生成 POTCAR）
VASPKIT_TIMEOUT = 120           # vaspkit 单次调用超时（秒）
RECORD_FILE = "potcar_gen.txt"  # 记录文件（脚本所在目录，覆盖模式）
# ============================================

# 默认 INCAR 模板：直接写入各数字文件夹（已有则覆盖），如需自定义请修改此模板。
# 注意：写入时强制 LF 换行（\n）、UTF-8 无 BOM 编码，符合 Linux VASP 格式要求。
DEFAULT_INCAR = """ISTART   = 0
ISPIN    = 1

ENCUT    = 500
PREC      = Normal
LREAL     = Auto

ISMEAR    = 0
SIGMA     = 0.05

EDIFF     = 1E-5
NELM       = 150

NSW        = 0
IBRION     = -1
ISIF       = 2

KSPACING   = 0.30
KGAMMA     = .TRUE.

LWAVE      = .FALSE.
LCHARG     = .FALSE.

IVDW       = 12

ISYM       = 0
SYMPREC    = 1e-3

NCORE = 2
"""

# 默认任务提交脚本模板：写入各数字文件夹并命名为 sub_<编号>.sh（已有则覆盖），如需自定义请修改此模板。
# 注意 1：模板中的 {name} 会替换为所在文件夹编号（如 1/sub_1.sh 的 Slurm 作业名为 1），其余内容原样写入。
# 注意 2：写入时强制 LF 换行（\n）、UTF-8 无 BOM 编码，符合 Linux 作业提交格式要求。
DEFAULT_SUB_SH = """#!/bin/bash
#SBATCH --job-name={name}
#SBATCH --partition=v6_384  
#SBATCH --nodes=1        
#SBATCH --ntasks=24        
#SBATCH --output=%j.log     

#======================================================================
source /public5/soft/modules/module.sh  
module load mpi/oneAPI/2022.1  
export PATH=/public5/home/t6s008728/software-t6s008728/vasp.6.3.0/bin:$PATH
echo
echo
echo "=== VASP 版本检查 ==="
which vasp_std
vasp_std --version 2>&1 | grep -i version  
echo
echo
echo "=== 输入文件检查 ==="
ls -l INCAR KPOINTS POSCAR POTCAR  
echo
echo
#======================================================================
mpirun -np 24 vasp_std  
"""

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def read_poscar_elements(path):
    """读取 POSCAR 第 6 行元素顺序；缺失或含非字母（疑似 VASP4 格式）返回 None"""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    if len(lines) < 6:
        return None
    elements = lines[5].split()
    if not elements or not all(e.isalpha() for e in elements):
        return None
    return elements


def read_potcar_elements(path):
    """读取 POTCAR 元素顺序（按 VRHFIN = 字段出现的先后）"""
    elements = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = re.search(r"VRHFIN\s*=\s*([A-Za-z]+)", line)
            if m:
                elements.append(m.group(1))
    return elements


def read_potcar_titels(path):
    """读取 POTCAR 的 TITEL 行（核对赝势版本用）"""
    titels = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.strip().startswith("TITEL"):
                titels.append(line.strip())
    return titels


def run_vaspkit(folder):
    """在指定文件夹内执行 vaspkit -task X；成功生成 POTCAR 返回 True"""
    cmd = VASPKIT_CMD + ["-task", VASPKIT_TASK]
    try:
        proc = subprocess.run(
            cmd, cwd=folder, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=VASPKIT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        print(f"      ❌ vaspkit 超时（>{VASPKIT_TIMEOUT} 秒）")
        return False
    except Exception as e:
        print(f"      ❌ vaspkit 调用失败：{e}")
        return False
    if not os.path.exists(os.path.join(folder, "POTCAR")):
        print("      ❌ vaspkit 未生成 POTCAR，输出（末10行）：")
        for line in (proc.stdout or "").strip().splitlines()[-10:]:
            print(f"         {line}")
        return False
    return True


def main():
    os.chdir(SCRIPT_DIR)

    # ---------- 环境检查 ----------
    if shutil.which(VASPKIT_CMD[0]) is None:
        print(f"❌ 未找到 vaspkit 命令（{VASPKIT_CMD[0]}），请检查 PATH 或修改 VASPKIT_CMD。")
        sys.exit(1)

    # ---------- 收集数字文件夹并读取元素顺序 ----------
    folders = sorted(
        (n for n in os.listdir(".") if n.isdigit() and os.path.isdir(n)),
        key=int,
    )
    if not folders:
        print("❌ 当前目录下未找到数字文件夹，请先运行 1xyz2poscar_number.py。")
        sys.exit(1)

    skipped = []            # 跳过的文件夹及其原因
    elements_of = {}        # 文件夹 -> 元素列表
    groups = {}             # 元素元组 -> [文件夹, ...]
    for name in folders:
        poscar = os.path.join(name, "POSCAR")
        if not os.path.exists(poscar):
            skipped.append((name, "缺 POSCAR"))
            continue
        elements = read_poscar_elements(poscar)
        if elements is None:
            skipped.append((name, "POSCAR 第 6 行元素行异常（疑似 VASP4 格式）"))
            continue
        elements_of[name] = elements
        groups.setdefault(tuple(elements), []).append(name)

    if not elements_of:
        print("❌ 没有可处理的文件夹（全部缺失或缺 POSCAR），请先运行 1xyz2poscar_number.py。")
        sys.exit(1)

    print(f"✅ 检测到 {len(folders)} 个数字文件夹，参与处理 {len(elements_of)} 个")
    if skipped:
        print(f"⚠️ 跳过 {len(skipped)} 个文件夹（不复制、不生成、不校验）：")
        for name, reason in skipped:
            print(f"   {name}/  {reason}")

    group_items = sorted(groups.items(), key=lambda kv: int(kv[1][0]))
    print(f"🔍 元素分组统计（共 {len(group_items)} 组）：")
    print("   组号  元素顺序      文件夹范围            数量   代表文件夹")
    for i, (key, members) in enumerate(group_items, 1):
        scope = members[0] if len(members) == 1 else f"{members[0]}-{members[-1]}"
        print(f"   {i:<4}  {' '.join(key):<14} {scope:<20} {len(members):<6} {members[0]}/")

    target = list(elements_of)
    print(f"即将执行：生成 INCAR、sub_<编号>.sh → 清空旧 POTCAR → "
          f"按 {len(group_items)} 组生成 POTCAR → 全量校验")

    # ---------- [1/3] 生成 INCAR 与 sub_<编号>.sh ----------
    # 写入强制 LF 换行（newline="\n"）、UTF-8 无 BOM，保证 Linux 下可直接使用
    created = 0
    overwritten = 0
    removed_old = []        # 清理掉的旧提交脚本 (文件夹, 文件名)
    for name in target:
        sub_name = f"sub_{name}.sh"      # 提交脚本按文件夹编号命名：1/ → sub_1.sh，52/ → sub_52.sh
        # 清理同目录遗留的旧提交脚本（如上一版 sub2.sh）：3batch_submit.sh 以
        # sub*.sh 通配提交，目录内必须只保留一个匹配脚本，否则可能提交到旧脚本
        for old in sorted(os.listdir(name)):
            if (old != sub_name and old.startswith("sub") and old.endswith(".sh")
                    and os.path.isfile(os.path.join(name, old))):
                os.remove(os.path.join(name, old))
                removed_old.append((name, old))
        # 模板中的 {name} 替换为所在文件夹编号（Slurm 作业名等随之对齐）
        sub_content = DEFAULT_SUB_SH.replace("{name}", name)
        for fname, content in (("INCAR", DEFAULT_INCAR), (sub_name, sub_content)):
            fpath = os.path.join(name, fname)
            if os.path.exists(fpath):
                overwritten += 1
            else:
                created += 1
            with open(fpath, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            if fname.endswith(".sh"):
                # 补可执行位（sbatch 提交不要求，但方便手动 ./sub_<编号>.sh 提交）
                os.chmod(fpath, 0o755)
    if removed_old:
        print(f"🧹 已清理 {len(removed_old)} 个旧提交脚本（统一改名为 sub_<编号>.sh）：")
        for name, old in removed_old:
            print(f"   {name}/{old} → {name}/sub_{name}.sh")
    print(f"📦 [1/3] 已写入 INCAR、sub_<编号>.sh → {len(target)} 个文件夹（新建 {created}，覆盖 {overwritten}）")

    # ---------- [2/3] 生成 POTCAR ----------
    # 先统一删除旧 POTCAR：任何失败/中断都不会留下元素错配的旧文件
    for name in target:
        old = os.path.join(name, "POTCAR")
        if os.path.exists(old):
            os.remove(old)

    gen_count = 0
    copy_count = 0
    source_of = {}          # 文件夹 -> 生成/复制
    print(f"📦 [2/3] POTCAR 生成（vaspkit -task {VASPKIT_TASK}）：")
    for i, (key, members) in enumerate(group_items, 1):
        lead = members[0]
        print(f"   [{i}/{len(group_items)}] {' '.join(key)} → 在 {lead}/ 生成 ...")
        if run_vaspkit(lead):
            gen_count += 1
            source_of[lead] = "生成"
            for title in read_potcar_titels(os.path.join(lead, "POTCAR")):
                print(f"         {title}")
            for m in members[1:]:
                shutil.copy2(os.path.join(lead, "POTCAR"), os.path.join(m, "POTCAR"))
                source_of[m] = "复制"
                copy_count += 1
            print(f"      ✅ 生成成功，已复制到组内其余 {len(members) - 1} 个文件夹")
        else:
            print(f"      ⚠️ 本组 {len(members)} 个文件夹保持无 POTCAR，请排查后重跑本脚本")

    # ---------- [3/3] 全量校验 ----------
    print("🔍 [3/3] 全量校验（POSCAR 第 6 行 vs POTCAR VRHFIN）：")
    rows = []               # (文件夹, 元素顺序, 来源, 校验结果)
    pass_count = 0
    for name in target:
        elements = elements_of[name]
        potcar = os.path.join(name, "POTCAR")
        src = source_of.get(name, "-")
        if not os.path.exists(potcar):
            status = "缺失"
        elif read_potcar_elements(potcar) == elements:
            status = "通过"
            pass_count += 1
        else:
            # 元素顺序未对齐的 POTCAR 直接删除：宁可缺失（提交脚本会跳过缺文件目录），
            # 也不允许错配赝势被提交导致结果错误
            os.remove(potcar)
            status = "不一致(已删)"
        rows.append((name, ",".join(elements), src, status))
    fail_count = len(target) - pass_count
    if fail_count:
        print(f"   ⚠️ 未通过 {fail_count} 个：")
        for name, elems, src, status in rows:
            if status != "通过":
                print(f"      {name}/  {status}（元素顺序 {elems}）")
    print(f"   校验通过：{pass_count}/{len(target)}")

    # ---------- 记录文件与总结 ----------
    with open(RECORD_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write("# 2gen_potcar_number.py 运行记录\n")
        f.write(f"# 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(
            f"# 统计: 文件夹 {len(target)} | 分组 {len(group_items)} | 生成 {gen_count} | "
            f"复制 {copy_count} | 校验通过 {pass_count} | 失败 {fail_count}\n"
        )
        if skipped:
            f.write(f"# 跳过: {len(skipped)} 个（不参与处理，详见终端输出）\n")
        f.write("# 文件夹    元素顺序      来源   校验\n")
        for name, elems, src, status in rows:
            f.write(f"{name:<10} {elems:<13} {src:<6} {status}\n")

    print()
    if fail_count:
        print(f"⚠️ 完成，但有 {fail_count} 个文件夹未通过（见上），请人工排查后重跑本脚本。")
    else:
        print(f"🎉 全部完成！处理 {len(target)} 个文件夹，分组 {len(group_items)} 组，POTCAR 校验全部通过。")
    print(f"📄 记录文件：{os.path.join(SCRIPT_DIR, RECORD_FILE)}")
    sys.exit(1 if fail_count else 0)


if __name__ == "__main__":
    main()
