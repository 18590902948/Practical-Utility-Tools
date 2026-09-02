#!/usr/bin/env python3
"""
=============================================================================
脚本:        check_bad_frames.py
分类:        结构检查工具
功能:        逐行扫描 xyz/extxyz 文件并检测坏帧 (帧头标注原子数与帧内实际
             坐标行数不一致: 缺行/多行/含非法行)，终端与报告文件输出坏帧
             清单，好帧原样写入 good.xyz (剔除坏帧，可直接用于训练)
使用方法:    python check_bad_frames.py [输入文件 ...] [-o 输出路径] [-h/--help]
参数:        输入文件 ...   待检查的 xyz/extxyz 文件 (可多个，支持通配符；
                         命令行参数先按当前运行目录解析，不存在再相对
                         脚本所在目录)
             -o/--output   输出路径 (两种形式: 以 .xyz/.extxyz 结尾视为
                         输出文件完整路径，仅单输入时可用；否则视为输出
                         目录。不带点开头的相对路径默认相对脚本所在目录
                         解析，./ 或 ../ 开头相对当前运行目录；不指定时
                         输出到配置区 OUTPUT_PATH)
             -h/--help     显示本帮助
输入文件:    配置区 INPUT_FILES (默认 *.xyz/*.extxyz，相对 INPUT_PATH)
输出文件:
  good.xyz                 剔除坏帧后的好帧文件 (单输入命名 good.xyz，
                           多输入命名 <原名去扩展名>_good.xyz 防覆盖；
                           好帧原行内容原样写入，帧号 0 起始重排)
  check_bad_frames.txt     坏帧检查报告 (分节明细 + 坏帧清单表，覆盖写)
输出路径:    默认脚本所在目录下 good/ (OUTPUT_PATH)，可用 -o 指定
             (输出文件或输出目录，相对/绝对路径均可)
帧号约定:    OVITO 0 起始索引 (0 = 第一帧，编辑器中第 n+1 帧)；
             帧头行号为原文件 1 起始行号 (文本编辑器打开定位用)
判定规则:    帧头行 = 单独一个正整数；其后首个非空行若为原子行则视为无
             属性/注释行，否则视为属性/注释行不计数；原子行 = 元素符号/
             原子序号 + 3 列以上数字 (可带 forces 等性质列)。帧内实际
             原子行数与帧头标注不一致 → 坏帧 (缺行/多行)；帧内出现无法
             解析的非空行 → 异常帧。坏帧及帧外杂质行一律不写入 good.xyz
示例:
  python check_bad_frames.py ./train.xyz
  python check_bad_frames.py ./A/a.xyz ./B/b.xyz -o ./C/
  python check_bad_frames.py ./train.xyz -o ./D/good.xyz
  (不指定输入文件时用配置区 INPUT_FILES，检查脚本所在目录下所有文件)
作者:        隼蝶.
最后修改:    2026-09-02
=============================================================================
"""

import datetime
import glob
import os
import sys

# ============================== 参数配置区 =====================================
INPUT_FILES    = ["*.xyz", "*.extxyz"]   # 输入文件列表 (支持通配符，相对 INPUT_PATH 展开；命令行参数优先)
OUTPUT_FILES   = ["good.xyz"]            # 好帧输出文件 (多输入时自动加 <原名>_ 前缀；相对 OUTPUT_PATH)
RECORD_FILE    = "check_bad_frames.txt"  # 坏帧检查报告 (输出目录，覆盖写)
INPUT_PATH     = "./"                    # 输入文件寻找路径 (相对脚本所在目录)
OUTPUT_PATH    = "./good/"               # 输出文件寻找路径 (相对脚本所在目录)
INPUT_ENCODING = "utf-8-sig"             # 输入文件编码 (自动去除 BOM；GBK 文件请改 "gbk")
DETAIL_W       = 60                      # 非法行内容截断宽度 (报告/终端显示)
# =============================================================================

# ============================== 环境准备区 =====================================
# 终端 locale 可能非 UTF-8 (如 POSIX/C), 强制 stdout 用 UTF-8,
# 避免打印中文时抛 UnicodeEncodeError (Windows 终端显示乱码不影响功能)。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
# ===========================================================================


# ============================== 函数配置区 =====================================
def print_usage():
    """打印头部注释块 (脚本功能与完整使用方法)。"""
    print(__doc__)


