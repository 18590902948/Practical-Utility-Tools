#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查并修正所有 POSCAR 的元素行顺序：Al 在前、O 在后。

用法:
    python fix_poscar_order.py          # 只检查，不改动任何文件
    python fix_poscar_order.py --fix    # 检查并修正（修改前备份为 POSCAR.bak）

原理:
    按元素块整体重排（Al 块 -> O 块 -> 其它元素块，稳定排序），块内原子顺序不变，
    晶格、缩放系数以及每个原子的坐标数值逐字保留，因此结构完全不变。
    修正后用 ASE 读取修正前后的结构做校验（晶格、化学配比、按元素分组的坐标多重集），
    若校验不通过则自动从备份回滚。
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from ase.io import read

PREFERRED_ORDER = ['Al', 'O']


def elem_of(token):
    """从元素 token 中取化学符号，如 'Al3+' -> 'Al'。"""
    m = re.match(r'([A-Za-z]+)', token)
    return m.group(1) if m else token


def line_ending(line):
    if line.endswith('\r\n'):
        return '\r\n'
    if line.endswith('\n'):
        return '\n'
    return ''


def read_lines(path):
    with open(path, 'r', encoding='utf-8', errors='replace', newline='') as f:
        return f.readlines()


def write_lines(path, lines):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.writelines(lines)


def parse_poscar(path):
    """解析 POSCAR 的头部与坐标块；VASP4（无元素符号行）返回 None。"""
    lines = read_lines(path)
    if len(lines) < 8:
        raise ValueError('文件行数不足')

    sym_tokens = lines[5].split()
    if not sym_tokens or not sym_tokens[0][0].isalpha():
        return None  # VASP4：第 6 行只有计数，没有元素符号
    syms = [elem_of(t) for t in sym_tokens]

    counts = [int(x) for x in lines[6].split()]
    if len(counts) != len(syms):
        raise ValueError('元素行与计数行数量不一致')
    natoms = sum(counts)

    mode_idx = 7
    if lines[mode_idx].strip().lower().startswith('s'):  # Selective dynamics
        mode_idx += 1
    if mode_idx >= len(lines) or lines[mode_idx].strip()[:1].lower() not in ('d', 'c'):
        raise ValueError('未找到 Direct/Cartesian 坐标行')
    coord_start = mode_idx + 1

    coord_lines = lines[coord_start:coord_start + natoms]
    if len(coord_lines) != natoms:
        raise ValueError('坐标行数不足：期望 %d，实际 %d' % (natoms, len(coord_lines)))

    return {
        'lines': lines,
        'syms': syms,
        'counts': counts,
        'coord_start': coord_start,
        'coord_lines': coord_lines,
        'natoms': natoms,
    }


def element_order(syms):
    """按首次出现顺序去重，即 POSCAR 元素行的顺序。"""
    order = []
    for s in syms:
        if s not in order:
            order.append(s)
    return order


def need_fix(syms):
    """Al 与 O 同时存在且 Al 不在 O 前面时，需要修正。"""
    order = element_order(syms)
    if 'Al' in order and 'O' in order:
        return order.index('Al') > order.index('O')
    return False


def build_fixed_lines(info):
    """返回重排后的完整文件行列表及新元素/计数序列。"""
    blocks = []
    pos = 0
    for s, c in zip(info['syms'], info['counts']):
        blocks.append((s, c, info['coord_lines'][pos:pos + c]))
        pos += c

    rank = {s: i for i, s in enumerate(PREFERRED_ORDER)}
    blocks = sorted(blocks, key=lambda b: rank.get(b[0], len(PREFERRED_ORDER)))  # 稳定排序

    new_syms = [b[0] for b in blocks]
    new_counts = [b[1] for b in blocks]
    new_coords = [line for b in blocks for line in b[2]]

    lines = list(info['lines'])
    end = line_ending(lines[5]) or '\n'
    sym_indent = re.match(r'[ \t]*', lines[5]).group(0)
    cnt_indent = re.match(r'[ \t]*', lines[6]).group(0)
    lines[5] = sym_indent + '  '.join(new_syms) + end
    lines[6] = cnt_indent + '  '.join('%d' % c for c in new_counts) + end
    lines[info['coord_start']:info['coord_start'] + info['natoms']] = new_coords
    return lines, new_syms, new_counts


def signature(path):
    """结构签名：晶格 + 化学配比 + 按元素分组的排序坐标多重集。"""
    atoms = read(str(path), format='vasp')
    syms = atoms.get_chemical_symbols()
    scaled = atoms.get_scaled_positions(wrap=False)
    by_elem = {}
    for el in sorted(set(syms)):
        mask = np.array([s == el for s in syms])
        coords = np.round(scaled[mask], 8)
        by_elem[el] = np.array(sorted(coords.tolist())) if len(coords) else np.zeros((0, 3))
    return np.array(atoms.cell), Counter(syms), by_elem


