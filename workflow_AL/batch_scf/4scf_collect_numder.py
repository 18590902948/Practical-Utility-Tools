"""
=============================================================================
脚本:        scf_collect_numder.py
分类:        SCF结果收集脚本
功能:        扫描当前目录下所有数字命名的子文件夹，读取各文件夹中的OUTCAR；
             检测电子自洽收敛标记（EDIFF reached，出现且仅出现1次）判断计算是否收敛；
             提取收敛结构的能量与virial，以extxyz格式写入train.xyz（供NEP/MTP等势训练）；
             内存缓冲达到50个结构时批量落盘，最终生成收集统计报告，并在终端末尾
             打印未收集文件夹列表及原因。
使用方法:    python scf_collect_numder.py
参数:        无参数，自动扫描当前工作目录下数字命名的子文件夹
输出:
  train.xyz          收集的合格结构（extxyz格式，含energy、virial信息）
  collect_info.txt   收集统计报告（成功/跳过文件夹列表及原因）
作者:        Hongbo Sun
最后修改日期: 2026‑08‑23
=============================================================================
# 目录树示例:
# ============================================================================
# .
# ├── scf_collect_numder.py
# ├── 1/                # 数字命名子文件夹
# │   └── OUTCAR
# ├── 2/
# │   └── OUTCAR
# ├── ...
# ├── train.xyz         # 收集的合格结构（extxyz）
# └── collect_info.txt  # 收集统计报告
# ============================================================================
"""
import os
import numpy as np
from ase.io import read, write


def Convert_atoms(atom):
    xx, yy, zz, yz, xz, xy = -atom.calc.results['stress'] * atom.get_volume()
    atom.info['virial'] = np.array([[xx, xy, xz],
                                    [xy, yy, yz],
                                    [xz, yz, zz]])
    atom.calc.results['energy'] = atom.calc.results['free_energy']
    del atom.calc.results['stress']
    del atom.calc.results['free_energy']


