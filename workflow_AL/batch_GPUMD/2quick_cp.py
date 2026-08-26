"""
=============================================================================
脚本:        quick_cp.py
分类:        文件批量复制工具
功能:        将来源文件夹/文件（-s/--source，从这里复制）中的文件批量复制到
             多个靶文件夹（-t/--target，复制到的文件夹）。支持两种运行模式：
             ① 命令行模式：-t 指定靶文件夹（支持单/双引号通配符），-s 指定
               来源文件夹（默认复制其下全部文件）或来源文件，-sn 指定来源
               文件夹内的部分文件（Tab 补全见参数说明）；
             ② 交互式模式（无参数）：自动识别脚本所在目录下的规律文件夹
               作为靶文件夹，选择传递文件/文件夹后复制。
             复制前展示来源清单与靶文件夹清单，确认后执行。

使用方法:    python quick_cp.py -t './1_md*' -s ./a.xyz ./b.xyz
             # ① 通配符靶文件夹: 把 a.xyz、b.xyz 复制到脚本所在目录下所有 1_md* 里
             python quick_cp.py -t ./A ./B ./C -s ./a*.xyz
             # ② 通配符来源文件: 把脚本所在目录下所有 a*.xyz 复制到 A、B、C 里
             python quick_cp.py -t './1_md*' -s ./D -sn a*.xyz
             # ③ 通配符来源文件名: 把 D 文件夹内所有 a*.xyz 复制到每个 1_md* 里
             python quick_cp.py                            # 无参数，交互式模式
             # 注: 示例中的 a.xyz、b.xyz、A/B/C/D、1_md* 均为演示用占位名
参数:        -t/--target 靶文件夹 ...   复制到的文件夹列表（支持通配符，单/双引号
                                      均可；不带点开头相对脚本所在目录解析）
             -s/--source 来源 ...       来源文件夹或文件列表（从这里复制；文件夹
                                      默认复制其下全部文件，支持通配符；位置参数
                                      可省略 -s 标记，一律视为来源）
             -sn/--source-names ...     指定来源文件夹内的部分文件（仅对文件夹来源
                                      生效，文件在 -s 来源文件夹内）；可输入纯
                                      文件名（自动到各来源文件夹内查找）或带路径
                                      形式（如 ./D/a.xyz）；Tab 补全是 shell 自带
                                      能力，命令行输入文件名时按 Tab 可自动补全
             -h/--help                显示帮助
输入文件:    （来源文件夹/文件，由 -s 指定）
输出文件:
  quick_cp.txt   记录文件（复制日志，追加模式，脚本所在目录）
输出路径:    各靶文件夹（-t/--target 指定）
作者:        隼蝶.
最后修改日期: 2026-08-24
=============================================================================
# 交互式模式目录树示例（脚本所在目录）:
# ============================================================================
# .                       <- 脚本所在目录（交互式模式在此运行）
# ├── quick_cp.py
# ├── INCAR                <- 传递文件
# ├── 1/ 2/ 3/             <- 数字序列组（靶文件夹）
# ├── frame_1/ frame_2/    <- 通配符模式组 frame_*（靶文件夹）
# ├── raw_data/            <- 传递文件夹（无规律）
# └── __pycache__/         <- 自动排除
# ============================================================================
"""
import glob
import os
import re
import shutil
import sys
import time

# ============================== 参数配置区 =====================================
SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))   # 脚本所在目录（路径基准）
SCRIPT_NAME    = os.path.basename(__file__)                   # 脚本文件名
RECORD_FILE    = "quick_cp.txt"         # 记录文件 (复制日志，追加模式，脚本所在目录)
MIN_GROUP_SIZE = 2                       # 交互模式: 规律组最少成员数（少于该数量不构成规律组）
EXCLUDE_DIRS   = {"__pycache__", ".git", ".svn", ".hg", ".idea", ".vscode", "node_modules"}
# =============================================================================

# ============================== 环境准备区 =====================================
# Windows 控制台默认 GBK 编码无法输出 emoji，统一改用 UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
# =============================================================================

# ============================== 函数配置区 =====================================

def dw(s):
    """显示宽度：中文等宽字符按 2 列计"""
    return sum(2 if ord(c) > 127 else 1 for c in str(s))


