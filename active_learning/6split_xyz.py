"""
=============================================================================
脚本:        split_xyz.py
分类:        数据划分脚本
功能:        读取XYZ数据集文件，按80%/20%比例随机划分为训练集与测试集，
             分别写入train.xyz与test.xyz；支持指定随机种子保证可复现。
使用方法:    python split_xyz.py <active_structures.xyz> [输出目录] [随机种子]
参数:
  active_structures.xyz   输入XYZ数据集文件（必填）
  输出目录                结果输出目录（可选，默认 C:/Users/29828/Desktop/NEP/1_train）
  随机种子                随机数种子，保证划分结果可复现（可选，默认 42）
输出:
  */train.xyz        训练集结构（80%）
  */test.xyz         测试集结构（20%）
作者:        Hongbo Sun
最后修改日期: 2026‑08‑21
=============================================================================
# 目录树示例:
# ============================================================================
# .
# ├── active_structures.xyz
# ├── split_xyz.py
# └── NEP/
#     ├── train.xyz        训练集（80%）
#     └── test.xyz         测试集（20%）
# ============================================================================
"""
import os
import sys
import random

from ase.io import read, write


def main():
    if len(sys.argv) < 2:
        print("用法: python split_xyz.py <active_structures.xyz> [输出目录] [随机种子]")
        sys.exit(1)

    input_path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else r"C:\Users\29828\Desktop\NEP\1_train"
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 42

    print(f"读取数据集: {input_path}")
    atoms_list = read(input_path, index=":")
    total = len(atoms_list)
    if total == 0:
        print("错误: 数据集中没有结构")
        sys.exit(1)

    random.seed(seed)
    indices = list(range(total))
    random.shuffle(indices)

    n_train = int(round(total * 0.8))
    train_idx = sorted(indices[:n_train])
    test_idx = sorted(indices[n_train:])

    os.makedirs(out_dir, exist_ok=True)
    train_path = os.path.join(out_dir, "train.xyz")
    test_path = os.path.join(out_dir, "test.xyz")

    write(train_path, [atoms_list[i] for i in train_idx])
    write(test_path, [atoms_list[i] for i in test_idx])

    print(f"总结构数: {total}")
    print(f"训练集: {len(train_idx)}  (80%)  -> {train_path}")
    print(f"测试集: {len(test_idx)}  (20%)  -> {test_path}")


if __name__ == "__main__":
    main()
