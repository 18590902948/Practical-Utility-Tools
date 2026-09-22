import ctypes
import glob
import os
import sys
import traceback
from ase.io import read, write

here = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
outdir = os.path.join(here, "vasp")
frozen = getattr(sys, "frozen", False)


def notify(text, error=False, popup=True):
    print(text)
    if frozen and popup:
        ctypes.windll.user32.MessageBoxW(0, text, "xyz2vasp 出错" if error else "xyz2vasp", 0x10 if error else 0x40)
try:
    os.makedirs(outdir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(here, "*.xyz")) + glob.glob(os.path.join(here, "*.extxyz")))
    lines = []
    for path in files:
        atoms = read(path)
        atoms = atoms[sorted(range(len(atoms)), key=lambda i: atoms[i].number)]
        name = os.path.splitext(os.path.basename(path))[0]
        write(os.path.join(outdir, name + ".vasp"), atoms, format="vasp")
        lines.append(f"{os.path.basename(path)} -> vasp/{name}.vasp")
    if files:
        notify(f"完成，共转换 {len(files)} 个文件：\n\n" + "\n".join(lines) + f"\n\n输出目录：\n{outdir}", popup=False)
    else:
        notify(f"未找到 xyz/extxyz 文件，请把文件放到该目录：\n{here}")
except Exception:
    notify(traceback.format_exc(), error=True)
    sys.exit(1)
