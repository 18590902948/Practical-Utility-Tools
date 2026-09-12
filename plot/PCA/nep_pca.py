# -*- coding: utf-8 -*-
"""
=============================================================================
Script:     nep_pca.py
Purpose:    利用目录中的 NEP 势函数模型（nep3/nep4，如 nep_gen20000.txt），
            对目录中的 xyz 结构/轨迹文件逐帧计算原子平均描述符，PCA 降维
            到前两个主成分并绘制散点图，输出一张 Nature 出版级 PNG。
Usage:      python nep_pca.py [-d DIR] [-x XYZ [XYZ ...]] [-n NEP] [-o NAME]
            默认：扫描脚本所在目录，*.xyz/*.extxyz 全部作为输入，
            自动探测 NEP 模型文件（首行形如 "nep4_zbl 3 Li Mo Te"）。
Output:     <脚本所在目录>/descriptor_pca.png（仅点图，无坐标轴）
            <脚本所在目录>/descriptor_pca.txt（PCA 投影坐标与方差占比）
Example:    python nep_pca.py -x train.xyz -n nep_gen20000.txt
            python nep_pca.py -x "dump_*.xyz" -o pca_new.png
Dependencies (须 Python 3.14 / 建议 sketch 环境):
            numpy  ase  matplotlib  scikit-learn
            NEP 引擎 nep_adapters 1.0.2 已随脚本携带于同目录 nep_adapters/ 文件夹
            （内含 cp314 编译引擎，锁 Python 3.14），无需 pip 安装
=============================================================================
"""
import argparse
import glob
import re
import sys
from pathlib import Path

import numpy as np

# Nature 规范：先设非交互后端，再导入 pyplot
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from ase.io import iread
from sklearn.decomposition import PCA

# Nature 出版级版式基线（字号 7 pt 对应单栏图）
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["font.size"] = 7
plt.rcParams["axes.spines.right"] = False
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.linewidth"] = 0.8
plt.rcParams["legend.frameon"] = False
plt.rcParams["xtick.labelsize"] = 7
plt.rcParams["ytick.labelsize"] = 7

# 低饱和出版调色板（色盲友好），单文件时使用主蓝
PALETTE = {
    "blue_main": "#0F4D92",
    "blue_pale": "#7C8ED0",
    "green_3": "#8BCF8B",
    "red_strong": "#B64342",
    "teal": "#42949E",
    "violet": "#9A4D8E",
    "gold": "#E0A800",
    "neutral_dark": "#4D4D4D",
}
SERIES_COLORS = [
    PALETTE["blue_main"],
    PALETTE["red_strong"],
    PALETTE["teal"],
    PALETTE["green_3"],
    PALETTE["violet"],
    PALETTE["gold"],
    PALETTE["neutral_dark"],
]

BATCH_SIZE = 512          # 描述符分批计算帧数，控制内存
# NEP 模型首行形如 "nep4_zbl 3 Li Mo Te"：类型前缀 + 类型数，即可认定
MODEL_HEAD_RE = re.compile(r"^\s*nep\d+(?:_[A-Za-z0-9]+)*\s+\d+", re.IGNORECASE)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="NEP descriptor PCA plot (PNG) for xyz files using the NEP model"
    )
    parser.add_argument(
        "-d", "--dir", type=str, default=None,
        help="directory to scan (default: folder of this script)",
    )
    parser.add_argument(
        "-x", "--xyz", nargs="+", default=None,
        help="xyz files or wildcards, repeatable; default: all *.xyz in --dir",
    )
    parser.add_argument(
        "-n", "--nep", type=str, default=None,
        help="NEP potential file; auto-detected when omitted",
    )
    parser.add_argument(
        "-o", "--output", type=str, default="descriptor_pca.png",
        help="output file name (default: descriptor_pca.png, .png auto-appended)",
    )
    return parser.parse_args(argv)


def script_dir():
    return Path(__file__).resolve().parent


