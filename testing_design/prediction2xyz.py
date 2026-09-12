#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==================================================================================================
# prediction2xyz.py —— 用 NEP 预测模式的输出给 train.xyz 重新标注
# ==================================================================================================
#
# 【NEP 预测量在哪里】prediction 模式 (nep.in 里写 prediction 1) 固定只评估 train.xyz,
# 输出 4 个纯数字矩阵文件 (都在预测目录, 即运行 nep 的目录):
#   energy_train.out : 每行一帧, 第 1 列 = 预测能量 (eV/atom), 第 2 列 = xyz 中原有的参考值
#   force_train.out  : 每行一原子 (按帧序、原子序), 前 3 列 = 预测力 (eV/Å), 后 3 列 = 原参考值
#   virial_train.out : 每行一帧, 前 6 列 = 预测维里 (eV/atom, 分量序 xx yy zz xy yz zx), 后 6 列 = 原参考值
#   stress_train.out : 每行一帧, 前 6 列 = 预测应力 (GPa, 分量序同上), 后 6 列 = 原参考值
#   (目标缺失的行, 对应目标列为 -1e+06 哨兵值; 预测列永远是有效值)
#   源码: snes.cu 预测分支 (读 nep.txt 权重后调用 Fitness::predict);
#         fitness.cu Fitness::predict (写上述 4 个文件)
#
# 【本脚本做什么】复制一份 train.xyz (原件不动), 清除其中原有的能量/力/维里/应力标注,
# 再写入 NEP 预测量。单位换算依据 GPUMD-5.6 文档 (train_test_xyz.rst) 与源码 (structure.cu):
#   energy=  总量 eV          = energy_train.out 第 1 列 × 原子数  (源码读取时再除以原子数)
#   force    eV/Å             = force_train.out 前 3 列
#   virial=  总量 eV (9 分量)  = virial_train.out 前 6 列 × 原子数, 展开为 9 分量
#             文件分量序 vxx vxy vxz vyx vyy vyz vzx vzy vzz
#             = out [0, 3, 5, 3, 1, 4, 5, 4, 2]  (源码 structure.cu reduced_index 映射)
#   stress=  eV/Å^3 (可选 --stress) = -virial/体积  (文档: virial 正=压缩, stress 正=拉伸;
#             源码读取 stress 时乘以 -V/原子数, 故写回时 stress = -virial/V)
#             注: stress_train.out 单位是 GPa (factor 160.21766), 本脚本由预测 virial 换算, 结果等价
#
# 【用法】在预测目录 (train.xyz 与 4 个 .out 放一起) 下运行:
#   python3 prediction2xyz.py                    # train.xyz -> train_NEP.xyz
#   python3 prediction2xyz.py -i train.xyz -o my_nep.xyz
#   python3 prediction2xyz.py --stress           # 额外把 stress= 也写上
#
# 【注意】virial 与 stress 是同一个量的两种表示, 一般二选一; 两者都写时 GPUMD/nep 优先读 virial。
# ==================================================================================================

import argparse
import os
import sys


def iter_rows(path):
    """流式读取纯数字矩阵文件, 每行返回一个 float 列表"""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            tokens = line.split()
            if tokens:
                yield [float(x) for x in tokens]


def split_comment(line):
    """按空白拆分 comment 行, 保留 "..." 引号内部的整体 token (引号可出现在 token 中段, 如 Lattice="...")"""
    tokens, i, n = [], 0, len(line)
    while i < n:
        while i < n and line[i].isspace():
            i += 1
        if i >= n:
            break
        j = i
        while j < n:
            if line[j] == '"':
                k = line.find('"', j + 1)
                j = n if k == -1 else k + 1
            elif line[j].isspace():
                break
            else:
                j += 1
        tokens.append(line[i:j])
        i = j
    return tokens


def unquote(value):
    return value.strip('"')


def parse_properties(value):
    """'species:S:1:pos:R:3:forces:R:3' -> [('species','S',1), ('pos','R',3), ...]"""
    parts = unquote(value).split(":")
    props = []
    for k in range(0, len(parts) - 2, 3):
        props.append((parts[k], parts[k + 1], int(parts[k + 2])))
    return props


