# The MIT License (MIT)
#
# Copyright (c) 2014 Muratahan Aykol
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE

import numpy as np
from copy import deepcopy


# This function reads an XYZ file and a list of lattice vectors L = [x,y,z] and gives MSD + unwrapped coordinates
def MSD(xyz_file, L):
    a = [];
    l = [];
    a.append(L[0]);
    a.append(L[1]);
    a.append(L[2]);  # basis vectors in cartesian coords
    l.append(np.sqrt(np.dot(a[0], a[0])));
    l.append(np.sqrt(np.dot(a[1], a[1])));
    l.append(np.sqrt(np.dot(a[2], a[2])));  # basis vector lengths

    # 【修改1】输出文件名从msd.out改为MSD.txt
    file = open(xyz_file, 'r')
    recorder = open("MSD.txt", 'w')  # 核心修改：文件名调整
    rmsd_recorder = open("RMSD.txt", 'w')  # 新增RMSD相关：打开RMSD输出文件
    coord_rec = open("unwrapped.xyz", 'w')

    origin_list = []  # Stores the origin as [element,[coords]]
    prev_list = []  # Stores the wrapped previous step
    unwrapped_list = []  # Stores the instantenous unwrapped

    msd = []  # Stores atom-wise MSD  Stores msd as [msd]
    msd_dict = {}  # Stores element-wise MSD
    msd_lattice = []
    msd_dict_lattice = {}

    # 新增RMSD相关：定义RMSD存储字典
    rmsd_dict = {}
    rmsd_dict_lattice = {}

    element_list = []  # element list
    element_dict = {}  # number of elements stored

    content = file.readline()
    N = int(content)

    for i in range(N):
        msd.append(np.float64('0.0'))
        msd_lattice.append([0.0, 0.0, 0.0])

    file.readline()
    step = 0

    while True:
        step += 1
        # Get and store the origin coordinates in origin_dict at first step
        if step == 1:
            for i in range(N):
                t = file.readline().rstrip('\n').split()
                element = t[0]
                if element not in element_list:
                    element_list.append(element)
                if element not in element_dict:
                    element_dict[element] = 1.0
                else:
                    element_dict[element] += 1.0
                coords = np.array([float(s) for s in t[1:]])
                origin_list.append([element, coords])
            # Copy the first set of coordinates as prev_dict and unwrapped
            unwrapped_list = deepcopy(origin_list)
            prev_list = deepcopy(origin_list)

            # 【修改2】重构列头：为每个元素添加4列标注（总MSD、x/y/z方向MSD）
            recorder.write("step ")  # 第一列是步数
            for element in element_list:
                # 列头格式：元素_total（总MSD）、元素_x（x方向MSD）、元素_y（y方向MSD）、元素_z（z方向MSD）
                recorder.write(f"{element}_total {element}_x {element}_y {element}_z ")
            recorder.write("\n")

            # 新增RMSD相关：写入RMSD.txt的列头（和MSD对应，后缀加_rmsd）
            rmsd_recorder.write("step ")
            for element in element_list:
                rmsd_recorder.write(f"{element}_total_rmsd {element}_x_rmsd {element}_y_rmsd {element}_z_rmsd ")
            rmsd_recorder.write("\n")

        # Read wrapped coordinates into wrapped_dict
        content = file.readline()
        if len(content) == 0:
            print("\n---End of file---\n")
            break
        N = int(content)
        file.readline()
        wrapped_list = []  # Erease the previous set of coordinates
        for i in range(N):
            t = file.readline().rstrip('\n').split()
            element = t[0]
            coords = np.array([float(s) for s in t[1:]])
            wrapped_list.append([element, coords])

        coord_rec.write(str(N) + "\ncomment\n")

        # Unwrap coodinates and get MSD
        for atom in range(N):
            msd[atom] = 0.0
            coord_rec.write(wrapped_list[atom][0])

            # decompose wrapped atom coordinates to onto lattice vectors:
            w1 = wrapped_list[atom][1][0]
            w2 = wrapped_list[atom][1][1]
            w3 = wrapped_list[atom][1][2]

            # decompose prev atom coordinates to onto lattice vectors:
            p1 = prev_list[atom][1][0]
            p2 = prev_list[atom][1][1]
            p3 = prev_list[atom][1][2]

            # get distance between periodic images and use the smallest one
            if np.fabs(w1 - p1) > 0.5:
                u1 = w1 - p1 - np.sign(w1 - p1)
            else:
                u1 = w1 - p1

            if np.fabs(w2 - p2) > 0.5:
                u2 = w2 - p2 - np.sign(w2 - p2)
            else:
                u2 = w2 - p2

            if np.fabs(w3 - p3) > 0.5:
                u3 = w3 - p3 - np.sign(w3 - p3)
            else:
                u3 = w3 - p3

            # add unwrapped displacements to unwrapped coords
            unwrapped_list[atom][1][0] += u1
            unwrapped_list[atom][1][1] += u2
            unwrapped_list[atom][1][2] += u3

            uw = unwrapped_list[atom][1][0] * a[0] + unwrapped_list[atom][1][1] * a[1] + unwrapped_list[atom][1][2] * a[
                2]
            ol = origin_list[atom][1][0] * a[0] + origin_list[atom][1][1] * a[1] + origin_list[atom][1][2] * a[2]

            msd[atom] = np.linalg.norm(uw - ol) ** 2
            msd_lattice[atom] = [np.linalg.norm(uw[0] - ol[0]) ** 2, np.linalg.norm(uw[1] - ol[1]) ** 2,
                                 np.linalg.norm(uw[2] - ol[2]) ** 2]

            coord_rec.write(" " + np.array_str(uw).replace("[", "").replace("]", ""))
            coord_rec.write("\n")

        prev_list = []  # Store current wrapped coordinates for the next step
        prev_list = deepcopy(wrapped_list)
        # record msd
        recorder.write(str(step) + " ")

        # 初始化元素的MSD字典
        for el in element_list:
            msd_dict[el] = 0.0
            msd_dict_lattice[el] = [0., 0., 0.]
            # 新增RMSD相关：初始化RMSD字典
            rmsd_dict[el] = 0.0
            rmsd_dict_lattice[el] = [0., 0., 0.]

        # 按元素统计MSD（平均到每个原子）
        for atom in range(len(msd)):
            el = wrapped_list[atom][0]
            msd_dict[el] += msd[atom] / element_dict[el]
            for i in range(3):
                msd_dict_lattice[el][i] += msd_lattice[atom][i] / element_dict[el]

        # 新增RMSD相关：计算RMSD（MSD开平方）
        for el in element_list:
            rmsd_dict[el] = np.sqrt(msd_dict[el])  # 总RMSD
            for i in range(3):
                # 分方向RMSD（注意：若MSD为0，开平方后仍为0，无数学问题）
                rmsd_dict_lattice[el][i] = np.sqrt(msd_dict_lattice[el][i])

        # 写入当前步的MSD数据（和列头一一对应）
        for el in element_list:
            recorder.write(
                f"{msd_dict[el]} {msd_dict_lattice[el][0]} {msd_dict_lattice[el][1]} {msd_dict_lattice[el][2]} ")
        recorder.write("\n")

        # 新增RMSD相关：写入当前步的RMSD数据到RMSD.txt
        rmsd_recorder.write(str(step) + " ")
        for el in element_list:
            rmsd_recorder.write(
                f"{rmsd_dict[el]} {rmsd_dict_lattice[el][0]} {rmsd_dict_lattice[el][1]} {rmsd_dict_lattice[el][2]} ")
        rmsd_recorder.write("\n")

        if step % 10 == 0:
            print(step)

    # 新增RMSD相关：关闭RMSD文件句柄
    rmsd_recorder.close()
    recorder.close()
    file.close()
    coord_rec.close()


def read_lat_vec():
    lat_file = open('lattice.vectors', 'r')
    line = []
    for i in range(3):
        line.append([float(x) for x in lat_file.readline().rstrip('\n').split()])
        print(line[i])
    lattice = np.array([line[0], line[1], line[2]])
    return lattice


# 读取晶格向量（从lattice.vectors文件）
lattice = read_lat_vec()

# 手动定义晶格向量的示例（注释掉，如需手动改则取消注释）
# lattice =np.array([[-12.181156,-4.306689,7.459404],[0.000000,-12.920067,7.459404],[0.000000,0.000000,14.918808]])

# 运行MSD计算：输入分数坐标XYZ文件 + 晶格向量
MSD("XDATCAR_fract.xyz", lattice)