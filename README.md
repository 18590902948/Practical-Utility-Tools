<div align="center">

# 🧰 Practical Utility Tools

**研究生学习生涯中沉淀的实用脚本与工具合集**

涵盖 VASP 主动学习训练流水线 · 材料结构格式转换 · 日常生活小工具

</div>

---

## 📖 目录

- [📁 项目结构](#-项目结构)
- [🔬 主动学习流水线](#-主动学习流水线)
- [🔄 格式转换工具](#-格式转换工具)
- [🎮 生活小工具](#-生活小工具)
- [⚙️ 环境依赖](#️-环境依赖)
- [👤 关于作者](#-关于作者)

---

## 📁 项目结构

```text
Practical-Utility-Tools/
├── active_learning/          # 🔬 VASP 主动学习训练流水线
│   ├── Ycalculate_file/      #    VASP 计算模板（INCAR / POTCAR / sub2.sh）
│   ├── 1xyz2poscar.py        #    XYZ 轨迹 → 分组 POSCAR
│   ├── 2cp_cal_file.py       #    批量复制计算输入文件
│   ├── 4merge_xyz.py         #    合并各组的 train.xyz
│   ├── split_xyz.py          #    数据集随机划分（8:2）
│   ├── scf_collect.py        #    收集 SCF 结果生成训练集
│   └── batch_submit.sh       #    Slurm 批量作业提交
├── format_convert/           # 🔄 结构格式转换
│   ├── cif2pos.py            #    CIF → VASP
│   ├── xsd2pos.py            #    XSD → VASP
│   ├── bc_cif_xsd2pos.py     #    一键批量转换
│   └── download_cif.py       #    Materials Project 批量下载
├── mini_program/             # 🎮 生活小工具
│   ├── cloudmusic/           #    网易云音乐 VIP 歌曲转换
│   └── shutdown/             #    GUI 定时关机工具
└── README.md
```

---

## 🔬 主动学习流水线

> 机器学习势函数（NEP / MLIP）训练数据的自动化生产线：
> **XYZ 轨迹 → 拆帧 → VASP 计算 → 结果收集 → 数据集合并与划分**

| 脚本 | 功能 | 用法 |
| --- | --- | --- |
| `1xyz2poscar.py` | 读取 XYZ 轨迹，每 500 帧分 a/b/c… 组，逐帧生成 POSCAR | `python 1xyz2poscar.py` |
| `2cp_cal_file.py` | 将 `Ycalculate_file/` 模板（INCAR/POTCAR/sub2.sh）批量复制到各任务目录 | `python 2cp_cal_file.py` |
| `batch_submit.sh` | Slurm 分批提交任务，自动控制提交速率与并发上限 | `./batch_submit.sh` |
| `scf_collect.py` | 遍历各任务 OUTCAR，筛选自洽收敛构型，输出含能量/维里的 `train.xyz` | `python scf_collect.py` |
| `4merge_xyz.py` | 按字母顺序拼接 a/b/c…/train.xyz，生成 `merge_train.xyz` | `python 4merge_xyz.py` |
| `split_xyz.py` | 数据集随机打乱，按 8:2 划分为训练集 / 测试集 | `python split_xyz.py <data.xyz> [输出目录] [种子]` |

```text
流程示意:
XYZ 轨迹 ──► 1xyz2poscar 分帧分组 ──► 2cp_cal_file 拷贝输入 ──► batch_submit 提交计算
                                                                    │
        split_xyz 划分训练/测试 ◄── 4merge_xyz 合并数据集 ◄── scf_collect 收集结果 ◄─┘
```

---

## 🔄 格式转换工具

> 各类材料结构文件与 VASP 格式之间的转换，支持单个转换与批量处理

| 脚本 | 功能 | 用法 |
| --- | --- | --- |
| `cif2pos.py` | CIF 晶体结构 → `.vasp`（支持空间群对称性展开） | `python cif2pos.py A.cif` |
| `xsd2pos.py` | Materials Studio 的 XSD → `.vasp`（支持固定原子） | `python xsd2pos.py [A.xsd]` |
| `bc_cif_xsd2pos.py` | 扫描当前目录全部 `.cif` / `.xsd`，一键批量转换为 `.vasp` | `python bc_cif_xsd2pos.py` |
| `download_cif.py` | 从 Materials Project 数据库按化学式批量下载结构（需 API Key） | `python download_cif.py` |

```text
输入来源                       输出
─────────                     ─────
Materials Studio (.xsd) ─┐
CIF 晶体数据库 (.cif) ────┼─►  .vasp（VASP POSCAR 格式）→ 超算 VASP 计算
Materials Project (API) ─┘
```

---

## 🎮 生活小工具

| 工具 | 功能 |
| --- | --- |
| `网易云VIP歌曲转换工具.exe` | 网易云音乐 VIP 歌曲格式转换（本地工具） |
| `shutdown.exe` / `shutdown.py` | 带图形界面的定时关机工具 |

---

## ⚙️ 环境依赖

- **Python 3.10+**，推荐使用 `conda` 管理环境
- 核心依赖：`numpy` · `ase` · `pymatgen`
- 可选依赖：`mp-api`（下载脚本需要，API Key 通过环境变量 `MP_API_KEY` 提供）
- 超算环境：需 `Slurm` 作业调度系统（`batch_submit.sh`）

---

## 👤 关于作者

**Hongbo Sun** · 计算材料学方向研究生

> 这些脚本都是我在科研与生活中遇到重复性劳动时随手沉淀的，希望能帮到同样被琐事困扰的你。欢迎使用、修改与分享～

<div align="center">

**✨ 持续更新中，欢迎 Star ✨**

</div>
