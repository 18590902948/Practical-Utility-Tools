#!/usr/bin/env python3
"""
从所有 md/traj.extxyz 中提取最后 300K 弛豫阶段的结构，
每 10 帧采样 1 帧（共 30 帧/结构），保存到：
  1. 每个 den_*/Structural_sampling/ 下（单独 xyz 文件，含 x 和 density 元信息）
  2. NEW/ 下汇总为一个总 xyz 文件（所有结构含 x 和 density 元信息）
"""

import os
import re
import glob
from ase.io import read, write

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def extract_x_from_path(path):
    """从路径中提取 x 值，如 x_0.0 → 0.0"""
    match = re.search(r'x_(\d+\.?\d*)', path)
    return float(match.group(1)) if match else None


def extract_den_from_path(path):
    """从路径中提取密度值，如 den_2.0 → 2.0"""
    match = re.search(r'den_(\d+\.?\d*)', path)
    return float(match.group(1)) if match else None


def main():
    # 查找所有 traj.extxyz
    traj_files = sorted(glob.glob(
        os.path.join(SCRIPT_DIR, "x_*", "den_*", "md", "traj.extxyz")
    ))

    if not traj_files:
        print("❌ 未找到任何 traj.extxyz 文件！")
        return

    print(f"找到 {len(traj_files)} 个轨迹文件\n")

    all_frames = []
    total = 0

    for traj_path in traj_files:
        # 读取所有帧
        frames = read(traj_path, format="extxyz", index=":")
        n_total = len(frames)

        if n_total < 300:
            rel = os.path.relpath(traj_path, SCRIPT_DIR)
            print(f"⚠ {rel}: 仅 {n_total} 帧（不足 300），跳过")
            continue

        # 取最后 300 帧（300K 弛豫阶段）
        relax = frames[-300:]
        # 每 10 帧采 1 帧 → 30 帧
        sampled = relax[::10]

        # 提取元信息
        x_val = extract_x_from_path(traj_path)
        den_val = extract_den_from_path(traj_path)

        # 确定输出目录: x_*/den_*/Structural_sampling/
        den_dir = os.path.dirname(os.path.dirname(traj_path))  # 去掉 /md
        sampling_dir = os.path.join(den_dir, "Structural_sampling")
        os.makedirs(sampling_dir, exist_ok=True)

        # 命名
        x_dir = os.path.basename(os.path.dirname(den_dir))   # x_0.0
        den_name = os.path.basename(den_dir)                  # den_2.0
        out_name = f"{x_dir}_{den_name}_sampled.extxyz"
        out_path = os.path.join(sampling_dir, out_name)

        # 给每帧添加组分和密度元信息
        for frame in sampled:
            if x_val is not None:
                frame.info["x"] = x_val
            if den_val is not None:
                frame.info["density"] = den_val

        write(out_path, sampled, format="extxyz")

        all_frames.extend(sampled)

        print(f"  {x_dir}/{den_name}: {len(sampled)} 帧 (x={x_val}, density={den_val}) → {out_path}")
        total += len(sampled)

    # 汇总所有结构到 NEW/ 下
    combined_path = os.path.join(SCRIPT_DIR, "all_sampled_structures.extxyz")
    write(combined_path, all_frames, format="extxyz")

    print(f"\n✅ 共采样 {total} 帧")
    print(f"📄 分文件: 每个 Structural_sampling/ 目录下")
    print(f"📄 汇总文件: {combined_path}")
    print(f"\n💡 每帧 extxyz 头部包含: x=<组分值>  density=<密度值>")


if __name__ == "__main__":
    main()