def format_properties(props):
    return ":".join("%s:%s:%d" % (name, dtype, count) for name, dtype, count in props)


def det3(m):
    """3x3 矩阵行列式 (m 为 9 个数的行主序列表)"""
    return (
        m[0] * (m[4] * m[8] - m[5] * m[7])
        - m[1] * (m[3] * m[8] - m[5] * m[6])
        + m[2] * (m[3] * m[7] - m[4] * m[6])
    )


def fmt(x):
    return "%.10g" % x


def main():
    # 兼容 Windows 控制台 (GBK) 无法编码的字符
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")

    parser = argparse.ArgumentParser(
        description="用 NEP prediction 模式的输出给 train.xyz 重新标注 (清旧标签, 写 NEP 预测值)"
    )
    parser.add_argument("-i", "--input", default="train.xyz", help="待标注的 xyz (默认 train.xyz)")
    parser.add_argument("-o", "--output", default="train_NEP.xyz", help="输出 xyz (默认 train_NEP.xyz)")
    parser.add_argument("--stress", action="store_true", help="额外写入 stress= (eV/Angstrom^3)")
    args = parser.parse_args()

    in_dir = os.path.dirname(os.path.abspath(args.input))
    files = {
        "energy": os.path.join(in_dir, "energy_train.out"),
        "force": os.path.join(in_dir, "force_train.out"),
        "virial": os.path.join(in_dir, "virial_train.out"),
    }
    for name, path in [("输入 xyz", args.input)] + list(files.items()):
        if not os.path.isfile(path):
            sys.exit("错误: 找不到文件 (%s): %s" % (name, path))

    energy_rows = list(iter_rows(files["energy"]))  # 每行一帧
    virial_rows = list(iter_rows(files["virial"]))  # 每行一帧
    force_iter = iter_rows(files["force"])          # 每行一原子, 流式消费

    num_frames = 0
    num_atoms_total = 0
    with open(args.input, "r", encoding="utf-8", errors="ignore") as fin, \
            open(args.output, "w", encoding="utf-8", newline="\n") as fout:
        while True:
            count_line = fin.readline()
            if not count_line:
                break
            if not count_line.strip():
                continue
            n_atom = int(count_line.split()[0])
            comment = fin.readline().rstrip("\r\n")
            atom_lines = [fin.readline() for _ in range(n_atom)]

            if num_frames >= len(energy_rows) or num_frames >= len(virial_rows):
                sys.exit("错误: %s 的帧数多于预测输出行数, 文件不匹配 (检查 train.xyz 是否与本次预测一致)"
                         % args.input)

            e_pred = energy_rows[num_frames][0]        # eV/atom
            v_pred = virial_rows[num_frames][:6]       # eV/atom, xx yy zz xy yz zx

            # 预测量换算: 按总能量/总维里写入 (文档: energy/virial 为 per-cell 总量)
            e_total = e_pred * n_atom
            v9 = [v_pred[0], v_pred[3], v_pred[5], v_pred[3], v_pred[1], v_pred[4], v_pred[5], v_pred[4], v_pred[2]]
            v9_total = [v * n_atom for v in v9]

            # 第一遍: 找体积 (stress 需要), 并解析 properties 列布局
            volume = None
            keep_ranges = None
            total_columns = None
            for tok in split_comment(comment):
                if "=" not in tok:
                    continue
                key, value = tok.split("=", 1)
                key_l = key.lower()
                if key_l == "lattice":
                    nums = [float(x) for x in unquote(value).split()]
                    if len(nums) == 9:
                        volume = abs(det3(nums))
                elif key_l == "properties":
                    props = parse_properties(value)
                    total_columns = sum(count for _, _, count in props)
                    offset = 0
                    keep_ranges = []
                    for name, dtype, count in props:
                        if name.lower() not in ("force", "forces"):
                            keep_ranges.append((offset, count))
                        offset += count
            if keep_ranges is None:
                sys.exit("错误: 第 %d 帧的 comment 行缺少 Properties 字段" % (num_frames + 1))
            if args.stress and (volume is None or volume == 0.0):
                sys.exit("错误: 第 %d 帧缺少 Lattice (计算 stress 需要体积)" % (num_frames + 1))

            # 第二遍: 重建 comment 行 —— 清除旧能量/力/维里/应力, 写入 NEP 预测值
            new_tokens = []
            new_props_written = False
            has_energy = False
            has_virial = False
            has_stress = False
            for tok in split_comment(comment):
                if "=" not in tok:
                    new_tokens.append(tok)
                    continue
                key, value = tok.split("=", 1)
                key_l = key.lower()
                if key_l == "energy":
                    has_energy = True
                    new_tokens.append("%s=%s" % (key, fmt(e_total)))
                elif key_l == "virial":
                    has_virial = True
                    new_tokens.append('%s="%s"' % (key, " ".join(fmt(v) for v in v9_total)))
                elif key_l == "stress":
                    has_stress = True
                    if args.stress:
                        s9 = [-v / volume for v in v9_total]
                        new_tokens.append('%s="%s"' % (key, " ".join(fmt(v) for v in s9)))
                    # 未指定 --stress: 清掉原有 stress
                elif key_l == "properties":
                    props = parse_properties(value)
                    kept = [(n, d, c) for (n, d, c) in props if n.lower() not in ("force", "forces")]
                    new_tokens.append("%s=%s" % (key, format_properties(kept + [("forces", "R", 3)])))
                    new_props_written = True
                else:
                    new_tokens.append(tok)
            if not new_props_written:
                sys.exit("错误: 第 %d 帧缺少 Properties 字段" % (num_frames + 1))
            if not has_energy:
                new_tokens.append("energy=%s" % fmt(e_total))
            if not has_virial:
                new_tokens.append('virial="%s"' % " ".join(fmt(v) for v in v9_total))
            if args.stress and not has_stress:
                s9 = [-v / volume for v in v9_total]
                new_tokens.append('stress="%s"' % " ".join(fmt(v) for v in s9))

            fout.write("%d\n" % n_atom)
            fout.write(" ".join(new_tokens) + "\n")

            # 原子行: 保留非力列, 力列换成 NEP 预测值 (追加在末尾)
            for line in atom_lines:
                vals = line.split()
                if len(vals) != total_columns:
                    sys.exit("错误: 第 %d 帧原子行列数与 Properties 不一致" % (num_frames + 1))
                out_vals = []
                for offset, count in keep_ranges:
                    out_vals.extend(vals[offset:offset + count])
                try:
                    f_pred = next(force_iter)
                except StopIteration:
                    sys.exit("错误: force_train.out 行数不足 (原子数对不上, 检查 train.xyz 与本次预测是否一致)")
                out_vals.extend([fmt(f_pred[0]), fmt(f_pred[1]), fmt(f_pred[2])])
                fout.write(" ".join(out_vals) + "\n")

            num_frames += 1
            num_atoms_total += n_atom

    # 收尾校验
    if num_frames != len(energy_rows) or num_frames != len(virial_rows):
        sys.exit("错误: 预测输出行数 (%d/%d) 多于 %s 的帧数 (%d), 文件不匹配"
                 % (len(energy_rows), len(virial_rows), args.input, num_frames))
    for _ in force_iter:
        sys.exit("错误: force_train.out 行数多于 xyz 原子数, 文件不匹配")

    print("完成: %s" % args.output)
    print("  帧数 = %d, 原子数 = %d" % (num_frames, num_atoms_total))
    print("  已写入: energy= (总eV, 来自 energy_train.out), forces (eV/Angstrom, 来自 force_train.out),")
    print("          virial= (总eV, 来自 virial_train.out)" + (" , stress= (eV/Angstrom^3, 由 virial 换算)" if args.stress else ""))
    print("  原件 %s 未改动" % args.input)


if __name__ == "__main__":
    main()
