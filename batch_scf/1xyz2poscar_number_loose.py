"""
=============================================================================
脚本:        1xyz2poscar_number_loose.py（宽松临时版）
分类:        格式转换脚本
功能:        读取XYZ轨迹文件，将轨迹每一帧拆分为独立POSCAR文件；
             每帧放入以帧号命名的数字文件夹（1/、2/、…、n/）中；
             支持两种运行模式：
             - 默认模式(-def)：全新分发，从 1/ 开始创建数字文件夹；
             - 续算模式(-con)：在已有数字文件夹基础上继续分发，
               新轨迹帧从当前最大文件夹号+1开始（补充数据单点能计算）；
             与正式版差异：续算模式找不到元素顺序记录文件(.elements_order.txt)时
             不终止，改为从最大文件夹的已有POSCAR自动推断元素顺序（临时应急用，
             处理旧版脚本生成的数据目录，用后即弃）
             所有帧按全局统一的元素顺序排列（第6行元素顺序一致，第7行计数与第6行一一对应）；
             输出POSCAR使用direct直接坐标。
使用方法:    python 1xyz2poscar_number.py [-def | -con] [xyz文件名]
参数:        -def, --default   默认模式，从 1/ 开始全新分发（未指定时默认）
             -con, --continue  续算模式，从最大数字文件夹号+1开始继续分发
             -h,   --help      显示帮助信息
             以上选项参数位置任意，可与xyz文件名混排
             xyz文件名   要转换的XYZ轨迹文件（可选）；
             不传参数时，自动扫描脚本所在目录下的*.xyz文件（仅限单个文件）
输出:
  1/, 2/, … n/    以帧号命名的数字文件夹，生成在脚本所在目录
  */POSCAR        VASP输入文件，原子已按元素排序，direct坐标
  .elements_order.txt  元素顺序记录文件（默认模式自动生成，续算模式读取）
作者:        Hongbo Sun
最后修改日期: 2026-08-23
=============================================================================
# 目录树示例(默认模式):
# ============================================================================
# .
# ├── 1_FPS.xyz
# ├── 1xyz2poscar_number.py
# ├── 1/                # 第1帧
# │   └── POSCAR
# ├── 2/                # 第2帧
# │   └── POSCAR
# └── ...
# └── n/                # 第n帧
#     └── POSCAR
# ============================================================================
# 目录树示例(续算模式):
# 已有 1/ ~ 3/，补充数据从 4/ 开始分发：
# python 1xyz2poscar_number.py -con new_data.xyz
# ├── 1/, 2/, 3/        # 第一次运行生成
# └── 4/, 5/, …         # 续算生成
# ============================================================================
"""
import os
import sys
import glob

# Windows 控制台默认 GBK 编码无法输出 emoji，统一改用 UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))


def print_help():
    """打印帮助信息"""
    print("""
脚本功能：
  读取XYZ轨迹文件，将每一帧拆分为独立POSCAR文件，
  每帧放入以帧号命名的数字文件夹（1/、2/、…、n/）中，
  POSCAR使用direct直接坐标，元素按全局统一顺序排列。

运行模式：
  -def, --default   默认模式（未指定模式时默认）：从 1/ 开始全新分发
  -con, --continue  续算模式：检测脚本目录下已有数字文件夹，
                    新轨迹帧从最大文件夹号+1开始分发
                    （适用于补充数据单点能计算：先运行一次默认模式，
                     后续新数据用 -con 接着分发）
  -h,   --help      显示本帮助信息

使用方法：
  python 1xyz2poscar_number.py [-def | -con] [xyz文件名]
  选项参数位置任意，例如：
    python 1xyz2poscar_number.py -con new_data.xyz
    python 1xyz2poscar_number.py new_data.xyz -con
  不传xyz文件名时，自动扫描脚本所在目录下唯一的*.xyz文件

输出：
  1/, 2/, … n/        数字文件夹，生成在脚本所在目录
  */POSCAR            VASP输入文件，direct坐标
  .elements_order.txt 元素顺序记录文件（续算模式依赖，勿删除）
""")

