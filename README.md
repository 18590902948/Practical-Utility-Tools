<div align="center">

# 🧰 Practical Utility Tools

**研究生学习生涯中沉淀的实用脚本与工具合集**

涵盖 VASP 主动学习流水线 · 机器学习势函数（NEP）训练 · 结构格式转换

</div>

---

## 📖 目录

- [📁 项目结构](#-项目结构)
- [💾 classic_data — 经典数据文件](#-classic_data--经典数据文件)
- [⭐ perfect_design — 他人设计的优秀脚本](#-perfect_design--他人设计的优秀脚本)
- [🧪 testing_design — 自研 DFT 与机器学习脚本](#-testing_design--自研-dft-与机器学习脚本)
- [🔬 workflow_AL — 主动学习工作流脚本](#-workflow_al--主动学习工作流脚本)
- [🧫 AI_laboratory — 新脚本测试区](#-ai_laboratory--新脚本测试区)
- [⚙️ 环境依赖](#️-环境依赖)
- [👤 关于作者](#-关于作者)

---

## 📁 项目结构

```text
Practical-Utility-Tools/
├── classic_data/        # 💾 经典数据文件（NEP 势模型、xyz 格式示例）
├── perfect_design/      # ⭐ 他人编写的非常好用的脚本（格式转换、结构采样）
├── testing_design/      # 🧪 自研 DFT / 机器学习脚本
├── workflow_AL/         # 🔬 主动学习工作流脚本
├── AI_laboratory/       # 🧫 新脚本测试文件夹
└── README.md
```

---

## 💾 classic_data — 经典数据文件

存放一些经典的数据文件，作为测试与示例数据使用。

| 子目录 | 内容 |
| --- | --- |
| `NEP89/` | NEP 势模型相关文件：`nep.in`（NEP 输入参数）、训练好的势函数 `nep89_*.txt`、训练中间态 `*.restart` |
| `xyz_format/` | XYZ 格式示例文件：`example.xyz`、`example.extxyz`（测试转换脚本用） |

---

## ⭐ perfect_design — 他人设计的优秀脚本

收集了其他作者编写、经实际使用验证**非常好用**的脚本，主要用于 GPUMD / NEP 训练的数据准备与采样，每个子目录内均有详细的 README 说明。

> **来源声明**：本目录内容取自 [GPUMDkit](https://github.com/zhyan0603/GPUMDkit.git)，作者为 **Zihan YAN**（yanzihan@westlake.edu.cn），原始仓库：[https://github.com/zhyan0603/GPUMDkit.git](https://github.com/zhyan0603/GPUMDkit.git)。使用及引用请遵循原作者的开源许可，并参阅 GPUMDkit 的引用说明。

| 子目录 | 内容 |
| --- | --- |
| `GPUMD_convert/` | **格式转换脚本集**：VASP / CP2K / ABACUS / LAMMPS / CIF / MTP 等格式与 extxyz 之间的相互转换，以及添加 group / weight 标签、帧提取、超胞复制、数据清洗等后处理工具 |
| `GPUMD_sample/` | **结构采样脚本集**：均匀/随机采样、NepTrain 描述符 FPS 采样（并行）、最大力偏差筛选（`select_max_modev.py`）、结构扰动扩增、训练/测试集划分等 |

> 脚本基本保持原样使用；如需定制，可将改写版放至 `testing_design/` 或 `AI_laboratory/` 中迭代。

---

## 🧪 testing_design — 自研 DFT 与机器学习脚本

自己设计的、用于 **DFT 和机器学习**的一些脚本，多由 `perfect_design` 中的脚本改造成"免参数、批量自动处理"的版本，并遵循统一的脚本设计规范。

| 脚本 | 功能 |
| --- | --- |
| `cif2pos.py` / `xsd2pos.py` / `bc_cif_xsd2pos.py` | CIF / XSD（Materials Studio）→ VASP POSCAR，支持批量一键转换 |
| `vasp2xyz.py` | 扫描目录下全部 VASP 文件，按类型自动分类合并为 xyz |
| `download_structures4MP.py` | 从 Materials Project 按化学式批量下载结构（需 API Key） |
| `replicate.py` | 超胞复制：指定倍数或目标原子数，支持多帧模式 |
| `orthocell.py` / `orthocell_projection.py` | 周期性晶体正交化处理 |
| `check_dup_xyz.py` | 严格检测 xyz/extxyz 文件内部及文件之间的重复结构并去重 |
| `merge_clean_xyz.py` | 合并并清洗 xyz 数据 |
| `xyzs2xyz_file.py` / `xyzs2xyz_folder.py` | 多文件 / 多文件夹 xyz 批量合并（带日志记录） |
| `pos2model_xyz.py` / `xyz2model_xyz.py` | 从 POSCAR / xyz 轨迹抽取指定帧，输出 `model.xyz`（带记录文件与去重审计） |
| `quick_cp.py` | 快速复制工具 |

---

## 🔬 workflow_AL — 主动学习工作流脚本

主动学习（Active Learning）过程中需要用到的一些脚本，将"**MD 轨迹 → 选帧 → DFT 单点 → 收集标注 → 更新训练集**"整条流水线脚本化，分两条支线：

```text
batch_GPUMD/   训练集 → 抽取初始结构 (train_xyz2model_xyz2.py) → 批量 MD
                            ↓ active 模式
               select_active.py 按力偏差不确定度筛选 top-N → 转 POSCAR → DFT 标注
                                                      ↓
batch_scf/     1xyz2poscar 拆帧 → 2cp_cal_file 复制输入 → 3batch_submit 提交
               → 4scf_collect 收集 OUTCAR 生成 train.xyz → 5xyzs2xyz_folder 合并
               → 6split_xyz 划分训练/测试集
```

### batch_GPUMD/ — MD 批量准备与选帧

| 脚本 | 功能 |
| --- | --- |
| `train_xyz2model_xyz2.py` | 在 NEP 训练目录中按指定帧号/随机抽取结构生成 `model.xyz`，并同步 `nep.txt`、`sub_MD.sh` 至各 `1_md*` 文件夹（MD 初始结构创建器） |
| `select_active.py` | 从各 `1_md*/active.xyz` 中按帧级不确定度降序取每文件夹 top-N，合并为单一 xyz 供 DFT 批量标注 |

### batch_scf/ — DFT 单点批量标注流水线

| 脚本 | 功能 |
| --- | --- |
| `1xyz2poscar_letter.py` / `1xyz2poscar_number.py` | XYZ 轨迹每帧拆分为独立 POSCAR，按 500 帧一组（字母分组 a/b/c…）或逐帧（数字文件夹 1/2/…）存放，支持续算模式 |
| `2cp_cal_file_letter.py` / `2cp_cal_file_number.py` | 将 `Y_VASP_file/` 模板（INCAR / POTCAR / sub2.sh）批量复制到各任务目录，自动补全缺失文件并校验元素顺序 |
| `3batch_submit.sh` | Slurm 批量提交作业，控制提交速率与并发上限 |
| `4scf_collect_numder.py` | 扫描各任务 OUTCAR，检测自洽收敛，收集能量与 virial 生成 `train.xyz`（含统计报告） |
| `5xyzs2xyz_folder.py` | 合并各文件夹的 xyz/extxyz |
| `6split_xyz.py` | 数据集随机划分（默认 8:2 训练/测试），支持固定随机种子 |
| `Y_VASP_file/` | VASP 计算模板：INCAR / POTCAR / sub2.sh |

---

## 🧫 AI_laboratory — 新脚本测试区

新脚本的测试文件夹，用于脚本开发调试阶段的试验与临时输出（`0/`、`1/`、`A/`、`out/`、`out2/`、`sub/` 等子目录为测试过程的临时产物）。测试成熟后，脚本再归档到 `testing_design/` 或 `workflow_AL/`。

---

## ⚙️ 环境依赖

- **Python 3.10+**，推荐使用 `conda` 管理环境
- 核心依赖：`numpy` · `ase` · `pymatgen`
- 可选依赖：
  - `mp-api`：`download_structures4MP.py` 需要，API Key 通过环境变量 `MP_API_KEY` 提供
  - `NepTrain` / `dpdata`：`perfect_design/GPUMD_sample` 中的 FPS 采样、结构扰动脚本需要
  - `ovito`：`pos2lmp.py` 需要
- 超算环境：`workflow_AL` 中 `.sh` 脚本需 Slurm 作业调度系统（Linux / WSL）

---

## 👤 关于作者

**Hongbo Sun** · 计算材料学方向研究生

> 这些脚本都是我在科研中遇到重复性劳动时随手沉淀的，希望能帮到同样被琐事困扰的你。欢迎使用、修改与分享～

<div align="center">

**✨ 持续更新中，欢迎 Star ✨**

</div>