def parse_args(argv):
    """解析命令行参数 (选项位置随意): 输入文件为位置参数 (可多个);
    -h/--help、-o/--output 为选项。返回 (输入文件列表, 输出路径)。"""
    inputs = []
    out_path = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print_usage()
            sys.exit(0)
        elif arg in ("-o", "--output", "--outdir"):
            if i + 1 >= len(argv):
                print("❌ 错误: 选项 -o/--output 需要一个输出路径。")
                sys.exit(1)
            out_path = argv[i + 1]
            i += 2
        else:
            inputs.append(arg)
            i += 1
    return inputs, out_path


def resolve_cmd_path(p, script_dir):
    """命令行路径解析: 绝对路径照旧；以 ./ ../ 或 . 开头的相对路径相对
    当前运行目录解析；不带点开头的相对路径默认相对脚本所在目录解析。"""
    if os.path.isabs(p):
        return p
    if p in (".", "..") or p.startswith(("./", "../")):
        return os.path.abspath(p)
    return os.path.normpath(os.path.join(script_dir, p))


def expand_cmd_inputs(args, script_dir):
    """展开命令行输入文件: 含通配符的 glob 展开 (先相对当前运行目录，未匹配
    且不带点开头再相对脚本目录兜底)；无通配符的字面路径先按当前运行目录
    探测，不存在再相对脚本目录解析。返回存在的文件完整路径列表。"""
    inputs = []
    for a in args:
        if any(ch in a for ch in "*?["):
            matches = sorted(glob.glob(a))
            if not matches and not a.startswith(("./", "../")):
                matches = sorted(glob.glob(os.path.join(script_dir, a)))
            if not matches:
                print(f"⚠️ 警告: 模式 '{a}' 未匹配任何文件，已跳过。")
            else:
                inputs.extend(os.path.normpath(m) for m in matches)
            continue
        p = a if os.path.isfile(a) else os.path.join(script_dir, a)
        if not os.path.isfile(p):
            print(f"❌ 错误: 输入文件不存在: {a}")
            sys.exit(1)
        inputs.append(os.path.normpath(p))
    return inputs


def expand_default_inputs(input_base):
    """按配置区 INPUT_FILES 展开默认输入文件 (相对 input_base，支持通配符)。"""
    files = []
    for p in INPUT_FILES:
        if any(ch in p for ch in "*?["):
            files.extend(sorted(glob.glob(os.path.join(input_base, p))))
        else:
            files.append(os.path.join(input_base, p))
    return [os.path.normpath(f) for f in files]


def dw(text):
    """字符串显示宽度: 中文等宽字符按 2 列计 (终端/报告表格对齐用)。"""
    return sum(2 if ord(c) > 127 else 1 for c in text)


def pad(text, width, align="l"):
    """按显示宽度填充到 width 列: align 'l' 左对齐 / 'r' 右对齐。"""
    gap = max(0, width - dw(text))
    return (" " * gap + text) if align == "r" else (text + " " * gap)


def is_header(line):
    """帧头判定: 整行仅一个正整数 (xyz 第一行标准写法，避免注释行首为数字
    时误判；ASE/OVITO 输出均符合此格式)。"""
    parts = line.split()
    return (len(parts) == 1 and parts[0].isdigit() and int(parts[0]) > 0)


def is_atom_row(line):
    """原子行判定: 元素符号/原子序号 + 3 列以上数字 (xyz/extxyz 坐标行，
    可带 forces 等性质列；属性行 token 含 '='，不会误判为原子行)。"""
    parts = line.split()
    if len(parts) < 4 or "=" in parts[0]:
        return False
    for tok in parts[1:4]:
        try:
            float(tok)
        except ValueError:
            return False
    return True


def bad_header():
    """坏帧清单表头 (5 列, 以 # 开头, 按显示宽度右对齐)。"""
    return ("# " + pad("帧号", 8, "r") + " " + pad("帧头行号", 10, "r")
            + " " + pad("标注原子数", 10, "r") + " "
            + pad("实际原子数", 10, "r") + "  " + pad("状态", 4))


def bad_row(b):
    """坏帧清单数据行: (帧号, 帧头行号, 标注, 实际, 状态) 右对齐。"""
    return (pad(str(b["idx"]), 8, "r") + " " + pad(str(b["row"]), 10, "r")
            + " " + pad(str(b["n"]), 10, "r") + " "
            + pad(str(b["m"]), 10, "r") + "  " + pad(b["status"], 4))


