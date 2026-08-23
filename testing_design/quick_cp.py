"""
=============================================================================
脚本:        quick_cp.py
分类:        文件批量复制脚本（交互式）
功能:        自动识别脚本所在目录下的规律文件夹作为目标文件夹，支持两种传递模式：
             ① 传递文件模式：将脚本目录下的文件（除自身外）编号后选择复制；
             ② 传递文件夹模式：选择无规律文件夹，将其下所有文件复制。
             复制前展示来源清单与目标清单，确认后执行。

目标文件夹识别规则（有规律）:
             1. 数字序列组   : 1/ 2/ 3/ … 纯数字文件夹（按数值排序）
             2. 字母序列组   : a/ b/ c/ … 纯字母文件夹（按连续段分组）
             3. 通配符模式组 : 其余文件夹中共享"前缀+后缀"的集合，
                              如 frame_1/ frame_2/ … 可用 frame_* 描述
             其余无规律文件夹称为传递文件夹；脚本所在目录下的文件
             （除脚本自身外）称为传递文件。

使用方法:    python quick_cp.py
参数:        无参数，交互式运行
输出:        按用户选择将文件复制到各目标文件夹
作者:        Hongbo Sun
最后修改日期: 2026-08-23
=============================================================================
# 目录树示例:
# ============================================================================
# .
# ├── quick_cp.py
# ├── INCAR                    <- 传递文件
# ├── POTCAR
# ├── sub.sh
# ├── 1/                       <- 数字序列组
# │   └── POSCAR
# ├── 2/
# │   └── POSCAR
# ├── frame_1/                 <- 通配符模式组 frame_*
# │   └── ...
# ├── frame_2/
# │   └── ...
# ├── raw_data/                <- 传递文件夹（无规律）
# │   └── ...
# └── __pycache__/             <- 自动排除
# ============================================================================
"""
import glob
import os
import re
import shutil
import sys

# Windows 控制台默认 GBK 编码无法输出 emoji，统一改用 UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_NAME = os.path.basename(__file__)

# ============ 配置区（可按需调整） ============
# 规律组最少成员数：少于该数量的文件夹不构成规律组（自动归为传递文件夹）
MIN_GROUP_SIZE = 2
# 自动排除的特殊目录（缓存/版本控制等，不参与目标与传递判定）
EXCLUDE_DIRS = {"__pycache__", ".git", ".svn", ".hg", ".idea", ".vscode", "node_modules"}


# ==================== 工具函数 ====================

def fmt_size(nbytes):
    """文件大小格式化：B/KB/MB/GB"""
    nbytes = float(nbytes)
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024 or unit == "GB":
            return f"{nbytes:.1f} {unit}" if unit != "B" else f"{int(nbytes)} B"
        nbytes /= 1024


