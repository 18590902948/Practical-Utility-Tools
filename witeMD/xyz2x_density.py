#!/usr/bin/env python3
"""
=============================================================================
脚本:        xyz2x_density.py
分类:        结构分析脚本
功能:        读取目标 XYZ (extxyz) 轨迹，逐帧计算组分与密度：
             组分 x = n_O / n_Si  (O/Si 原子比, SiO2 → 2.0, 纯 Si → 0)
             密度 = 总质量 / 晶格体积 (g/cm3)
             输出：
              1. extxyz 文件: 每帧注释行附加 x=... density=...
              2. txt 表格:   第一列帧序号 (OVITO 0 起始)，第二列组分，
                             第三列密度
使用方法:    python xyz2x_density.py [xyz文件]
参数:        xyz文件   要计算的 XYZ 轨迹文件（必填）
输出:
  <输入文件同目录>/<输入名>_x_density.extxyz   带组分与密度的轨迹
  <输入文件同目录>/<输入名>_x_density.txt      帧号/组分/密度 表格
示例:
  python xyz2x_density.py E:/repositorie/Data/SixOy/SixOy.xyz
作者:        Hongbo Sun
最后修改日期: 2026-08-22
=============================================================================
"""

import os
import sys

from ase.io import read, write

# Windows 控制台默认 GBK 编码无法输出 emoji，统一改用 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 密度换算系数: 原子质量 (g/mol = amu)，1 amu = 1.66053906660e-24 g，
# 1 A3 = 1e-24 cm3，故 g/cm3 = amu * 1.66053906660 / A3
AMU_TO_G_PER_CM3 = 1.66053906660


def main():
    if len(sys.argv) < 2:
        print("❌ 请指定要计算的 XYZ 文件：python xyz2x_density.py xyz文件")
        sys.exit(1)
    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"❌ 未找到文件：{input_file}")
        sys.exit(1)

    # 读取所有帧
    frames = read(input_file, index=":")
    nframes = len(frames)
    print(f"✅ 已读取 {os.path.abspath(input_file)}，共 {nframes} 帧")

    rows = []
    for i, atoms in enumerate(frames):
        symbols = atoms.get_chemical_symbols()
        n_si = symbols.count("Si")
        n_o = symbols.count("O")
        if n_si == 0:
            print(f"⚠ 帧 {i}: 不含 Si 元素 (n_Si=0)，组分记 0。")
        x = n_o / n_si if n_si > 0 else 0.0

        # 总质量 (g/mol = amu)，密度 = 质量 * 系数 / 体积(A3)
        mass = atoms.get_masses().sum()
        volume = atoms.get_volume()
        density = mass * AMU_TO_G_PER_CM3 / volume if volume > 0 else 0.0

        # 元信息写入 info，写 extxyz 时自动进入注释行
        atoms.info["x"] = x
        atoms.info["density"] = density
        rows.append((i, x, density))

    # 输出 extxyz: 与输入同目录、同前缀
    base = os.path.splitext(input_file)[0]
    out_extxyz = base + "_x_density.extxyz"
    write(out_extxyz, frames, format="extxyz")
    print(f"✅ 已写出带组分/密度的轨迹: {os.path.abspath(out_extxyz)}")

    # 输出 txt: 帧号 (OVITO 0 起始) / 组分 / 密度
    out_txt = base + "_x_density.txt"
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(f"# {'帧号':<8}{'组分 (n_O/n_Si)':<18}{'密度 (g/cm3)'}\n")
        for i, x, density in rows:
            f.write(f"{i:<8}{x:<18.4f}{density:.4f}\n")
    print(f"✅ 已写出帧号/组分/密度表格: {os.path.abspath(out_txt)}")
    print(f"\n🎉 全部完成！共计算 {nframes} 帧")


if __name__ == "__main__":
    main()
