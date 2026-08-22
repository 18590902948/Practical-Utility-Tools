#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
=============================================================================
脚本:        vasp2xyz.py
分类:        格式转换脚本
功能:        扫描脚本所在目录下所有 VASP 格式文件 (*.vasp、POSCAR*、CONTCAR*)，
             按文件类型自动分类，将同类文件合并为一个 xyz 文件，
             存放在脚本所在目录下对应的文件夹中；
             改编自 GPUMD_convert/pos2exyz.py，为无需参数的自动批量版。
使用方法:    python vasp2xyz.py
参数:        无参数，自动扫描脚本所在目录下的全部 VASP 格式文件
输出:
  vasp/vasp.xyz           由 *.vasp 文件合并的 xyz 文件
  poscar/pos.xyz          由 POSCAR* 文件合并的 xyz 文件
  contcar/cont.xyz        由 CONTCAR* 文件合并的 xyz 文件
作者:        Hongbo Sun
最后修改日期: 2026-08-22
=============================================================================
# 目录树示例:
# ============================================================================
# .                        # 脚本所在目录(含 VASP 格式文件)
# ├── 1.vasp               # 输入:VASP 文件
# ├── 2.vasp               # 输入:VASP 文件
# ├── POSCAR               # 输入:POSCAR 文件
# ├── POSCAR_1             # 输入:POSCAR 文件
# ├── CONTCAR              # 输入:CONTCAR 文件
# ├── CONTCAR_8            # 输入:CONTCAR 文件
# ├── vasp/
# │   └── vasp.xyz         # 输出:由 *.vasp 合并
# ├── poscar/
# │   └── pos.xyz          # 输出:由 POSCAR* 合并
# └── contcar/
#     └── cont.xyz         # 输出:由 CONTCAR* 合并
# ============================================================================
"""

import os
from ase.io import read, write

# =============================================================================
# 配置区
# =============================================================================
OUTPUT_FORMAT = "xyz"   # 输出文件格式: 纯 xyz 即可(VASP 文件无能量/维里/力信息,
                          # extxyz 的扩展信息用不上; 若后续需要保留晶格, 改回 "extxyz")
# 各组输出文件名。注意: 文件名中不能包含 POSCAR/CONTCAR 字样(任意大小写),
# 否则会被 ASE 按 glob 规则误判为 VASP 格式而无法读取。
GROUP_OUTPUT_NAMES = {
    "vasp": "vasp.xyz",
    "poscar": "pos.xyz",
    "contcar": "cont.xyz",
}


def classify_vasp_file(filename):
    """按文件名将 VASP 文件归类,返回分组目录名；非 VASP 格式文件返回 None。

    匹配规则(不区分大小写)：
      *.vasp        -> vasp 组
      POSCAR*       -> poscar 组
      CONTCAR*      -> contcar 组
    分组目录名使用小写，避免与裸 POSCAR/CONTCAR 输入文件同名(大小写敏感系统)。
    """
    lower = filename.lower()
    if lower.endswith(".xyz"):
        return None  # 排除 xyz 输出文件
    if lower.endswith(".vasp"):
        return "vasp"
    if lower.startswith("poscar"):
        return "poscar"
    if lower.startswith("contcar"):
        return "contcar"
    return None


def merge_vasp_to_xyz(filenames, output_path):
    """将多个 VASP 文件的所有帧合并写入一个 xyz 文件。"""
    all_frames = []
    for filename in filenames:
        try:
            frames = read(filename, format="vasp")
            if isinstance(frames, list):
                all_frames.extend(frames)
            else:
                all_frames.append(frames)
        except Exception as e:
            print("  ERROR 读取 %s 失败: %s" % (filename, e))

    if not all_frames:
        print("  警告: 未读取到任何结构, 跳过写入 %s" % output_path)
        return
    write(output_path, all_frames, format=OUTPUT_FORMAT, append=False)


def main():
    # 切换到脚本所在目录，确保扫描与输出均相对于脚本目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # 扫描当前目录所有文件，按类型归类
    groups = {}        # 组名 -> [文件名列表]
    for name in sorted(os.listdir(".")):
        if not os.path.isfile(name):
            continue
        group = classify_vasp_file(name)
        if group:
            groups.setdefault(group, []).append(name)

    if not groups:
        print("未在脚本所在目录发现任何 VASP 格式文件(*.vasp / POSCAR* / CONTCAR*)。")
        return

    for group, filenames in groups.items():
        out_dir = group
        try:
            os.makedirs(out_dir, exist_ok=True)
        except FileExistsError:
            print("  ERROR: 输出文件夹 %s 与同名输入文件冲突, 请先移动该文件后重试" % out_dir)
            continue
        out_path = os.path.join(out_dir, GROUP_OUTPUT_NAMES[group])

        print("\n[%s] 合并 %d 个文件:" % (group, len(filenames)))
        for f in filenames:
            print("  - %s" % f)
        merge_vasp_to_xyz(filenames, out_path)
        print("  输出: %s" % os.path.abspath(out_path))

    print("\n完成。")


if __name__ == "__main__":
    main()