def same_structure(sig1, sig2, atol=1e-6):
    cell1, comp1, pos1 = sig1
    cell2, comp2, pos2 = sig2
    if comp1 != comp2:
        return False, '化学配比不一致'
    if not np.allclose(cell1, cell2, atol=atol):
        return False, '晶格不一致'
    for el in pos1:
        if el not in pos2:
            return False, '缺少元素 %s' % el
        a, b = pos1[el], pos2[el]
        if a.shape != b.shape or not np.allclose(a, b, atol=atol):
            return False, '元素 %s 的坐标多重集不一致' % el
    return True, ''


def main():
    default_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description='检查/修正 POSCAR 元素顺序（Al 在前，O 在后）')
    parser.add_argument('root', nargs='?', default=str(default_root),
                        help='扫描根目录（默认：脚本所在目录）')
    parser.add_argument('--fix', action='store_true', help='执行修正（默认只检查）')
    args = parser.parse_args()

    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    root = Path(args.root).resolve()
    files = sorted(p for p in root.rglob('POSCAR') if p.is_file())
    if not files:
        print('在 %s 下未找到任何 POSCAR' % root)
        return 2

    print('=' * 78)
    print('扫描目录 : %s' % root)
    print('POSCAR 数: %d' % len(files))
    print('运行模式 : %s' % ('修正 (--fix)' if args.fix else '仅检查（不改文件）'))
    print('=' * 78)

    n_ok = n_fixed = n_fail = n_skip = n_need = 0

    for path in files:
        name = path.parent.name if path.parent != root else path.name
        try:
            info = parse_poscar(path)
        except Exception as exc:
            print('[ERROR] %-18s 解析失败: %s' % (name, exc))
            n_fail += 1
            continue
        if info is None:
            print('[SKIP ] %-18s VASP4 格式（无元素符号行），无法判断顺序' % name)
            n_skip += 1
            continue

        order = element_order(info['syms'])
        formula = ' '.join('%s%d' % (s, c) for s, c in zip(info['syms'], info['counts']))

        if not need_fix(info['syms']):
            note = '' if ('Al' in order and 'O' in order) else '仅含 %s，无需调整' % '/'.join(order)
            print('[OK   ] %-18s 元素顺序: %-10s (%s) %s'
                  % (name, ' '.join(order), formula, note))
            n_ok += 1
            continue

        if not args.fix:
            print('[NEED ] %-18s 元素顺序: %-10s (%s)  -> 需调整为 Al 在前'
                  % (name, ' '.join(order), formula))
            n_need += 1
            continue

        # ---- 执行修正 ----
        try:
            sig_before = signature(path)
        except Exception as exc:
            print('[ERROR] %-18s ASE 无法读取原结构，未修改: %s' % (name, exc))
            n_fail += 1
            continue

        new_lines, new_syms, new_counts = build_fixed_lines(info)
        bak = path.with_name('POSCAR.bak')
        if not bak.exists():
            bak.write_bytes(path.read_bytes())
            backup_note = '已备份 POSCAR.bak'
        else:
            backup_note = 'POSCAR.bak 已存在，未覆盖'
        write_lines(path, new_lines)

        try:
            sig_after = signature(path)
            ok, reason = same_structure(sig_before, sig_after)
        except Exception as exc:
            ok, reason = False, 'ASE 复读失败: %s' % exc

        if ok:
            formula_new = ' '.join('%s%d' % (s, c) for s, c in zip(new_syms, new_counts))
            print('[FIXED] %-18s 元素顺序: %-10s -> %-10s (%s; %s; 结构校验通过)'
                  % (name, ' '.join(order), ' '.join(new_syms), formula_new, backup_note))
            n_fixed += 1
        else:
            path.write_bytes(bak.read_bytes())
            print('[FAIL ] %-18s 修正后校验失败（%s），已从备份回滚' % (name, reason))
            n_fail += 1

    print('-' * 78)
    if args.fix:
        print('汇总: 合规 %d | 已修正 %d | 失败 %d | 跳过 %d'
              % (n_ok, n_fixed, n_fail, n_skip))
    else:
        print('汇总: 合规 %d | 需修正 %d | 失败 %d | 跳过 %d'
              % (n_ok, n_need, n_fail, n_skip))

    # 修正模式下做一次全面复核
    if args.fix:
        remaining = []
        for path in files:
            try:
                info = parse_poscar(path)
            except Exception:
                remaining.append(path.parent.name)
                continue
            if info is not None and need_fix(info['syms']):
                remaining.append(path.parent.name)
        if remaining:
            print('复核: 仍有 %d 个文件不符合 Al 在前: %s'
                  % (len(remaining), ', '.join(remaining)))
            return 1
        print('复核: 全部 POSCAR 的元素行顺序均为 Al 在前、O 在后（或仅含单一元素）')

    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
