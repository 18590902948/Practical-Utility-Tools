# -*- coding: utf-8 -*-
"""
=============================================================================
Script:     nep_pca.py
Purpose:    利用目录中的 NEP 势函数模型（nep3/nep4，如 nep_gen20000.txt），
            对目录中的 xyz 结构/轨迹文件逐帧计算原子平均描述符，PCA 降维
            到前两个主成分并绘制散点图，输出一张 Nature 出版级 PNG。
            同时输出每帧的平均单原子能量（E）。
Usage:      python nep_pca.py [-d DIR] [-x XYZ [XYZ ...]] [-n NEP] [-o NAME]
            默认：扫描脚本所在目录下的 input/ 子目录，*.xyz/*.extxyz 全部
            作为输入，自动探测 NEP 模型文件（首行形如 "nep4_zbl 3 Li Mo Te"）。
            -x 的相对路径优先在 input/ 下解析，找不到再回落到当前目录。
Output:     <脚本所在目录>/plot/descriptor_pca.png（主图：点图 + 底部水平色度条，无坐标轴；
            颜色浅→深对应单原子能量最小→最大）
            <脚本所在目录>/plot/descriptor_pca_scatter.png（纯点图，无坐标轴）
            <脚本所在目录>/plot/descriptor_pca_colorbar.png（单独的水平色度条）
            <脚本所在目录>/plot/descriptor_pca.txt（PCA 投影坐标、方差占比、
            每帧平均单原子能量 E 与 E 的取值区间，表头与数据列右对齐）
            plot/ 目录不存在时自动创建。
Example:    python nep_pca.py
            python nep_pca.py -x train.xyz -n nep_gen20000.txt
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
from matplotlib.cm import ScalarMappable
from matplotlib.colors import LinearSegmentedColormap, Normalize
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

# 低饱和出版调色板（色盲友好）
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

# 单原子位点能连续色标：浅 → 深（色度条左端=最小值，右端=最大值）
ENERGY_CMAP = LinearSegmentedColormap.from_list(
    "site_energy",
    ["#DEE7F3", "#A8BFDD", "#6E92C7", "#3566A2", PALETTE["blue_main"]],
)

BATCH_SIZE = 512          # 描述符分批计算帧数，控制内存
INPUT_DIRNAME = "input"   # 输入目录名（相对脚本所在目录）
OUTPUT_DIRNAME = "plot"   # 输出目录名（相对脚本所在目录，缺失时自动创建）
# NEP 模型首行形如 "nep4_zbl 3 Li Mo Te"：类型前缀 + 类型数，即可认定
MODEL_HEAD_RE = re.compile(r"^\s*nep\d+(?:_[A-Za-z0-9]+)*\s+\d+", re.IGNORECASE)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="NEP descriptor PCA plot (PNG) for xyz files using the NEP model"
    )
    parser.add_argument(
        "-d", "--dir", type=str, default=None,
        help="input directory to scan (default: <script dir>/input)",
    )
    parser.add_argument(
        "-x", "--xyz", nargs="+", default=None,
        help="xyz files or wildcards, repeatable; relative paths resolve against "
             "--dir first; default: all *.xyz/*.extxyz in --dir",
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


def input_dir():
    """输入目录 <脚本所在目录>/input。"""
    return script_dir() / INPUT_DIRNAME


def ensure_output_dir():
    """输出目录 <脚本所在目录>/plot，缺失时自动创建。"""
    out_dir = script_dir() / OUTPUT_DIRNAME
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def expand_patterns(items, base_dir):
    """把可能含通配符的输入展开为文件列表；相对路径优先在 base_dir 下解析。"""
    files = []
    for item in items:
        path = Path(item)
        if any(ch in item for ch in "*?["):
            pattern = str(path if path.is_absolute() else base_dir / item)
            matched = sorted(glob.glob(pattern))
            if not matched and not path.is_absolute():
                matched = sorted(glob.glob(item))
            files.extend(Path(p) for p in matched)
            continue
        if not path.is_absolute() and (base_dir / item).exists():
            path = base_dir / item
        if path.is_dir():
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


def compute_batch(calc, batch, combined=True):
    """单批次前向：返回 (逐帧平均描述符, 逐帧平均单原子位点能)。"""
    if combined:
        prediction, atom_desc = calc.predict_with_descriptors_structures(batch)
    else:
        prediction = calc.predict_structures(batch)
        atom_desc = calc.predict_descriptors(batch)
    counts = np.asarray(prediction.atom_counts, dtype=np.int64)
    offsets = np.r_[0, np.cumsum(counts)]
    mean_desc = np.asarray(
        [atom_desc[offsets[i]:offsets[i + 1]].mean(axis=0) for i in range(len(counts))],
        dtype=np.float64,
    )
    # 位点能逐原子求和即总能，除以原子数即该帧的平均单原子位点能
    return mean_desc, np.asarray(prediction.energy, dtype=np.float64) / counts


def compute_descriptors(calc, path, combined=True):
    """逐批读取 xyz 帧，返回 (平均描述符 (n_frames, dim), 平均位点能 (n_frames,))。"""
    desc_blocks = []
    energy_blocks = []
    batch = []
    total = 0
    for atoms in iread(path, index=":"):
        batch.append(atoms)
        if len(batch) >= BATCH_SIZE:
            desc, energy = compute_batch(calc, batch, combined)
            desc_blocks.append(desc)
            energy_blocks.append(energy)
            total += len(batch)
            batch = []
            print(f"\r Processing {path.name}: {total} frames", end="", flush=True)
    if batch:
        desc, energy = compute_batch(calc, batch, combined)
        desc_blocks.append(desc)
        energy_blocks.append(energy)
        total += len(batch)
    if not desc_blocks:
        print(f" Error: no frame read from {path.name}")
        sys.exit(1)
    print(f"\r Processing {path.name}: done, {total} frames        ")
    return np.vstack(desc_blocks), np.concatenate(energy_blocks)


def marker_params(n_points):
    """按总点数自适应散点大小与透明度；s 为面积(pt^2)，半径放大 1.5 倍。"""
    if n_points <= 3000:
        return 18.0, 0.80
    if n_points <= 20000:
        return 6.75, 0.50
    if n_points <= 80000:
        return 3.375, 0.35
    return 1.8, 0.22


def energy_scale(site_energy):
    """位点能归一化区间与色条 mappable；色条用独立 mappable，避免继承散点 alpha。"""
    vmin = float(np.min(site_energy))
    vmax = float(np.max(site_energy))
    if vmax <= vmin:  # 全部数值相同时给一个退化区间，避免归一化报错
        vmin, vmax = vmin - 0.5, vmax + 0.5
    norm = Normalize(vmin=vmin, vmax=vmax)
    mappable = ScalarMappable(norm=norm, cmap=ENERGY_CMAP)
    mappable.set_array(np.asarray([vmin, vmax]))
    return vmin, vmax, norm, mappable


def draw_cloud(ax, projected, file_index, file_names, site_energy, norm):
    """在 ax 上画无坐标轴点云：颜色编码位点能，多文件用点形状区分来源。"""
    s, alpha = marker_params(projected.shape[0])
    ax.set_facecolor("white")
    groups = list(np.unique(file_index))
    markers = ["o", "s", "^", "D", "v", "P", "X"]
    if len(groups) == 1:
        # 单文件：颜色只编码位点能
        ax.scatter(
            projected[:, 0], projected[:, 1],
            s=s, alpha=0.7, c=site_energy, cmap=ENERGY_CMAP, norm=norm,
            linewidths=0, rasterized=True,
        )
    else:
        # 多文件：颜色仍编码位点能，改用点形状区分来源
        handles = []
        for index, group in enumerate(groups):
            mask = file_index == group
            marker = markers[index % len(markers)]
            ax.scatter(
                projected[mask, 0], projected[mask, 1],
                s=s, alpha=alpha, c=site_energy[mask], cmap=ENERGY_CMAP, norm=norm,
                marker=marker, linewidths=0, rasterized=True,
            )
            handles.append(
                plt.Line2D([0], [0], marker=marker, linestyle="", markersize=3.2,
                           markerfacecolor=PALETTE["neutral_dark"],
                           alpha=0.9, label=file_names[group])
            )
        ax.legend(handles=handles, loc="center left", bbox_to_anchor=(1.005, 0.5),
                  fontsize=6.8, handletextpad=0.4, borderaxespad=0.2)

    # 纯点图：不画坐标轴、刻度与轴标签（数值信息由色度条与同名 txt 承担）
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])


def style_colorbar(cbar, vmin, vmax):
    """统一色度条样式：无边框，三档刻度，右端深色对应最大值。"""
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(labelsize=6.8, length=2, width=0.6, pad=2)
    cbar.set_ticks([vmin, 0.5 * (vmin + vmax), vmax])
    cbar.ax.set_xticklabels(
        [f"{vmin:.2f}", f"{0.5 * (vmin + vmax):.2f}", f"{vmax:.2f}"]
    )
    cbar.set_label("$E$ (eV/atom)", fontsize=6.8, labelpad=3)


def plot_pca(projected, file_index, file_names, site_energy, out_path):
    """输出三张 PNG：纯点图、单独色度条、点图 + 色度条（主图沿用 out_path）。"""
    vmin, vmax, norm, mappable = energy_scale(site_energy)
    out_cloud = out_path.with_name(f"{out_path.stem}_scatter{out_path.suffix}")
    out_bar = out_path.with_name(f"{out_path.stem}_colorbar{out_path.suffix}")

    # 1. 纯点图
    fig, ax = plt.subplots(figsize=(3.45, 3.15))
    draw_cloud(ax, projected, file_index, file_names, site_energy, norm)
    fig.tight_layout(pad=0.2)
    fig.savefig(out_cloud, dpi=600, bbox_inches="tight")
    plt.close(fig)

    # 2. 单独色度条（左浅=最小位点能，右深=最大位点能），尺寸与主图内嵌色条一致
    fig = plt.figure(figsize=(3.45, 0.55))
    cax = fig.add_axes([0.03, 0.50, 0.927, 0.224])
    cbar = fig.colorbar(mappable, cax=cax, orientation="horizontal")
    style_colorbar(cbar, vmin, vmax)
    fig.savefig(out_bar, dpi=600, bbox_inches="tight")
    plt.close(fig)

    # 3. 点图 + 色度条
    fig, ax = plt.subplots(figsize=(3.45, 3.15))
    draw_cloud(ax, projected, file_index, file_names, site_energy, norm)
    cbar = fig.colorbar(mappable, ax=ax, orientation="horizontal",
                        fraction=0.055, pad=0.05, aspect=26)
    style_colorbar(cbar, vmin, vmax)
    fig.tight_layout(pad=0.2)
    fig.savefig(out_path, dpi=600, bbox_inches="tight")
    plt.close(fig)

    return [out_cloud, out_bar, out_path]


def save_pca_txt(out_txt, file_names, file_index, projected, explained,
                 model_name, site_energy):
    """把 PCA 投影坐标、方差占比与每帧平均位点能写成列右对齐的 txt。"""
    counts = np.bincount(file_index)
    offsets = np.zeros(len(counts), dtype=np.int64)
    np.cumsum(counts[:-1], out=offsets[1:])
    header = ("file", "frame", "PC1", "PC2", "E")
    rows = [
        (
            file_names[file_index[row]],
            str(row - offsets[file_index[row]]),
            f"{projected[row, 0]:.6e}",
            f"{projected[row, 1]:.6e}",
            f"{site_energy[row]:.6e}",
        )
        for row in range(projected.shape[0])
    ]
    widths = [len(label) for label in header]
    for row in rows:
        for column, cell in enumerate(row):
            widths[column] = max(widths[column], len(cell))
    lines = [
        f"# NEP model: {model_name}",
        f"# PCA explained variance: PC1 {explained[0] * 100:.1f}%, "
        f"PC2 {explained[1] * 100:.1f}%",
        f"# E range: {float(np.min(site_energy)):.4f} ~ "
        f"{float(np.max(site_energy)):.4f} eV/atom (min ~ max)",
        "# E = per-frame mean atomic energy (eV/atom)",
        "# " + "  ".join(label.rjust(width) for label, width in zip(header, widths)),
    ]
    for row in rows:
        # 数据行补上与表头 "# " 等宽的前缀，保证两者逐列对齐
        lines.append("  " + "  ".join(cell.rjust(width) for cell, width in zip(row, widths)))
    out_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    args = parse_args(argv)

    base_dir = Path(args.dir).resolve() if args.dir else input_dir()
    if not base_dir.is_dir():
        print(f" Error: input directory not found: {base_dir}")
        sys.exit(1)

    # 1. 收集 xyz 输入
    if args.xyz:
        xyz_list = expand_patterns(args.xyz, base_dir)
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
        if nep_path is None and base_dir != script_dir():
            # input/ 未放模型时，回落到脚本所在目录再探测一次
            nep_path = find_nep_model(script_dir())
        if nep_path is None:
            print(f" Error: no NEP model auto-detected in {base_dir} or "
                  f"{script_dir()}; use -n to specify")
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

    # 4. 计算各文件描述符与逐帧平均位点能
    print(f" XYZ files: {len(xyz_list)}")
    combined = model.supports("evaluate_with_descriptors")
    descriptors = []
    site_energies = []
    file_index = []
    file_names = []
    for index, path in enumerate(xyz_list):
        desc, site = compute_descriptors(calc, path, combined)
        descriptors.append(desc)
        site_energies.append(site)
        file_index.extend([index] * len(desc))
        file_names.append(path.name)
    all_desc = np.vstack(descriptors)
    site_energy = np.concatenate(site_energies)
    file_index = np.asarray(file_index, dtype=int)
    print(f" Total frames: {all_desc.shape[0]} | descriptor dim: {all_desc.shape[1]}")
    print(f" Site energy: {site_energy.min():.4f} ~ {site_energy.max():.4f} eV/atom")

    # 5. PCA 降维
    reducer = PCA(n_components=2)
    projected = reducer.fit_transform(all_desc)
    explained = reducer.explained_variance_ratio_
    print(f" PCA explained variance: PC1 {explained[0] * 100:.1f}%, "
          f"PC2 {explained[1] * 100:.1f}%")

    # 6. 输出纯点 PNG + PCA 数据 txt 到 plot/（缺失时自动创建）
    out_name = args.output if args.output.lower().endswith(".png") else args.output + ".png"
    out_path = ensure_output_dir() / out_name
    out_txt = out_path.with_suffix(".txt")
    out_paths = plot_pca(projected, file_index, file_names, site_energy, out_path)
    save_pca_txt(out_txt, file_names, file_index, projected, explained,
                 nep_path.name, site_energy)
    for path in out_paths:
        print(f" Output: {path}")
    print(f" Output: {out_txt}")


if __name__ == "__main__":
    main()