def settle_frame(buf, n_expect, fout):
    """结算一帧 (buf 为 [(行文本, 类别, 行号)], 首行为帧头): 统计实际原子
    行数与非法行；好帧整帧原样写入 fout。返回 None 表示好帧, 否则返回
    dict {status, m, invalid} (invalid 为非法行 [(行号, 内容)])。"""
    n_atom = 0
    first_non_blank = True
    invalid = []
    for text, kind, row_no in buf[1:]:
        if kind == "blank":
            continue
        if first_non_blank:
            first_non_blank = False
            if kind == "atom":
                n_atom += 1        # 帧头后首行即原子行 → 该帧无属性行
            continue               # 否则视为属性/注释行，不计数
        if kind == "atom":
            n_atom += 1
        else:
            invalid.append((row_no, text.strip()))
    if invalid:
        status = "异常"
    elif n_atom < n_expect:
        status = "缺行"
    elif n_atom > n_expect:
        status = "多行"
    else:
        for text, _, _ in buf:
            fout.write(text)
        return None
    return {"status": status, "n": n_expect, "m": n_atom,
            "invalid": invalid}


def process_file(in_path, out_path):
    """逐行扫描单个 xyz/extxyz 文件: 坏帧与杂质剔除, 好帧原样写入
    out_path。返回 dict {frames, bad, impurity, out}。"""
    stats = {"frames": 0, "bad": [], "impurity": 0}
    cur_idx = 0                     # 当前帧的 OVITO 帧号 (开新帧时分配)
    try:
        fin = open(in_path, "r", encoding=INPUT_ENCODING, newline="")
    except OSError as e:
        print(f"❌ 错误: 无法打开输入文件: {in_path} ({e})")
        sys.exit(1)
    try:
        with fin, open(out_path, "w", encoding="utf-8", newline="") as fout:
            buf = []                  # 当前帧行缓冲 [(行文本, 类别, 行号)]
            for row_no, line in enumerate(fin, start=1):
                kind = ("blank" if not line.strip()
                        else "header" if is_header(line)
                        else "atom" if is_atom_row(line) else "other")
                if kind == "header":
                    # 新帧头到达: 先结算上一帧 (其 OVITO 帧号为开帧时
                    # 分配的 cur_idx, 0 起始)
                    if buf:
                        bad = settle_frame(buf, int(buf[0][0].split()[0]), fout)
                        if bad is not None:
                            bad.update({"idx": cur_idx, "row": buf[0][2]})
                            stats["bad"].append(bad)
                    cur_idx = stats["frames"]
                    stats["frames"] += 1
                    buf = [(line, "header", row_no)]
                elif buf:
                    buf.append((line, kind, row_no))
                else:
                    stats["impurity"] += 1    # 首帧前的杂质行 (非空), 剔除
            # EOF: 结算最后一帧
            if buf:
                bad = settle_frame(buf, int(buf[0][0].split()[0]), fout)
                if bad is not None:
                    bad.update({"idx": cur_idx, "row": buf[0][2]})
                    stats["bad"].append(bad)
    except UnicodeDecodeError as e:
        print(f"❌ 错误: 输入文件解码失败 (编码 {INPUT_ENCODING}): {e}")
        print("  提示: 若文件为 GBK 等其他编码，请修改配置区 "
              "INPUT_ENCODING 后重试。")
        sys.exit(1)
    stats["out"] = os.path.abspath(out_path)
    return stats
# ===========================================================================