def check_ediff_converged(outcar_path: str) -> tuple[bool, int]:
    target_str = "aborting loop because EDIFF is reached"
    count = 0
    with open(outcar_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if target_str in line:
                count += 1
                if count >= 2:
                    break
    ok = (count == 1)
    return ok, count


def dw(s):
    """字符串显示宽度：中文等宽字符按2列计，用于终端对齐。"""
    return sum(2 if ord(c) > 127 else 1 for c in str(s))


def pad(s, w, align="<"):
    """按显示宽度填充空格对齐: '<'左对齐, '>'右对齐。"""
    s = str(s)
    n = w - dw(s)
    return s + " " * n if align == "<" else " " * n + s


def col(s, w, align="<"):
    """单列: 按宽度对齐 + 列间2空格分隔。"""
    return pad(s, w, align) + "  "


def skip_status(reason):
    """跳过原因 -> 简短状态标签 (终端列表用)。"""
    if "未找到OUTCAR" in reason:
        return "缺少OUTCAR"
    if "未检测到" in reason or "自洽计数=0" in reason:
        return "未收敛"
    if "自洽计数" in reason:
        return "自洽异常"
    if "异常" in reason:
        return "读取异常"
    return "其他"


def main():
    root = "."
    BUFFER_SIZE = 50    # 缓冲区阈值，攒够50就落盘
    out_xyz = "train.xyz"

    buffer_atoms = []    # 内存缓冲区，最多存BUFFER_SIZE个atoms
    total_written = 0    # 累计已经写入xyz的总构型数
    collected_count = 0  # 当前已收集合格构型计数（屏幕打印用）
    first_write = True   # 标记是否第一次写文件（覆盖模式）

    success_dirs = []   # 元组 (文件夹名, 自洽计数)
    skip_dirs = []      # 元组 (文件夹名, 跳过原因)

    entries = os.listdir(root)
    digit_entries = [e for e in entries if e.isdigit()]
    digit_entries = sorted(digit_entries, key=lambda x: int(x))

    print("="*60)
    print(f"[INFO] 工作目录: {os.path.abspath(root)}")
    print(f"[INFO] 扫描数字命名子文件夹，收集电子自洽标记=1的构型写入xyz")
    print(f"[INFO] 内存缓冲区大小: {BUFFER_SIZE}")
    print("="*60)

    def flush_buffer():
        """把buffer_atoms写入磁盘，然后清空缓冲区释放内存"""
        nonlocal total_written, first_write
        if len(buffer_atoms) == 0:
            return
        if first_write:
            write(out_xyz, buffer_atoms, format='extxyz')
            first_write = False
        else:
            write(out_xyz, buffer_atoms, format='extxyz', append=True)
        cnt = len(buffer_atoms)
        total_written += cnt
        buffer_atoms.clear()  # 释放内存

    for entry in digit_entries:
        dpath = os.path.join(root, entry)
        if not os.path.isdir(dpath):
            continue

        outcar = os.path.join(dpath, "OUTCAR")
        print(f"\n>> 处理文件夹 [{entry}]")

        if not os.path.exists(outcar):
            print(f"  ⚠️  跳过：未找到OUTCAR")
            skip_dirs.append((entry, "未找到OUTCAR"))
            continue

        converged, hit_cnt = check_ediff_converged(outcar)
        if not converged:
            if hit_cnt == 0:
                print(f"  ❌ 跳过：未检测到自洽标记，计算未收敛或计算出错(自洽计数=0)")
                skip_dirs.append((entry, "未检测到自洽标记，计算未收敛或计算出错，自洽计数=0"))
            else:
                print(f"  ❌ 跳过：自洽标记出现 {hit_cnt} 次")
                skip_dirs.append((entry, f"自洽计数={hit_cnt}"))
            continue

        try:
            atoms = read(outcar, format='vasp-out', index=-1)
            Convert_atoms(atoms)
            buffer_atoms.append(atoms)
            success_dirs.append((entry, hit_cnt))
            collected_count += 1
            print(f"  ✅ 成功读取，加入缓冲区 (自洽计数={hit_cnt})，缓冲区当前:{len(buffer_atoms)}/{BUFFER_SIZE}")
            print(f"  ✅ 已收集{collected_count}个结构")

            if len(buffer_atoms) >= BUFFER_SIZE:
                flush_buffer()

        except Exception:
            print(f"  ❗ 读取OUTCAR异常，跳过")
            skip_dirs.append((entry, "读取OUTCAR异常"))

    flush_buffer()

    stat_file = "collect_info.txt"
    with open(stat_file, "w", encoding="utf-8") as f:
        f.write(f"扫描到的数字命名文件夹总数: {len(success_dirs)+len(skip_dirs)}\n")
        f.write(f"✅ 成功收集(自洽标记=1): {len(success_dirs)}\n")
        f.write(f"❌ 跳过的文件夹总数: {len(skip_dirs)}\n\n")

        f.write("【成功收集文件夹列表】\n")
        for d, cnt in success_dirs:
            f.write(f"  [{d}] ：自洽计数={cnt}，已收敛\n")

        f.write("\n【跳过文件夹列表 | 文件夹编号 : 跳过原因】\n")
        for d, reason in skip_dirs:
            f.write(f"  [{d}]  :  {reason}\n")

    print(f"\n✅ 输出文件: {out_xyz} ，总共 {total_written} 个合格结构")
    print(f"📄 统计报告已保存至 {stat_file}")

    # 终端末尾打印未收集文件夹列表（含原因），与 collect_info.txt 内容对应
    bar = "=" * 60
    line = "-" * 60
    print(bar)
    if skip_dirs:
        print(f"📊 未收集文件夹列表 (共 {len(skip_dirs)} 个):")
        print(line)
        hdr = col("序号", 6, ">") + col("文件夹", 8, ">") + col("状态", 10) + "原因"
        sep = (col("-" * 6, 6, ">") + col("-" * 8, 8, ">")
               + col("-" * 10, 10) + "-" * 30)
        print(hdr)
        print(sep)
        for i, (d, reason) in enumerate(skip_dirs, 1):
            print(col(i, 6, ">") + col(d, 8, ">")
                  + col(skip_status(reason), 10) + reason)
        print(sep)
        total = len(success_dirs) + len(skip_dirs)
        print(f"✅ 成功收集 {len(success_dirs)}/{total}，"
              f"未收集 {len(skip_dirs)} 个，详情见 collect_info.txt")
    else:
        print("📊 未收集文件夹列表: 0 个，全部收集成功 🎉")
    print(bar)


if __name__ == "__main__":
    main()