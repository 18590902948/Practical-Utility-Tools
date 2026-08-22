"""
=============================================================================
脚本:        xyzs2xyz_file.py
功能:        合并脚本所在目录下的 xyz/extxyz 文件（文件直接位于目录中，非子文件夹）：
             1) 不传参数：自动扫描脚本所在目录下的所有 xyz/extxyz 文件，按文件名排序合并；
             2) 传参数：按命令行参数指定的文件顺序合并（参数为已存在文件时
                直接使用，否则相对脚本所在目录解析）。
             终端展示检测结果（第一列文件名，第二列格式，格式列右对齐）；
             将相同格式的文件分别合并
使用方法:    python xyzs2xyz_file.py
             python xyzs2xyz_file.py 文件1.xyz 文件2.xyz
参数说明:    文件1 文件2 ... 按顺序指定要合并的文件
运行位置:    脚本所在目录
输出:        merged.xyz（所有 xyz 文件合并）
             merged.extxyz（所有 extxyz 文件合并）
=============================================================================
"""
import os
import sys


def collect_files(folder):
    """返回文件夹内直接存放的 (xyz 文件列表, extxyz 文件列表)，均按文件名排序"""
    xyz_files, extxyz_files = [], []
    for name in sorted(os.listdir(folder)):
        full = os.path.join(folder, name)
        if not os.path.isfile(full):
            continue
        if name.endswith(".extxyz"):
            extxyz_files.append(full)
        elif name.endswith(".xyz"):
            xyz_files.append(full)
    return xyz_files, extxyz_files


def resolve_files(script_dir, args):
    """解析待合并的文件列表，返回按合并顺序排列的文件路径
    无参数: 自动扫描脚本目录下的所有 xyz/extxyz 文件（按文件名排序）
    有参数: 按参数顺序解析，参数为已存在文件则直接使用，否则相对脚本目录解析"""
    if not args:
        xyz_files, extxyz_files = collect_files(script_dir)
        return xyz_files + extxyz_files
    files = []
    for a in args:
        f = a if os.path.isfile(a) else os.path.join(script_dir, a)
        if not os.path.isfile(f):
            print(f"警告: 文件不存在，已跳过: {a}")
            continue
        files.append(f)
    return files


def merge_files(file_list, out_file, buf_size=1024 * 1024):
    """将多个文件按顺序拼接为一个文件（行为等价 cat）
    自动检查每个文件末尾，缺换行符则补一个，防止帧粘连"""
    with open(out_file, "w") as fout:
        for f in file_list:
            print(f"  处理 {f} ...", end=" ")
            last_chunk = ""
            with open(f, "r") as fin:
                while True:
                    chunk = fin.read(buf_size)
                    if not chunk:
                        break
                    fout.write(chunk)
                    last_chunk = chunk
            # 文件末尾缺换行符时补一个，避免与下一个文件拼接时两帧挤在一起
            if last_chunk and not last_chunk.endswith("\n"):
                fout.write("\n")
            print("完成")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"脚本所在目录: {script_dir}")

    # 解析待合并的文件（无参数自动扫描，有参数按指定顺序）
    files = resolve_files(script_dir, sys.argv[1:])
    if not files:
        print("未找到任何 xyz/extxyz 文件！")
        return

    # 按格式分组（保持文件顺序）
    groups = {"xyz": [], "extxyz": []}   # 格式 -> 文件路径列表
    for f in files:
        if f.endswith(".extxyz"):
            groups["extxyz"].append(f)
        else:
            groups["xyz"].append(f)

    # 终端展示: 第一列文件名，第二列格式（右对齐）
    print("\n检测到 xyz/extxyz 文件:")
    print(f"  {'文件名':<22}{'格式':>8}")
    for f in files:
        fmt = "extxyz" if f.endswith(".extxyz") else "xyz"
        print(f"  {os.path.basename(f):<22}{fmt:>8}")

    # 按格式分别合并
    for fmt in ("xyz", "extxyz"):
        f_list = groups[fmt]
        if not f_list:
            continue
        out_file = os.path.join(script_dir, f"merged.{fmt}")
        print(f"\n合并 {len(f_list)} 个 .{fmt} 文件 -> {out_file}")
        merge_files(f_list, out_file)
        print(f"输出文件: {os.path.abspath(out_file)}")

    print("\n全部合并完成！")


if __name__ == "__main__":
    main()
