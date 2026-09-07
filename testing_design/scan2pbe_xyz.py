#!/usr/bin/env python3
"""
=============================================================================
脚本:        scan2pbe_xyz.py
分类:        格式转换工具
功能:        将 SCAN 泛函 MLIP (如 SevenNet-Omni) 输出的 extxyz 轨迹逐帧
             转换为 PBE (nep2xyz 风格) extxyz 文件: Properties 列名
             forces 改为 force、删除 SCAN 专用键 (probability/umlip/
             free_energy)、补充 config_type=nep2xyz 与 volume (由
             Lattice 行列式计算)、属性行按 PBE 顺序重排，原子行
             坐标/力数值文本原样保留 (不损失精度)。
使用方法:    python scan2pbe_xyz.py 输入xyz文件 [更多输入...] [-o 输出]
参数:        输入xyz文件    SCAN 泛函 extxyz 轨迹文件 (可多个或含通配符;
                         不带点路径先按当前运行目录探测, 不存在再相对
                         脚本所在目录解析)
             -o/--output  输出文件或目录: 以 .xyz/.extxyz 结尾视为输出
                         文件完整路径 (仅限单输入), 否则视为输出目录;
                         省略时输出到配置区 OUTPUT_PATH (默认脚本目录下 scan_pbe/)
             -h/--help    显示本帮助
输入文件:    ScC-ycfang.xyz  (SCAN 泛函格式, SevenNet 输出)
输出文件:    ScC-ycfang_pbe.xyz  (PBE/nep2xyz 格式, 同名自动覆盖)
             scan2pbe_xyz.txt      (转换记录文件, 表格形式, 表头+6列)
输出路径:    默认输出到脚本所在目录下 scan_pbe/ 子文件夹 (配置区
             OUTPUT_PATH)，可用 -o 指定目录或文件路径，
             输出 xyz 与记录 txt 同在此目录
转换规则:
  1. Properties 中列名 forces -> force (其余列保留)
  2. 属性行重排为 PBE 顺序: Lattice Properties config_type virial
     volume energy pbc (缺失键省略, 其余未知键保留在 pbc 之后)
  3. 删除 SCAN 专用键: probability / umlip / free_energy
  4. 新增 config_type=nep2xyz 与 volume (由 Lattice 行列式计算)
  5. 原子行输出为 "元素 坐标 力", 数值文本原样保留 (不重格式化)
-o 双形式:   -o ./pbe_out        输出目录 (文件名用默认规则)
             -o ./a_pbe.xyz        输出文件完整路径 (仅单输入)
帧号约定:    记录文件中帧号为 1 起始的文件内帧序
示例:
  python scan2pbe_xyz.py ./ScC-ycfang.xyz
  python scan2pbe_xyz.py ./ScC-ycfang.xyz -o ./pbe_out
  python scan2pbe_xyz.py ./ScC-ycfang.xyz -o ./ScC_pbe.xyz
  python scan2pbe_xyz.py ./*.xyz -o ./pbe_out
作者:        隼蝶.
最后修改日期: 2026-09-07
=============================================================================
"""

import datetime
import glob
import os
import re
import sys

# ============================== 参数配置区 =====================================
INPUT_FILES   = []                     # 输入文件列表 (支持通配符，相对 INPUT_PATH 展开；命令行参数优先)
RECORD_FILE   = "scan2pbe_xyz.txt"     # 转换记录文件 (表格形式，与输出文件同目录)
INPUT_PATH    = "./"                   # 输入文件寻找路径 (相对脚本所在目录)
OUTPUT_PATH   = "./scan_pbe/"           # 输出文件寻找路径 (相对脚本所在目录, 输出 xyz/txt 均在此)
OUT_SUFFIX    = "_pbe.xyz"             # 输出文件名后缀: 输入名去扩展名 + 后缀 (标识已转 PBE 格式)
DROP_KEYS     = ("probability", "umlip", "free_energy")  # SCAN 专用键 (转换时删除)
VOLUME_DIGITS = 7                      # volume 计算值保留小数位数
RECORD_HEADER = "# 输入文件  帧号  原子数  能量  状态  备注"   # 记录文件表头 (以#开头)
# =============================================================================

