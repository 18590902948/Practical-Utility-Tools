"""
=============================================================================
脚本:        train_xyz2model_xyz.py
分类:        格式转换脚本
功能:        读取XYZ轨迹文件，将轨迹每一帧分发到以帧号命名的数字文件夹
             （1/、2/、…、n/），每帧保存为 model.xyz（extxyz格式，
             可直接作为GPUMD MD的初始结构）；
             fork 自 1xyz2poscar_number.py，仅将输出由 POSCAR 改为
             model.xyz (extxyz)。
使用方法:    python train_xyz2model_xyz.py [xyz文件名]
参数:        xyz文件名   要转换的XYZ轨迹文件（可选）；
             不传参数时，自动扫描脚本所在目录下的*.xyz文件（仅限单个文件）
输出:
  1/, 2/, … n/    以帧号命名的数字文件夹，生成在脚本所在目录
  */model.xyz     GPUMD可读取的extxyz格式文件（含 Lattice）
作者:        Hongbo Sun（fork 自 1xyz2poscar_number.py）
最后修改日期: 2026-08-22
=============================================================================
# 目录树示例:
# ============================================================================
# .
# ├── merged_global.xyz
# ├── train_xyz2model_xyz.py
# ├── 1/                # 第1帧
# │   └── model.xyz
# ├── 2/                # 第2帧
# │   └── model.xyz
# └── ...
# └── n/                # 第n帧
#     └── model.xyz
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

OUTPUT_FILE = "model.xyz"

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
        print("   请指定要转换的文件：python train_xyz2model_xyz.py xyz文件名")
        exit(1)

    input_file = xyz_list[0]

print(f"✅ 找到XYZ文件：{input_file}")

# 读取所有结构
frames = read(input_file, ":")
total_frames = len(frames)
print(f"✅ 总帧数：{total_frames}")

created_dirs = 0
for idx, atoms in enumerate(frames, 1):
    # 数字文件夹 1/、2/、3/ …，生成在脚本所在目录
    out_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), str(idx))
    os.makedirs(out_folder, exist_ok=True)
    created_dirs += 1

    model_path = os.path.join(out_folder, OUTPUT_FILE)

    # 写为 extxyz 格式（注释行含 Lattice，GPUMD 可直接读取）
    write(model_path, atoms, format="extxyz")

    if idx % 100 == 0:
        print(f"📦 已处理 {idx}/{total_frames}，已创建文件夹 {created_dirs}")

print(f"\n🎉 全部完成！共分发 {total_frames} 帧，创建 {created_dirs} 个文件夹（1/ ~ {total_frames}/）")