def expand_patterns(items):
    """把可能含通配符的路径展开为存在的文件列表。"""
    files = []
    for item in items:
        path = Path(item)
        if any(ch in item for ch in "*?["):
            files.extend(Path(p) for p in sorted(glob.glob(item)))
        elif path.is_dir():
            files.extend(sorted(path.glob("*.xyz")) + sorted(path.glob("*.extxyz")))
        elif path.is_file():
            files.append(path)
        else:
            print(f" Error: file not found: {item}")
            sys.exit(1)
    return files


def find_nep_model(directory):
    """在目录中自动探测 NEP 模型：首行形如 'nep4_zbl 3 Li Mo Te' 的文本文件。"""
    candidates = []
    for path in sorted(directory.iterdir()):
        if not (path.suffix.lower() in (".txt", ".in", ".restart")):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                head = fh.readline()
        except OSError:
            continue
        if MODEL_HEAD_RE.match(head.strip()):
            candidates.append(path)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        names = ", ".join(p.name for p in candidates)
        print(f" Error: multiple NEP models detected ({names}); use -n to pick one")
        sys.exit(1)
    return None


def check_composition(calc, xyz_list, model_elements):
    """用每文件第一帧预检元素集合是否落在模型元素内。"""
    for path in xyz_list:
        for atoms in iread(path, index=":1"):
            symbols = set(atoms.get_chemical_symbols())
            unknown = symbols.difference(model_elements)
            if unknown:
                print(
                    f" Error: {path.name} contains elements outside the model "
                    f"({sorted(unknown)}); model elements: {', '.join(model_elements)}"
                )
                sys.exit(1)
            break


def compute_descriptors(calc, path):
    """逐批读取 xyz 帧并计算原子平均描述符，返回 (n_frames, dim) 数组。"""
    blocks = []
    batch = []
    total = 0
    for atoms in iread(path, index=":"):
        batch.append(atoms)
        if len(batch) >= BATCH_SIZE:
            blocks.append(np.asarray(calc.get_structures_descriptor(batch, mean_descriptor=True)))
            total += len(batch)
            batch = []
            print(f"\r Processing {path.name}: {total} frames", end="", flush=True)
    if batch:
        blocks.append(np.asarray(calc.get_structures_descriptor(batch, mean_descriptor=True)))
        total += len(batch)
    if not blocks:
        print(f" Error: no frame read from {path.name}")
        sys.exit(1)
    print(f"\r Processing {path.name}: done, {total} frames        ")
    return np.vstack(blocks)


def marker_params(n_points):
    """按总点数自适应散点大小与透明度；s 为面积(pt^2)，半径放大 1.5 倍。"""
    if n_points <= 3000:
        return 18.0, 0.80
    if n_points <= 20000:
        return 6.75, 0.50
    if n_points <= 80000:
        return 3.375, 0.35
    return 1.8, 0.22


def plot_pca(projected, file_index, file_names, out_path):
    """绘制无坐标轴的纯点图：单文件淡蓝填充点，多文件按来源分色。"""
    n_total = projected.shape[0]
    s, alpha = marker_params(n_total)
    fig, ax = plt.subplots(figsize=(3.45, 3.15))
    ax.set_facecolor("white")

    groups = list(np.unique(file_index))
    if len(groups) == 1:
        # 单文件：Nature 淡蓝填充点（无轮廓），靠点重叠自然呈现聚集
        ax.scatter(
            projected[:, 0], projected[:, 1],
            s=s, alpha=0.7, color=PALETTE["blue_pale"],
            linewidths=0, edgecolors="none", rasterized=True,
        )
    else:
        handles = []
        for color_index, group in enumerate(groups):
            mask = file_index == group
            ax.scatter(
                projected[mask, 0], projected[mask, 1],
                s=s, alpha=alpha,
                color=SERIES_COLORS[color_index % len(SERIES_COLORS)],
                linewidths=0, rasterized=True,
            )
            handles.append(
                plt.Line2D([0], [0], marker="o", linestyle="", markersize=3.2,
                           markerfacecolor=SERIES_COLORS[color_index % len(SERIES_COLORS)],
                           alpha=0.9, label=file_names[group])
            )
        ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.005, 0.5),
                  fontsize=6.8, handletextpad=0.4, borderaxespad=0.2)

    # 纯点图：不画坐标轴、刻度与轴标签（数值信息随同名 txt 输出）
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.tight_layout(pad=0.2)
    fig.savefig(out_path, dpi=600, bbox_inches="tight")
    plt.close(fig)


