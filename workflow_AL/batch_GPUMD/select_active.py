#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
脚本:       select_active.py
用途:       主动学习一轮 MD 跑完后, 从每个 1_md*/active.xyz 中按不确定度
            筛选 top-N 结构, 合并为一个 xyz 文件, 供后续 DFT 单点批量标注。
背景:       active 模式 MD 输出的 active.xyz 会保存所有"超阈值"帧, 相邻帧
            高度冗余 (单个文件可达成千上万帧), 全部做 DFT 单点浪费机时;
            按帧级不确定度降序取每文件夹 top-N, 即可覆盖高价值结构。

运行位置:   必须在 1_md* 文件夹所在的目录下运行 (脚本文件本身可放在任意
            位置, 例如 weiyuanhui/, 运行时:
              cd <1_md* 所在目录>        # 例如 active_learning/
              python ../weiyuanhui/select_active.py
            脚本以"当前工作目录"为基准扫描 1_md* 文件夹)。

不确定度来源 (重要):
            每个 1_md*/active.xyz 文件, 每帧头部属性的 uncertainty=<值>。
            GPUMD active 模式在保存该帧时写入 (源码: src/measure/active.cu
            output_line2(), 帧属性 " uncertainty=%.8f"), 数值 = 该帧所有
            原子力不确定度 sigma_f 的最大值 (单位 eV/Angstrom), 与同目录
            active.out 中同一时刻的数值完全一致。
            ⚠ active.out 只有"时间 + 不确定度"两列, 不含结构信息,
              无法用来挑帧, 只适合看不确定度分布 / 调整下轮阈值。

输出:
            当前目录下新建 <outdir>/ (默认 selected_from_active/):
              selected_active.xyz  <- 合并后的筛选结构 (extxyz 格式)
              selected_active.txt  <- 终端打印内容的日志 (内容一致)
            ⚠ 每次运行都覆盖旧输出 (xyz 与 txt 均不追加)。
            每帧 Info 增加 source="1_mdXXX" 属性标注来源; 原始属性
            (uncertainty / energy / virial / stress / forces 等) 全部保留。

用法示例:
  python select_active.py                    # 每个文件夹取 top 15
  python select_active.py --top 20           # 每个文件夹取 top 20
  python select_active.py --min-unc 0.2      # 只保留 uncertainty >= 0.2 的帧
  python select_active.py --outdir select    # 自定义输出文件夹名
