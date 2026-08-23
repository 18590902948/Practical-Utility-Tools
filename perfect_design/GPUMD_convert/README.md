<div align="center">
  <h1>🔄 格式转换脚本（Format Conversion Scripts）</h1>
    <p style="text-align: justify;">本目录提供计算材料科学中常用文件格式之间的转换工具，主要用于为 GPUMD / NEP 训练准备数据集。</p>
</div>

## 项目简介

本工具集支持以下格式间的相互转换：

- **VASP**（POSCAR、OUTCAR、XDATCAR）↔ extxyz
- **CP2K** 输出 → extxyz
- **ABACUS** 输出 → extxyz
- **LAMMPS** dump / data ↔ extxyz
- **CIF** → POSCAR / extxyz
- **MTP** 训练数据 → extxyz
- 辅助功能：添加分组（group）标签、添加权重（weight）、帧提取、超胞复制、数据清洗等

每个脚本均可直接通过 `python <脚本名>.py <参数>` 运行；如果安装了 GPUMDkit 命令行工具，也可通过 `gpumdkit.sh -<命令> <参数>` 调用（见各脚本的「命令行模式」示例）。

---

## 运行环境与依赖

- **Python 3** 环境
- 大部分脚本依赖 [ASE](https://wiki.fysik.dtu.dk/ase/)：`pip install ase`
- 部分脚本额外依赖：
  - `out2exyz.py`：`numpy`、`tqdm`
  - `pos2lmp.py`：OVITO（`pip install ovito`）
  - `abacus2xyz_scf.py`：读取 `running_scf.log` 时需要 `pip install git+https://gitlab.com/1041176461/ase-abacus.git`
- `.sh` 脚本为 Bash 脚本，需在 Linux / WSL 环境下运行，且依赖 `dos2unix`

---

## 快速命令参考

#### 格式转换类（17 个）

<table align="center">
<tr>
<th align="center">编号</th>
<th align="center">脚本名</th>
<th align="center">所属软件</th>
<th align="center">源格式/输入文件</th>
<th align="center">目标格式/输出文件</th>
<th align="center">gpumdkit 命令用法</th>
<th align="center">Python/Bash 用法</th>
</tr>
<tr>
<td align="center">1</td>
<td align="center">out2xyz.sh</td>
<td align="center" rowspan="7">VASP</td>
<td align="center">OUTCAR<br>（目录）</td>
<td align="center">extxyz<br>（<code>NEPdataset/train.xyz</code>）</td>
<td align="left"><code>gpumdkit.sh -out2xyz &lt;dir&gt;</code></td>
<td align="left"><code>./out2xyz.sh &lt;dir&gt;</code></td>
</tr>
<tr>
<td align="center">2</td>
<td align="center">out2exyz.py</td>
<td align="center">OUTCAR<br>（目录）</td>
<td align="center">extxyz<br>（<code>train.xyz</code>）</td>
<td align="left"><code>gpumdkit.sh -out2exyz &lt;dir&gt;</code></td>
<td align="left"><code>python out2exyz.py &lt;dir&gt;</code></td>
</tr>
<tr>
<td align="center">3</td>
<td align="center">xdatcar2exyz.py</td>
<td align="center">XDATCAR</td>
<td align="center">extxyz</td>
<td align="left"><code>gpumdkit.sh -xdat2exyz &lt;XDATCAR&gt; &lt;xyz&gt;</code></td>
<td align="left"><code>python xdatcar2exyz.py &lt;XDATCAR&gt; &lt;xyz&gt;</code></td>
</tr>
<tr>
<td align="center">4</td>
<td align="center">pos2exyz.py</td>
<td align="center">POSCAR<br>（支持通配符）</td>
<td align="center">extxyz</td>
<td align="left"><code>gpumdkit.sh -pos2exyz &lt;poscar&gt; &lt;xyz&gt;</code></td>
<td align="left"><code>python pos2exyz.py &lt;poscar&gt; &lt;xyz&gt;</code></td>
</tr>
<tr>
<td align="center">5</td>
<td align="center">exyz2pos.py</td>
<td align="center">extxyz<br>（默认 <code>train.xyz</code>）</td>
<td align="center">POSCAR<br>（<code>POSCAR_*.vasp</code>）</td>
<td align="left"><code>gpumdkit.sh -exyz2pos &lt;xyz&gt;</code></td>
<td align="left"><code>python exyz2pos.py [xyz]</code></td>
</tr>
<tr>
<td align="center">6</td>
<td align="center">pos2lmp.py</td>
<td align="center">POSCAR</td>
<td align="center">LAMMPS data</td>
<td align="left"><code>gpumdkit.sh -pos2lmp &lt;poscar&gt; &lt;lmp&gt;</code></td>
<td align="left"><code>python pos2lmp.py &lt;poscar&gt; &lt;lmp&gt;</code></td>
</tr>
<tr>
<td align="center">7</td>
<td align="center">exyz2lmp.py</td>
<td align="center">extxyz</td>
<td align="center">LAMMPS data</td>
<td align="left">无</td>
<td align="left"><code>python exyz2lmp.py &lt;xyz&gt; &lt;lmp&gt;</code></td>
</tr>
<tr>
<td align="center">8</td>
<td align="center">abacus2xyz_md.sh</td>
<td align="center" rowspan="3">ABACUS</td>
<td align="center">MD 轨迹<br>（<code>running_md.log</code> + <code>MD_dump</code>）</td>
<td align="center">extxyz<br>（<code>NEPdataset/train.xyz</code>）</td>
<td align="left">无</td>
<td align="left"><code>./abacus2xyz_md.sh &lt;dir&gt;</code></td>
</tr>
<tr>
<td align="center">9</td>
<td align="center">abacus2xyz_scf.sh</td>
<td align="center">SCF<br>（<code>running_scf.log</code>）</td>
<td align="center">extxyz<br>（<code>NEPdataset/train.xyz</code>）</td>
<td align="left">无</td>
<td align="left"><code>./abacus2xyz_scf.sh &lt;dir&gt;</code></td>
</tr>
<tr>
<td align="center">10</td>
<td align="center">abacus2xyz_scf.py</td>
<td align="center">SCF<br>（<code>running_scf.log</code> / <code>abacus.json</code>）</td>
<td align="center">extxyz</td>
<td align="left">无</td>
<td align="left"><code>python abacus2xyz_scf.py &lt;dir&gt; &lt;xyz&gt;</code></td>
</tr>
<tr>
<td align="center">11</td>
<td align="center">cp2k2xyz.py</td>
<td align="center" rowspan="2">CP2K</td>
<td align="center">pos / frc / cell 文件</td>
<td align="center">XYZ<br>（<code>original.xyz</code> / <code>shifted.xyz</code>）</td>
<td align="left">无</td>
<td align="left"><code>python cp2k2xyz.py [pos] [frc] [cell] [-shifted yes/no]</code></td>
</tr>
<tr>
<td align="center">12</td>
<td align="center">cp2k_log2xyz.py</td>
<td align="center"><code>.log</code> + 结构文件</td>
<td align="center">extxyz<br>（<code>cp2k_exyz.xyz</code>）</td>
<td align="left">无</td>
<td align="left"><code>python cp2k_log2xyz.py</code></td>
</tr>
<tr>
<td align="center">13</td>
<td align="center">lmp2exyz.py</td>
<td align="center">LAMMPS</td>
<td align="center">dump</td>
<td align="center">extxyz<br>（<code>dump.xyz</code>）</td>
<td align="left"><code>gpumdkit.sh -lmp2exyz &lt;dump&gt; &lt;elem1&gt; &lt;elem2&gt; ...</code></td>
<td align="left"><code>python lmp2exyz.py &lt;dump&gt; &lt;elem1&gt; &lt;elem2&gt; ...</code></td>
</tr>
<tr>
<td align="center">14</td>
<td align="center">cif2exyz.py</td>
<td align="center" rowspan="2">CIF</td>
<td align="center">CIF</td>
<td align="center">extxyz</td>
<td align="left"><code>gpumdkit.sh -cif2exyz &lt;cif&gt; &lt;xyz&gt;</code></td>
<td align="left"><code>python cif2exyz.py &lt;cif&gt; &lt;xyz&gt;</code></td>
</tr>
<tr>
<td align="center">15</td>
<td align="center">cif2pos.py</td>
<td align="center">CIF</td>
<td align="center">POSCAR</td>
<td align="left"><code>gpumdkit.sh -cif2pos &lt;cif&gt; &lt;pos&gt;</code></td>
<td align="left"><code>python cif2pos.py &lt;cif&gt; &lt;pos&gt;</code></td>
</tr>
<tr>
<td align="center">16</td>
<td align="center">mtp2xyz.py</td>
<td align="center">MTP</td>
<td align="center">cfg<br>（<code>train.cfg</code>）</td>
<td align="center">extxyz<br>（<code>XYZ/mtp2xyz.xyz</code>）</td>
<td align="left">无</td>
<td align="left"><code>python mtp2xyz.py &lt;cfg&gt; &lt;elem1&gt; &lt;elem2&gt; ...</code></td>
</tr>
<tr>
<td align="center">17</td>
<td align="center">traj2exyz.py</td>
<td align="center">ASE</td>
<td align="center"><code>.traj</code> 轨迹</td>
<td align="center">extxyz</td>
<td align="left">无</td>
<td align="left"><code>python traj2exyz.py &lt;in.traj&gt; &lt;out.xyz&gt;</code></td>
</tr>
</table>

> **注释（针对上表）：括号（ ）内内容的含义**
>
> **输入列（源格式/输入文件）中的括号** —— 说明该参数应传入的内容或取值形式：
> - `（目录）`：参数传**目录路径**，脚本会递归查找该目录下的目标文件（如 `out2xyz.sh` 传入目录后自动查找其中的 OUTCAR），而非直接指定文件本身。
> - `（支持通配符）`：参数支持 `*` 通配符（如 `POSCAR*`），可一次匹配多个文件。
> - `（默认 train.xyz）`：该参数**可省略**，不提供时使用括号内的默认值。
> - `（running_md.log + MD_dump）` 等：脚本实际读取的具体文件名。
>
> **输出列（目标格式/输出文件）中的括号** —— 说明输出的具体文件名/路径或内容：
> - `（NEPdataset/train.xyz）`、`（dump.xyz）` 等：输出文件的具体路径或固定文件名（脚本不会询问，直接写入该位置）。
>
> 括号外的内容表示**文件格式**，括号内的内容表示该格式下的**具体文件名、路径或参数的取值要求**。

#### 数据处理/后处理类（6 个）

<table align="center">
<tr>
<th align="center">编号</th>
<th align="center">脚本名</th>
<th align="center">功能概括</th>
<th align="center">输入文件</th>
<th align="center">输出文件</th>
<th align="center">gpumdkit 命令用法</th>
<th align="center">Python/Bash 用法</th>
</tr>
<tr>
<td align="center">18</td>
<td align="center">add_groups.py</td>
<td align="center">按元素顺序添加 group 分组标签</td>
<td align="center">结构文件<br>（POSCAR / xyz）</td>
<td align="center"><code>model.xyz</code><br>（含 group 标签）</td>
<td align="left"><code>gpumdkit.sh -addgroup &lt;poscar&gt; &lt;elem1&gt; &lt;elem2&gt; ...</code></td>
<td align="left"><code>python add_groups.py &lt;file&gt; &lt;elem1&gt; &lt;elem2&gt; ...</code></td>
</tr>
<tr>
<td align="center">19</td>
<td align="center">add_weight.py</td>
<td align="center">为所有结构统一设置 Weight 权重值</td>
<td align="center">结构文件<br>（如 <code>train.xyz</code>）</td>
<td align="center">结构文件<br>（含新 Weight）</td>
<td align="left"><code>gpumdkit.sh -addweight &lt;in&gt; &lt;out&gt; &lt;weight&gt;</code></td>
<td align="left"><code>python add_weight.py &lt;in&gt; &lt;out&gt; &lt;weight&gt;</code></td>
</tr>
<tr>
<td align="center">20</td>
<td align="center">clean_xyz.py</td>
<td align="center">删除应力/virial/力信息，仅保留结构</td>
<td align="center">extxyz<br>（含应力/力）</td>
<td align="center">清洗后的 extxyz</td>
<td align="left">无</td>
<td align="left"><code>python clean_xyz.py &lt;in.xyz&gt; &lt;out.xyz&gt;</code></td>
</tr>
<tr>
<td align="center">21</td>
<td align="center">get_frame.py</td>
<td align="center">按帧号提取单帧</td>
<td align="center">extxyz 轨迹</td>
<td align="center"><code>frame_&lt;N&gt;.xyz</code></td>
<td align="left"><code>gpumdkit.sh -get_frame &lt;xyz&gt; &lt;index&gt;</code></td>
<td align="left"><code>python get_frame.py &lt;xyz&gt; &lt;frame_number&gt;</code></td>
</tr>
<tr>
<td align="center">22</td>
<td align="center">split_single_xyz.py</td>
<td align="center">拆分多帧为单帧文件</td>
<td align="center">多帧 XYZ</td>
<td align="center"><code>model_*.xyz</code></td>
<td align="left">无</td>
<td align="left"><code>python split_single_xyz.py &lt;xyz&gt;</code></td>
</tr>
<tr>
<td align="center">23</td>
<td align="center">replicate.py</td>
<td align="center">复制晶胞生成超胞<br>（指定倍数 a b c 或目标原子数）</td>
<td align="center">POSCAR / xyz 结构</td>
<td align="center">超胞结构</td>
<td align="left"><code>gpumdkit.sh -replicate &lt;in&gt; &lt;out&gt; &lt;a&gt; &lt;b&gt; &lt;c&gt;</code> 或 <code>-replicate &lt;in&gt; &lt;out&gt; &lt;num&gt;</code></td>
<td align="left"><code>python replicate.py &lt;in&gt; &lt;out&gt; &lt;a&gt; &lt;b&gt; &lt;c&gt;</code> 或 <code>&lt;in&gt; &lt;out&gt; &lt;num&gt;</code></td>
</tr>
</table>

---

## 脚本详细说明

### 一、VASP 相关转换

---

#### 1. out2xyz.sh —— 批量转换 OUTCAR 为 extxyz（Shell 版）

将指定目录下（递归）所有**已收敛**的 VASP `OUTCAR` 文件转换为 extxyz 格式，用于 NEP 训练。脚本会自动判断每个计算是否收敛：`NSW != 0` 视为收敛；`NSW == 0` 时检查是否达到 EDIFF 收敛条件。未收敛的 OUTCAR 路径会被写入 `non_converged_files.txt`，不会参与转换。

**用法**

```bash
./out2xyz.sh <dire_name>
```

**参数**

- `<dire_name>`：包含 OUTCAR 文件的目录（会递归查找）

**输出**

- `NEPdataset/train.xyz`：转换后的 extxyz 数据集
- `non_converged_files.txt`：未收敛的 OUTCAR 文件列表

**脚本内部可调参数**（位于脚本头部）：

| 变量 | 默认值 | 含义 |
|------|--------|------|
| `isol_ener` | 0 | 每个原子的能量平移量（用于能量对齐） |
| `viri_logi` | 1 | 是否输出 virial（1=输出，0=不输出） |

**示例**

```bash
./out2xyz.sh ./vasp_calcs
```

---

#### 2. out2exyz.py —— 批量转换 OUTCAR 为 extxyz（Python 版）

将指定目录下（递归）所有已收敛的 VASP `OUTCAR` 文件转换为 extxyz 格式，包含能量、力、应力和 virial 信息（能量取自由能 free_energy，应力转换为 virial）。

**用法**

```bash
python out2exyz.py <directory>
```

**参数**

- `<directory>`：包含 OUTCAR 文件的目录（会递归查找）

**输出**

- `train.xyz`：转换后的 extxyz 数据集

**依赖**：`ase`、`numpy`、`tqdm`

**示例**

```bash
python out2exyz.py ./vasp_calcs
```

---

#### 3. xdatcar2exyz.py —— XDATCAR 转 extxyz

使用 ASE 将 VASP `XDATCAR` 轨迹文件（含所有帧）转换为 extxyz 格式。

**用法**

```bash
python xdatcar2exyz.py <XDATCAR> <output.xyz>
```

**参数**

- `<XDATCAR>`：输入的 XDATCAR 文件路径
- `<output.xyz>`：输出的 extxyz 文件路径

**示例**

```bash
python xdatcar2exyz.py XDATCAR dump.xyz
```

---

#### 4. pos2exyz.py —— POSCAR 转 extxyz

将一个或多个 VASP `POSCAR` 文件转换为 extxyz 格式。第一个参数支持通配符模式（如 `POSCAR*`），可一次转换多个文件；多帧 POSCAR 也会被全部保留。

**用法**

```bash
python pos2exyz.py <POSCAR> <output.xyz>
```

**参数**

- `<POSCAR>`：输入 POSCAR 文件路径或通配符模式（如 `POSCAR*`）
- `<output.xyz>`：输出的 extxyz 文件路径

**示例**

```bash
# 单个文件
python pos2exyz.py POSCAR model.xyz

# 通配符批量转换
python pos2exyz.py 'POSCAR*' train.xyz

# 命令行模式
gpumdkit.sh -pos2exyz POSCAR model.xyz
```

---

#### 5. exyz2pos.py —— extxyz 转 POSCAR

将 extxyz 文件中的**每一帧**分别写出为一个 POSCAR 文件。

**用法**

```bash
python exyz2pos.py [extxyz_file]
```

**参数**

- `[extxyz_file]`：输入的 extxyz 文件（可选，默认 `train.xyz`）

**输出**

- `POSCAR_1.vasp`、`POSCAR_2.vasp`、……（每帧一个文件，序号从 1 开始）

**示例**

```bash
python exyz2pos.py structs.xyz
gpumdkit.sh -exyz2pos structs.xyz
```

---

#### 6. pos2lmp.py —— POSCAR 转 LAMMPS data

使用 OVITO 将 VASP `POSCAR` 文件转换为 LAMMPS data 格式。

**用法**

```bash
python pos2lmp.py <poscar_file> <lammps_data_file>
```

**参数**

- `<poscar_file>`：输入的 POSCAR 文件路径
- `<lammps_data_file>`：输出的 LAMMPS data 文件路径

**依赖**：OVITO（`pip install ovito`）

**示例**

```bash
python pos2lmp.py POSCAR lammps.data
gpumdkit.sh -pos2lmp POSCAR lammps.data
```

---

#### 7. exyz2lmp.py —— extxyz 转 LAMMPS data

将 extxyz 文件转换为 LAMMPS data 格式，自动按元素种类映射原子类型（type），并写出盒子尺寸（含 tilt 因子 xy/xz/yz）和质量（Masses）信息。

**用法**

```bash
python exyz2lmp.py <extxyz_file> <lammps_data_file>
```

**参数**

- `<extxyz_file>`：输入的 extxyz 文件路径
- `<lammps_data_file>`：输出的 LAMMPS data 文件路径

**示例**

```bash
python exyz2lmp.py model.xyz lammps.data
```

---

### 二、ABACUS 相关转换

---

#### 8. abacus2xyz_md.sh —— ABACUS MD 轨迹转 extxyz

将 ABACUS 分子动力学（MD）输出文件 `running_md.log` 和 `MD_dump` 转换为 extxyz 格式，用于 NEP 训练。脚本会读取 MD 每一步的总能量（etot）、晶格矢量（LATTICE_VECTORS）、原子坐标与力，并计算 virial（kbar 转 eV）。会自动跳过 SCF 未收敛的 MD 步。

**用法**

```bash
./abacus2xyz_md.sh <dire_name>
```

**参数**

- `<dire_name>`：包含 `running_md.log`、`MD_dump` 和 `INPUT` 文件的目录（通常为 ABACUS 计算目录，`INPUT` 用于读取 `scf_nmax`）

**输出**

- `NEPdataset/train.xyz`：转换后的 extxyz 数据集

**脚本内部可调参数**（位于脚本头部）：

| 变量 | 默认值 | 含义 |
|------|--------|------|
| `isol_ener` | 0 | 每个原子的能量平移量 |
| `viri_logi` | 1 | 是否输出 virial（1=输出，0=不输出） |

**示例**

```bash
./abacus2xyz_md.sh ./abacus_md_dir
```

---

#### 9. abacus2xyz_scf.sh —— ABACUS SCF 结果转 extxyz（Shell 版）

将指定目录下（递归）所有 ABACUS 自洽计算（SCF）的 `running_scf.log` 转换为 extxyz 格式，用于 NEP 训练。自动跳过未完成或未收敛的计算（SCF 迭代次数达到 `scf_nmax` 或缺少 `FINAL_ETOT_IS`）。

**用法**

```bash
./abacus2xyz_scf.sh <dire_name>
```

**参数**

- `<dire_name>`：包含 `running_scf.log` 的目录（会递归查找）

**输出**

- `NEPdataset/train.xyz`：转换后的 extxyz 数据集

**说明**

- 若已安装 ASE，则从 `STRU.cif` 读取原子坐标和晶格；否则从 `STRU` / `INPUT` 解析
- 若 log 中有 `TOTAL-STRESS`，自动计算 virial；否则警告并仅输出能量/力

**示例**

```bash
./abacus2xyz_scf.sh ./scf_calcs
```

---

#### 10. abacus2xyz_scf.py —— ABACUS SCF 结果转 extxyz（Python 版）

将指定目录下（递归）所有 ABACUS 自洽计算的输出转换为 extxyz 格式。支持两种输入来源：`running_scf.log`（需 ase-abacus 扩展）或 `abacus.json`。自动跳过未收敛（SCF 次数达到 `scf_nmax`）或未完成的计算；若未计算应力则给出提示。

**用法**

```bash
python abacus2xyz_scf.py <dir> <extxyz>
```

**参数**

- `<dir>`：包含 ABACUS SCF 输出的根目录（递归查找 `running_scf.log` 或 `abacus.json`）
- `<extxyz>`：输出的 extxyz 文件路径

**依赖**：`ase`、`numpy`；读取 `running_scf.log` 需额外安装：
`pip install git+https://gitlab.com/1041176461/ase-abacus.git`

**示例**

```bash
python abacus2xyz_scf.py ./scf_calcs train.xyz
```

---

### 三、CP2K 相关转换

---

#### 11. cp2k2xyz.py —— 合并 CP2K AIMD 输出为 XYZ

将 CP2K AIMD 分别输出的位置文件（`*-pos-1*`）、力文件（`*-frc-1*`）和盒子文件（`*.cell`）合并为一个 XYZ 文件（含能量、力、晶格）。可选通过最小二乘拟合对各元素进行能量平移（`-shifted yes`），使平均总能归零，用于 NEP 训练前的能量对齐。

**用法**

```bash
python cp2k2xyz.py [pos.xyz] [frc.xyz] [cell.cell] [-shifted yes/no]
```

**参数**

- `[pos.xyz]`：CP2K 位置输出文件（可选，缺省时自动查找 `*-pos-1*`）
- `[frc.xyz]`：CP2K 力输出文件（可选，缺省时自动查找 `*-frc-1*`）
- `[cell.cell]`：CP2K 盒子文件（可选，缺省时自动查找 `*.cell`）
- `-shifted yes/no`：是否进行能量平移（默认 `no`）

**输出**

- `original.xyz`：原始数据转换结果（总是生成）
- `shifted.xyz`：能量平移后的结果（仅当 `-shifted yes` 时生成）

**单位换算**：能量 Hartree → eV（×27.211386245988）；力 a.u. → eV/Å（×51.4220674763259）

**示例**

```bash
# 自动查找默认文件名
python cp2k2xyz.py

# 显式指定文件并做能量平移
python cp2k2xyz.py pos.xyz frc.xyz cell.cell -shifted yes
```

---

#### 12. cp2k_log2xyz.py —— CP2K log 转 extxyz

在当前目录及其子目录中递归查找所有 CP2K 输出文件（`.log`），结合同目录下的结构文件（`.xyz` 或 `.inp` 中的 `&COORD` / `&CELL` 段），转换为包含能量、力和 virial 的 extxyz 格式。兼容新旧版 CP2K 日志格式（包括 CP2K 2025+ 的新格式）。

**用法**（无参数，直接运行）

```bash
python cp2k_log2xyz.py
```

**输入**

- 当前目录及子目录中的所有 `*.log` 文件（每个子目录视为一个计算任务）
- 每个子目录中需有 `.xyz` 或 `.inp` 结构文件；优先使用 `cp2k.log`，否则取第一个 `.log`

**输出**

- `cp2k_exyz.xyz`：转换后的 extxyz 轨迹
- `Logfile.txt`：处理摘要（单位换算常数、成功/失败统计、警告与失败原因）

**示例**

```bash
python cp2k_log2xyz.py
```

---

### 四、LAMMPS 相关转换

---

#### 13. lmp2exyz.py —— LAMMPS dump 转 extxyz

将 LAMMPS dump 轨迹文件（text 格式）转换为 extxyz 格式。dump 中的原子类型（type 1, 2, 3, …）按参数中给出的元素顺序映射为真实元素符号。

**用法**

```bash
python lmp2exyz.py <dump_file> <element1> <element2> ...
```

**参数**

- `<dump_file>`：输入的 LAMMPS dump 文件路径
- `<element1> <element2> ...`：按原子类型顺序给出的元素符号列表（type 1 → 第 1 个元素，依次类推）

**输出**

- `dump.xyz`：转换后的 extxyz 文件（固定输出名）

**示例**

```bash
python lmp2exyz.py dump.data Li Y Cl
gpumdkit.sh -lmp2exyz dump.data Li Y Cl
```

---

### 五、CIF 相关转换

---

#### 14. cif2exyz.py —— CIF 转 extxyz

使用 ASE 将 CIF 晶体结构文件转换为 extxyz 格式，并清理 ASE 写入的额外字段（spacegroup、unit_cell、occupancy、spacegroup_kinds）。

**用法**

```bash
python cif2exyz.py <input.cif> <output.xyz>
```

**参数**

- `<input.cif>`：输入的 CIF 文件路径
- `<output.xyz>`：输出的 extxyz 文件路径

**示例**

```bash
python cif2exyz.py struct.cif struct.xyz
gpumdkit.sh -cif2exyz struct.cif struct.xyz
```

---

#### 15. cif2pos.py —— CIF 转 POSCAR

使用 ASE 将 CIF 晶体结构文件转换为 VASP POSCAR 格式（VASP5 格式，直接坐标 direct）。

**用法**

```bash
python cif2pos.py <input.cif> <output.vasp>
```

**参数**

- `<input.cif>`：输入的 CIF 文件路径
- `<output.vasp>`：输出的 POSCAR 文件路径

**示例**

```bash
python cif2pos.py struct.cif POSCAR
gpumdkit.sh -cif2pos struct.cif POSCAR
```

---

### 六、其他格式转换

---

#### 16. mtp2xyz.py —— MTP 训练数据转 extxyz

将 MTP（Machine Learning Interatomic Potential，机器学习原子间势）训练数据文件（`train.cfg`）解析并转换为 extxyz 格式，包含能量、力、virial 信息。元素类型（type）按命令行参数顺序映射为元素符号。

**用法**

```bash
python mtp2xyz.py <train.cfg> <Symbol1> <Symbol2> ...
```

**参数**

- `<train.cfg>`：MTP 训练数据文件（`BEGIN_CFG` / `END_CFG` 格式）
- `<Symbol1> <Symbol2> ...`：按 type 顺序给出的元素符号（type 0 → 第 1 个元素，依次类推）

**输出**

- `XYZ/mtp2xyz.xyz`：转换后的 extxyz 文件

**示例**

```bash
python mtp2xyz.py train.cfg Li Y Cl
```

---

#### 17. traj2exyz.py —— ASE 轨迹转 extxyz

将 ASE 的 `.traj` 轨迹文件（可含多帧）转换为 extxyz 格式。

**用法**

```bash
python traj2exyz.py <input.traj> <output.xyz>
```

**参数**

- `<input.traj>`：输入的 ASE 轨迹文件
- `<output.xyz>`：输出的 extxyz 文件

**示例**

```bash
python traj2exyz.py md.traj md.xyz
```

---

### 七、数据处理与后处理工具

---

#### 18. add_groups.py —— 添加分组（group）标签

根据元素类型为结构中的原子添加分组信息（`group` 数组），输出到 `model.xyz`。**注意：输入结构中出现的所有元素都必须包含在参数列表中，否则脚本报错。**

**用法**

```bash
python add_groups.py <filename> <Symbol1> <Symbol2> ...
```

**参数**

- `<filename>`：输入结构文件（如 POSCAR 或 extxyz，ASE 自动识别格式）
- `<Symbol1> <Symbol2> ...`：按顺序给出的元素符号列表，元素的 group 编号即其在列表中的顺序（从 0 开始）

**输出**

- `model.xyz`：带 group 标签的结构文件

**示例**

```bash
python add_groups.py POSCAR Li Y Cl
gpumdkit.sh -addgroup POSCAR Li Y Cl
```

上例中 Li、Y、Cl 的 group 编号分别为 0、1、2，结果保存到 `model.xyz`。

---

#### 19. add_weight.py —— 添加权重（weight）标签

为输入文件中**所有结构**设置统一的 `Weight` 值（覆盖原有值），并写出到新文件。常用于 NEP 训练前调整不同数据集的权重。

**用法**

```bash
python add_weight.py <input_file> <output_file> <new_weight>
```

**参数**

- `<input_file>`：输入结构文件（如 `train.xyz`）
- `<output_file>`：输出结构文件（如 `train_weighted.xyz`）
- `<new_weight>`：要设置的权重数值（浮点数）

**示例**

```bash
python add_weight.py train.xyz train_weighted.xyz 5
gpumdkit.sh -addweight train.xyz train_weighted.xyz 5
```

---

#### 20. clean_xyz.py —— 清洗 extxyz 训练数据

从 extxyz 训练文件中移除应力（stress）、virial 和力（force）信息，只保留结构信息（晶格 + 原子坐标），适用于只关心结构、不需要标签数据的场景。

**用法**

```bash
python clean_xyz.py <input.xyz> <output.xyz>
```

**参数**

- `<input.xyz>`：输入的 extxyz 训练文件（可含多帧）
- `<output.xyz>`：输出的清洗后 extxyz 文件

**示例**

```bash
python clean_xyz.py train.xyz clean.xyz
```

---

#### 21. get_frame.py —— 提取指定帧

从多帧 extxyz 轨迹中按帧号提取单帧，写出到 `frame_<N>.xyz`。帧号从 **1** 开始计数；超出范围时报错。

**用法**

```bash
python get_frame.py <extxyz_file> <frame_number>
```

**参数**

- `<extxyz_file>`：输入的 extxyz 轨迹文件
- `<frame_number>`：要提取的帧号（1 起始）

**输出**

- `frame_<N>.xyz`：提取的单帧文件

**示例**

```bash
python get_frame.py dump.xyz 1000
gpumdkit.sh -get_frame dump.xyz 1000
```

---

#### 22. split_single_xyz.py —— 拆分多帧 XYZ

将多帧 XYZ 文件按帧拆分为独立的单帧文件，每帧一个文件。

**用法**

```bash
python split_single_xyz.py <input.xyz>
```

**参数**

- `<input.xyz>`：输入的多帧 XYZ 文件

**输出**

- `model_1.xyz`、`model_2.xyz`、……（每帧一个文件，序号从 1 开始）

**示例**

```bash
python split_single_xyz.py train.xyz
```

---

#### 23. replicate.py —— 超胞复制

将输入结构沿晶格方向复制生成超胞。支持两种模式：直接指定各方向复制倍数，或指定目标原子数（自动寻找最接近且晶胞形状最方正的复制方案）。

**用法**

```bash
# 模式一：指定复制倍数 a b c
python replicate.py <input> <output> <a> <b> <c>

# 模式二：指定目标原子数
python replicate.py <input> <output> <target_num>
```

**参数**

- `<input>`：输入结构文件（`.vasp` / `.poscar` / `.xyz`，格式由扩展名自动推断）
- `<output>`：输出超胞文件
- `<a> <b> <c>`：沿 a、b、c 三个方向的复制倍数（正整数）
- `<target_num>`：目标原子总数，脚本会找到最接近该原子数且三个方向长度最均衡的超胞

**说明**

- 模式二中，若目标原子数小于原胞原子数，则返回 1×1×1（警告提示）
- 输出的原子会按输入文件中的元素顺序重新排列（物种分组）

**示例**

```bash
# 2×2×2 超胞
python replicate.py input.vasp output.vasp 2 2 2

# 目标原子数为 1000
python replicate.py input.vasp output.vasp 1000
```

---

## 注意事项

1. **收敛性检查**：`out2xyz.sh`、`out2exyz.py`、`abacus2xyz_*.sh`、`abacus2xyz_scf.py` 会自动跳过未收敛或未完成的计算，转换前请确认计算已正常结束。
2. **元素映射**：`lmp2exyz.py` 和 `mtp2xyz.py` 中，元素符号参数必须与文件内的原子类型编号顺序严格一致，否则元素会对应错误。
3. **固定输出名**：部分脚本使用固定输出文件名（如 `train.xyz`、`dump.xyz`、`model.xyz`），运行前请注意备份同名文件。
4. **Windows 用户**：`.sh` 脚本请在 WSL / Linux 环境中运行；`.py` 脚本在安装好依赖后可直接运行。
5. **`修改脚本/` 目录**：该目录当前为空，可放置个人修改或备用脚本。

---

## 贡献指南

如需添加新的格式转换器：

1. **命名规范**：`<源格式>2<目标格式>.py`
2. **错误处理**：处理前先校验输入格式
3. **文档**：在本文档中补充用法说明
4. **命令行入口**：如有需要，在 `gpumdkit.sh` 中添加对应的命令行参数

详细指南请参阅 [CONTRIBUTING.md](../../CONTRIBUTING.md)。

---

感谢使用 GPUMDkit！如对格式转换有任何疑问，欢迎在 [GitHub 仓库](https://github.com/zhyan0603/GPUMDkit/issues) 提交 Issue，或联系 Zihan YAN（yanzihan@westlake.edu.cn）。