# ============================== 环境准备区 =====================================
# 终端 locale 可能非 UTF-8, 强制 stdout 用 UTF-8, 避免打印中文时抛
# UnicodeEncodeError (Windows 控制台 GBK 无法输出 emoji/部分中文)。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
# ===========================================================================


# ============================== 函数配置区 =====================================
def dw(s):
    """字符串显示宽度: 中文等宽字符按 2 列计, 用于终端/记录文件对齐。"""
    return sum(2 if ord(c) > 127 else 1 for c in str(s))


def pad(s, w, align="<"):
    """按显示宽度填充空格对齐: '<' 左对齐, '>' 右对齐。"""
    s = str(s)
    n = w - dw(s)
    return s + " " * n if align == "<" else " " * n + s


def col(s, w, align="<"):
    """单列: 按宽度对齐 + 列间 2 空格分隔。"""
    return pad(s, w, align) + "  "


def print_usage():
    """打印头部注释块 (脚本功能与完整使用方法)。"""
    print(__doc__)


def parse_args(argv):
    """解析命令行参数: 非选项位置参数一律视为输入文件 (可多个);
    -h/--help、-o/--output、-t/--target 为选项。
    返回 (输入文件列表, 输出路径或 None)。"""
    inputs = []
    out_arg = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif arg in ("-o", "--output"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -o/--output 需要一个输出文件或目录。")
                sys.exit(1)
            out_arg = argv[i + 1]
            i += 2
        elif arg in ("-t", "--target"):
            i += 1                      # 显式目标标记, 位置参数本即输入文件
        elif arg.startswith("-"):
            print(f"❌ 错误: 无法识别的选项 '{arg}'。")
            print_usage()
            sys.exit(1)
        else:
            inputs.append(arg)
            i += 1
    return inputs, out_arg


def expand_pattern(pattern, base_dir):
    """将单个文件模式展开为文件列表: 含通配符 (* ? [) 的按 glob 展开
    (相对 base_dir, 结果排序), 无通配符的字面路径原样返回。"""
    if any(ch in pattern for ch in "*?["):
        return sorted(glob.glob(os.path.join(base_dir, pattern)))
    return [os.path.join(base_dir, pattern)]


def resolve_inputs(script_dir, tokens):
    """解析输入文件: 命令行指定优先 (不带点路径先按当前运行目录探测,
    不存在再相对脚本目录展开), 未指定时用配置区 INPUT_FILES 展开
    (相对 INPUT_PATH)。返回输入文件绝对路径列表。"""
    files = []
    if tokens:
        for token in tokens:
            # 命令行: 当前运行目录优先, 无匹配再相对脚本所在目录
            for base in (os.getcwd(), script_dir):
                hits = expand_pattern(token, base)
                if hits:
                    files.extend(os.path.abspath(h) for h in hits)
                    break
        files = sorted(set(files))
        missing = [f for f in files if not os.path.isfile(f)]
        for m in missing:
            print(f"❌ 错误: 输入文件 '{m}' 不存在。")
        if missing:
            sys.exit(1)
    else:
        # 配置区默认: 相对 INPUT_PATH (脚本所在目录)
        base = os.path.normpath(os.path.join(script_dir, INPUT_PATH))
        for pat in INPUT_FILES:
            files.extend(expand_pattern(pat, base))
        files = [os.path.abspath(f) for f in files if os.path.isfile(f)]
    if not files:
        print("❌ 错误: 未找到任何输入文件。")
        print("  请用命令行指定 SCAN 泛函 xyz 文件，用法:")
        print("  python scan2pbe_xyz.py 输入xyz文件 [-o 输出文件或目录]")
        sys.exit(1)
    return files


def resolve_out_path(script_dir, out_arg):
    """解析 -o 输出路径: 绝对路径照旧; 以 ./ ../ . .. 开头相对当前运行
    目录; 不带点开头的相对路径相对脚本所在目录。返回绝对路径。"""
    if out_arg is None:
        return None
    if os.path.isabs(out_arg):
        return os.path.abspath(out_arg)
    if out_arg.startswith(("./", "../")) or out_arg in (".", ".."):
        return os.path.abspath(out_arg)
    return os.path.abspath(os.path.join(script_dir, out_arg))


def parse_meta(line):
    """解析属性行键值对为有序字典 (值去引号); 解析失败返回 None。"""
    meta = {}
    pattern = re.compile(r'(\S+)="([^"]*)"|(\S+)=(\S+)')
    try:
        for m in pattern.finditer(line):
            if m.group(1) is not None:
                meta[m.group(1)] = m.group(2)
            else:
                meta[m.group(3)] = m.group(4)
    except ValueError:
        return None
    return meta


def build_properties(props):
    """Properties 列定义中 forces -> force (其余列保留), 返回
    (新列定义, 每行期望字段数); 解析失败返回 (None, None)。"""
    parts = props.split(":")
    if len(parts) < 3 or len(parts) % 3 != 0:
        return None, None
    cols = []
    ncols = 0
    for k in range(0, len(parts), 3):
        name, typ = parts[k], parts[k + 1]
        try:
            cnt = int(parts[k + 2])
        except ValueError:
            return None, None
        name = "force" if name == "forces" else name
        cols.extend([name, typ, parts[k + 2]])
        ncols += 1 if typ == "S" else cnt
    return ":".join(cols), ncols


def compute_volume(lattice):
    """由 Lattice 三个行向量 (a, b, c) 计算体积 V = |a·(b×c)|;
    值非法返回 None。"""
    parts = lattice.split()
    if len(parts) != 9:
        return None
    try:
        v = [float(x) for x in parts]
    except ValueError:
        return None
    a, b, c = v[0:3], v[3:6], v[6:9]
    bc = (b[1] * c[2] - b[2] * c[1],
          b[2] * c[0] - b[0] * c[2],
          b[0] * c[1] - b[1] * c[0])
    return abs(a[0] * bc[0] + a[1] * bc[1] + a[2] * bc[2])


def build_meta(meta, vol_digits):
    """按 PBE (nep2xyz) 规则重组属性行: 返回 (新属性字典, 期望行字段数,
    跳过原因); 跳过时后两项为 (None, 原因)。"""
    lattice = meta.get("Lattice")
    if not lattice:
        return None, None, "缺Lattice键"
    volume = compute_volume(lattice)
    if volume is None:
        return None, None, "Lattice值非法"
    props = meta.get("Properties")
    if not props:
        return None, None, "缺Properties键"
    new_props, ncols = build_properties(props)
    if new_props is None:
        return None, None, "Properties值非法"
    energy = meta.get("energy")
    if energy is None:
        return None, None, "缺energy键"

    # PBE 属性顺序: Lattice Properties config_type virial volume energy pbc
    ordered = [("Lattice", lattice), ("Properties", new_props),
               ("config_type", "nep2xyz"), ("virial", meta.get("virial")),
               ("volume", f"{volume:.{vol_digits}f}"),
               ("energy", energy), ("pbc", meta.get("pbc"))]
    used = {k for k, v in ordered if v is not None}
    extra = [(k, v) for k, v in meta.items()
             if k not in used and k not in DROP_KEYS]
    new_meta = [(k, v) for k, v in ordered if v is not None] + extra
    return new_meta, ncols, None


def format_meta_line(kv_list):
    """属性行输出: 值含空格时加引号, 否则裸键值 (与 target 风格一致)。"""
    parts = []
    for k, v in kv_list:
        parts.append(f'{k}="{v}"' if " " in v else f"{k}={v}")
    return " ".join(parts)


def convert_trajectory(in_path, out_path, progress_every=500):
    """流式逐帧转换单个文件: SCAN 格式 -> PBE 格式, 数值文本原样保留。
    返回 (总帧数, 成功帧数, 跳过帧数, 跳过原因分布, 记录行列表)。"""
    n_total = n_ok = n_skip = 0
    skip_reasons = {}
    rows = []
    with open(in_path, encoding="utf-8") as fin, \
         open(out_path, "w", encoding="utf-8", newline="\n") as fout:
        line_no = 0
        while True:
            head = fin.readline()
            if head == "":
                break
            line_no += 1
            head = head.strip()
            if not head:                # 容错帧间空行
                continue
            if not head.isdigit():
                raise ValueError(
                    f"第 {line_no} 行原子数 '{head}' 非法, 文件帧边界损坏")
            natom = int(head)
            meta_line = fin.readline()          # 属性行
            if meta_line == "":
                break
            line_no += 1
            atom_lines = [fin.readline() for _ in range(natom)]
            if not atom_lines[-1]:
                raise ValueError(f"第 {line_no} 行后文件提前结束, 帧不完整")
            line_no += natom
            n_total += 1

            meta = parse_meta(meta_line)
            if not meta:
                n_skip += 1
                reason = "属性行解析失败"
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                rows.append((n_total, "-", "-", "跳过", reason))
                continue
            new_meta, ncols, reason = build_meta(meta, VOLUME_DIGITS)
            if reason is not None:
                n_skip += 1
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                rows.append((n_total, natom, "-", "跳过", reason))
                continue

            # 逐行校验原子行字段数并重排 (元素/坐标/力文本原样保留)
            new_atoms = []
            bad = False
            for j, aline in enumerate(atom_lines, start=1):
                fields = aline.split()
                if len(fields) != ncols:
                    reason = f"字段数{len(fields)}!={ncols}"
                    skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                    bad = True
                    break
                new_atoms.append(" ".join(fields))
            if bad:
                n_skip += 1
                rows.append((n_total, natom, "-", "跳过", reason))
                continue

            energy = meta.get("energy", "-")
            fout.write(f"{natom}\n{format_meta_line(new_meta)}\n")
            fout.writelines(f"{a}\n" for a in new_atoms)
            n_ok += 1
            rows.append((n_total, natom, energy, "成功", "-"))
            if n_total % progress_every == 0:
                print(f"  📦 已处理 {n_total} 帧 "
                      f"(成功 {n_ok}, 跳过 {n_skip})...")
    return n_total, n_ok, n_skip, skip_reasons, rows


def print_summary(inputs, file_stats, out_dir, record_path):
    """运行完毕后集中总结关键信息 (文件统计表 + 关键路径)。"""
    print("=" * 62)
    print("🎉 运行完成，总结:")
    print(f"  输入文件:  {len(inputs)} 个")
    print(f"  总帧数:    {sum(s['total'] for s in file_stats)} 帧 "
          f"(成功 {sum(s['ok'] for s in file_stats)}, "
          f"跳过 {sum(s['skip'] for s in file_stats)})")
    if sum(s["skip"] for s in file_stats) > 0:
        reasons = {}
        for s in file_stats:
            for k, v in s["reasons"].items():
                reasons[k] = reasons.get(k, 0) + v
        detail = "  ".join(f"{k}×{v}" for k, v in reasons.items())
        print(f"  跳过原因:  {detail}")
    print()
    head = col("输入文件", max(dw("输入文件"), 24)) + \
           col("总帧数", 8, ">") + col("成功", 8, ">") + \
           col("跳过", 8, ">") + col("输出文件", 40)
    print("  " + head)
    for i, in_path in enumerate(inputs):
        s = file_stats[i]
        out_name = os.path.basename(s["out"])
        row = col(os.path.basename(in_path), max(dw("输入文件"), 24)) + \
              col(s["total"], 8, ">") + col(s["ok"], 8, ">") + \
              col(s["skip"], 8, ">") + col(out_name, 40)
        print("  " + row)
    print()
    print(f"  输出目录:  {os.path.abspath(out_dir)}")
    print(f"  记录文件:  {os.path.abspath(record_path)}")
    print("=" * 62)
# ============================================================================


# ============================== 脚本工作区 =====================================
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    inputs, out_arg = parse_args(sys.argv[1:])
    in_paths = resolve_inputs(script_dir, inputs)

    # 输出规则: -o 以 .xyz/.extxyz 结尾 = 输出文件 (仅单输入); 否则为目录
    out_is_file = (out_arg is not None and
                   out_arg.lower().endswith((".xyz", ".extxyz")))
    if out_is_file and len(in_paths) > 1:
        print("❌ 错误: -o 指定输出文件时仅支持单个输入文件。")
        print("  多个输入请用 -o 指定输出目录 (或省略 -o 使用默认目录)。")
        sys.exit(1)

    out_root = resolve_out_path(script_dir, out_arg)
    if out_root is None:
        out_root = os.path.normpath(os.path.join(script_dir, OUTPUT_PATH))
        print(f"ℹ️ 未指定输出路径，使用脚本所在目录: {out_root}")
    os.makedirs(out_root, exist_ok=True)

    file_stats, all_rows = [], []
    for i, in_path in enumerate(in_paths):
        in_name = os.path.basename(in_path)
        if out_is_file:
            out_path = out_root
        else:
            base, _ = os.path.splitext(in_name)
            out_path = os.path.join(out_root, base + OUT_SUFFIX)
        print(f"📦 转换 {i + 1}/{len(in_paths)}: {in_path}")
        if os.path.exists(out_path):
            print(f"  ⚠️ 警告: {out_path} 已存在，将被覆盖。")

        # 首帧属性检查: 是否含 SCAN 特征键 (probability/umlip/free_energy)
        with open(in_path, encoding="utf-8") as f:
            f.readline()                # 跳过原子数行
            first_meta = parse_meta(f.readline())
        scan_keys = [k for k in DROP_KEYS
                     if first_meta and first_meta.get(k) is not None]
        if not scan_keys:
            print(f"  ⚠️ 警告: 未检测到 SCAN 特征键 "
                  f"({'/'.join(DROP_KEYS)})，输入可能不是 SCAN 泛函格式，"
                  f"仍将按规则转换。")

        n_total, n_ok, n_skip, reasons, rows = convert_trajectory(
            in_path, out_path)
        if n_ok == 0 and os.path.exists(out_path):
            os.remove(out_path)         # 全帧跳过时删除空输出文件
        file_stats.append({"total": n_total, "ok": n_ok, "skip": n_skip,
                           "reasons": reasons, "out": out_path})
        all_rows.append((in_name, n_ok, n_skip, rows))
        print(f"  ✅ {in_name}: {n_ok}/{n_total} 帧转换成功 -> {out_path}")

    # 写记录文件 (与输出文件同目录, 覆盖模式)
    record_path = os.path.join(out_root, RECORD_FILE)
    with open(record_path, "w", encoding="utf-8", newline="\n") as f:
        header_cols = ["输入文件", "帧号", "原子数", "能量", "状态", "备注"]
        widths = [dw(c) for c in header_cols]
        records = []
        for in_name, n_ok, n_skip, rows in all_rows:
            for r in rows:
                rec = (in_name, r[0], r[1], r[2], r[3], r[4])
                for k, cell in enumerate(rec):
                    widths[k] = max(widths[k], dw(cell))
                records.append(rec)
        f.write("# " + "".join(col(c, widths[k])
                for k, c in enumerate(header_cols)).rstrip() + "\n")
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"# {stamp} 共转换 {len(in_paths)} 个输入文件 "
                f"({sum(s['ok'] for s in file_stats)} 成功, "
                f"{sum(s['skip'] for s in file_stats)} 跳过)\n")
        for rec in records:
            f.write("".join(col(cell, widths[k])
                    for k, cell in enumerate(rec)).rstrip() + "\n")

    print_summary(in_paths, file_stats, out_root, record_path)


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
