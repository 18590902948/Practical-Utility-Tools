#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
=============================================================================
脚本:        bc_cif_xsd2pos.py
分类:        格式转换脚本
功能:        扫描当前目录下所有 .cif 和 .xsd 文件，自动批量转换为 .vasp
             （VASP POSCAR 格式），转换结果按类型分类存放；
             相当于 cif2pos 与 xsd2pos 的批量整合版。
使用方法:    python bc_cif_xsd2pos.py
参数:        无参数，自动扫描当前工作目录下全部 *.cif 和 *.xsd 文件
输出:
  cif/*.vasp          由 .cif 文件转换的 VASP 结构文件
  xsd/*.vasp          由 .xsd 文件转换的 VASP 结构文件
作者:        Hongbo Sun
最后修改日期: 2026-08-20
=============================================================================
# 目录树示例:
# ============================================================================
# .                       # 运行目录（含 .cif/.xsd 文件）
# ├── A.cif              # 输入：CIF 文件
# ├── B.xsd              # 输入：XSD 文件
# ├── cif/
# │   └── A.vasp         # 输出：由 A.cif 转换
# └── xsd/
#     └── B.vasp         # 输出：由 B.xsd 转换
# ============================================================================
"""

import os
import re
import sys
import math
import shutil
from glob import glob
import numpy as np
from fractions import Fraction as frac

# =============================================================================
# Part 1: CIF -> VASP conversion (from cif2pos.py)
# =============================================================================

def readfile(filename):
    try:
        f = open(filename)
    except:
        print('Error: cannot open file:' + filename)
        sys.exit(1)
    rst = []
    try:
        for line in f:
            if len(line.strip()) != 0:
                rst.append(line.strip())
    finally:
        f.close()
    return rst


def appro_float(flo):
    for i in range(len(flo)):
        if flo[i] == "(":
            flo = flo[:i]
            break
    return float(flo)


def symmetry(cif):
    symm = []; __HALL = ''; __H_M = ''
    symmetry = []
    trans = []
    iline = 0
    find_symm_info = False
    for line in cif:
        iline += 1
        if '_symmetry_equiv_pos_as_xyz' in line or '_space_group_symop_operation_xyz' in line:
            for item in cif[iline:]:
                if item.strip()[0] != '_' and item.strip() != 'loop_':
                    if '\'' in item:
                        pattern = r'\'(.*?)\''
                        itemlist = re.findall(pattern, item)
                        item = itemlist[0]
                    if item[0] == "'" or item[0] == '"':
                        iitem = item[1:-1]
                    else:
                        iitem = item[:]
                    symm.append(iitem.strip().split(','))
                    find_symm_info = True
                else:
                    break
            break
        elif 'name_Hall' in line:
            try:
                pattern = r'\'(.*?)\''
                _HALL = re.findall(pattern, line)
                __HALL = _HALL[0]
            except:
                try:
                    pattern = r'\"(.*?)\"'
                    _HALL = re.findall(pattern, line)
                    __HALL = _HALL[0]
                except:
                    __HALL = ' '.join(line.split()[1:])
        elif 'name_H-M' in line:
            try:
                pattern = r'\'(.*?)\''
                _H_M = re.findall(pattern, line)
                __H_M = _H_M[0]
            except:
                try:
                    pattern = r'\"(.*?)\"'
                    _H_M = re.findall(pattern, line)
                    __H_M = _H_M[0]
                except:
                    __H_M = ' '.join(line.split()[1:])

    if not find_symm_info:
        if __H_M == '' and __HALL == '':
            print("P1 symmetry is assumed!")
            symm = [['x', ' y', ' z']]
        elif __HALL != '':
            __HALL = ' '.join(__HALL.split())
            try:
                symm = SymOpsHall[__HALL]
            except:
                raise OSError("WRONG HALL SYMBOL")
        elif __H_M != '':
            __H_M = ''.join(__H_M.split())
            try:
                hall = HM2Hall[__H_M]
                symm = SymOpsHall[hall]
            except:
                raise OSError("WRONG H-M SYMBOL")

    for item in symm:
        s2 = []
        tran1 = []
        for subtem in item:
            subtem = subtem.strip()
            try:
                isprit = subtem.index('/')
                stt = [istr for istr in subtem]
                for i in range(0, 3):
                    del(stt[isprit - 1])
                if stt[-1] == '+' or stt[-1] == '-':
                    del(stt[-1])
                subt = ''.join(stt)
            except:
                subt = subtem[:]
            s1 = [0, 0, 0]
            if subt[0] == '-' or subt[0] == '+':
                for i in range(0, len(subt) - 1, 2):
                    if subt[i:i+2] == '-x': s1[0] = -1
                    if subt[i:i+2] == '+x': s1[0] = 1
                    if subt[i:i+2] == '-y': s1[1] = -1
                    if subt[i:i+2] == '+y': s1[1] = 1
                    if subt[i:i+2] == '-z': s1[2] = -1
                    if subt[i:i+2] == '+z': s1[2] = 1
            else:
                if subt[0] == 'x': s1[0] = 1
                if subt[0] == 'y': s1[1] = 1
                if subt[0] == 'z': s1[2] = 1
                for i in range(1, len(subt) - 1, 2):
                    if subt[i:i+2] == '-x': s1[0] = -1
                    if subt[i:i+1] == '+x': s1[0] = 1
                    if subt[i:i+2] == '-y': s1[1] = -1
                    if subt[i:i+2] == '+y': s1[1] = 1
                    if subt[i:i+2] == '-z': s1[2] = -1
                    if subt[i:i+2] == '+z': s1[2] = 1
            t1 = 0.
            for subsub in re.split('[+,-]', subtem):
                try:
                    t1 = float(frac(subsub))
                except:
                    continue
            tran1.append(t1)
            s2.append(s1)
        symmetry.append(s2)
        trans.append(tran1)
    return (np.array(symmetry), np.array(trans))


def atominfo(cif):
    loopinfo = []
    atominfo = []
    for i in range(0, len(cif)):
        if cif[i].strip() == 'loop_':
            istart = i
            loopinfo = []
            atominfo = []
            for j in range(istart + 1, len(cif)):
                if cif[j].strip() == 'loop_' or cif[j].strip().startswith("#"):
                    break
                if cif[j].strip()[0] == '_':
                    loopinfo.append(cif[j].strip())
                else:
                    atominfo.append(cif[j].strip())
        if '_atom_site_fract_x' in loopinfo:
            break

    try:
        il = loopinfo.index('_atom_site_label')
        ix = loopinfo.index('_atom_site_fract_x')
        iy = loopinfo.index('_atom_site_fract_y')
        iz = loopinfo.index('_atom_site_fract_z')
    except:
        print('Unsupport CIF format!')
        sys.exit(1)

    typesym = True
    try:
        it = loopinfo.index('_atom_site_type_symbol')
    except:
        typesym = False

    fractional_occupation = False
    try:
        fractional_occupation = True
        f_o = loopinfo.index('_atom_site_occupancy')
    except:
        fractional_occupation = False

    atomtmp = [a.split() for a in atominfo]
    label = []
    ato = []
    symbol = []
    for item in atomtmp:
        label.append(item[il])
        ato.append([appro_float(ii) for ii in [item[ix], item[iy], item[iz]]])

    for item in atomtmp:
        recognized = False
        two_width = False
        for jk in element:
            for i_item in range(len(item)):
                if item[i_item].upper() == jk:
                    symbol.append(item[i_item])
                    recognized = True
                    two_width = True
                    break
            if recognized:
                break
        if not recognized:
            for jk in element:
                if item[il][:2].upper() == jk:
                    symbol.append(item[il][:2])
                    recognized = True
                    two_width = True
                    break
        if not two_width:
            for jk in element:
                if item[il][0].upper() == jk:
                    symbol.append(item[il][0])
                    recognized = True
                    break
        if not recognized:
            raise OSError("Unidentified atom type!")
    if fractional_occupation:
        for item in atomtmp:
            if appro_float(item[f_o]) != 1.0:
                raise OSError("Not support for fractional occupation!")
    equAtom = {}
    for i in range(0, len(label)):
        equAtom[label[i]] = [symbol[i], ato[i]]
    return equAtom, label


def lattice(cif):
    for item in cif:
        if "_cell_length_a" in item:
            a = appro_float(item.split()[1])
        if "_cell_length_b" in item:
            b = appro_float(item.split()[1])
        if "_cell_length_c" in item:
            c = appro_float(item.split()[1])
        if "_cell_angle_alpha" in item:
            alpha = appro_float(item.split()[1]) / 180 * math.pi
        if "_cell_angle_beta" in item:
            beta = appro_float(item.split()[1]) / 180 * math.pi
        if "_cell_angle_gamma" in item:
            gamma = appro_float(item.split()[1]) / 180 * math.pi

    bc2 = b**2 + c**2 - 2 * b * c * math.cos(alpha)
    h1 = a
    h2 = b * math.cos(gamma)
    h3 = b * math.sin(gamma)
    h4 = c * math.cos(beta)
    h5 = ((h2 - h4)**2 + h3**2 + c**2 - h4**2 - bc2) / (2 * h3)
    h6 = math.sqrt(c**2 - h4**2 - h5**2)

    lattice = [[h1, 0., 0.], [h2, h3, 0.], [h4, h5, h6]]
    return lattice


def optAtom(atom, symm, trans):
    a = np.asmatrix(atom).transpose()
    alist = []
    for imat in symm:
        mat = np.asmatrix(imat)
        ta = mat * a
        alist.append(ta.transpose().tolist()[0])

    slist = np.array(alist) + trans
    for item in slist:
        for i in range(0, 3):
            item[i] = item[i] - int(item[i])
            if item[i] < 0.:
                item[i] += 1
            if item[i] >= 1.:
                item[i] -= 1
            if np.abs(np.abs(item[i]) - 1.0) < 1e-5:
                item[i] = 0.

    badlist = []
    for i in range(0, len(slist)):
        for j in range(i + 1, len(slist)):
            dd = np.sqrt(sum((slist[i] - slist[j]) * (slist[i] - slist[j])))
            if abs(dd) < 1e-5:
                badlist.append(j)
    rsl = []
    for i in range(0, len(slist)):
        if i not in badlist:
            rsl.append(slist[i])
    return np.array(rsl)


def p1atom(order, ea, symm, trans):
    p1 = []
    type = []
    k = list(ea.keys())
    for item in order:
        it = 0
        for ik in k:
            if ea[ik][0].lower() == item.lower():
                t = optAtom(ea[ik][1], symm, trans)
                t1 = t.tolist()
                it += len(t1)
                p1 += t1
        type.append(it)
    return (np.array(p1), type)


def auto_order(ea):
    """Auto-determine element order from CIF data (non-interactive)."""
    order = []
    seen = set()
    for k in ea:
        sym = ea[k][0]
        if sym not in seen:
            seen.add(sym)
            order.append(sym)
    return order


def write_poscar(filename, title, lat, type, pos, order):
    with open(filename, 'w') as f:
        f.write(title + "\n")
        f.write("1.0\n")
        for item in lat:
            f.write("{0:>15.8f}{1:>15.8f}{2:>15.8f}\n".format(
                item[0], item[1], item[2]))
        f.write('  ' + '  '.join(order) + '\n')
        f.write('  ' + '  '.join([str(j) for j in type]) + '\n')
        f.write("Direct\n")
        for item in pos:
            f.write("{0:>15.8f}{1:>15.8f}{2:>15.8f}\n".format(
                item[0], item[1], item[2]))


def convert_cif(cif_path, output_path):
    """Convert a .cif file to .vasp (VASP POSCAR) format."""
    cif = readfile(cif_path)
    s = symmetry(cif)
    eq_atoms, labels = atominfo(cif)
    lat = lattice(cif)
    order = auto_order(eq_atoms)
    pos, atom_counts = p1atom(order, eq_atoms, s[0], s[1])
    title = os.path.basename(cif_path) + " converted by vasp.py"
    write_poscar(output_path, title, lat, atom_counts, pos, order)
    print("  -> %s" % output_path)


# =============================================================================
# Part 2: XSD -> VASP conversion (from xsd2pos.py)
# =============================================================================

class XSD2VASP(object):
    def __init__(self):
        self.lattice = []
        self.atominfo = []
        self.Selective_infomation = False
        self.Direct_mode = True
        self.element = []
        self.xyzs = []
        self.fixed_fraction = False
        self.fixed_cartesian = False
        self.atominMS = []
        self.spacegroup = False

    def dot_product(self, array1, array2):
        assert len(array1) == len(array2)
        ret = 0
        for i in range(len(array2)):
            ret += array1[i] * array2[i]
        return ret

    def read(self, filename):
        with open(filename, 'r') as reader:
            alllines = reader.read()
            reader.seek(0)
            for index, line in enumerate(reader):
                if "AVector" in line or "BVector" in line or "CVector" in line:
                    pattern = u'Vector=\"(.*?)\"'
                    try:
                        for i in re.findall(pattern, line, re.S):
                            self.lattice.append(
                                [float(j) for j in i.split(',')])
                    except:
                        raise SystemError(
                            'No lattice information contained!')
                elif "Components" in line:
                    self.atominfo.append(line)
                if "RestrictedProperties" in line:
                    self.fixed_fraction = True
                if "AlongAxisSlider" in line:
                    self.fixed_cartesian = True
                if "\"P1\"" in line:
                    self.spacegroup = True
            if self.fixed_cartesian:
                pass  # alllines already captured via read()

        if not self.spacegroup:
            raise SystemError('No support for system with symmetry!')

        lattice1 = math.sqrt(self.lattice[0][0]**2 + self.lattice[0][1]**2 +
                             self.lattice[0][2]**2)
        lattice2 = math.sqrt(self.lattice[1][0]**2 + self.lattice[1][1]**2 +
                             self.lattice[1][2]**2)
        lattice3 = math.sqrt(self.lattice[2][0]**2 + self.lattice[2][1]**2 +
                             self.lattice[2][2]**2)

        alpha_angle = math.acos(self.dot_product(
            self.lattice[1], self.lattice[2]) / float((lattice2 * lattice3)))
        beta_angle = math.acos(self.dot_product(
            self.lattice[0], self.lattice[2]) / float((lattice1 * lattice3)))
        gamma_angle = math.acos(self.dot_product(
            self.lattice[0], self.lattice[1]) / float((lattice1 * lattice2)))

        bc2 = lattice2**2 + lattice3**2 - 2 * lattice2 * lattice3 * math.cos(alpha_angle)
        h1 = lattice1
        h2 = lattice2 * math.cos(gamma_angle)
        h3 = lattice2 * math.sin(gamma_angle)
        h4 = lattice3 * math.cos(beta_angle)
        h5 = ((h2 - h4)**2 + h3**2 + lattice3**2 - h4**2 - bc2) / (2 * h3)
        h6 = math.sqrt(lattice3**2 - h4**2 - h5**2)
        self.lattice = [[h1, 0., 0.], [h2, h3, 0.], [h4, h5, h6]]

        pattern = r'ID=\"(\d+)\"'
        for line in self.atominfo:
            if re.findall(pattern, line, re.S):
                self.atominMS.append(
                    int(re.findall(pattern, line, re.S)[0]))

        pattern = u'Components=\"(.*?)\"'
        self.elements = [re.findall(pattern, line, re.S)[0]
                         for line in self.atominfo]

        self.element_list = list(set(self.elements))
        self.element_list.sort(key=self.elements.index)
        self.element_amount = [self.elements.count(i)
                               for i in self.element_list]

        pattern = u'XYZ=\"(.*?)\"'
        self._atomic_position = []
        for line in self.atominfo:
            try:
                tmps_ = re.findall(pattern, line, re.S)[0]
            except IndexError:
                tmps_ = "0,0,0"
            finally:
                self._atomic_position.append(tmps_)

        self._cartesian_fixed = [
            ['F', 'F', 'F'] if "RestrictedProperties" in line
            else ['T', 'T', 'T']
            for line in self.atominfo
        ]
        self._atomic_position = [
            [float(j) for j in i.split(',')]
            for i in self._atomic_position
        ]

        if self.fixed_cartesian:
            pattern = (r'<AlongAxisSlider.*?RestrictedProperties.*?'
                       r'Objects=\"(\d+)\".*?\"LocalAxis(\d+)\".*?'
                       r'</AlongAxisSlider>')
            find_ret = re.findall(pattern, alllines, re.S)
            if find_ret:
                for i in find_ret:
                    try:
                        self._cartesian_fixed[
                            self.atominMS.index(int(i[0]))
                        ][int(i[1]) - 1] = 'F'
                    except:
                        pass

        newsorted = sorted(
            zip(self.elements, self._cartesian_fixed, self._atomic_position),
            key=lambda tmp: self.elements.index(list(tmp)[0])
        )
        _, self.cartesian_fixed, self.atomic_position = tuple(
            zip(*newsorted))

        self.title = "Converted by vasp.py"
        self.scaling_factor = 1.0
        if self.fixed_fraction or self.fixed_cartesian:
            self.Selective_infomation = True
        else:
            self.Selective_infomation = False

    def write(self, filename):
        if os.path.exists(filename):
            os.remove(filename)
        writen_lines = []
        writen_lines.append(self.title)
        writen_lines.append(str(self.scaling_factor))
        for i in range(3):
            writen_lines.append(
                "{0:>15.8f}{1:>15.8f}{2:>15.8f}".format(
                    self.lattice[i][0], self.lattice[i][1],
                    self.lattice[i][2]))
        writen_lines.append('  ' + '  '.join(self.element_list))
        writen_lines.append('  ' +
                            '  '.join([str(j) for j in self.element_amount]))
        if self.Selective_infomation:
            writen_lines.append("Selective")
        writen_lines.append("Direct")
        if self.Selective_infomation:
            for i in range(len(self.atomic_position)):
                suffix = " ".join(self.cartesian_fixed[i])
                tobewriten = "{0:>15.8f}{1:>15.8f}{2:>15.8f}   " + suffix
                writen_lines.append(tobewriten.format(
                    self.atomic_position[i][0], self.atomic_position[i][1],
                    self.atomic_position[i][2]))
        else:
            for i in range(len(self.atomic_position)):
                writen_lines.append("{0:>15.8f}{1:>15.8f}{2:>15.8f}".format(
                    self.atomic_position[i][0], self.atomic_position[i][1],
                    self.atomic_position[i][2]))
        writen_lines = [j + '\n' for j in writen_lines]
        with open(filename, 'w') as f:
            f.writelines(writen_lines)


def convert_xsd(xsd_path, output_path):
    """Convert a .xsd file to .vasp (VASP POSCAR) format."""
    converter = XSD2VASP()
    converter.read(xsd_path)
    converter.write(output_path)
    print("  -> %s" % output_path)


# =============================================================================
# Part 3: Element list (from cif2pos.py)
# =============================================================================

element = ['H', 'HE', 'LI', 'BE', 'B', 'C', 'N', 'O', 'F', 'NE',
           'NA', 'MG', 'AL', 'SI', 'P', 'S', 'CL', 'AR',
           'K', 'CA', 'SC', 'TI', 'V', 'CR', 'MN', 'FE',
           'CO', 'NI', 'CU', 'ZN', 'GA', 'GE', 'AS', 'SE', 'BR', 'KR',
           'RB', 'SR', 'Y', 'ZR', 'NB', 'MO', 'TC', 'RU',
           'RH', 'PD', 'AG', 'CD', 'IN', 'SN', 'SB', 'TE', 'I', 'XE',
           'CS', 'BA', 'LA', 'CE', 'PR', 'ND', 'PM',
           'SM', 'EU', 'GD', 'TB', 'DY', 'HO', 'ER', 'TM', 'YB', 'LU',
           'HF', 'TA', 'W', 'RE', 'OS', 'IR', 'PT', 'AU', 'HG',
           'TL', 'PB', 'BI', 'PO', 'AT', 'RN',
           'FR', 'RA', 'AC', 'TH', 'PA', 'U', 'NP',
           'PU', 'AM', 'CM', 'BK', 'CF', 'ES', 'FM', 'MD', 'NO', 'LR']

# =============================================================================
# Part 4: Symmetry operation dictionaries (from cif2pos.py / cif2cell)
# =============================================================================

HM2Hall = {
    'P1': 'P 1',
    'P-1': '-P 1',
    'P2': 'P 2y',
    'P2:b': 'P 2y',
    'P2b': 'P 2y',
    'P121': 'P 2y',
    'P2:c': 'P 2',
    'P2c': 'P 2',
    'P112': 'P 2',
    'P2:a': 'P 2x',
    'P2a': 'P 2x',
    'P211': 'P 2x',
    'P21': 'P 2yb',
    'P21:b': 'P 2yb',
    'P21b': 'P 2yb',
    'P1211': 'P 2yb',
    'P21:c': 'P 2c',
    'P21c': 'P 2c',
    'P1121': 'P 2c',
    'P21:a': 'P 2xa',
    'P21a': 'P 2xa',
    'P2111': 'P 2xa',
    'C2': 'C 2y',
    'C2:b1': 'C 2y',
    'C2b1': 'C 2y',
    'C121': 'C 2y',
    'C2:b2': 'A 2y',
    'C2b2': 'A 2y',
    'A121': 'A 2y',
    'A2': 'A 2y',
    'C2:b3': 'I 2y',
    'C2b3': 'I 2y',
    'I121': 'I 2y',
    'I2': 'I 2y',
    'C2:c1': 'A 2',
    'C2c1': 'A 2',
    'A112': 'A 2',
    'C2:c2': 'B 2',
    'C2c2': 'B 2',
    'B112': 'B 2',
    'B2': 'B 2',
    'C2:c3': 'I 2',
    'C2c3': 'I 2',
    'I112': 'I 2',
    'C2:a1': 'B 2x',
    'C2a1': 'B 2x',
    'B211': 'B 2x',
    'C2:a2': 'C 2x',
    'C2a2': 'C 2x',
    'C211': 'C 2x',
    'C2:a3': 'I 2x',
    'C2a3': 'I 2x',
    'I211': 'I 2x',
    'Pm': 'P -2y',
    'Pm:b': 'P -2y',
    'Pmb': 'P -2y',
    'P1m1': 'P -2y',
    'Pm:c': 'P -2',
    'Pmc': 'P -2',
    'P11m': 'P -2',
    'Pm:a': 'P -2x',
    'Pma': 'P -2x',
    'Pm11': 'P -2x',
    'Pc': 'P -2yc',
    'Pc:b1': 'P -2yc',
    'Pcb1': 'P -2yc',
    'P1c1': 'P -2yc',
    'Pc:b2': 'P -2yac',
    'Pcb2': 'P -2yac',
    'P1n1': 'P -2yac',
    'Pn': 'P -2yac',
    'Pc:b3': 'P -2ya',
    'Pcb3': 'P -2ya',
    'P1a1': 'P -2ya',
    'Pa': 'P -2ya',
    'Pc:c1': 'P -2a',
    'Pcc1': 'P -2a',
    'P11a': 'P -2a',
    'Pc:c2': 'P -2ab',
    'Pcc2': 'P -2ab',
    'P11n': 'P -2ab',
    'Pc:c3': 'P -2b',
    'Pcc3': 'P -2b',
    'P11b': 'P -2b',
    'Pb': 'P -2b',
    'Pc:a1': 'P -2xb',
    'Pca1': 'P -2xb',
    'Pb11': 'P -2xb',
    'Pc:a2': 'P -2xbc',
    'Pca2': 'P -2xbc',
    'Pn11': 'P -2xbc',
    'Pc:a3': 'P -2xc',
    'Pca3': 'P -2xc',
    'Pc11': 'P -2xc',
    'B1a1': 'B -2yc',
    'Cm': 'C -2y',
    'Cm:b1': 'C -2y',
    'Cmb1': 'C -2y',
    'C1m1': 'C -2y',
    'Cm:b2': 'A -2y',
    'Cmb2': 'A -2y',
    'A1m1': 'A -2y',
    'Cm:b3': 'I -2y',
    'Cmb3': 'I -2y',
    'I1m1': 'I -2y',
    'Im': 'I -2y',
    'Cm:c1': 'A -2',
    'Cmc1': 'A -2',
    'A11m': 'A -2',
    'Cm:c2': 'B -2',
    'Cmc2': 'B -2',
    'B11m': 'B -2',
    'Bm': 'B -2',
    'Cm:c3': 'I -2',
    'Cmc3': 'I -2',
    'I11m': 'I -2',
    'Cm:a1': 'B -2x',
    'Cma1': 'B -2x',
    'Bm11': 'B -2x',
    'Cm:a2': 'C -2x',
    'Cma2': 'C -2x',
    'Cm11': 'C -2x',
    'Cm:a3': 'I -2x',
    'Cma3': 'I -2x',
    'Im11': 'I -2x',
    'Cc': 'C -2yc',
    'Cc:b1': 'C -2yc',
    'Ccb1': 'C -2yc',
    'C1c1': 'C -2yc',
    'Cc:b2': 'A -2yac',
    'Ccb2': 'A -2yac',
    'A1n1': 'A -2yac',
    'Cc:b3': 'I -2ya',
    'Ccb3': 'I -2ya',
    'I1a1': 'I -2ya',
    'Ia': 'I -2ya',
    'Cc:-b1': 'A -2ya',
    'Cc-b1': 'A -2ya',
    'A1a1': 'A -2ya',
    'Aa': 'A -2ya',
    'Cc:-b2': 'C -2ybc',
    'Cc-b2': 'C -2ybc',
    'C1n1': 'C -2ybc',
    'Cc:-b3': 'I -2yc',
    'Cc-b3': 'I -2yc',
    'I1c1': 'I -2yc',
    'Cc:c1': 'A -2a',
    'Ccc1': 'A -2a',
    'A11a': 'A -2a',
    'Cc:c2': 'B -2bc',
    'B11n': 'B -2bc',
    'Cc:c3': 'I -2b',
    'Ccc3': 'I -2b',
    'I11b': 'I -2b',
    'Ib': 'I -2b',
    'C2/m': 'C -2y',
    'C2/m:b1': 'C -2y',
    'C2/m:b2': 'A -2y',
    'C2/m:b3': 'I -2y',
    'C2/c': 'C -2yc',
    'C2/c:b1': 'C -2yc',
    'C2/c:b2': 'A -2yac',
    'C2/c:b3': 'I -2ya',
    'P222': 'P 2 2',
    'P222:a': 'P 2 2',
    'P21212': 'P 2 2ab',
    'P21212:a': 'P 2 2ab',
    'P21212:b': 'P 2 2ab',
    'P21212:c': 'P 2 2ab',
    'P212121': 'P 2ac 2ab',
    'P212121:a': 'P 2ac 2ab',
    'P21221': 'P 2a 2a',
    'P22121': 'P 2b 2b',
    'P2212': 'P 2c 2c',
    'P2221': 'P 2 2c',
    'P2221:a': 'P 2 2c',
    'P2221:b': 'P 2 2c',
    'P2221:c': 'P 2 2c',
    'C2221': 'C 2 2c',
    'C2221:b1': 'C 2 2c',
    'C2221:b2': 'A 2 2b',
    'C2221:b3': 'A 2 2a',
    'C222': 'C 2 2',
    'C222:b1': 'C 2 2',
    'C222:b2': 'A 2 2',
    'C222:b3': 'I 2 2',
    'F222': 'F 2 2',
    'I222': 'I 2 2',
    'I212121': 'I 2b 2c',
    'Pmm2': 'P -2 2',
    'Pmm2:a': 'P -2 2',
    'Pmm2:b': 'P -2 2',
    'Pmm2:c': 'P -2 2',
    'Pma2': 'P -2 2a',
    'Pma2:a': 'P -2 2a',
    'Pma2:b': 'P -2 2a',
    'Pma2:c': 'P -2 2a',
    'Pcc2': 'P -2 2c',
    'Pcc2:a': 'P -2 2c',
    'Pcc2:b': 'P -2 2c',
    'Pcc2:c': 'P -2 2c',
    'Pba2': 'P -2 2ab',
    'Pba2:a': 'P -2 2ab',
    'Pba2:b': 'P -2 2ab',
    'Pba2:c': 'P -2 2ab',
    'Pnn2': 'P -2 2n',
    'Pna2:a': 'P -2 2a',
    'Pna2:b': 'P -2 2a',
    'Pna2:c': 'P -2 2a',
    'Pna21': 'P -2c 2ab',
    'Pna21:a': 'P -2c 2ab',
    'Pna21:b': 'P -2c 2ab',
    'Pna21:c': 'P -2c 2ab',
    'Cmm2': 'C -2 2',
    'Cmm2:b1': 'C -2 2',
    'Cmm2:b2': 'A -2 2',
    'Cmm2:b3': 'I -2 2',
    'Ccc2': 'C -2 2c',
    'Ccc2:b1': 'C -2 2c',
    'Ccc2:b2': 'A -2 2b',
    'Ccc2:b3': 'A -2 2a',
    'Amm2': 'A -2 2',
    'Amm2:b1': 'A -2 2',
    'Amm2:b2': 'B -2 2',
    'Amm2:b3': 'I -2 2',
    'Abm2': 'A -2 2ab',
    'Abm2:b1': 'A -2 2ab',
    'Abm2:b2': 'B -2 2a',
    'Abm2:b3': 'B -2 2b',
    'Ama2': 'A -2 2a',
    'Ama2:b1': 'A -2 2a',
    'Ama2:b2': 'B -2 2a',
    'Ama2:b3': 'B -2 2a',
    'Aba2': 'A -2 2ab',
    'Aba2:b1': 'A -2 2ab',
    'Aba2:b2': 'B -2 2ab',
    'Aba2:b3': 'B -2 2ab',
    'Fmm2': 'F -2 2',
    'Fdd2': 'F -2 2d',
    'Imm2': 'I -2 2',
    'Iba2': 'I -2 2ab',
    'Ima2': 'I -2 2a',
    'Pmmm': 'P 2 2',
    'Pnnn': 'P 2 2',
    'Pccm': 'P 2 2c',
    'Pban': 'P 2 2',
    'Pmma': 'P 2 2a',
    'Pnna': 'P 2 2a',
    'Pmna': 'P 2 2a',
    'Pcca': 'P 2 2a',
    'Pbam': 'P 2 2ab',
    'Pccn': 'P 2 2c',
    'Pbcm': 'P 2 2c',
    'Pnnm': 'P 2 2n',
    'Pmmn': 'P 2 2n',
    'Pbcn': 'P 2 2ab',
    'P112/m': 'P 2 2',
    'P12/m1': 'P 2 2',
    'P2/m11': 'P 2 2',
    'P2/m': 'P 2 2',
    'P2/c': 'P 2 2c',
    'P2/n': 'P 2 2n',
    'C2/m': 'C 2 2',
    'C2/c': 'C 2 2c',
    'P112/a': 'P 2 2a',
    'P112/b': 'P 2 2b',
    'P112/n': 'P 2 2n',
    'P12/c1': 'P 2 2c',
    'P12/n1': 'P 2 2n',
    'Pb11': 'P 2 2ab',
    'Pn11': 'P 2 2',
    'Pc11': 'P 2 2c',
    'Pa11': 'P 2 2a',
    'C2/c:b1': 'C -2yc',
    'C2/c:b2': 'A -2yac',
    'C2/c:b3': 'I -2ya',
    'P42/mcm': 'P 4 2 -2c',
    'P4/nbm': 'P 4 2 -2c',
    'P4/ncc': 'P 4 2 -2c',
    'P42/mbc': 'P 4 2 -2c',
    'P42/mnm': 'P 4 2 -2c',
    'P42/nmc': 'P 4 2 -2c',
    'P4/mbm': 'P 4 2 -2c',
    'P4/mnc': 'P 4 2 -2c',
    'P4/mcc': 'P 4 2 -2c',
    'P4/nmm': 'P 4 2 -2c',
    'P42/mmc': 'P 4 2 -2c',
    'P42/mbc:b': 'P 4 2 -2ab',
    'P42/mnm:b': 'P 4 2 -2ab',
    'P42/nmc:b': 'P 4 2 -2ab',
    'P42/mcm:b': 'P 4 2 -2ab',
    'P42/mbc:a': 'P 4 2 -2b',
    'P42/mnm:a': 'P 4 2 -2b',
    'P42/nmc:a': 'P 4 2 -2b',
    'P42/mcm:a': 'P 4 2 -2b',
    'P4/mbm:b': 'P 4 2 -2a',
    'P4/mnc:b': 'P 4 2 -2a',
    'P4/mcc:b': 'P 4 2 -2a',
    'P4/nmm:b': 'P 4 2 -2a',
    'P4/mbm:a': 'P 4 2 -2ab',
    'P4/mnc:a': 'P 4 2 -2ab',
    'P4/mcc:a': 'P 4 2 -2ab',
    'P4/nmm:a': 'P 4 2 -2ab',
    'I4/mmm': 'I 4 2 -2',
    'I4/mcm': 'I 4 2 -2c',
    'I41/amd': 'I 4b 2 -2b',
    'I41/acd': 'I 4b 2 -2c',
    'I4/m': 'I 4',
    'I41/a': 'I 4b',
    'I-4': 'I -4',
    'I-42m': 'I -4 2',
    'I-42d': 'I -4 2b',
    'I4mm': 'I 4',
    'I4cm': 'I 4',
    'I41md': 'I 4b',
    'I41cd': 'I 4b',
    'I422': 'I 4 2',
    'I4122': 'I 4b 2',
    'Fm-3m': 'F 4 2 3',
    'Fm-3c': 'F 4 2 3',
    'Fd-3m': 'F 4 2 3',
    'Fd-3c': 'F 4 2 3',
    'F23': 'F 2 3',
    'F432': 'F 4 2 3',
    'F4132': 'F 4 2 3',
    'F-43m': 'F 4 2 3',
    'F-43c': 'F 4 2 3',
    'Fm3m': 'F 4 2 3',
    'Pm3m': 'P 4 2 3',
    'Pn3n': 'P 4 2 3',
    'Pm3n': 'P 4 2 3',
    'Pn3m': 'P 4 2 3',
    'P43m': 'P 4 2 3',
    'P-43m': 'P 4 2 3',
    'P-43n': 'P 4 2 3',
    'P432': 'P 4 2 3',
    'P4232': 'P 4 2 3',
    'P4132': 'P 4 2 3',
    'P4332': 'P 4 2 3',
    'P213': 'P 2 3',
    'P23': 'P 2 3',
    'Pa-3': 'P 2 3',
    'Ia-3': 'I 2 3',
    'I23': 'I 2 3',
    'I213': 'I 2b 3',
    'I432': 'I 4 2 3',
    'I4132': 'I 4b 2 3',
    'I-43m': 'I 4 2 3',
    'I-43d': 'I 4 2b 3',
    'R3m': 'R 3',
    'R3c': 'R 3',
    'R-3': '-R 3',
    'R-3m': '-R 3',
    'R-3c': '-R 3',
    'R32': 'R 3',
    'P3m1': 'P 3',
    'P31m': 'P 3',
    'P3c1': 'P 3',
    'P31c': 'P 3',
    'P3': 'P 3',
    'P-3': '-P 3',
    'P312': 'P 3',
    'P321': 'P 3',
    'P6': 'P 6',
    'P-6': 'P -6',
    'P6/m': 'P 6',
    'P63': 'P 6c',
    'P61': 'P 6',
    'P65': 'P 6',
    'P62': 'P 6',
    'P64': 'P 6',
    'P-62m': 'P 6',
    'P-6c2': 'P 6',
    'P-6m2': 'P 6',
    'P6mm': 'P 6',
    'P6cc': 'P 6c',
    'P63cm': 'P 6c',
    'P63mc': 'P 6c',
    'P622': 'P 6',
    'P6122': 'P 6',
    'P6522': 'P 6',
    'P6222': 'P 6',
    'P6422': 'P 6',
    'P6322': 'P 6c',
    'P6/mmm': 'P 6',
    'P63/mcm': 'P 6c',
    'P63/mmc': 'P 6c',
    'P6_3mc': 'P 6c',
    'P6_3cm': 'P 6c',
    'P6_322': 'P 6c',
    'P4/mmm': 'P 4 2 -2',
    'P4/mcc': 'P 4 2 -2c',
    'P4/nbm': 'P 4 2 -2ab',
    'P4/nnc': 'P 4 2 -2ab',
    'P4/mbm': 'P 4 2 -2a',
    'P4/mnc': 'P 4 2 -2a',
    'P4/nmm': 'P 4 2 -2a',
    'P4/ncc': 'P 4 2 -2a',
    'P42/mmc': 'P 4 2 -2c',
    'P42/mcm': 'P 4 2 -2c',
    'P42/nbc': 'P 4 2 -2c',
    'P42/nnm': 'P 4 2 -2c',
    'P42/mbc': 'P 4 2 -2ab',
    'P42/mnm': 'P 4 2 -2ab',
    'P42/nmc': 'P 4 2 -2ab',
    'P42/ncm': 'P 4 2 -2ab',
    'P4mm': 'P 4',
    'P4bm': 'P 4',
    'P42cm': 'P 4c',
    'P42nm': 'P 4c',
    'P4cc': 'P 4',
    'P4nc': 'P 4',
    'P42mc': 'P 4c',
    'P42bc': 'P 4c',
    'P4/m': 'P 4',
    'P42/m': 'P 4c',
    'P4/n': 'P 4',
    'P42/n': 'P 4c',
    'P4': 'P 4',
    'P41': 'P 4',
    'P42': 'P 4c',
    'P43': 'P 4',
    'P-4': 'P -4',
    'P-42m': 'P -4 2',
    'P-4c2': 'P -4 2c',
    'P-4b2': 'P -4 2',
    'P-4n2': 'P -4 2c',
    'P422': 'P 4 2',
    'P4212': 'P 4 2',
    'P4122': 'P 4 2',
    'P41212': 'P 4 2',
    'P4222': 'P 4 2',
    'P42212': 'P 4 2',
    'P4322': 'P 4 2',
    'P43212': 'P 4 2',
    'Cmmm': 'C 2 2',
    'Cccm': 'C 2 2c',
    'Cmme': 'C 2 2',
    'Ccc': 'C 2 2c',
    'Cmma': 'C 2 2a',
    'Ccca': 'C 2 2a',
    'C222:b1': 'C 2 2',
    'C222:b2': 'A 2 2',
    'C222:b3': 'F 2 2',
    'Cmm2:b1': 'C -2 2',
    'Cmm2:b2': 'A -2 2',
    'Cmm2:b3': 'F -2 2',
    'Ccc2:b1': 'C -2 2c',
    'Ccc2:b2': 'A -2 2b',
    'Ccc2:b3': 'A -2 2a',
    'C2/c:b1': 'C -2yc',
    'C2/c:b2': 'A -2yac',
    'C2/c:b3': 'F -2y',
    'A2/m': 'A -2y',
    'A2/a': 'A -2yac',
}
# Note: HM2Hall returns Hall symbols, which are then looked up in SymOpsHall.

SymOpsHall = {
    'P 1': [['x', 'y', 'z']],
    '-P 1': [['x', 'y', 'z'], ['-x', '-y', '-z']],
    'P 2y': [['x', 'y', 'z'], ['-x', 'y', '-z']],
    'P 2': [['x', 'y', 'z'], ['-x', '-y', 'z']],
    'P 2x': [['x', 'y', 'z'], ['x', '-y', '-z']],
    'P 2yb': [['x', 'y', 'z'], ['-x', 'y+1/2', '-z']],
    'P 2c': [['x', 'y', 'z'], ['-x', '-y', 'z+1/2']],
    'P 2xa': [['x', 'y', 'z'], ['x+1/2', '-y', '-z']],
    'C 2y': [['x', 'y', 'z'], ['-x', 'y', '-z']],
    'A 2y': [['x', 'y', 'z'], ['-x', 'y', '-z']],
    'I 2y': [['x', 'y', 'z'], ['-x', 'y', '-z']],
    'A 2': [['x', 'y', 'z'], ['-x', '-y', 'z']],
    'B 2': [['x', 'y', 'z'], ['-x', '-y', 'z']],
    'I 2': [['x', 'y', 'z'], ['-x', '-y', 'z']],
    'B 2x': [['x', 'y', 'z'], ['x', '-y', '-z']],
    'C 2x': [['x', 'y', 'z'], ['x', '-y', '-z']],
    'I 2x': [['x', 'y', 'z'], ['x', '-y', '-z']],
    'P -2y': [['x', 'y', 'z'], ['-x', 'y', '-z']],
    'P -2': [['x', 'y', 'z'], ['-x', '-y', 'z']],
    'P -2x': [['x', 'y', 'z'], ['x', '-y', '-z']],
    'P -2yc': [['x', 'y', 'z'], ['-x', 'y', '-z+1/2']],
    'P -2yac': [['x', 'y', 'z'], ['-x+1/2', 'y', '-z+1/2']],
    'P -2ya': [['x', 'y', 'z'], ['-x+1/2', 'y', '-z']],
    'P -2a': [['x', 'y', 'z'], ['-x', '-y+1/2', 'z']],
    'P -2ab': [['x', 'y', 'z'], ['-x+1/2', '-y+1/2', 'z']],
    'P -2b': [['x', 'y', 'z'], ['-x', '-y+1/2', 'z']],
    'P -2xb': [['x', 'y', 'z'], ['x', '-y+1/2', '-z']],
    'P -2xbc': [['x', 'y', 'z'], ['x', '-y+1/2', '-z+1/2']],
    'P -2xc': [['x', 'y', 'z'], ['x', '-y', '-z+1/2']],
    'B -2yc': [['x', 'y', 'z'], ['-x', 'y', '-z+1/2']],
    'C -2y': [['x', 'y', 'z'], ['-x', 'y', '-z']],
    'A -2y': [['x', 'y', 'z'], ['-x', 'y', '-z']],
    'I -2y': [['x', 'y', 'z'], ['-x', 'y', '-z']],
    'A -2': [['x', 'y', 'z'], ['-x', '-y', 'z']],
    'B -2': [['x', 'y', 'z'], ['-x', '-y', 'z']],
    'I -2': [['x', 'y', 'z'], ['-x', '-y', 'z']],
    'B -2x': [['x', 'y', 'z'], ['x', '-y', '-z']],
    'C -2x': [['x', 'y', 'z'], ['x', '-y', '-z']],
    'I -2x': [['x', 'y', 'z'], ['x', '-y', '-z']],
    'C -2yc': [['x', 'y', 'z'], ['-x', 'y', '-z+1/2']],
    'A -2yac': [['x', 'y', 'z'], ['-x+1/2', 'y', '-z+1/2']],
    'I -2ya': [['x', 'y', 'z'], ['-x+1/2', 'y', '-z']],
    'A -2ya': [['x', 'y', 'z'], ['-x+1/2', 'y', '-z']],
    'C -2ybc': [['x', 'y', 'z'], ['-x', 'y+1/2', '-z+1/2']],
    'I -2yc': [['x', 'y', 'z'], ['-x', 'y', '-z+1/2']],
    'A -2a': [['x', 'y', 'z'], ['-x', '-y+1/2', 'z']],
    'B -2bc': [['x', 'y', 'z'], ['-x+1/2', '-y+1/2', 'z']],
    'I -2b': [['x', 'y', 'z'], ['-x', '-y+1/2', 'z']],
    'P 2 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z']
    ],
    'P 2 2ab': [
        ['x', 'y', 'z'], ['-x+1/2', '-y+1/2', 'z'],
        ['-x+1/2', 'y', '-z'], ['x', '-y+1/2', '-z']
    ],
    'P 2ac 2ab': [
        ['x', 'y', 'z'], ['-x+1/2', '-y', 'z+1/2'],
        ['-x', 'y+1/2', '-z+1/2'], ['x+1/2', '-y+1/2', '-z']
    ],
    'P 2a 2a': [
        ['x', 'y', 'z'], ['-x+1/2', '-y', 'z'],
        ['-x', 'y', '-z'], ['x+1/2', '-y', '-z']
    ],
    'P 2b 2b': [
        ['x', 'y', 'z'], ['-x', '-y+1/2', 'z'],
        ['-x', 'y', '-z'], ['x', '-y+1/2', '-z']
    ],
    'P 2c 2c': [
        ['x', 'y', 'z'], ['-x', '-y', 'z+1/2'],
        ['-x', 'y', '-z'], ['x', '-y', '-z+1/2']
    ],
    'P 2 2c': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z+1/2'], ['x', '-y', '-z+1/2']
    ],
    'C 2 2c': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z+1/2'], ['x', '-y', '-z+1/2']
    ],
    'A 2 2b': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z+1/2'], ['x', '-y', '-z+1/2']
    ],
    'A 2 2a': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z+1/2'], ['x', '-y', '-z+1/2']
    ],
    'C 2 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z']
    ],
    'A 2 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z']
    ],
    'I 2 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z']
    ],
    'F 2 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z']
    ],
    'I 2b 2c': [
        ['x', 'y', 'z'], ['-x', '-y+1/2', 'z+1/2'],
        ['-x+1/2', 'y', '-z+1/2'], ['x+1/2', '-y+1/2', '-z']
    ],
    'P -2 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z']
    ],
    'P -2 2a': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x+1/2', 'y', '-z'], ['x+1/2', '-y', '-z']
    ],
    'P -2 2c': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z+1/2'], ['x', '-y', '-z+1/2']
    ],
    'P -2 2ab': [
        ['x', 'y', 'z'], ['-x+1/2', '-y+1/2', 'z'],
        ['-x+1/2', 'y', '-z'], ['x', '-y+1/2', '-z']
    ],
    'P -2 2n': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x+1/2', 'y+1/2', '-z'], ['x+1/2', '-y+1/2', '-z']
    ],
    'P -2c 2ab': [
        ['x', 'y', 'z'], ['-x+1/2', '-y+1/2', 'z+1/2'],
        ['-x+1/2', 'y+1/2', '-z'], ['x', '-y', '-z+1/2']
    ],
    'C -2 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z']
    ],
    'A -2 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z']
    ],
    'I -2 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z']
    ],
    'C -2 2c': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z+1/2'], ['x', '-y', '-z+1/2']
    ],
    'A -2 2b': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z+1/2'], ['x', '-y', '-z+1/2']
    ],
    'A -2 2a': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z+1/2'], ['x', '-y', '-z+1/2']
    ],
    'A -2 2ab': [
        ['x', 'y', 'z'], ['-x+1/2', '-y+1/2', 'z'],
        ['-x+1/2', 'y', '-z'], ['x', '-y+1/2', '-z']
    ],
    'B -2 2a': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x+1/2', 'y', '-z'], ['x+1/2', '-y', '-z']
    ],
    'B -2 2b': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z+1/2'], ['x', '-y', '-z+1/2']
    ],
    'B -2 2ab': [
        ['x', 'y', 'z'], ['-x+1/2', '-y+1/2', 'z'],
        ['-x+1/2', 'y', '-z'], ['x', '-y+1/2', '-z']
    ],
    'F -2 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z']
    ],
    'F -2 2d': [
        ['x', 'y', 'z'], ['-x+1/4', '-y+1/4', 'z'],
        ['-x+1/4', 'y+1/4', '-z'], ['x', '-y', '-z+1/2']
    ],
    'I -2 2ab': [
        ['x', 'y', 'z'], ['-x+1/2', '-y+1/2', 'z'],
        ['-x+1/2', 'y', '-z'], ['x', '-y+1/2', '-z']
    ],
    'I -2 2a': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x+1/2', 'y', '-z'], ['x+1/2', '-y', '-z']
    ],
    'P 4': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-y', 'x', 'z'], ['y', '-x', 'z']
    ],
    'P 4c': [
        ['x', 'y', 'z'], ['-x', '-y', 'z+1/2'],
        ['-y', 'x', 'z+1/4'], ['y', '-x', 'z+3/4']
    ],
    'P -4': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-y', 'x', '-z'], ['y', '-x', '-z']
    ],
    'P -4 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-y', 'x', '-z'], ['y', '-x', '-z']
    ],
    'P -4 2c': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-y', 'x', '-z+1/2'], ['y', '-x', '-z+1/2']
    ],
    'P 4 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-y', 'x', 'z'], ['y', '-x', 'z']
    ],
    'P 4 2 -2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z'],
        ['-y', 'x', 'z'], ['y', '-x', 'z'],
        ['y', 'x', '-z'], ['-y', '-x', '-z']
    ],
    'P 4 2 -2c': [
        ['x', 'y', 'z'], ['-x', '-y', 'z+1/2'],
        ['-x', 'y', '-z+1/2'], ['x', '-y', '-z'],
        ['-y', 'x', 'z+1/4'], ['y', '-x', 'z+3/4'],
        ['y', 'x', '-z+1/4'], ['-y', '-x', '-z+3/4']
    ],
    'P 4 2 -2ab': [
        ['x', 'y', 'z'], ['-x+1/2', '-y+1/2', 'z'],
        ['-x+1/2', 'y+1/2', '-z'], ['x', '-y', '-z'],
        ['-y+1/2', 'x+1/2', 'z'], ['y+1/2', '-x+1/2', 'z'],
        ['y+1/2', 'x+1/2', '-z'], ['-y+1/2', '-x+1/2', '-z']
    ],
    'P 4 2 -2b': [
        ['x', 'y', 'z'], ['-x', '-y', 'z+1/2'],
        ['-x', 'y', '-z'], ['x', '-y', '-z+1/2'],
        ['-y', 'x', 'z+1/4'], ['y', '-x', 'z+3/4'],
        ['y', 'x', '-z+1/4'], ['-y', '-x', '-z+3/4']
    ],
    'P 4 2 -2a': [
        ['x', 'y', 'z'], ['-x+1/2', '-y+1/2', 'z'],
        ['-x+1/2', 'y+1/2', '-z'], ['x', '-y', '-z'],
        ['-y', 'x', 'z'], ['y', '-x', 'z'],
        ['y', 'x', '-z'], ['-y', '-x', '-z']
    ],
    'I 4': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-y', 'x', 'z'], ['y', '-x', 'z']
    ],
    'I 4b': [
        ['x', 'y', 'z'], ['-x', '-y', 'z+1/2'],
        ['-y+1/2', 'x+1/2', 'z+1/4'], ['y+1/2', '-x+1/2', 'z+3/4']
    ],
    'I -4': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-y', 'x', '-z'], ['y', '-x', '-z']
    ],
    'I -4 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z'],
        ['-y', 'x', 'z'], ['y', '-x', 'z'],
        ['y', 'x', '-z'], ['-y', '-x', '-z']
    ],
    'I -4 2b': [
        ['x', 'y', 'z'], ['-x', '-y', 'z+1/2'],
        ['-x+1/2', 'y+1/2', '-z+1/4'], ['x+1/2', '-y+1/2', '-z+3/4'],
        ['-y', 'x', 'z'], ['y', '-x', 'z'],
        ['y', 'x', '-z'], ['-y', '-x', '-z']
    ],
    'I 4 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z'],
        ['-y', 'x', 'z'], ['y', '-x', 'z'],
        ['y', 'x', '-z'], ['-y', '-x', '-z']
    ],
    'I 4b 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z+1/2'],
        ['-x+1/2', 'y+1/2', '-z+1/4'], ['x+1/2', '-y+1/2', '-z+3/4'],
        ['-y+1/2', 'x+1/2', 'z+1/4'], ['y+1/2', '-x+1/2', 'z+3/4'],
        ['y+1/2', 'x+1/2', '-z+1/4'], ['-y+1/2', '-x+1/2', '-z+3/4']
    ],
    'I 4b 2 -2b': [
        ['x', 'y', 'z'], ['-x', '-y', 'z+1/2'],
        ['-x+1/2', 'y+1/2', '-z+1/4'], ['x+1/2', '-y+1/2', '-z+3/4'],
        ['-y+1/2', 'x+1/2', 'z+1/4'], ['y+1/2', '-x+1/2', 'z+3/4'],
        ['y+1/2', 'x+1/2', '-z+1/4'], ['-y+1/2', '-x+1/2', '-z+3/4']
    ],
    'P 3': [
        ['x', 'y', 'z'], ['-y', 'x-y', 'z'], ['-x+y', '-x', 'z']
    ],
    'P -3': [
        ['x', 'y', 'z'], ['-y', 'x-y', 'z'], ['-x+y', '-x', 'z'],
        ['-x', '-y', '-z'], ['y', '-x+y', '-z'], ['x-y', 'x', '-z']
    ],
    'R 3': [
        ['x', 'y', 'z'], ['-y', 'x-y', 'z'], ['-x+y', '-x', 'z'],
        ['z', 'x', 'y'], ['-y+z', '-x+y+z', 'y'],
        ['-x+z', '-x+y', 'x']
    ],
    '-R 3': [
        ['x', 'y', 'z'], ['-y', 'x-y', 'z'], ['-x+y', '-x', 'z'],
        ['-x', '-y', '-z'], ['y', '-x+y', '-z'], ['x-y', 'x', '-z'],
        ['z', 'x', 'y'], ['-y+z', '-x+y+z', 'y'],
        ['-x+z', '-x+y', 'x'],
        ['-z', '-x', '-y'], ['y-z', 'x-y-z', '-y'],
        ['x-z', 'x-y', '-x']
    ],
    'P 6': [
        ['x', 'y', 'z'], ['x-y', 'x', 'z'],
        ['-y', 'x-y', 'z'], ['-x', '-y', 'z'],
        ['-x+y', '-x', 'z'], ['y', '-x+y', 'z']
    ],
    'P 6c': [
        ['x', 'y', 'z'], ['x-y', 'x', 'z+1/2'],
        ['-y', 'x-y', 'z'], ['-x', '-y', 'z+1/2'],
        ['-x+y', '-x', 'z'], ['y', '-x+y', 'z+1/2']
    ],
    'P -6': [
        ['x', 'y', 'z'], ['x-y', 'x', '-z'],
        ['-y', 'x-y', 'z'], ['-x', '-y', '-z'],
        ['-x+y', '-x', 'z'], ['y', '-x+y', '-z']
    ],
    'P 2 3': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z'],
        ['z', 'x', 'y'], ['-z', '-x', 'y'],
        ['-z', 'x', '-y'], ['z', '-x', '-y'],
        ['y', 'z', 'x'], ['-y', '-z', 'x'],
        ['-y', 'z', '-x'], ['y', '-z', '-x']
    ],
    'I 2b 3': [
        ['x', 'y', 'z'], ['-x', '-y+1/2', 'z+1/2'],
        ['-x+1/2', 'y', '-z+1/2'], ['x+1/2', '-y+1/2', '-z'],
        ['z', 'x', 'y'], ['-z', '-x+1/2', 'y+1/2'],
        ['-z+1/2', 'x', '-y+1/2'], ['z+1/2', '-x+1/2', '-y'],
        ['y', 'z', 'x'], ['-y', '-z+1/2', 'x+1/2'],
        ['-y+1/2', 'z', '-x+1/2'], ['y+1/2', '-z+1/2', '-x']
    ],
    'F 2 3': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z'],
        ['z', 'x', 'y'], ['-z', '-x', 'y'],
        ['-z', 'x', '-y'], ['z', '-x', '-y'],
        ['y', 'z', 'x'], ['-y', '-z', 'x'],
        ['-y', 'z', '-x'], ['y', '-z', '-x']
    ],
    'P 4 2 3': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z'],
        ['-y', 'x', 'z'], ['y', '-x', 'z'],
        ['y', 'x', '-z'], ['-y', '-x', '-z'],
        ['z', 'x', 'y'], ['-z', '-x', 'y'],
        ['-z', 'x', '-y'], ['z', '-x', '-y'],
        ['y', 'z', 'x'], ['-y', '-z', 'x'],
        ['-y', 'z', '-x'], ['y', '-z', '-x'],
        ['x', 'z', 'y'], ['-x', '-z', 'y'],
        ['-x', 'z', '-y'], ['x', '-z', '-y'],
        ['z', 'y', 'x'], ['-z', '-y', 'x'],
        ['-z', 'y', '-x'], ['z', '-y', '-x']
    ],
    'F 4 2 3': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z'],
        ['-y', 'x', 'z'], ['y', '-x', 'z'],
        ['y', 'x', '-z'], ['-y', '-x', '-z'],
        ['z', 'x', 'y'], ['-z', '-x', 'y'],
        ['-z', 'x', '-y'], ['z', '-x', '-y'],
        ['y', 'z', 'x'], ['-y', '-z', 'x'],
        ['-y', 'z', '-x'], ['y', '-z', '-x'],
        ['x', 'z', 'y'], ['-x', '-z', 'y'],
        ['-x', 'z', '-y'], ['x', '-z', '-y'],
        ['z', 'y', 'x'], ['-z', '-y', 'x'],
        ['-z', 'y', '-x'], ['z', '-y', '-x']
    ],
    'I 4 2 3': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z'],
        ['-y', 'x', 'z'], ['y', '-x', 'z'],
        ['y', 'x', '-z'], ['-y', '-x', '-z'],
        ['z', 'x', 'y'], ['-z', '-x', 'y'],
        ['-z', 'x', '-y'], ['z', '-x', '-y'],
        ['y', 'z', 'x'], ['-y', '-z', 'x'],
        ['-y', 'z', '-x'], ['y', '-z', '-x'],
        ['x', 'z', 'y'], ['-x', '-z', 'y'],
        ['-x', 'z', '-y'], ['x', '-z', '-y'],
        ['z', 'y', 'x'], ['-z', '-y', 'x'],
        ['-z', 'y', '-x'], ['z', '-y', '-x']
    ],
    'I 4b 2 3': [
        ['x', 'y', 'z'], ['-x', '-y', 'z+1/2'],
        ['-x+1/2', 'y+1/2', '-z+1/4'], ['x+1/2', '-y+1/2', '-z+3/4'],
        ['-y+1/2', 'x+1/2', 'z+1/4'], ['y+1/2', '-x+1/2', 'z+3/4'],
        ['y+1/2', 'x+1/2', '-z+1/4'], ['-y+1/2', '-x+1/2', '-z+3/4'],
        ['z', 'x', 'y'], ['-z', '-x', 'y+1/2'],
        ['-z+1/2', 'x+1/2', '-y+1/4'], ['z+1/2', '-x+1/2', '-y+3/4'],
        ['-x+1/2', 'z+1/2', 'y+1/4'], ['x+1/2', '-z+1/2', 'y+3/4'],
        ['x+1/2', 'z+1/2', '-y+1/4'], ['-x+1/2', '-z+1/2', '-y+3/4'],
        ['y', 'z', 'x'], ['-y', '-z', 'x+1/2'],
        ['-y+1/2', 'z+1/2', '-x+1/4'], ['y+1/2', '-z+1/2', '-x+3/4'],
        ['-z+1/2', 'y+1/2', 'x+1/4'], ['z+1/2', '-y+1/2', 'x+3/4'],
        ['z+1/2', 'y+1/2', '-x+1/4'], ['-z+1/2', '-y+1/2', '-x+3/4']
    ],
    'P 6 2 -2': [
        ['x', 'y', 'z'], ['-y', 'x-y', 'z'], ['-x+y', '-x', 'z'],
        ['y', 'x', '-z'], ['x-y', '-y', '-z'], ['-x', '-x+y', '-z'],
        ['-x', '-y', 'z'], ['y', '-x+y', 'z'], ['x-y', 'x', 'z'],
        ['-y', '-x', '-z'], ['-x+y', 'y', '-z'], ['x', 'x-y', '-z']
    ],
    'P 6 2': [
        ['x', 'y', 'z'], ['-y', 'x-y', 'z'], ['-x+y', '-x', 'z'],
        ['y', 'x', '-z'], ['x-y', '-y', '-z'], ['-x', '-x+y', '-z'],
        ['-x', '-y', 'z'], ['y', '-x+y', 'z'], ['x-y', 'x', 'z'],
        ['-y', '-x', '-z'], ['-x+y', 'y', '-z'], ['x', 'x-y', '-z']
    ],
    'P 3 2 -2': [
        ['x', 'y', 'z'], ['-y', 'x-y', 'z'], ['-x+y', '-x', 'z'],
        ['y', 'x', '-z'], ['x-y', '-y', '-z'], ['-x', '-x+y', '-z']
    ],
    'P 3 2': [
        ['x', 'y', 'z'], ['-y', 'x-y', 'z'], ['-x+y', '-x', 'z'],
        ['y', 'x', '-z'], ['x-y', '-y', '-z'], ['-x', '-x+y', '-z']
    ],
}
# Remaining SymOpsHall entries (additional settings for completeness)
# These cover additional space group settings found in CIF files.
_SymOpsHall_extra = {
    'C 2y 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z'],
        ['x+1/2', 'y+1/2', 'z'], ['-x+1/2', '-y+1/2', 'z'],
        ['-x+1/2', 'y+1/2', '-z'], ['x+1/2', '-y+1/2', '-z']
    ],
    'A 2y 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z'],
        ['x', 'y+1/2', 'z+1/2'], ['-x', '-y+1/2', 'z+1/2'],
        ['-x', 'y+1/2', '-z+1/2'], ['x', '-y+1/2', '-z+1/2']
    ],
    'F 2y 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z'],
        ['x+1/2', 'y+1/2', 'z'], ['-x+1/2', '-y+1/2', 'z'],
        ['-x+1/2', 'y+1/2', '-z'], ['x+1/2', '-y+1/2', '-z'],
        ['x', 'y+1/2', 'z+1/2'], ['-x', '-y+1/2', 'z+1/2'],
        ['-x', 'y+1/2', '-z+1/2'], ['x', '-y+1/2', '-z+1/2'],
        ['x+1/2', 'y', 'z+1/2'], ['-x+1/2', '-y', 'z+1/2'],
        ['-x+1/2', 'y', '-z+1/2'], ['x+1/2', '-y', '-z+1/2']
    ],
    'C -2y 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z'],
        ['x+1/2', 'y+1/2', 'z'], ['-x+1/2', '-y+1/2', 'z'],
        ['-x+1/2', 'y+1/2', '-z'], ['x+1/2', '-y+1/2', '-z']
    ],
    'A -2y 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z'],
        ['x', 'y+1/2', 'z+1/2'], ['-x', '-y+1/2', 'z+1/2'],
        ['-x', 'y+1/2', '-z+1/2'], ['x', '-y+1/2', '-z+1/2']
    ],
    'F -2y 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z'],
        ['x+1/2', 'y+1/2', 'z'], ['-x+1/2', '-y+1/2', 'z'],
        ['-x+1/2', 'y+1/2', '-z'], ['x+1/2', '-y+1/2', '-z'],
        ['x', 'y+1/2', 'z+1/2'], ['-x', '-y+1/2', 'z+1/2'],
        ['-x', 'y+1/2', '-z+1/2'], ['x', '-y+1/2', '-z+1/2'],
        ['x+1/2', 'y', 'z+1/2'], ['-x+1/2', '-y', 'z+1/2'],
        ['-x+1/2', 'y', '-z+1/2'], ['x+1/2', '-y', '-z+1/2']
    ],
    'I -2y 2': [
        ['x', 'y', 'z'], ['-x', '-y', 'z'],
        ['-x', 'y', '-z'], ['x', '-y', '-z'],
        ['x+1/2', 'y+1/2', 'z+1/2'], ['-x+1/2', '-y+1/2', 'z+1/2'],
        ['-x+1/2', 'y+1/2', '-z+1/2'], ['x+1/2', '-y+1/2', '-z+1/2']
    ],
}

# Merge extra entries into SymOpsHall
for _k, _v in _SymOpsHall_extra.items():
    SymOpsHall[_k] = _v


# =============================================================================
# Part 5: Main entry point
# =============================================================================

def main():
    cif_files = glob("*.cif")
    xsd_files = glob("*.xsd")

    if not cif_files and not xsd_files:
        print("No .cif or .xsd files found in the current directory.")
        return

    # Convert .cif files
    if cif_files:
        out_dir = "cif"
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        print("\nConverting CIF files:")
        for f in sorted(cif_files):
            base = os.path.splitext(f)[0]
            out_path = os.path.join(out_dir, base + ".vasp")
            try:
                convert_cif(f, out_path)
            except Exception as e:
                print("  ERROR converting %s: %s" % (f, e))

    # Convert .xsd files
    if xsd_files:
        out_dir = "xsd"
        if not os.path.exists(out_dir):
            os.makedirs(out_dir)
        print("\nConverting XSD files:")
        for f in sorted(xsd_files):
            base = os.path.splitext(f)[0]
            out_path = os.path.join(out_dir, base + ".vasp")
            try:
                convert_xsd(f, out_path)
            except Exception as e:
                print("  ERROR converting %s: %s" % (f, e))

    print("\nDone.")


if __name__ == "__main__":
    main()
