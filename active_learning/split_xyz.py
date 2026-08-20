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