# ============================== 脚本工作区 =====================================
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    args, out_path = parse_args(sys.argv[1:])

    # 输入文件: 命令行参数优先，无参数用配置区 INPUT_FILES (相对 INPUT_PATH)
    if args:
        inputs = expand_cmd_inputs(args, script_dir)
    else:
        inputs = expand_default_inputs(
            os.path.normpath(os.path.join(script_dir, INPUT_PATH)))
    inputs = [f for f in inputs if os.path.isfile(f)]
    if not inputs:
        print("❌ 错误: 未找到任何输入文件。请指定输入文件，或用 -h/--help 查看帮助。")
        sys.exit(1)
    for p in inputs:
        print(f"ℹ️ 输入文件: {os.path.abspath(p)}")

    # 输出路径: -o 命令行优先，否则配置区 OUTPUT_PATH (相对脚本目录)
    out_file = None
    if out_path:
        out_base = resolve_cmd_path(out_path, script_dir)
        if os.path.splitext(out_base)[1].lower() in (".xyz", ".extxyz"):
            # -o 为输出文件完整路径: 仅单输入时可用
            if len(inputs) > 1:
                print("❌ 错误: 指定了多个输入文件时，-o 只能指定输出目录。")
                sys.exit(1)
            out_file = out_base
            out_dir = os.path.dirname(out_base)
        else:
            out_dir = out_base
    else:
        out_dir = os.path.normpath(os.path.join(script_dir, OUTPUT_PATH))
    os.makedirs(out_dir, exist_ok=True)

    # 终端与报告同步输出 (emit 同时打印与收集)
    report_lines = []

    def emit(msg=""):
        print(msg)
        report_lines.append(msg)

    emit("=" * 56)
    emit("坏帧检查报告 (check_bad_frames.py)")
    emit("检查时间: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    emit("=" * 56)

    # 逐文件检查 (覆盖模式); 输出文件名: -o 文件 / 单输入用配置区
    # OUTPUT_FILES[0] (默认 good.xyz) / 多输入加 <原名>_ 前缀防覆盖
    good_name = OUTPUT_FILES[0]
    n_file = len(inputs)
    total_frames = total_bad = total_good = 0
    for i, in_file in enumerate(inputs, start=1):
        name = os.path.basename(in_file)
        if out_file:
            target = out_file
        else:
            stem = os.path.splitext(name)[0]
            target = os.path.join(
                out_dir, good_name if n_file == 1 else f"{stem}_{good_name}")
        print(f"\n📦 [{i}/{n_file}] 正在扫描: {os.path.abspath(in_file)}")
        st = process_file(in_file, target)
        if st["frames"] == 0:
            # 文件不含任何 xyz 帧 (如误传 txt): 跳过并删除空输出
            if os.path.exists(target):
                os.remove(target)
            emit(f"\n[检查文件 {i}/{n_file}] {name}")
            emit(f"  输入文件:   {os.path.abspath(in_file)}")
            emit("  ⚠️ 未发现任何 xyz 帧 (可能不是 xyz 文件)，"
                 "已跳过，未生成输出。")
            continue
        total_frames += st["frames"]
        total_bad += len(st["bad"])
        total_good += st["frames"] - len(st["bad"])

        # 报告小节: 文件统计
        emit(f"\n[检查文件 {i}/{n_file}] {name}")
        emit(f"  输入文件:   {os.path.abspath(in_file)}")
        emit(f"  总帧数:     {st['frames']}")
        if st["impurity"]:
            emit(f"  杂质行:     {st['impurity']} 行 (首帧前的非空行, 已剔除)")
        if not st["bad"]:
            emit("  ✅ 未发现坏帧。")
            emit(f"  输出文件:   {st['out']}  ({st['frames']} 帧全部写入)")
            continue
        # 坏帧统计 + 清单表 (表头 # 开头, 帧号 OVITO 0 起始, 行号为
        # 原文件 1 起始, 便于文本编辑器定位)
        cnt = {}
        for b in st["bad"]:
            cnt[b["status"]] = cnt.get(b["status"], 0) + 1
        summary = " / ".join(f"{k} {v}" for k, v in cnt.items())
        n_ok = st["frames"] - len(st["bad"])
        emit(f"  坏帧:       {len(st['bad'])} 个 ({summary})")
        emit(f"  输出文件:   {st['out']}  (好帧 {n_ok} 个, 帧号 0 起始重排)")
        emit(bad_header())
        for b in st["bad"]:
            emit(bad_row(b))
            for row_no, text in b["invalid"]:
                emit(f"    帧 {b['idx']} 内非法行 (第 {row_no} 行): "
                     f"{text[:DETAIL_W]}")

    # 汇总 (终端与报告同步)
    emit("\n[汇总]")
    emit(f"  检查文件:   {n_file}")
    emit(f"  总帧数:     {total_frames}")
    emit(f"  总坏帧:     {total_bad}  (好帧 {total_good})")
    emit(f"  输出目录:   {os.path.abspath(out_dir)}")

    # 报告写入 (覆盖模式, 输出目录)
    report_path = os.path.join(out_dir, RECORD_FILE)
    with open(report_path, "w", encoding="utf-8") as fout:
        fout.write("\n".join(report_lines) + "\n")

    # 运行完毕集中总结关键信息
    print("=" * 56)
    print("🎉 检查完成, 总结:")
    print(f"  检查文件:   {n_file} 个")
    print(f"  总帧数:     {total_frames} | 坏帧 {total_bad} 个 | 好帧 {total_good} 个")
    print(f"  输出目录:   {os.path.abspath(out_dir)}")
    print(f"  报告文件:   {os.path.abspath(report_path)}")
    print("=" * 56)


# ============================== 脚本运行区 =====================================
if __name__ == "__main__":
    main()
