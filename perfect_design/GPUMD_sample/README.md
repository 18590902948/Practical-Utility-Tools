<div align="center">
  <h1>📦 结构采样脚本（详细说明）</h1>
    <p style="text-align: justify;">本目录包含用于 NEP 训练和分子动力学模拟的原子结构采样、筛选与生成工具。所有脚本均可通过 <code>gpumdkit.sh</code> 交互菜单 / 命令行调用，或直接用 python 运行。</p>
</div>

## 目录

- [一、脚本总览表](#一脚本总览表)
- [二、通用说明](#二通用说明)
- [三、脚本详解](#三脚本详解)
  - [1. frame_range.py —— 按比例抽取帧范围](#1-frame_rangepy--按比例抽取帧范围)
  - [2. sample_structures.py —— 均匀/随机采样](#2-sample_structurespy--均匀随机采样)
  - [3. neptrain_select_structs.py —— NepTrain 描述符 FPS（单线程）](#3-neptrain_select_structspy--neptrain-描述符-fps单线程)
  - [⭐ 4. parallel_neptrain_select_structs.py —— NepTrain 描述符 FPS（并行，推荐）](#4-parallel_neptrain_select_structspy--neptrain-描述符-fps并行推荐)
  - [5. pynep_select_structs.py —— PyNEP 描述符 FPS（已废弃）](#5-pynep_select_structspy--pynep-描述符-fps已废弃)
  - [6. parallel_pynep_select_structs.py —— PyNEP 描述符 FPS（并行，兼容入口）](#6-parallel_pynep_select_structspy--pynep-描述符-fps并行兼容入口)
  - [7. perturb_structure.py —— 结构扰动](#7-perturb_structurepy--结构扰动)
  - [⭐ 8. select_max_modev.py —— 最大力偏差筛选](#8-select_max_modevpy--最大力偏差筛选)
  - [9. split_train_test.py —— 训练/测试集划分](#9-split_train_testpy--训练测试集划分)
- [四、主动学习（AL）选帧推荐流程](#四主动学习al选帧推荐流程)

---

## 一、脚本总览表

| # | 脚本 | 作用（一句话） | 交互菜单 | 命令行入口 |
|---|---|---|---|---|
| 1 | [frame_range.py](frame_range.py) | 按起止比例抽取轨迹的一段帧（如切掉平衡段） | 无 | `-frame_range` |
| 2 | [sample_structures.py](sample_structures.py) | 从轨迹均匀或随机抽 N 帧 | 201 | 无 |
| 3 | [neptrain_select_structs.py](neptrain_select_structs.py) | NepTrain 描述符 FPS 采样（单线程） | 无（203 调的是并行版） | 无 |
| 4 | ⭐ [parallel_neptrain_select_structs.py](parallel_neptrain_select_structs.py) | NepTrain 描述符 FPS 采样（多线程，**推荐**） | **203** | 无 |
| 5 | [pynep_select_structs.py](pynep_select_structs.py) | PyNEP 描述符 FPS（**已废弃**，PyNEP 不再维护） | 202（仅提示） | 无 |
| 6 | [parallel_pynep_select_structs.py](parallel_pynep_select_structs.py) | PyNEP 描述符 FPS 并行版（仅兼容保留） | 无 | `-pynep` |
| 7 | [perturb_structure.py](perturb_structure.py) | 从 POSCAR 生成扰动结构（训练集扩增） | 204 | 无 |
| 8 | ⭐ [select_max_modev.py](select_max_modev.py) | 从 GPUMD active 输出中选最大力偏差 top N | 205 | 无 |
| 9 | [split_train_test.py](split_train_test.py) | 检查数据集并交互式划分训练/测试集 | 206 | 无 |

> ⭐ = **采样最核心的两个脚本**：脚本 8（力偏差筛选，误差驱动）+ 脚本 4（FPS 筛选，多样性驱动），两者互补；其余脚本为辅助/预处理工具。
> **运行前提**：脚本 4 需要安装 **NepTrain** 依赖（另需 scipy / scikit-learn / matplotlib），并提供 NEP 模型文件（`nep.txt`，须与训练集同元素同版本）来算描述符；脚本 8 需要先用 GPUMD 跑 **active 模式**产生 `active.out`（每帧最大力偏差）+ `active.xyz`（对应结构），即在 nep.in 中加入 `active <间隔>` 命令。

---

## 二、通用说明

1. **三种调用方式**（以 203 为例）：
   - **交互菜单**：`gpumdkit.sh` → 输入 `2`（Sample Structures）→ 输入功能号（如 `203`）→ 按提示输入参数
   - **命令行**：部分脚本有直接入口（如 `gpumdkit.sh -frame_range ...`、`gpumdkit.sh -pynep`）
   - **python 直跑**：`python <脚本名>.py <参数>`（脚本在 `GPUMDkit-main/Scripts/sample_structures/` 下，需先 `cd` 到工作目录，因为输出文件都写在当前目录）
2. **所有脚本读/写当前目录**：输入文件路径按当前目录写相对路径，输出文件（`selected.xyz`、`sampled_structures.xyz` 等）一律生成在当前目录，不要从别的目录带路径调用。
3. **依赖包**：`ase` 几乎所有脚本必需；`numpy` 多数必需；`NepTrain`（FPS 203 系列）、`pynep`（已废弃）、`dpdata`（扰动）、`scipy`（FPS 距离计算）、`scikit-learn`（PCA 绘图）、`seaborn`（可选，增强 PCA 图边缘密度）按需安装。
4. **交互式 FPS 的两种选择方式**（脚本 3/4/5/6 通用，运行时会问你）：
   - `1) Select structures based on minimum distance`：**按距离阈值选**。输入一个 `min_dist`（如 0.01），只要与已选结构（含训练集）的描述符距离大于该阈值就继续选，直到选完——**不预先指定数量**，适合"想多选就多选、想少选就少选"的阈值控制。
   - `2) Select structures based on number of structures`：**按数量选**。输入 `min_select` 和 `max_select`（如 `50 100`），选够 `min_select` 个后，若还能继续拉开距离则最多选到 `max_select` 个——**明确控制输出数量**。
5. **输出文件命名冲突**：脚本 3/4/5/6 的输出都叫 `selected.xyz` + `select.png`，连续跑多个会互相覆盖，注意及时改名保存。

---

## 三、脚本详解

### 1. frame_range.py —— 按比例抽取帧范围

**作用**：从 extxyz 轨迹中按"起始比例 ~ 结束比例"抽出一段连续帧。典型用途：
- 切掉 MD 前段的平衡过程，只留生产段（如取前 80% 之后的 50%：`0.5 1.0`）；
- 截取轨迹中间某段做专门分析/采样（如只取 900 K 相变停留段）。

**gpumdkit 调用**（命令行入口）：

```bash
gpumdkit.sh -frame_range dump.xyz 0.2 0.5
```

**python 直接运行**：

```bash
python frame_range.py dump.xyz 0.2 0.5
```

**参数详解**：

| 参数 | 含义 | 说明 |
|---|---|---|
| `input.xyz` | 输入 extxyz 轨迹文件 | 任意帧数的轨迹 |
| `start_fraction` | 起始比例 | 0.0 ~ 1.0，`0` = 从头开始 |
| `end_fraction` | 结束比例 | 0.0 ~ 1.0，`0.8` = 取前 80% |

帧号换算：`start_idx = int(start_fraction × 总帧数)`，`end_idx = int(end_fraction × 总帧数)`，实际取 `[start_idx, end_idx)` 半开区间。

**输出**：`<输入名>_<起始>_<结束>.xyz`，例如 `dump_0.20_0.50.xyz`（比例保留两位小数拼进文件名）。

**依赖**：`ase`。

**注意事项**：示例比例（0.2/0.5）只是演示，请按自己的平衡/生产段划分来定；`start_fraction` 应小于 `end_fraction`，否则取出的子集为空。

---

### 2. sample_structures.py —— 均匀/随机采样

**作用**：从 extxyz 轨迹中按**均匀**（等间隔）或**随机**（无放回）方式抽取指定数量的帧，并可选择跳过开头若干帧（通常是平衡段）。适合"轨迹太长、先抽个代表性子集"的粗筛。

**gpumdkit 调用**（交互菜单 201）：

```bash
gpumdkit.sh
# 主菜单输入 2 → 采样子菜单输入 201
# 提示 Input <extxyz_file> <sampling_method> <num_samples> [skip_num]
# 示例输入：train.xyz uniform 50
```

**python 直接运行**：

```bash
# 均匀抽 50 帧
python sample_structures.py train.xyz uniform 50
# 跳过前 500 帧后随机抽 100 帧
python sample_structures.py dump.xyz random 100 500
```

**参数详解**：

| 参数 | 含义 | 默认 |
|---|---|---|
| `<extxyz_file>` | 输入 extxyz 轨迹文件 | 必填 |
| `<sampling_method>` | `uniform`（等间隔）或 `random`（无放回随机） | 必填 |
| `<num_samples>` | 要抽的帧数 | 必填 |
| `[skip_initial]` | 跳过的初始帧数（平衡段） | 0 |

**输出**：`sampled_structures.xyz`（抽出的帧按原顺序排列）。

**依赖**：`numpy` + `ase`。

**注意事项**：`num_samples` 不能超过（总帧数 - 跳过的帧数），`random` 模式超了会因无放回抽样而报错；均匀模式用 `np.linspace` 取整索引，数量越界时也会取到重复帧，建议先确认帧数再定 `num_samples`。

---

### 3. neptrain_select_structs.py —— NepTrain 描述符 FPS（单线程）

**作用**：用 **NepTrain 描述符**（NEP 模型的原子描述符逐帧求平均）把候选结构映射到描述符空间，然后相对**已有训练集**做**最远点采样（FPS）**：从训练集出发，反复挑选"与已选集合（含全部训练帧）描述符距离最远"的候选帧。得到的是**与训练集最不重复、且彼此尽量分散**的构型子集——主动学习（AL）挑 DFT 候选的标准做法。会额外输出描述符 PCA 降维图，直观展示候选/训练/选中三者的空间关系。

**⚠ 单线程版**：逐帧串行算描述符，数据量大时慢。**gpumdkit 菜单 203 实际调用的是下面的并行版**；本脚本仅支持 python 直跑。

**python 直接运行**：

```bash
python neptrain_select_structs.py dump.xyz train.xyz nep.txt
```

运行后会进入交互：

```
Choose selection method:
1) Select structures based on minimum distance
2) Select structures based on number of structures
 ------------>>
1                     ← 方式 1：输入最小距离阈值
Enter min_dist (e.g., 0.01): 0.01
2                     ← 方式 2：输入数量区间
Enter min_select and max_select (e.g., '50 100'): 50 100
```

**参数详解**：

| 参数 | 含义 | 说明 |
|---|---|---|
| `<sampledata_file>` | 候选结构文件 | 如 MD 轨迹 `dump.xyz` |
| `<traindata_file>` | 已有训练集 | 如 `train.xyz`，作为 FPS 的"已有点" |
| `<nep_model_file>` | NEP 势文件 | 如 `nep.txt`，用于算描述符（须与训练集同元素同版本） |

**输出**：
- `selected.xyz` —— 选中的结构（顺序 = 在候选文件中的原始顺序）
- `select.png` —— 描述符 PCA 降维图（蓝=候选、橙=训练、绿=选中，有 seaborn 时带边缘密度）
- `pca_sample.txt` / `pca_train.txt` / `pca_selected.txt` —— 三组 PCA 坐标文本

**依赖**：`NepTrain` + `ase` + `numpy` + `scipy` + `scikit-learn` + `matplotlib`（`seaborn` 可选）。

**引用**：使用 NepTrain 请引用 Chen et al., Comput. Phys. Commun. 317, 109859 (2025), doi:10.1016/j.cpc.2025.109859。

---

### 4. parallel_neptrain_select_structs.py —— NepTrain 描述符 FPS（并行，推荐）

**作用**：与脚本 3 完全相同的 FPS 采样逻辑，但描述符计算支持**多进程并行**（`threads` 个 worker），数据量大时速度可提升数倍；并行计算时保持输入帧的原始顺序，选中结果与单线程版一致。**这是 gpumdkit 交互菜单 203 实际调用的脚本，推荐日常使用。**

**gpumdkit 调用**（交互菜单 203）：

```bash
gpumdkit.sh
# 主菜单输入 2 → 采样子菜单输入 203
# 提示 Input <sample.xyz> <train.xyz> <nep_model> [threads]
# 示例输入：dump.xyz train.xyz nep.txt 4
```

**python 直接运行**：

```bash
# 单线程（等价于脚本 3）
python parallel_neptrain_select_structs.py dump.xyz train.xyz nep.txt
# 4 线程并行
python parallel_neptrain_select_structs.py dump.xyz train.xyz nep.txt 4
```

**参数详解**：

| 参数 | 含义 | 默认 |
|---|---|---|
| `<sample.xyz>` | 候选结构文件（MD 轨迹等） | 必填 |
| `<train.xyz>` | 已有训练集（FPS 的"已有点"） | 必填 |
| `<nep.txt>` | NEP 势文件（算描述符用） | 必填 |
| `[threads]` | 并行描述符计算进程数 | 1 |

运行后的交互（选 1 距离阈值 / 选 2 数量区间）与脚本 3 完全相同。

**并行原理**：每个 worker 进程独立加载一份 NEP 模型，并把 OpenMP 线程数固定为 1（`OMP_NUM_THREADS=1`），避免嵌套并行抢核——你设多少 `threads` 就有多少核真正在算。**建议 threads ≤ CPU 核数**。

**输出**：`selected.xyz` + `select.png` + `pca_sample.txt` / `pca_train.txt` / `pca_selected.txt`（与脚本 3 相同）。

**依赖**：`NepTrain` + `ase` + `numpy` + `scipy` + `scikit-learn` + `matplotlib`（`seaborn` 可选）。

**注意事项**：
- **`threads` 应设为实际可用的 CPU 核数**，而非登录节点的总核数；线程数超过可用核数反而会因进程争抢和调度开销变慢（上文"并行原理"已建议 `threads ≤ CPU 核数`，注意该核数指运行脚本那台机器实际分到的核）。
- **登录节点是共享资源**：大数据量（几千帧以上）不建议直接在登录节点并行跑，长时间高负载易被超算中心限流或杀进程；小数据量快速试跑（几百帧、2~4 线程）可以接受，适合交互式测试选帧参数。
- **推荐提交到计算节点跑**：写 qsub/sbatch 作业脚本，作业里申请核数（PBS：`nodes=1:ppn=N`；Slurm：`--cpus-per-task=N`），`threads` 与申请核数匹配即可；作业内可用 `nproc` / `lscpu` 或调度系统变量（`$SLURM_CPUS_PER_TASK` / `$PBS_NUM_PPN`）确认实际可用核数。
- **内存按 `threads` 倍增长**：每个 worker 进程独立加载一份 NEP 模型，核数拉满时注意节点内存是否够用，避免 OOM。
- **输出文件写在当前目录**：脚本输出（`selected.xyz` 等）均生成在运行目录，作业脚本里先 `cd` 到工作目录再运行。
- gpumdkit 调用 203 跑完会自动删除 `dpdispatcher.log`（NepTrain 产生的临时日志）。

---

### 5. pynep_select_structs.py —— PyNEP 描述符 FPS（已废弃）

**作用**：早期版本的 FPS 采样，用 **PyNEP 包**的 `NEP` 计算描述符 + `FarthestPointSample` 做最远点采样，逻辑与脚本 3/4 相同（相对训练集选多样化结构）。**PyNEP 包已不再积极维护，官方不推荐使用**：交互菜单 202 只打印提示、不再执行；建议改用 NepTrain 版（脚本 4）。

**python 直接运行**：

```bash
python pynep_select_structs.py dump.xyz train.xyz nep.txt
```

运行后同样交互选择方式 1（min_dist）或 2（min_select / max_select）。

**输出**：`selected.xyz` + `select.png`（无 PCA 文本文件）。

**依赖**：`pynep` + `ase` + `numpy` + `scipy` + `scikit-learn` + `matplotlib`。

---

### 6. parallel_pynep_select_structs.py —— PyNEP 描述符 FPS（并行，兼容入口）

**作用**：PyNEP 版的并行实现（`threads` 个进程并行算描述符），**仅为兼容保留**，同样推荐改用 NepTrain 版。`gpumdkit.sh -pynep` 命令行入口实际调用的是这个脚本。

**gpumdkit 调用**（命令行入口）：

```bash
gpumdkit.sh -pynep
# 提示 Input <sample.xyz> <train.xyz> <nep_model> <threads>
# 示例输入：dump.xyz train.xyz nep.txt 8
```

**python 直接运行**：

```bash
python parallel_pynep_select_structs.py dump.xyz train.xyz nep.txt 8
```

**输出**：`selected.xyz` + `select.png`。

**依赖**：`pynep` + `ase` + `numpy` + `scipy` + `scikit-learn` + `matplotlib`。

---

### 7. perturb_structure.py —— 结构扰动

**作用**：基于一个 VASP POSCAR/CONTCAR 结构，用 **dpdata** 的 `perturb` 方法批量生成扰动结构：**胞扰动**（晶格矢量随机伸缩，比例由 `cell_pert_fraction` 控制）+ **原子扰动**（原子位置随机移动，距离由 `atom_pert_distance` 控制，分布风格由 `atom_pert_style` 指定）。典型用途：只有少量 DFT 初始结构时，通过扰动快速扩增训练集（扰动后的结构需再做 DFT 单点拿标签）；或给 MD 准备多个相似起始构型。

**gpumdkit 调用**（交互菜单 204）：

```bash
gpumdkit.sh
# 主菜单输入 2 → 采样子菜单输入 204
# 提示 Input <input.vasp> <pert_num> <cell_pert_fraction> <atom_pert_distance> <atom_pert_style>
# 默认参数 20 0.03 0.2 uniform；示例输入：POSCAR 20 0.03 0.2 uniform
```

**python 直接运行**：

```bash
python perturb_structure.py POSCAR 20 0.03 0.2 uniform
```

**参数详解**：

| 参数 | 含义 | 默认 | 说明 |
|---|---|---|---|
| `<input.vasp>` | 输入 POSCAR/CONTCAR | 必填 | VASP 格式 |
| `<pert_num>` | 生成扰动结构个数 | 20 | 越多输出文件越多 |
| `<cell_pert_fraction>` | 胞扰动比例 | 0.03 | 晶格矢量的随机伸缩幅度（3%） |
| `<atom_pert_distance>` | 原子扰动距离（Å） | 0.2 | 原子位移幅度 |
| `<atom_pert_style>` | 原子扰动分布风格 | uniform | `normal`（高斯）/ `uniform`（均匀）/ `const`（定值） |

**输出**：`POSCAR_01.vasp`、`POSCAR_02.vasp` … `POSCAR_<pert_num>.vasp`（编号按位数补零对齐）。

**依赖**：`dpdata`。

**注意事项**：扰动幅度要小于体系特征尺度，避免生成原子重叠等物理不合理的结构；扰动后一般需要跑 DFT 单点计算获得能量/力标签，再并入训练集。

---

### 8. select_max_modev.py —— 最大力偏差筛选

**作用**：从 **GPUMD active 模式的输出**中，挑出"当前 NEP 模型最拿不准"的结构：先按力偏差阈值过滤（`deviation > min_deviation` 的帧才进入候选），再从候选中取最大力偏差最大的前 `top_n` 帧。这是**误差驱动的主动学习选帧**——比纯几何的 FPS 更直接地回答"模型哪里不懂"。

**前置条件**（重要）：需要先用 GPUMD 对轨迹跑 active 模式，产生两个文件：
- `active.out` —— 每帧一行，两列：`时间步 最大力偏差`，行号与 active.xyz 帧号一一对应
- `active.xyz` —— 对应的结构文件（extxyz 格式）

（GPUMD 的 nep.in 中加 `active <间隔>` 命令即可在 prediction 时输出这两个文件，具体见 GPUMD 手册。）

**gpumdkit 调用**（交互菜单 205）：

```bash
gpumdkit.sh
# 主菜单输入 2 → 采样子菜单输入 205
# 提示 Input <structs_num> <threshold> (eg. 200 0.15)
# 示例输入：200 0.15
```

**python 直接运行**：

```bash
python select_max_modev.py 200 0.15
```

**参数详解**：

| 参数 | 含义 | 说明 |
|---|---|---|
| `<top_n>` | 最终输出多少个结构 | 取力偏差最大的前 N 个 |
| `<min_deviation>` | 力偏差过滤阈值（eV/Å） | 偏差低于此值的帧直接丢弃，不参与排名 |

**输出**：`selected.xyz`（按力偏差从大到小排列的 top N 结构）。终端会打印：过滤后候选数、top N 帧在 active.xyz 中的索引。

**依赖**：`numpy` + `ase`。

**注意事项**：`min_deviation` 太小会选进大量低偏差（模型已懂）的冗余帧，太大可能过滤后不足 `top_n` 个；建议先看 `active.out` 的偏差分布再定阈值。阈值/数量与 FPS 的"距离阈值/数量"是两种互补思路，可组合使用（见第四节）。

---

### 9. split_train_test.py —— 训练/测试集划分

**作用**：检查一个 extxyz 数据集的摘要（文件名、全部元素、总帧数、每帧原子数范围），然后**交互式**把它划分为互补的训练集和测试集。三种划分方式：均匀（等间隔取测试帧）、随机（无放回，可设固定种子保证可复现）、FPS（用 NepTrain 描述符 + NEP 模型，从第 0 帧开始反复取最远帧进测试集——测试集尽量"代表性分散"）。

**gpumdkit 调用**（交互菜单 206）：

```bash
gpumdkit.sh
# 主菜单输入 2 → 采样子菜单输入 206
# 提示 Input <extxyz_file>；示例输入：data.xyz
# 随后脚本交互式引导：STEP 1 测试集大小 → STEP 2 选择方法
```

**python 直接运行**：

```bash
python split_train_test.py data.xyz
```

**交互流程详解**：

```
STEP 1/2: TEST-SET SIZE（测试集大小，两种写法）
   0 < 值 < 1      → 占总帧数的比例（0.1 = 10%）
   正整数          → 测试帧的确切数量（100 = 100 帧）
STEP 2/2: SELECTION METHOD（划分方法）
   1) Uniform      → 等间隔取测试帧
   2) Random       → 无放回随机，可输入整数种子（回车则不固定，不可复现）
   3) FPS          → 需再输入 NEP 模型文件（如 nep.txt）
```

小数帧数按四舍五入取整（半值向上），且至少选 1 帧；测试集必须小于总帧数，否则报错退出（保证训练集非空）。

**输出**：
- `<输入名>_train.xyz` —— 未被选为测试集的全部帧
- `<输入名>_test.xyz` —— 被选为测试集的帧
（如 `data.xyz` → `data_train.xyz` / `data_test.xyz`；两个输出中的帧均保持原始输入顺序。）

**依赖**：`numpy` + `ase`；选 FPS 方式还需 `NepTrain` + `scipy` + 兼容的 NEP 模型。

---

## 四、主动学习（AL）选帧推荐流程

**采样最重要的两个脚本：⭐ [select_max_modev.py](select_max_modev.py)（力偏差筛选，误差驱动）与 ⭐ [parallel_neptrain_select_structs.py](parallel_neptrain_select_structs.py)（FPS 筛选，多样性驱动）**——一个回答"模型哪里不懂"，一个回答"构型空间哪里没覆盖"，二者互补（见下方方式 A / B / C）。其余脚本（切段、均匀/随机抽样、扰动扩增、训练/测试划分）都是围绕它们的辅助环节。**运行前提**：脚本 4 需装 NepTrain 包并备好 NEP 模型（`nep.txt`）；脚本 8 需先用 GPUMD active 模式跑出 `active.out` / `active.xyz`（nep.in 加 `active <间隔>`）。

结合本目录工具，一轮完整的"MD 轨迹 → 选帧 → DFT"循环建议：

**方式 A：误差驱动（最推荐，脚本 8）**
```
① MD 跑完得 dump.xyz（820 帧）
② 先去相关：frame_range.py 按温度段切段，段内每 5~10 帧取 1（脚本 2 uniform 抽到段内子集）
③ GPUMD nep.in 加 active 命令，对子集跑 prediction → active.out + active.xyz（每帧最大力偏差）
④ select_max_modev.py 200 0.15 → 高偏差 top 200 帧 → 转 POSCAR → DFT
```

**方式 B：多样性驱动（脚本 4，FPS）**
```
① dump.xyz（候选）+ train.xyz（已有训练集）+ nep.txt
② gpumdkit.sh → 2 → 203 → 输入 dump.xyz train.xyz nep.txt 4（4 线程）
③ 交互选方式 2（数量控制）：min_select max_select（如 100 300）→ selected.xyz
④ 用 select.png 检查选中的帧是否覆盖描述符空间空白区 → 转 POSCAR → DFT
```

**方式 C：两者结合（覆盖更全）**
```
① 先去相关（同方式 A ②）
② 高偏差 top 100（方式 A）+ FPS 分散 100 帧（方式 B）合并去重 → 200 帧 → DFT
```

**经验提示**：
- 小胞（<50 原子）DFT 便宜，可从轨迹多选；大胞（>200 原子）少选、优先选高偏差帧；
- 每轮 AL 增量训练用上一轮模型的 `load_restart` 续训（几千~几万代），不要从头训；
- `selected.xyz` 每次运行都会覆盖，多轮采样记得及时改名归档。

---

感谢使用 GPUMDkit！如果您对结构采样有任何问题，请在 [GitHub 仓库](https://github.com/zhyan0603/GPUMDkit/issues) 上提交 issue，或联系 Zihan YAN (yanzihan@westlake.edu.cn)。