# ---------- 参数解析：选项(-def/-con/-h)位置任意，剩余参数为xyz文件名 ----------
mode = "default"          # 运行模式：default(默认模式) / continue(续算模式)
input_arg = None          # 命令行指定的xyz文件名（可选）
for arg in sys.argv[1:]:
    if arg in ("-def", "--default"):
        mode = "default"
    elif arg in ("-con", "--continue"):
        mode = "continue"
    elif arg in ("-h", "--help"):
        print_help()
        sys.exit(0)
    elif input_arg is None:
        input_arg = arg
    else:
        print(f"❌ 无法识别的参数：{arg}")
        print("   用法：python 1xyz2poscar_number.py [-def | -con] [xyz文件名]")
        exit(1)

# 从命令行参数获取 xyz 文件名（可选）
if input_arg is not None:
    input_file = input_arg
    if not os.path.exists(input_file):
        print(f"❌ 未找到文件：{input_file}")
        exit(1)
else:
    # 无参数：默认扫描脚本所在目录下的 xyz 文件
    xyz_list = glob.glob(os.path.join(script_dir, "*.xyz"))

    if len(xyz_list) == 0:
        print(f"❌ 脚本所在目录下未找到任何 .xyz 文件！")
        exit(1)

    if len(xyz_list) > 1:
        print(f"❌ 脚本所在目录下存在多个 .xyz 文件，无法自动判断：")
        for f in xyz_list:
            print(f"   {os.path.basename(f)}")
        print("   请指定要转换的文件：python 1xyz2poscar_number.py [-def | -con] xyz文件名")
        exit(1)

    input_file = xyz_list[0]

print(f"✅ 找到XYZ文件：{input_file}")

from ase.io import read, write

# 读取所有结构
frames = read(input_file, ":")
total_frames = len(frames)
print(f"✅ 总帧数：{total_frames}")

# 元素顺序记录文件（默认模式写入，续算模式读取）
elem_order_file = os.path.join(script_dir, ".elements_order.txt")

if mode == "continue":
    # ---------- 续算模式：在已有数字文件夹基础上继续分发 ----------
    # 扫描脚本目录下的纯数字文件夹（排除 a/、b/、3.txt 等）
    num_dirs = sorted(
        int(name) for name in os.listdir(script_dir)
        if name.isdigit() and os.path.isdir(os.path.join(script_dir, name))
    )

    if len(num_dirs) == 0:
        print(f"❌ 续算模式未检测到任何数字文件夹（1/、2/、…），请先使用默认模式运行一次！")
        exit(1)

    max_num = num_dirs[-1]
    print(f"🔍 检测到 {len(num_dirs)} 个数字文件夹（1/ ~ {max_num}/）")

    # 检查残缺文件夹：空目录或缺少POSCAR（上次运行可能中断）
    incomplete = [n for n in num_dirs
                  if not os.path.isfile(os.path.join(script_dir, str(n), "POSCAR"))]
    if incomplete:
        print(f"⚠️ 警告：以下文件夹缺少POSCAR文件：{'、'.join(str(n) for n in incomplete)}")
        if max_num in incomplete:
            print(f"❌ 最大文件夹 {max_num}/ 缺少POSCAR，续算基线不完整，终止运行！")
            exit(1)

    # 读取上次运行记录的元素顺序，保证新旧POSCAR第6行一致
    # 【宽松版】记录文件缺失时不终止，改为从最大文件夹的已有POSCAR推断元素顺序
    if os.path.isfile(elem_order_file):
        with open(elem_order_file, encoding="utf-8") as f:
            elements = f.read().strip().split()
        if not elements:
            print(f"❌ 元素顺序记录文件为空：{elem_order_file}")
            exit(1)
        print(f"✅ 沿用上次元素顺序：{' '.join(elements)}")
    else:
        print(f"⚠️ 未找到元素顺序记录文件（宽松模式），从已有POSCAR推断元素顺序")
        try:
            old_atoms = read(os.path.join(script_dir, str(max_num), "POSCAR"), format='vasp')
            elements = []
            for sym in old_atoms.get_chemical_symbols():
                if sym not in elements:
                    elements.append(sym)
            print(f"✅ 从 {max_num}/POSCAR 推断元素顺序：{' '.join(elements)}")
        except Exception as e:
            print(f"⚠️ 从已有POSCAR推断元素顺序失败（{e}），改用新轨迹元素字母排序")
            elements = sorted({sym for a in frames for sym in a.get_chemical_symbols()})
            print(f"✅ 新轨迹元素顺序：{' '.join(elements)}")

    # 新轨迹出现记录文件之外的元素 → 元素顺序会漂移，终止
    new_elements = {sym for a in frames for sym in a.get_chemical_symbols()}
    extra = sorted(new_elements - set(elements))
    if extra:
        print(f"❌ 新轨迹出现记录文件中不存在的元素：{' '.join(extra)}")
        print("   新旧POSCAR元素顺序无法保持一致，终止运行！")
        print(f"   如确认需要，请先将这些元素加入 {os.path.basename(elem_order_file)} 后重试")
        exit(1)

    start_num = max_num + 1
    print(f"▶️ 续算分发：新轨迹第1帧 → {start_num}/")