def fmt_size(nbytes):
    """文件大小格式化：B/KB/MB/GB"""
    nbytes = float(nbytes)
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024 or unit == "GB":
            return f"{nbytes:.1f} {unit}" if unit != "B" else f"{int(nbytes)} B"
        nbytes /= 1024


def show_table(rows, headers, title=None):
    """终端表格输出：按显示宽度右对齐（中文按 2 列计）"""
    if title:
        print(title)
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], dw(cell))
    line = "  ".join(str(h).rjust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("-" * len(line))
    for row in rows:
        print("  ".join(str(c).rjust(widths[i]) for i, c in enumerate(row)))
    print()


def ask(prompt):
    """输入询问：提示独占一行，必须显式输入内容并回车（防止误触）；
    输入 q 退出脚本"""
    while True:
        s = input(f"\n{prompt}\n").strip()
        if s.lower() in ("q", "quit", "exit"):
            print("👋 已取消，退出脚本。")
            sys.exit(0)
        if s:
            return s
        print("⚠️  输入不能为空，请明确输入后回车。")


def ask_yes_no(prompt, default=None):
    """是非询问：必须显式输入 y/n 确认；提示末尾自动标注选项；
    default 仅作为提示中的建议值"""
    hint = "" if default is None else f"（建议：{default}）"
    while True:
        s = ask(f"{prompt}（y=是，n=否）{hint}")
        if s.lower() in ("y", "yes", "是"):
            return True
        if s.lower() in ("n", "no", "否"):
            return False
        print("⚠️  请输入 y（是）或 n（否）。")


def parse_choice(text, total, allow_all=True):
    """解析编号输入：支持 all、1,3,5、1-3、空格/逗号混合；非法返回 None"""
    text = text.strip().lower()
    if not text:
        return None
    if allow_all and text in ("all", "*", "a"):
        return set(range(1, total + 1))
    result = set()
    for part in re.split(r"[,，\s;；]+", text):
        if not part:
            continue
        m = re.match(r"^(\d+)\s*-\s*(\d+)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            result.update(range(min(a, b), max(a, b) + 1))
        elif part.isdigit():
            result.add(int(part))
        else:
            return None
    if not result or min(result) < 1 or max(result) > total:
        return None
    return result


def choose_ids(total, prompt, allow_all=True):
    """交互式选择编号：必须显式输入；默认支持 all、1,3,5、1-3；
    allow_all=False 时禁止 all 模式；返回选中的编号集合（1 起）"""
    while True:
        ids = parse_choice(ask(prompt), total, allow_all=allow_all)
        if ids is not None:
            return ids
        range_hint = "1" if total == 1 else f"1-{total}"
        mode_hint = "，支持 1,3,5 / 1-3 / all" if allow_all else "，支持 1,3,5 / 1-3"
        print(f"⚠️  输入无效，请输入 {range_hint} 范围内的编号{mode_hint}。")


def resolve_cmd_path(p, script_dir=SCRIPT_DIR):
    """命令行路径解析：绝对路径照旧；./、../、. 开头相对当前运行目录；不带点开头相对脚本所在目录"""
    if os.path.isabs(p):
        return p
    if p.startswith(("./", "../")) or p == ".":
        return os.path.abspath(p)
    return os.path.abspath(os.path.join(script_dir, p))


def expand_glob(a, script_dir=SCRIPT_DIR):
    """命令行通配符展开：先相对当前运行目录 glob，无匹配且不带点开头时再相对脚本所在目录兑底；返回绝对路径"""
    matches = sorted(glob.glob(a))
    if not matches and not a.startswith(("./", "../")):
        matches = sorted(glob.glob(os.path.join(script_dir, a)))
    return [os.path.abspath(m) for m in matches]


def resolve_target_dirs(raw, script_dir=SCRIPT_DIR):
    """展开靶文件夹参数（-t/--target）：通配符展开后仅保留目录，去重保持顺序"""
    targets = []
    for a in raw:
        matches = expand_glob(a, script_dir)
        if not matches:
            print(f"⚠️ 靶文件夹 {a} 未匹配到任何文件夹，已忽略。")
            continue
        for m in matches:
            if os.path.isdir(m) and m not in targets:
                targets.append(m)
    return targets


def resolve_sources(raw, script_dir=SCRIPT_DIR):
    """展开来源参数（-s/--source）：文件进 src_files，文件夹进 src_dirs，去重保持顺序"""
    src_files, src_dirs = [], []
    for a in raw:
        matches = expand_glob(a, script_dir)
        if not matches:
            print(f"⚠️ 来源 {a} 未匹配到任何文件/文件夹，已忽略。")
            continue
        for m in matches:
            if os.path.isdir(m):
                if m not in src_dirs:
                    src_dirs.append(m)
            elif os.path.isfile(m):
                if m not in src_files:
                    src_files.append(m)
    return src_files, src_dirs


def collect_sources(src_files, src_dirs, names, script_dir=SCRIPT_DIR):
    """收集来源文件：-sn 带路径文件名按命令行路径规则直接用（不依赖文件夹来源），
    纯文件名到各来源文件夹内查找（支持 * 通配符）；无 -sn 时来源文件夹内全部文件"""
    if names:
        plain, with_path = [], []
        for n in names:
            (plain if os.path.basename(n) == n else with_path).append(n)
        for n in with_path:
            p = resolve_cmd_path(n, script_dir)
            if os.path.isfile(p):
                if p not in src_files:
                    src_files.append(p)
            else:
                print(f"⚠️ 来源文件不存在，已忽略：{p}")
        if plain:
            if not src_dirs:
                print("⚠️ -sn/--source-names 纯文件名需要文件夹来源（-s 目录）配合，当前没有文件夹来源，已忽略。")
            for d in src_dirs:
                for n in plain:
                    if glob.has_magic(n):
                        # 含通配符: 在来源文件夹内展开匹配的文件（如 -sn a*.xyz）
                        matched = [p for p in sorted(glob.glob(os.path.join(d, n)))
                                   if os.path.isfile(p)]
                        if not matched:
                            print(f"⚠️ 来源文件不存在，已忽略：{os.path.join(d, n)}")
                        for p in matched:
                            if p not in src_files:
                                src_files.append(p)
                    else:
                        p = os.path.join(d, n)
                        if os.path.isfile(p):
                            if p not in src_files:
                                src_files.append(p)
                        else:
                            print(f"⚠️ 来源文件不存在，已忽略：{p}")
        return src_files
    for d in src_dirs:
        for n in sorted(os.listdir(d)):
            p = os.path.join(d, n)
            if os.path.isfile(p) and p not in src_files:
                src_files.append(p)
    return src_files


def parse_args(argv):
    """命令行参数解析：-t/--target 靶文件夹、-s/--source 来源、-sn/--source-names 文件名；
    选项后收集所有非选项参数（直到下一个选项）；位置参数视为来源；-h 打印帮助退出"""
    target_raw, source_raw, names = [], [], []
    i, n = 0, len(argv)
    while i < n:
        a = argv[i]
        if a in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        elif a in ("-t", "--target"):
            mode = "target"
        elif a in ("-s", "--source"):
            mode = "source"
        elif a in ("-sn", "--source-names"):
            mode = "names"
        elif a.startswith("-") and a != "-":
            print(f"❌ 未知选项: {a}（可用 -h 查看帮助）")
            sys.exit(1)
        else:
            source_raw.append(a)  # 位置参数一律视为来源（-s 可省略）
            i += 1
            continue
        i += 1
        while i < n and not argv[i].startswith("-"):
            {"target": target_raw, "source": source_raw, "names": names}[mode].append(argv[i])
            i += 1
    return target_raw, source_raw, names


def write_record(cmdline, targets, sources, copied, skipped, failed):
    """记录文件：复制日志（追加模式），分节记录时间戳/命令行/来源/靶文件夹/统计"""
    rec_path = os.path.join(SCRIPT_DIR, RECORD_FILE)
    first = not os.path.exists(rec_path)
    lines = [f"## {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"[命令行] {cmdline}",
             f"[靶文件夹] ({len(targets)}) " + "  ".join(targets),
             f"[来源文件] ({len(sources)}) " + "  ".join(sources),
             f"[结果] 复制成功 {copied} 个，跳过 {skipped} 个，失败 {failed} 个",
             "#" + "=" * 79, ""]
    with open(rec_path, "a", encoding="utf-8") as f:
        if first:
            f.write("# quick_cp.txt 复制日志（追加模式，每次运行分节记录）\n")
        f.write("\n".join(lines) + "\n")


# ==================== 交互式模式：靶文件夹识别 ====================

def list_all_folders():
    """列出脚本目录下所有一级子文件夹（排除特殊目录与隐藏目录）"""
    folders = []
    for name in sorted(os.listdir(SCRIPT_DIR)):
        if name.startswith(".") or name in EXCLUDE_DIRS:
            continue
        path = os.path.join(SCRIPT_DIR, name)
        if os.path.isdir(path):
            folders.append(name)
    return folders


def find_number_group(folders):
    """数字序列组：纯数字文件夹，按数值排序"""
    nums = [f for f in folders if f.isdigit()]
    return sorted(nums, key=int)


def find_letter_groups(folders):
    """字母序列组：纯字母文件夹按连续段分组（大小写分别处理，每段>=MIN_GROUP_SIZE）"""
    groups = []
    for seq in (sorted(f for f in folders if f.isalpha() and f.islower()),
                sorted(f for f in folders if f.isalpha() and f.isupper())):
        if not seq:
            continue
        start = 0
        for i in range(1, len(seq)):
            if ord(seq[i]) - ord(seq[i - 1]) != 1:
                if i - start >= MIN_GROUP_SIZE:
                    groups.append(seq[start:i])
                start = i
        if len(seq) - start >= MIN_GROUP_SIZE:
            groups.append(seq[start:])
    return groups


def find_wildcard_groups(folders):
    """通配符模式组：对剩余文件夹提取共享"前缀+后缀"的模式。

    规则: 名称中任意连续数字/字母段视为变量部分，按（前缀, 后缀）聚合，
    组内成员数 >= MIN_GROUP_SIZE 且 glob 反向验证通过（模式匹配到的目录
    恰好等于组内成员，防止误伤其他文件夹）才构成规律组。
    """
    table = {}  # (prefix, suffix) -> [name, ...]
    for name in folders:
        for m in re.finditer(r"\d+|[A-Za-z]+", name):
            key = (name[:m.start()], name[m.end():])
            table.setdefault(key, []).append(name)

    result = []
    used = set()
    # 按成员数降序、通配符长度升序处理，保证每组文件夹只归属一个模式
    for (prefix, suffix), members in sorted(
            table.items(), key=lambda kv: (-len(kv[1]), len(kv[0]) + len(kv[1]))):
        new_members = [m for m in members if m not in used]
        if len(new_members) < MIN_GROUP_SIZE:
            continue
        pattern = prefix + "*" + suffix
        matched = {os.path.basename(p) for p in glob.glob(os.path.join(SCRIPT_DIR, pattern))
                   if os.path.isdir(p)}
        if matched and matched == set(new_members):
            result.append((pattern, sorted(new_members)))
            used.update(new_members)
    return result


def build_groups():
    """构建全部靶文件夹规律组：返回 (groups, transfer_folders)"""
    folders = list_all_folders()
    groups = []  # 每项: (类型描述, 通配符描述, [成员名,...])

    num = find_number_group(folders)
    if num:
        groups.append(("数字序列组", None, num))
        used = set(num)
    else:
        used = set()

    letters = find_letter_groups(folders)
    for g in letters:
        groups.append(("字母序列组", None, g))
        used.update(g)

    wildcards = find_wildcard_groups([f for f in folders if f not in used])
    for pattern, members in wildcards:
        groups.append(("通配符模式组", pattern, members))
        used.update(members)

    transfer_folders = [f for f in folders if f not in used]
    return groups, transfer_folders


def collect_transfer_files():
    """收集传递文件：脚本目录下的文件（除脚本自身、隐藏文件外）"""
    files = []
    for name in sorted(os.listdir(SCRIPT_DIR)):
        if name == SCRIPT_NAME or name.startswith("."):
            continue
        path = os.path.join(SCRIPT_DIR, name)
        if os.path.isfile(path):
            files.append(path)
    return files


def format_members(names, limit=5):
    """成员列表展示：不超过 5 个全部展示，超过时缩写为 1, 2, 3, …, 10"""
    if len(names) <= limit:
        return ", ".join(names)
    return ", ".join(names[:3]) + ", …, " + names[-1]


def show_groups(groups, selected=None):
    """展示靶文件夹组表格（编号/组别/形式/文件夹/数目）；
    selected 为编号集合时只展示选中的组，标题改为"靶目标文件夹组"。"""
    rows = [(str(i), gtype, f'"{pattern}"' if pattern else "—",
             format_members(members), str(len(members)))
            for i, (gtype, pattern, members) in enumerate(groups, 1)
            if selected is None or i in selected]
    title = (f"── 靶文件夹（共 {len(groups)} 组）──" if selected is None
             else f"── 靶目标文件夹组（共 {len(rows)} 组）──")
    print(f"\n{title}")
    show_table(rows, ["编号", "组别", "形式", "文件夹", "数目"])


def expand_targets(targets):
    """处理嵌套规律子文件夹（如 a/1、a/2）。

    靶组内的嵌套：询问是否展开为深层靶文件夹；
    非靶文件夹内的嵌套（如单个字母/数字容器）：询问是否将其子文件夹加入靶文件夹。
    """
    target_names = {os.path.basename(t): t for t in targets}
    in_target, out_target = [], []
    for name in sorted(os.listdir(SCRIPT_DIR)):
        if name.startswith(".") or name in EXCLUDE_DIRS:
            continue
        path = os.path.join(SCRIPT_DIR, name)
        if not os.path.isdir(path):
            continue
        subs = [os.path.join(path, n) for n in os.listdir(path)
                if (n.isdigit() or n.isalpha()) and os.path.isdir(os.path.join(path, n))]
        if not subs:
            continue
        (in_target if name in target_names else out_target).append((path, subs))

    if not in_target and not out_target:
        return targets

    if in_target:
        hint = "，".join(f"{os.path.basename(p)}/（{len(subs)} 个）" for p, subs in in_target)
        print(f"ℹ️  检测到靶文件夹内的嵌套规律子文件夹：{hint}，可展开为深层靶文件夹（如 a/1、a/2）。")
        if ask_yes_no("是否展开为深层靶文件夹？"):
            nested_names = {os.path.basename(p) for p, _ in in_target}
            targets = [sub for p, subs in in_target for sub in subs] + \
                      [t for t in targets if os.path.basename(t) not in nested_names]
            print(f"✅ 已展开，靶文件夹变为 {len(targets)} 个。\n")

    if out_target:
        hint = "，".join(f"{os.path.basename(p)}/（{len(subs)} 个）" for p, subs in out_target)
        print(f"ℹ️  检测到非靶文件夹内的嵌套规律子文件夹：{hint}（如 a/1、a/2）。")
        if ask_yes_no("是否将其子文件夹也加入靶文件夹？"):
            targets.extend(sub for p, subs in out_target for sub in subs)
            print(f"✅ 已加入，靶文件夹变为 {len(targets)} 个。\n")
    return targets


# ==================== 复制执行 ====================

def copy_files(sources, targets, skip_existing):
    """批量复制：sources 全部文件复制到每个 targets 文件夹，统计结果"""
    copied = skipped = failed = 0
    for t in targets:
        for src in sources:
            dest = os.path.join(t, os.path.basename(src))
            if os.path.exists(dest) and skip_existing:
                skipped += 1
                continue
            try:
                shutil.copy2(src, dest)
                copied += 1
            except Exception as e:
                failed += 1
                print(f"❌ 复制失败：{src} -> {dest}（{e}）")
        print(f"📦 已处理靶文件夹：{t}")
    return copied, skipped, failed


# ============================== 脚本工作区 =====================================

def run_cmdline(target_raw, source_raw, names):
    """命令行模式：展开靶文件夹与来源，收集来源文件，展示后复制并记录"""
    print("=" * 60)
    print("快捷复制脚本 quick_cp.py（命令行模式）")
    print("=" * 60)
    targets = resolve_target_dirs(target_raw)
    src_files, src_dirs = resolve_sources(source_raw)
    sources = collect_sources(src_files, src_dirs, names)
    if not targets:
        print("❌ 靶文件夹为空（-t/--target 未指定或通配符未匹配到文件夹）。")
        sys.exit(1)
    if not sources:
        print("❌ 来源文件为空（-s/--source 未匹配到文件/文件夹，或 -sn 指定文件不存在）。")
        sys.exit(1)

    print(f"\n── 待复制文件（{len(sources)} 个）──")
    show_table([(str(i), os.path.basename(s), fmt_size(os.path.getsize(s)))
                for i, s in enumerate(sources, 1)], ["编号", "文件", "大小"])
    print(f"── 靶文件夹（{len(targets)} 个）──")
    show_table([(str(i), t) for i, t in enumerate(targets, 1)],
               ["编号", "文件夹"])
    total_cp = len(sources) * len(targets)
    print(f"\n将执行 {len(sources)} × {len(targets)} = {total_cp} 次复制（命令行模式：同名文件直接覆盖）。")

    copied, skipped, failed = copy_files(sources, targets, skip_existing=False)
    print(f"\n🎉 全部完成！复制成功 {copied} 个，跳过 {skipped} 个，失败 {failed} 个。")
    print(f"   共处理 {len(targets)} 个靶文件夹，{len(sources)} 个来源文件。")
    write_record(" ".join(sys.argv), targets, sources, copied, skipped, failed)


def run_interactive():
    """交互式模式（无参数）：识别规律文件夹作为靶文件夹，选择传递文件/文件夹后复制"""
    print("=" * 60)
    print("快捷复制脚本 quick_cp.py（交互式模式）")
    print(f"脚本目录：{SCRIPT_DIR}")
    print("=" * 60)

    # 1. 扫描并整理靶文件夹集合
    groups, transfer_folders = build_groups()
    transfer_files = collect_transfer_files()

    if not groups:
        print("❌ 未识别到任何规律文件夹（数字序列/字母序列/通配符模式），无法确定靶文件夹。")
        print("   请确认目录结构后重试。")
    else:
        show_groups(groups)

    if transfer_folders:
        print(f"\n── 传递文件夹（共 {len(transfer_folders)} 个）──")
        show_table([(str(i), name)
                    for i, name in enumerate(transfer_folders, 1)],
                   ["编号", "文件夹"])
    if transfer_files:
        print(f"\n── 传递文件（共 {len(transfer_files)} 个）──")
        show_table([(str(i), os.path.basename(f))
                    for i, f in enumerate(transfer_files, 1)], ["编号", "文件"])

    # 2. 靶组选择
    if groups:
        group_ids = choose_ids(len(groups), "请选择靶文件夹组（all 或编号）：")
        targets = [os.path.join(SCRIPT_DIR, name)
                   for i, (_, _, members) in enumerate(groups, 1) if i in group_ids
                   for name in members]
    else:
        group_ids = set()
        targets = []

    # 3. 手动补充靶文件夹交互已移除：靶文件夹仅由规律组识别确定
    if not targets:
        print("❌ 靶文件夹为空，无法复制。请确认目录结构后重试。")
        sys.exit(1)

    # 4. 嵌套规律子文件夹展开
    targets = expand_targets(targets)

    # 5. 模式选择：传递当前目录文件 / 传递文件夹中文件
    print("── 传递模式 ──")
    print("  [1] 传递当前目录文件 ：选择脚本所在目录下的文件复制到靶文件夹")
    print("  [2] 传递文件夹中文件 ：选择传递文件夹中文件，将其下文件复制到靶文件夹")
    mode = ask("请选择传递模式：")
    while mode not in ("1", "2"):
        mode = ask("⚠️  输入无效，请输入 1 或 2：")

    # 6. 收集来源文件
    if mode == "1":
        if not transfer_files:
            print("❌ 脚本目录下没有可传递的文件（除脚本自身外）。")
            sys.exit(1)
        print(f"\n── 传递文件列表（共 {len(transfer_files)} 个）──")
        show_table([(str(i), os.path.basename(f))
                    for i, f in enumerate(transfer_files, 1)], ["编号", "文件"])
        show_groups(groups, group_ids)
        file_ids = choose_ids(len(transfer_files), "请选择要传递的文件编号：")
        sources = [transfer_files[i - 1] for i in sorted(file_ids)]
    else:
        if not transfer_folders:
            print("❌ 没有传递文件夹（无规律文件夹），请改用传递文件模式。")
            sys.exit(1)
        print(f"\n── 传递文件夹列表（共 {len(transfer_folders)} 个）──")
        rows = []
        for i, name in enumerate(transfer_folders, 1):
            inner = [n for n in os.listdir(os.path.join(SCRIPT_DIR, name))
                     if os.path.isfile(os.path.join(SCRIPT_DIR, name, n))]
            rows.append((str(i), name, str(len(inner))))
        show_table(rows, ["编号", "文件夹", "内部文件数"])
        folder_ids = choose_ids(len(transfer_folders), "请选择传递文件夹：",
                                allow_all=False)
        folder_sources = []
        for i in sorted(folder_ids):
            fdir = os.path.join(SCRIPT_DIR, transfer_folders[i - 1])
            for n in sorted(os.listdir(fdir)):
                p = os.path.join(fdir, n)
                if os.path.isfile(p):
                    folder_sources.append(p)
        if not folder_sources:
            print("❌ 选中文件夹内没有可传递的文件。")
            sys.exit(1)
        # 先展示选中文件夹内的全部文件，再让用户挑选要传递的部分
        print(f"\n── 待复制文件（{len(folder_sources)} 个）──")
        show_table([(str(i), os.path.basename(s))
                    for i, s in enumerate(folder_sources, 1)], ["编号", "文件"])
        show_groups(groups, group_ids)
        file_ids = choose_ids(len(folder_sources), "请选择要传递的文件编号：")
        sources = [folder_sources[i - 1] for i in sorted(file_ids)]

    if not sources:
        print("❌ 来源文件为空，无法复制。")
        sys.exit(1)

    # 7. 展示已选择文件，最终确认
    print("\n已选择文件：")
    show_table([(str(i), os.path.basename(s))
                for i, s in enumerate(sources, 1)], ["编号", "文件名"])
    total_cp = len(sources) * len(targets)
    if not ask_yes_no(f"\n将执行 {len(sources)} × {len(targets)} = {total_cp} 次复制，是否执行？"):
        print("👋 已取消，未执行任何复制。")
        sys.exit(0)

    # 8. 同名文件冲突检测
    src_names = [os.path.basename(s) for s in sources]
    dup_in_src = len(src_names) - len(set(src_names))
    exist_in_target = sum(1 for t in targets for s in sources
                          if os.path.exists(os.path.join(t, os.path.basename(s))))
    skip_existing = False
    if dup_in_src or exist_in_target:
        print(f"\n⚠️  检测到同名冲突：来源间同名 {dup_in_src} 处，靶文件夹中已存在 {exist_in_target} 处。")
        choice = ask("处理方式：[1] 覆盖已存在  [2] 跳过已存在：")
        while choice not in ("1", "2"):
            choice = ask("⚠️  输入无效，请输入 1 或 2：")
        if choice == "2":
            skip_existing = True
            print("ℹ️  将跳过靶文件夹中已存在的同名文件。")

    # 9. 执行复制
    print()
    copied, skipped, failed = copy_files(sources, targets, skip_existing)
    print(f"\n🎉 全部完成！复制成功 {copied} 个，跳过 {skipped} 个，失败 {failed} 个。")
    print(f"   共处理 {len(targets)} 个靶文件夹，{len(sources)} 个来源文件。")
    write_record("python quick_cp.py（交互式模式）", targets, sources, copied, skipped, failed)


def main():
    """主流程：有命令行参数走命令行模式，无参数走交互式模式"""
    if len(sys.argv) > 1:
        target_raw, source_raw, names = parse_args(sys.argv[1:])
        if not (target_raw or source_raw or names):
            print("❌ 参数不足：请用 -t 指定靶文件夹、-s 指定来源文件夹/文件。")
            print("   python quick_cp.py -t ./A ./B ./C -s ./D")
            sys.exit(1)
        run_cmdline(target_raw, source_raw, names)
    else:
        run_interactive()


# ============================== 脚本运行区 =====================================

if __name__ == "__main__":
    main()