def show_table(rows, headers, title=None):
    """终端表格输出：表头与所有数据列均采用右对齐格式"""
    if title:
        print(title)
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    line = "  ".join(str(h).rjust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("-" * len(line))
    for row in rows:
        print("  ".join(str(c).rjust(widths[i]) for i, c in enumerate(row)))
    print()


def ask(prompt):
    """输入询问：必须显式输入内容并回车（防止误触）；输入 q 退出脚本"""
    while True:
        s = input(f"\n{prompt} ").strip()
        if s.lower() in ("q", "quit", "exit"):
            print("👋 已取消，退出脚本。")
            sys.exit(0)
        if s:
            return s
        print("⚠️  输入不能为空，请明确输入后回车。")


def ask_yes_no(prompt, default=None):
    """是非询问：必须显式输入 y/n 确认；default 仅作为提示中的建议值"""
    hint = "" if default is None else f"（建议：{default}）"
    while True:
        s = ask(f"{prompt} {hint}")
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


def choose_ids(total, prompt):
    """交互式选择编号：必须显式输入（支持 all、1,3,5、1-3）；返回选中的编号集合（1 起）"""
    while True:
        ids = parse_choice(ask(prompt), total)
        if ids is not None:
            return ids
        range_hint = "1" if total == 1 else f"1-{total}"
        print(f"⚠️  输入无效，请输入 {range_hint} 范围内的编号，支持 1,3,5 / 1-3 / all。")


# ==================== 目标文件夹识别 ====================

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
    """构建全部目标规律组：返回 (groups, transfer_folders)"""
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


def format_members(names, limit=10):
    """成员列表展示：多时缩写为 1, 2, 3, …, 10"""
    if len(names) <= limit:
        return ", ".join(names)
    return ", ".join(names[:3]) + ", …, " + names[-1]


def expand_targets(targets):
    """处理嵌套规律子文件夹（如 a/1、a/2）。

    目标组内的嵌套：询问是否展开为深层目标；
    非目标文件夹内的嵌套（如单个字母/数字容器）：询问是否将其子文件夹加入目标。
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
        print(f"ℹ️  检测到目标文件夹内的嵌套规律子文件夹：{hint}，可展开为深层目标（如 a/1、a/2）。")
        if ask_yes_no("是否展开为深层目标文件夹？"):
            nested_names = {os.path.basename(p) for p, _ in in_target}
            targets = [sub for p, subs in in_target for sub in subs] + \
                      [t for t in targets if os.path.basename(t) not in nested_names]
            print(f"✅ 已展开，目标文件夹变为 {len(targets)} 个。\n")

    if out_target:
        hint = "，".join(f"{os.path.basename(p)}/（{len(subs)} 个）" for p, subs in out_target)
        print(f"ℹ️  检测到非目标文件夹内的嵌套规律子文件夹：{hint}（如 a/1、a/2）。")
        if ask_yes_no("是否将其子文件夹也加入目标文件夹？"):
            targets.extend(sub for p, subs in out_target for sub in subs)
            print(f"✅ 已加入，目标文件夹变为 {len(targets)} 个。\n")
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
        print(f"📦 已处理目标文件夹：{t}")
    return copied, skipped, failed


# ==================== 主流程 ====================

def main():
    print("=" * 60)
    print("快捷复制脚本 quick_cp.py")
    print(f"脚本目录：{SCRIPT_DIR}")
    print("=" * 60)

    # 1. 扫描并整理目标文件夹集合
    groups, transfer_folders = build_groups()
    transfer_files = collect_transfer_files()

    if not groups:
        print("❌ 未识别到任何规律文件夹（数字序列/字母序列/通配符模式），无法确定目标文件夹。")
        print("   可手动补充目标文件夹（见下一步），或确认目录结构后重试。")
    else:
        print(f"\n── 目标文件夹（有规律，共 {len(groups)} 组）──")
        for i, (gtype, pattern, members) in enumerate(groups, 1):
            pat = f'"{pattern}"' if pattern else "—"
            print(f"  [{i:>2}] {gtype:<7} 通配符 {pat:<15} {format_members(members)}（{len(members)} 个）")

    if transfer_folders:
        print(f"\n── 传递文件夹（无规律，共 {len(transfer_folders)} 个）──")
        print("  " + ", ".join(transfer_folders))
    if transfer_files:
        print(f"\n── 传递文件（脚本目录下，共 {len(transfer_files)} 个）──")
        print("  " + ", ".join(os.path.basename(f) for f in transfer_files))

    # 2. 目标组选择（默认全部）
    if groups:
        ids = choose_ids(len(groups), "\n请选择目标文件夹组（输入 all 或编号，如 1,2）：")
        targets = [os.path.join(SCRIPT_DIR, name)
                   for i, (_, _, members) in enumerate(groups, 1) if i in ids
                   for name in members]
    else:
        targets = []

    # 3. 手动补充目标文件夹（支持通配符）
    if ask_yes_no("\n是否手动补充目标文件夹（支持通配符，如 frame_*，空格分隔多个）？"):
        text = ask("请输入目标文件夹通配符（空格分隔多个）：")
        for pattern in text.split():
            matched = [p for p in glob.glob(os.path.join(SCRIPT_DIR, pattern)) if os.path.isdir(p)]
            if not matched:
                print(f"⚠️  通配符 {pattern} 未匹配到任何文件夹，已忽略。")
            else:
                for p in matched:
                    if p not in targets:
                        targets.append(p)
                print(f"✅ 通配符 {pattern} 匹配 {len(matched)} 个文件夹，已加入目标。")

    if not targets:
        print("❌ 目标文件夹为空，无法复制。请补充目标文件夹后重试。")
        sys.exit(1)

    # 4. 嵌套规律子文件夹展开
    targets = expand_targets(targets)

    # 5. 模式选择：传递文件 / 传递文件夹
    print("── 传递模式 ──")
    print("  [1] 传递文件模式   ：选择脚本目录下的文件复制到目标文件夹")
    print("  [2] 传递文件夹模式 ：选择无规律文件夹，将其下所有文件复制到目标文件夹")
    mode = ask("请选择传递模式（1=传递文件，2=传递文件夹）：")
    while mode not in ("1", "2"):
        mode = ask("⚠️  输入无效，请输入 1 或 2：")

    # 6. 收集来源文件
    if mode == "1":
        if not transfer_files:
            print("❌ 脚本目录下没有可传递的文件（除脚本自身外）。")
            sys.exit(1)
        print(f"\n── 传递文件列表（共 {len(transfer_files)} 个）──")
        show_table([(str(i), os.path.basename(f), fmt_size(os.path.getsize(f)))
                    for i, f in enumerate(transfer_files, 1)],
                   ["编号", "文件名", "大小"])
        ids = choose_ids(len(transfer_files), "请选择要传递的文件（输入 all 或编号，如 1,3-5）：")
        sources = [transfer_files[i - 1] for i in sorted(ids)]
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
        show_table(rows, ["编号", "文件夹名", "内部文件数"])
        ids = choose_ids(len(transfer_folders), "请选择传递文件夹（输入 all 或编号，如 1,3-5）：")
        sources = []
        for i in sorted(ids):
            fdir = os.path.join(SCRIPT_DIR, transfer_folders[i - 1])
            for n in sorted(os.listdir(fdir)):
                p = os.path.join(fdir, n)
                if os.path.isfile(p):
                    sources.append(p)

    if not sources:
        print("❌ 来源文件为空，无法复制。")
        sys.exit(1)

    # 7. 展示来源与目标，最终确认
    print(f"\n── 待复制文件（{len(sources)} 个）──")
    for i, s in enumerate(sources, 1):
        print(f"  {i:>3}. {os.path.basename(s)}")
    print(f"\n── 目标文件夹（{len(targets)} 个）──")
    for i, t in enumerate(targets, 1):
        print(f"  {i:>3}. {t}")
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
        print(f"\n⚠️  检测到同名冲突：来源间同名 {dup_in_src} 处，目标中已存在 {exist_in_target} 处。")
        choice = ask("处理方式：[1] 覆盖已存在  [2] 跳过已存在：")
        while choice not in ("1", "2"):
            choice = ask("⚠️  输入无效，请输入 1 或 2：")
        if choice == "2":
            skip_existing = True
            print("ℹ️  将跳过目标中已存在的同名文件。")

    # 9. 执行复制
    print()
    copied, skipped, failed = copy_files(sources, targets, skip_existing)
    print(f"\n🎉 全部完成！复制成功 {copied} 个，跳过 {skipped} 个，失败 {failed} 个。")
    print(f"   共处理 {len(targets)} 个目标文件夹，{len(sources)} 个来源文件。")


if __name__ == "__main__":
    main()
