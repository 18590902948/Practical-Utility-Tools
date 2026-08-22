"""
=============================================================================
脚本:        5xyzs2xyz_folder.py
功能:        合并多个文件夹中的 xyz/extxyz 文件：
             1) 不传参数：自动检测脚本所在目录下的所有子文件夹，按文件夹名排序合并；
             2) 传参数：按命令行参数指定的文件夹顺序合并（参数为已存在目录时
                直接使用，否则相对脚本所在目录解析）。
             终端展示检测结果（第一列文件夹名，第二列格式，格式列右对齐）；
             将包含相同格式的文件夹里的 xyz / extxyz 文件分别合并
使用方法:    python 5xyzs2xyz_folder.py
             python 5xyzs2xyz_folder.py 文件夹1 文件夹2 文件夹3
参数说明:    文件夹1 文件夹2 ... 按顺序指定要合并的文件夹
运行位置:    脚本所在目录（不传参数时自动扫描其子文件夹）
输出:        merged.xyz（所有 xyz 文件合并）
             merged.extxyz（所有 extxyz 文件合并）
=============================================================================
"""
import os
import sys


def collect_files(folder):
    """返回文件夹内的 (xyz 文件列表, extxyz 文件列表)，均按文件名排序"""
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


def resolve_folders(script_dir, args):
    """解析待合并的文件夹列表，返回按合并顺序排列的目录路径
    无参数: 自动扫描脚本目录下所有子文件夹（按文件夹名排序）
    有参数: 按参数顺序解析，参数为已存在目录则直接使用，否则相对脚本目录解析"""
    if not args:
        return [os.path.join(script_dir, d)
                for d in sorted(os.listdir(script_dir))
                if os.path.isdir(os.path.join(script_dir, d))]
    folders = []
    for a in args:
        folder = a if os.path.isdir(a) else os.path.join(script_dir, a)
        if not os.path.isdir(folder):
            print(f"警告: 文件夹不存在，已跳过: {a}")
            continue
        folders.append(folder)
    return folders


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

    # 解析待合并的文件夹（无参数自动扫描，有参数按指定顺序）
    folders = resolve_folders(script_dir, sys.argv[1:])
    if not folders:
        print("未找到任何文件夹！")
        return

    # 按指定顺序收集各文件夹中的 xyz/extxyz 文件
    groups = {"xyz": [], "extxyz": []}   # 格式 -> 文件路径列表
    table = []                            # (文件夹名, 格式)，用于终端展示
    for folder in folders:
        xyz_files, extxyz_files = collect_files(folder)
        d = os.path.basename(os.path.normpath(folder))
        for f in xyz_files:
            groups["xyz"].append(f)
            table.append((d, "xyz"))
        for f in extxyz_files:
            groups["extxyz"].append(f)
            table.append((d, "extxyz"))

    if not table:
        print("未找到含 xyz/extxyz 文件的文件夹！")
        return

    # 终端展示: 第一列文件夹名，第二列格式（右对齐）
    print("\n检测到含 xyz/extxyz 文件的文件夹:")
    print(f"  {'文件夹名':<22}{'格式':>8}")
    for d, fmt in table:
        print(f"  {d:<22}{fmt:>8}")

    # 按格式分别合并
    for fmt in ("xyz", "extxyz"):
        files = groups[fmt]
        if not files:
            continue
        out_file = os.path.join(script_dir, f"merged.{fmt}")
        print(f"\n合并 {len(files)} 个 .{fmt} 文件 -> {out_file}")
        merge_files(files, out_file)
        print(f"输出文件: {os.path.abspath(out_file)}")

    print("\n全部合并完成！")


if __name__ == "__main__":
    main()