else:
    # ---------- 默认模式：从 1/ 开始全新分发 ----------
    # 安全校验：已有含POSCAR的数字文件夹时禁止静默覆盖（SCF结果不可再生）
    exist_dirs = sorted(
        int(name) for name in os.listdir(script_dir)
        if name.isdigit() and os.path.isdir(os.path.join(script_dir, name))
    )
    if exist_dirs and any(
        os.path.isfile(os.path.join(script_dir, str(n), "POSCAR")) for n in exist_dirs
    ):
        print(f"❌ 检测到已有数字文件夹且含POSCAR（1/ ~ {exist_dirs[-1]}/），默认模式会覆盖已有结果！")
        print("   如想接着分发请使用 -con；如确认重新生成，请先删除/移走已有数字文件夹")
        exit(1)

    # 全局统一的元素顺序：收集所有帧出现的全部元素，按字母排序
    # （同一轨迹各帧元素组成可能不同，保证每帧不丢原子）
    elements = sorted({sym for a in frames for sym in a.get_chemical_symbols()})
    print(f"✅ 全局元素顺序：{' '.join(elements)}")

    # 保存元素顺序记录，供后续续算模式读取
    with open(elem_order_file, "w", encoding="utf-8") as f:
        f.write(" ".join(elements))
    print(f"💾 元素顺序已记录到 {os.path.basename(elem_order_file)}")

    start_num = 1

created_dirs = 0
for i, atoms in enumerate(frames, 1):
    # 数字文件夹：默认模式 1/、2/、…；续算模式从最大文件夹号+1开始
    out_folder = os.path.join(script_dir, str(start_num + i - 1))
    os.makedirs(out_folder, exist_ok=True)
    created_dirs += 1

    poscar_path = os.path.join(out_folder, "POSCAR")

    # 按全局统一的元素顺序重排（组内保持原顺序，缺失元素自动跳过）
    symbols = atoms.get_chemical_symbols()
    order = []
    for elem in elements:
        order.extend([i for i, sym in enumerate(symbols) if sym == elem])

    atoms_sorted = atoms[order]

    # 写入 POSCAR
    write(poscar_path, atoms_sorted, format='vasp', direct=True)

    if i % 100 == 0:
        print(f"📦 已处理 {i}/{total_frames}，已创建文件夹 {created_dirs}")

print(f"\n🎉 全部完成！共分发 {total_frames} 帧，新文件夹 {start_num}/ ~ {start_num + total_frames - 1}/")
