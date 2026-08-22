"""
=============================================================================
脚本:        5merge_xyz.py
功能:        自动检测脚本所在目录下的子文件夹中是否含有 xyz/extxyz 文件，
             终端展示检测结果（第一列文件夹名，第二列格式，格式列右对齐）；
             将包含相同格式的文件夹里的 xyz / extxyz 文件分别合并
使用方法:    python 5merge_xyz.py
运行位置:    脚本所在目录（自动扫描其子文件夹，无需在特定目录运行）
输出:        merged.xyz（所有 xyz 文件合并）
             merged.extxyz（所有 extxyz 文件合并）
=============================================================================
"""
import os


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

    # 检测脚本目录下所有子文件夹中的 xyz/extxyz 文件
    groups = {"xyz": [], "extxyz": []}   # 格式 -> 文件路径列表
    table = []                            # (文件夹名, 格式)，用于终端展示
    for d in sorted(os.listdir(script_dir)):
        folder = os.path.join(script_dir, d)
        if not os.path.isdir(folder):
            continue
        xyz_files, extxyz_files = collect_files(folder)
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
