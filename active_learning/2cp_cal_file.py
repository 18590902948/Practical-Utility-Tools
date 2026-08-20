"""
=============================================================================
脚本:        2cp_cal_file.py
分类:        文件批量处理脚本
功能:        遍历a/b/c…分组目录下所有帧号子文件夹，将Ycalculate_file目录下的
             INCAR、POTCAR、sub2.sh批量复制到各个子任务目录中。
使用方法:    python copyvasp_input.py
参数:        无参数，依赖本地Ycalculate_file源目录以及a/b/c分组目录结构
输出:
  */*/INCAR         复制到各子目录的VASP输入文件
  */*/POTCAR        复制到各子目录的赝势文件
  */*/sub2.sh       复制到各子目录的作业提交脚本
作者:        Hongbo Sun
最后修改日期: 2026‑08‑20
=============================================================================
# 目录树示例:
# ============================================================================
# .
# ├── Ycalculate_file/
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
import shutil
import string

# 配置
source_dir = "Ycalculate_file"
files_to_copy = ["INCAR", "POTCAR", "sub2.sh"]
group_chars = list(string.ascii_lowercase)  # a, b, c, ... z

# 遍历每个字母文件夹 a/b/c...
for g in group_chars:
    if not os.path.isdir(g):
        continue
    # 遍历该文件夹下所有数字子文件夹
    for sub in os.listdir(g):
        sub_path = os.path.join(g, sub)
        if not os.path.isdir(sub_path):
            continue
        # 复制每个文件
        for f in files_to_copy:
            src = os.path.join(source_dir, f)
            dst = os.path.join(sub_path, f)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                print(f"Copied: {dst}")

print("All files copied successfully!")