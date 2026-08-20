"""
=============================================================================
脚本:        1xyz2poscar.py
分类:        格式转换脚本
功能:        读取当前目录下第一个XYZ轨迹文件，将轨迹每一帧拆分为独立POSCAR文件；
             按每500帧划分为a/b/c…字母分组目录，原子按元素符号排序；
             输出POSCAR使用direct直接坐标。
使用方法:    python xyz2split_poscar.py
参数:        无参数，自动扫描当前工作目录下全部*.xyz文件
输出:
  a/, b/, c/ …      分组目录，内部包含以帧号命名的子文件夹
  */*/POSCAR        VASP输入文件，原子已按元素排序，direct坐标
作者:        Hongbo Sun
最后修改日期: 2026‑08‑20
=============================================================================
# 目录树示例:
# ============================================================================
# .
# └── a/                # a组：第1 ~ 500帧
#     ├── 1/
#     │   └── POSCAR
#     ├── 2/
#     │   └── POSCAR
#     └── ...
# └── b/                # b组：第501 ~ 1000帧
#     ├── 501/
#     │   └── POSCAR
#     └── ...
# ============================================================================
"""
from ase.io import read, write
import os
import glob
from collections import Counter

# 自动搜索当前目录所有 .xyz 文件
xyz_list = glob.glob("*.xyz")

if len(xyz_list) == 0:
    print("❌ 当前目录下未找到任何 .xyz 文件！")
    exit(1)

# 取第一个 xyz 文件
input_file = xyz_list[0]
print(f"✅ 找到XYZ文件：{input_file}")

group_size = 500

# 读取所有结构
frames = read(input_file, ":")
total_frames = len(frames)
print(f"✅ 总帧数：{total_frames}")

for idx, atoms in enumerate(frames, 1):
    # 分组 a, b, c...
    group_idx = (idx - 1) // group_size
    group_char = chr(ord('a') + group_idx)

    # 目录结构 a/123
    out_folder = os.path.join(group_char, str(idx))
    os.makedirs(out_folder, exist_ok=True)

    poscar_path = os.path.join(out_folder, "POSCAR")

    # 按元素排序
    symbols = atoms.get_chemical_symbols()
    count = Counter(symbols)
    elements = sorted(count.keys())
    order = []
    for elem in elements:
        order.extend([i for i, sym in enumerate(symbols) if sym == elem])

    atoms_sorted = atoms[order]

    # 写入 POSCAR
    write(poscar_path, atoms_sorted, format='vasp', direct=True)

    if idx % 100 == 0:
        print(f"📦 已处理 {idx}/{total_frames}")

print("\n🎉 全部完成！")