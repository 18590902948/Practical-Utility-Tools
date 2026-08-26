"""
=============================================================================
脚本:        1xyz2poscar.py
分类:        格式转换脚本
功能:        读取XYZ轨迹文件，将轨迹每一帧拆分为独立POSCAR文件；
             按每500帧划分为a/b/c…字母分组目录；
             所有帧按全局统一的元素顺序排列（第6行元素顺序一致，第7行计数与第6行一一对应）；
             输出POSCAR使用direct直接坐标。
使用方法:    python 1xyz2poscar.py [xyz文件名]
参数:        xyz文件名   要转换的XYZ轨迹文件（可选）；
             不传参数时，自动扫描脚本所在目录下的*.xyz文件（仅限单个文件）
输出:
  a/, b/, c/ …      分组目录，内部包含以帧号命名的子文件夹，生成在脚本所在目录
  */*/POSCAR        VASP输入文件，原子按全局统一的元素顺序排列，direct坐标
作者:        隼蝶.
最后修改日期: 2026‑08‑21
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
import sys
import glob

# Windows 控制台默认 GBK 编码无法输出 emoji，统一改用 UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# 从命令行参数获取 xyz 文件名（可选）
if len(sys.argv) >= 2:
    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"❌ 未找到文件：{input_file}")
        exit(1)
else:
    # 无参数：默认扫描脚本所在目录下的 xyz 文件
    script_dir = os.path.dirname(os.path.abspath(__file__))
    xyz_list = glob.glob(os.path.join(script_dir, "*.xyz"))

    if len(xyz_list) == 0:
        print(f"❌ 脚本所在目录下未找到任何 .xyz 文件！")
        exit(1)

    if len(xyz_list) > 1:
        print(f"❌ 脚本所在目录下存在多个 .xyz 文件，无法自动判断：")
        for f in xyz_list:
            print(f"   {os.path.basename(f)}")
        print("   请指定要转换的文件：python 1xyz2poscar.py xyz文件名")
        exit(1)

    input_file = xyz_list[0]

print(f"✅ 找到XYZ文件：{input_file}")

group_size = 500

# 读取所有结构
frames = read(input_file, ":")
total_frames = len(frames)
print(f"✅ 总帧数：{total_frames}")

# 全局统一的元素顺序：收集所有帧出现的全部元素，按字母排序
# （同一轨迹各帧元素组成可能不同，保证每帧不丢原子）
elements = sorted({sym for a in frames for sym in a.get_chemical_symbols()})
print(f"✅ 全局元素顺序：{' '.join(elements)}")

for idx, atoms in enumerate(frames, 1):
    # 分组 a, b, c...
    group_idx = (idx - 1) // group_size
    group_char = chr(ord('a') + group_idx)

    # 目录结构 a/123，生成在脚本所在目录
    out_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), group_char, str(idx))
    os.makedirs(out_folder, exist_ok=True)

    poscar_path = os.path.join(out_folder, "POSCAR")

    # 按全局统一的元素顺序重排（组内保持原顺序，缺失元素自动跳过）
    symbols = atoms.get_chemical_symbols()
    order = []
    for elem in elements:
        order.extend([i for i, sym in enumerate(symbols) if sym == elem])

    atoms_sorted = atoms[order]

    # 写入 POSCAR
    write(poscar_path, atoms_sorted, format='vasp', direct=True)

    if idx % 100 == 0:
        print(f"📦 已处理 {idx}/{total_frames}")

print("\n🎉 全部完成！")