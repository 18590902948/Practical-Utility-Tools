"""
=============================================================================
脚本:        merge_clean_xyz.py
功能:        合并 1_md712/1_md2379/1_md2412/1_md3494/1_md3631 五个目录下的
             dump.xyz 为一个 merge_dump.xyz, 并清除注释行中的
             energy / virial / stress 等标签, 只保留基本结构标签
             (Time, pbc, Lattice, Properties)
参考:        Practical-Utility-Tools/active_learning/4merge_xyz.py   (合并)
             GPUMDkit/Scripts/format_conversion/clean_xyz.py        (清洗)
使用方法:    python merge_clean_xyz.py
             (可选) python merge_clean_xyz.py 目录1 目录2 ...
运行位置:    active_learning 目录下 (脚本基于自身位置定位输入目录)
输出:        active_learning/merge_clean/merge_dump.xyz
=============================================================================
"""
import os
import re
import sys

# 只保留的基本标签 (键名白名单), 其余 (energy/virial/stress/... ) 一律删除
KEEP_KEYS = {"Time", "pbc", "Lattice", "Properties"}

# 匹配注释行中的键值对: key=value 或 key="value with space"
TAG_RE = re.compile(r'(\w+)=("[^"]*"|\S+)')


def clean_comment(line):
    """删除注释行中不在白名单里的标签, 只保留基本结构信息"""
    tags = TAG_RE.findall(line)
    kept = [f"{k}={v}" for k, v in tags if k in KEEP_KEYS]
    return " ".join(kept) + "\n"


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    default_dirs = ["1_md712", "1_md2379", "1_md2412", "1_md3494", "1_md3631"]

    if len(sys.argv) > 1:
        target_dirs = sys.argv[1:]
    else:
        target_dirs = default_dirs

    out_dir = os.path.join(base_dir, "merge_clean")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "merge_dump.xyz")

    print(f"输出文件: {out_file}")

    total_frames = 0
    with open(out_file, "w") as fout:
        for d in target_dirs:
            xyz_path = os.path.join(base_dir, d, "dump.xyz")
            if not os.path.isfile(xyz_path):
                print(f"跳过 {xyz_path} 不存在")
                continue

            frames = 0
            with open(xyz_path) as fin:
                while True:
                    nline = fin.readline()
                    if not nline:
                        break
                    n = int(nline.split()[0])  # 本帧原子数
                    fout.write(nline)
                    fout.write(clean_comment(fin.readline()))
                    for _ in range(n):
                        fout.write(fin.readline())
                    frames += 1
            total_frames += frames
            print(f"完成 {d}/dump.xyz: {frames} 帧")

    print(f"全部完成! 共 {total_frames} 帧, 已保存到 {out_file}")


if __name__ == "__main__":
    main()