=============================================================================
"""

import argparse
import heapq
import os
import sys

# 超算 locale 可能非 UTF-8 (如 POSIX/C), 强制 stdout 用 UTF-8, 避免打印
# 中文/特殊字符 (如 Å) 时抛 UnicodeEncodeError (Windows 终端乱码不影响功能)。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np

try:
    from ase.io import iread, write
except ImportError:
    print("错误: 未找到 ASE (Python 库)。请安装: pip install ase")
    sys.exit(1)

MD_PREFIX = "1_md"          # MD 文件夹前缀 (与 train_xyz2model_xyz2.py 一致)
ACTIVE_FILE = "active.xyz"  # active 模式输出文件
DEFAULT_TOP = 15            # 每个文件夹默认取 top 15
LOG_FILE = "selected_active.txt"  # 日志文件名 (内容 = 终端打印, 覆盖写)


def parse_args():
    parser = argparse.ArgumentParser(
        description="从 1_md*/active.xyz 按不确定度筛选 top-N 结构并合并为一个 xyz")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP,
                        help=f"每个文件夹取不确定度最高的前 N 帧 (默认 {DEFAULT_TOP})")
    parser.add_argument("--min-unc", type=float, default=None,
                        help="只保留 uncertainty >= 该值的帧 (可选, 默认不过滤)")
    parser.add_argument("--outdir", type=str, default="selected_from_active",
                        help="输出文件夹名 (默认 selected_from_active)")
    parser.add_argument("--output", type=str, default="selected_active.xyz",
                        help="输出文件名 (默认 selected_active.xyz)")
    return parser.parse_args()


def find_md_folders():
    """扫描当前工作目录下所有 1_md* 文件夹。"""
    folders = sorted(
        name for name in os.listdir(".")
        if name.startswith(MD_PREFIX) and os.path.isdir(name))
    if not folders:
        print(f"错误: 当前目录下未发现任何 {MD_PREFIX}* 文件夹。")
        print(f"请确认已在 1_md* 所在目录下运行 (当前目录: {os.getcwd()})")
        sys.exit(1)
    return folders


def select_top_from(folder, top_n, min_unc):
    """读取 <folder>/active.xyz, 返回不确定度最高的 top_n 帧 (降序) 与统计。

    流式遍历 + 最小堆: 堆中只保留 top-N 帧对象, 大文件 (几十万帧) 也不会
    全部驻留内存。堆元素 (uncertainty, 全局帧序号, atoms) 中帧序号全局
    唯一, 保证元组比较不会落到 atoms 对象上。
    """
    path = os.path.join(folder, ACTIVE_FILE)
    if not os.path.isfile(path):
        return None, None, None

    heap = []
    n_frames = 0      # 读取的总帧数
    n_skipped = 0     # 被过滤的帧数 (无 uncertainty 属性 或 低于 min_unc)
    for atoms in iread(path):
        n_frames += 1
        u = atoms.info.get("uncertainty", None)
        if u is None or (min_unc is not None and u < min_unc):
            n_skipped += 1
            continue
        item = (u, n_frames, atoms)
        if len(heap) < top_n:
            heapq.heappush(heap, item)
        elif u > heap[0][0]:
            heapq.heapreplace(heap, item)

    selected = sorted(heap, key=lambda x: -x[0])  # 按 uncertainty 降序
    return selected, n_frames, n_skipped


def sanitize_info(atoms):
    """把 info 中字符串形式的 virial/stress 转成 9 元素 float 数组。

    GPUMD active.xyz 中 virial/stress 是引号包裹的字符串, ASE 读入后
    info['virial']/['stress'] 为 str; 而 ASE 写 extxyz 时会访问
    info['stress'].shape (extxyz.py write_xyz), 字符串直接崩溃。
    转成 9 元素数组后, ASE 会按 SPECIAL_3_3_KEYS 处理, 序列化回
    与 GPUMD 相同的 "virial=\"...\"" 格式。
    """
    for key in ("virial", "stress"):
        val = atoms.info.get(key)
        if isinstance(val, str):
            try:
                atoms.info[key] = np.array([float(x) for x in val.split()])
            except ValueError:
                pass  # 解析失败则保留原字符串, 不影响主流程
    return atoms


def main():
    args = parse_args()
    if args.top < 1:
        print("错误: --top 必须 >= 1")
        sys.exit(1)

    # 所有输出同时进终端和日志列表, 最后整体写入 txt (覆盖写, 不追加)
    log_lines = []

    def emit(msg=""):
        print(msg)
        log_lines.append(msg)

    folders = find_md_folders()
    emit(f"发现 {len(folders)} 个 {MD_PREFIX}* 文件夹")
    if args.top == DEFAULT_TOP:
        emit(f"开始筛选 (默认取 uncertainty 最高的前 {args.top} 帧)")
    else:
        emit(f"开始筛选 (取 uncertainty 最高的前 {args.top} 帧)")

    all_selected = []
    all_u = []          # 全部选中帧的 uncertainty, 用于末尾总统计
    n_total = len(folders)
    for i, folder in enumerate(folders, start=1):
        selected, n_frames, n_skipped = select_top_from(
            folder, args.top, args.min_unc)
        if selected is None:
            emit(f"  [跳过] {folder}: 无 {ACTIVE_FILE}, 该文件夹未跑 active 模式?")
            emit()
            continue
        u_vals = [u for u, _, _ in selected]
        u_min = min(u_vals) if u_vals else 0.0
        u_max = max(u_vals) if u_vals else 0.0
        u_mean = sum(u_vals) / len(u_vals) if u_vals else 0.0
        note = f" (过滤 {n_skipped} 帧)" if n_skipped else ""
        emit(f"  [完成] {folder}: 共 {n_frames} 帧{note}, 取 top {len(selected)}")
        emit(f"               {len(selected)}帧的 uncertainty 范围 "
             f"{u_min:.4f} ~ {u_max:.4f} eV/Å，平均 uncertainty = {u_mean:.4f}")
        cum = len(all_selected) + len(selected)
        emit(f"               已收集{len(selected)}帧，共收集{cum}帧，{i}/{n_total}")
        emit()
        for u, _, atoms in selected:
            atoms.info["source"] = folder  # 标注来源, 便于追溯
            sanitize_info(atoms)          # 修复 virial/stress 字符串写回崩溃
            all_selected.append(atoms)
            all_u.append(u)

    if not all_selected:
        emit("错误: 所有文件夹都没有筛选出任何帧, 请检查 active.xyz 是否为空 "
             "或 --min-unc 是否过高。")
        sys.exit(1)

    # 全部选中帧的总统计
    u_min_all = min(all_u)
    u_max_all = max(all_u)
    u_mean_all = sum(all_u) / len(all_u)
    emit(f"完成: 共 {len(all_selected)} 帧，{len(all_selected)}帧的 uncertainty 范围 "
         f"{u_min_all:.4f} ~ {u_max_all:.4f} eV/Å，平均 uncertainty = {u_mean_all:.4f}")

    # 写结构文件 (覆盖写, 不追加)
    os.makedirs(args.outdir, exist_ok=True)
    out_path = os.path.join(args.outdir, args.output)
    write(out_path, all_selected, format="extxyz")
    emit(f"结构已写入 ./{args.outdir}/{args.output}")

    # 写日志 (内容 = 终端打印的全部, 覆盖写, 不追加)
    emit(f"日志已写入 ./{args.outdir}/{LOG_FILE}")
    log_path = os.path.join(args.outdir, LOG_FILE)
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    main()