def save_pca_txt(out_txt, file_names, file_index, projected, explained, model_name):
    """把 PCA 投影坐标与方差占比写成带表头的 txt（每文件帧号从 0 起）。"""
    counts = np.bincount(file_index)
    offsets = np.zeros(len(counts), dtype=np.int64)
    np.cumsum(counts[:-1], out=offsets[1:])
    lines = [
        f"# NEP model: {model_name}",
        f"# PCA explained variance: PC1 {explained[0] * 100:.1f}%, "
        f"PC2 {explained[1] * 100:.1f}%",
        "# file  frame  PC1  PC2",
    ]
    for row in range(projected.shape[0]):
        file_id = file_index[row]
        lines.append(
            f"{file_names[file_id]} {row - offsets[file_id]} "
            f"{projected[row, 0]:.6e} {projected[row, 1]:.6e}"
        )
    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    args = parse_args(argv)

    base_dir = Path(args.dir).resolve() if args.dir else script_dir()
    if not base_dir.is_dir():
        print(f" Error: directory not found: {base_dir}")
        sys.exit(1)

    # 1. 收集 xyz 输入
    if args.xyz:
        xyz_list = expand_patterns(args.xyz)
    else:
        xyz_list = sorted(base_dir.glob("*.xyz")) + sorted(base_dir.glob("*.extxyz"))
    if not xyz_list:
        print(f" Error: no xyz/extxyz files found in {base_dir}")
        sys.exit(1)

    # 2. 定位势函数模型
    if args.nep:
        nep_path = Path(args.nep).resolve()
        if not nep_path.is_file():
            print(f" Error: NEP model file not found: {nep_path}")
            sys.exit(1)
    else:
        nep_path = find_nep_model(base_dir)
        if nep_path is None:
            print(f" Error: no NEP model auto-detected in {base_dir}; use -n to specify")
            sys.exit(1)

    # 3. 加载模型（优先脚本同目录携带的 nep_adapters/，支持 nep3/nep4 及其 zbl/电荷等变体）
    try:
        from nep_adapters import NEPCalculator, inspect_model
    except ImportError:
        print(" Error: NEP engine not found; keep the bundled nep_adapters/ folder "
              "next to this script (Python 3.14), or run: pip install nep-adapters")
        sys.exit(1)

    print(f" NEP model: {nep_path}")
    calc = NEPCalculator(nep_path, backend="cpu")
    model = inspect_model(nep_path)
    print(f" Model: {model.model_type} | elements {', '.join(model.elements)} | "
          f"descriptor dim {model.descriptor_dim}")
    check_composition(calc, xyz_list, set(model.elements))

    # 4. 计算各文件描述符
    print(f" XYZ files: {len(xyz_list)}")
    descriptors = []
    file_index = []
    file_names = []
    for index, path in enumerate(xyz_list):
        desc = compute_descriptors(calc, path)
        descriptors.append(desc)
        file_index.extend([index] * len(desc))
        file_names.append(path.name)
    all_desc = np.vstack(descriptors)
    file_index = np.asarray(file_index, dtype=int)
    print(f" Total frames: {all_desc.shape[0]} | descriptor dim: {all_desc.shape[1]}")

    # 5. PCA 降维
    reducer = PCA(n_components=2)
    projected = reducer.fit_transform(all_desc)
    explained = reducer.explained_variance_ratio_
    print(f" PCA explained variance: PC1 {explained[0] * 100:.1f}%, "
          f"PC2 {explained[1] * 100:.1f}%")

    # 6. 输出纯点 PNG + PCA 数据 txt 到脚本所在目录
    out_name = args.output if args.output.lower().endswith(".png") else args.output + ".png"
    out_path = script_dir() / out_name
    out_txt = out_path.with_suffix(".txt")
    plot_pca(projected, file_index, file_names, out_path)
    save_pca_txt(out_txt, file_names, file_index, projected, explained, nep_path.name)
    print(f" Output: {out_path}")
    print(f" Output: {out_txt}")


if __name__ == "__main__":
    main()
