#!/bin/bash
# =============================================================================
# 脚本:        3batch_submit.sh
# 分类:        Slurm 批量作业提交脚本 (batch_scf 工作流第 3 步；模式可配置复用)
# 功能:        扫描当前目录下所有 FOLDER_PATTERN 匹配的任务文件夹 (默认
#              [0-9]*，可改为 1_md* 用于 GPUMD 流程)，筛选不存在 *.log 日志
#              的任务目录，按名称从小到大顺序逐批 sbatch 提交 JOB_SCRIPT
#              匹配的脚本 (默认 sub_*.sh)；每次提交前检测目录文件完整性
#              (INCAR、POSCAR、POTCAR、提交脚本必需，KPOINTS 可选)，不完整
#              则跳过；按 MAX_TOTAL_JOBS 与 BATCH_SIZE 控制提交速率，队列
#              满员时指数退避轮询 (MIN_WAIT_SEC 起步，最长 MAX_WAIT_SEC)，
#              等待时提示已提交进度 (最近提交的文件夹与作业 ID)，有空位
#              立即快速补位。
#              自动后台运行：直接执行 ./3batch_submit.sh 等价于
#              nohup ./3batch_submit.sh > submit.log 2>&1
# 使用方法:    ./3batch_submit.sh
# 参数:        无参数；BATCH_SIZE 等可改配置区
# 运行环境:    需放在包含众多任务子文件夹 (默认 1/、2/、...) 的父目录中
#              运行；在 Slurm 登录节点执行
# 输出:
#   submit.log            【批量脚本日志】3batch_submit.sh 自身运行日志，父目录仅生成一份
#   各任务子目录生成 %j.log 【子任务日志】由提交脚本的 --output=%j.log 生成
# 防重复运行:  .batch_submit.lock 记录后台进程 PID，检测到已在运行直接拒绝
#              (终端会提示查看/终止方式)；全部提交完成后生成完成标记
#              .batch_submit.done，此后再次运行会被拒绝 (第二次、第三次...均
#              退出)，如需重新提交先手动删除标记文件 (rm .batch_submit.done)
# 作者:        隼蝶.
# 最后修改日期: 2026-08-24
# =============================================================================

# ============ 配置区 (可按需调整) ============
FOLDER_PATTERN="[0-9]*"  # 目标文件夹模式 (VASP: "[0-9]*"；GPUMD: "1_md*")
JOB_SCRIPT="sub*.sh"     # 各文件夹内的作业提交脚本 (VASP: sub2.sh；GPUMD: sub_MD.sh)，目录内只能存在一个匹配脚本
BATCH_SIZE=9        # 每批最多提交数量
MAX_TOTAL_JOBS=18   # 集群上允许的最大总任务数 (R+PD 全部算)
MIN_WAIT_SEC=60     # 最短轮询间隔 (秒)：队列有空位时快速补位
MAX_WAIT_SEC=120    # 最长轮询间隔 (秒)：满员时指数退避上限 (=2 分钟)
DONE_FILE=".batch_submit.done"  # 完成标记文件 (全部提交完成后创建)
# ==============================================

# # 目录树示例:
# # ============================================================================
# # .
# # ├── task_parent/              # 3batch_submit.sh 运行所在父目录
# # │   ├── 1/                    # 单任务数字子文件夹
# # │   │   ├── INCAR             # VASP 输入 (必需)
# # │   │   ├── POSCAR
# # │   │   ├── POTCAR
# # │   │   ├── KPOINTS           # 可选
# # │   │   ├── sub2.sh
# # │   │   └── ${JOBID}.log      # 【子任务日志】sub2.sh 中 --output=%j.log 生成
# # │   ├── 2/
# # │   │   └── ...
# # │   └── ...
# # ├── 3batch_submit.sh
# # └── submit.log                # 【批量脚本日志】3batch_submit.sh 自身 nohup 输出
# # ============================================================================

############## 新增：自动后台 nohup + 防重复运行逻辑 ##############
LOCK_FILE="./.batch_submit.lock"

# 判断是否已经进入 nohup 后台子进程
if [[ ! "$NOHUP_INNER" == "1" ]]; then
    # 检测是否已有正在运行的实例
    if [ -f "$LOCK_FILE" ]; then
        old_pid=$(cat "$LOCK_FILE")
        if ps -p "$old_pid" > /dev/null 2>&1; then
            echo "❌ 检测到脚本已在后台运行，PID: ${old_pid}"
            echo "----------------------------------------"
            echo "查看实时日志：tail -f submit.log"
            echo "查看进程状态：ps aux | grep batch_submit.sh"
            echo "终止后台脚本：kill -9 ${old_pid}"
            echo "----------------------------------------"
            exit 1
        else
            # lock 文件存在但进程已死亡，清理旧锁
            rm -f "$LOCK_FILE"
        fi
    fi

    export NOHUP_INNER=1
    # readlink -f 解析绝对路径 + bash 显式调用，避免 $0 不带 ./ 时 nohup 在 PATH 中找不到脚本
    nohup bash "$(readlink -f "$0")" "$@" > submit.log 2>&1 &
    new_pid=$!
    echo "${new_pid}" > "$LOCK_FILE"
    echo "✅脚本已后台启动，日志输出到 submit.log"
    echo "PID: ${new_pid}"
    echo "----------------------------------------"
    echo "查看实时日志：tail -f submit.log"
    echo "查看进程状态：ps aux | grep batch_submit.sh"
    echo "终止后台脚本：kill -9 ${new_pid}"
    echo "----------------------------------------"
    exit 0
fi

# ============ 后台进程（NOHUP_INNER=1）：日志开头输出与终端一致的启动提示 ============
# $$ 即后台进程自身 PID，与前台终端打印的 new_pid 相同（bash 直接执行不 fork）
if [[ "$NOHUP_INNER" == "1" ]]; then
    echo "=========================================="
    echo "✅脚本已后台启动，日志输出到 submit.log"
    echo "PID: $$"
    echo "----------------------------------------"
    echo "查看实时日志：tail -f submit.log"
    echo "查看进程状态：ps aux | grep batch_submit.sh"
    echo "终止后台脚本：kill -9 $$"
    echo "----------------------------------------"
fi

# 脚本正常退出时自动删除锁文件
trap 'rm -f "$LOCK_FILE"' EXIT
####################################################

# ============ 环境准备区 ============
# 依赖检查: sbatch 必须可用
if ! command -v sbatch >/dev/null 2>&1; then
    echo "❌ 错误：未找到 sbatch 命令，请在 Slurm 登录节点运行。"
    exit 1
fi

# 防重复运行: 已有完成标记则拒绝执行
if [ -f "$DONE_FILE" ]; then
    echo "❌ 本脚本已完成批量提交，禁止重复运行。"
    echo "如需重新提交，请先删除完成标记：rm $DONE_FILE"
    exit 1
fi

# 前置校验: 当前目录必须存在 FOLDER_PATTERN 匹配的任务文件夹
if ! ls -d $FOLDER_PATTERN/ >/dev/null 2>&1; then
    echo "❌ 错误：当前目录未找到 $FOLDER_PATTERN 文件夹！"
    echo "请将 3batch_submit.sh 放在任务父目录（含 $FOLDER_PATTERN 子文件夹）中运行。"
    echo "当前目录内容如下，请核对是否运行在任务父目录："
    ls -la
    exit 1
fi
# ====================================

# ============ 函数配置区 ============
# 检查任务目录文件是否完整: INCAR、POSCAR、POTCAR 必需，提交脚本 (JOB_SCRIPT 通配) 需存在，KPOINTS 可选
check_files() {
    local dir="$1"
    for f in INCAR POSCAR POTCAR; do
        if [ ! -f "${dir}/${f}" ]; then
            return 1
        fi
    done
    if ! ls "${dir}"/$JOB_SCRIPT >/dev/null 2>&1; then
        return 1
    fi
    return 0
}
# ====================================

# ============ 主流程 ============
# 收集无 log 的任务目录并按名称排序
task_list=()
for dir in $FOLDER_PATTERN/; do
    [ -d "$dir" ] || continue
    if ! ls "$dir"/*.log >/dev/null 2>&1; then
        task_list+=("${dir%/}")
    fi
done
task_list=($(printf '%s\n' "${task_list[@]}" | sort -V))

total=${#task_list[@]}
echo "无 log、待提交目录总数：$total"

index=0
first_batch=1   # 首次提交标记: 第一轮允许按 MAX_TOTAL_JOBS 全量提交
wait_seconds=$MIN_WAIT_SEC   # 当前轮询间隔 (秒)
last_dir=""     # 最近一次成功提交的任务文件夹（满员等待时提示进度）
last_jobid=""   # 最近一次成功提交的作业 ID

while [ $index -lt $total ]; do
    echo
    echo "=================================================="
    date
    echo "=================================================="

    # 统计当前总任务数 (R+PD 全部算)
    total_jobs=$(squeue -u $USER -h | wc -l)
    echo "当前总任务数：$total_jobs / $MAX_TOTAL_JOBS"

    # 队列满员: 指数退避等待，并提示已提交进度（上一轮最后提交的文件夹与作业 ID）
    if [ "$total_jobs" -ge "$MAX_TOTAL_JOBS" ]; then
        echo "任务已满"
        if [ -n "$last_dir" ]; then
            echo "目前已提交到文件夹${last_dir}"
            echo "作业ID：${last_jobid}"
        fi
        echo "等待 ${wait_seconds} 秒后重试..."
        sleep $wait_seconds
        wait_seconds=$((wait_seconds * 2))
        if [ "$wait_seconds" -gt "$MAX_WAIT_SEC" ]; then
            wait_seconds=$MAX_WAIT_SEC
        fi
        continue
    fi

    # 本轮可提交数量: 首轮全量，后续每轮最多 BATCH_SIZE
    can_submit=$((MAX_TOTAL_JOBS - total_jobs))
    if [ "$first_batch" -eq 0 ] && [ "$can_submit" -gt "$BATCH_SIZE" ]; then
        can_submit=$BATCH_SIZE
    fi

    # 队列有空位: 重置为最短间隔，及时抓住陆续出现的空位
    wait_seconds=$MIN_WAIT_SEC

    echo "本轮最多可提交：$can_submit"
    submitted=0

    while [ $submitted -lt $can_submit ] && [ $index -lt $total ]; do
        dir="${task_list[$index]}"
        index=$((index + 1))

        # 提交前检测文件完整性，不完整则跳过
        if ! check_files "$dir"; then
            echo "⚠️ 跳过：${dir} 文件不完整（需要 INCAR、POSCAR、POTCAR、$JOB_SCRIPT，KPOINTS 可选）"
            continue
        fi

        echo "提交：$dir"
        # 捕获 sbatch 输出提取作业 ID（输出形如: Submitted batch job 35752356）
        # JOB_SCRIPT 为通配符，不加引号以展开实际脚本名 (sub2.sh / sub_MD.sh)
        job_output=$(cd "$dir" && sbatch $JOB_SCRIPT 2>&1)
        echo "$job_output"
        jobid=$(echo "$job_output" | awk '/Submitted batch job/ {id=$NF} END {print id}')
        if [ -n "$jobid" ]; then
            last_dir="$dir"
            last_jobid="$jobid"
        fi
        submitted=$((submitted + 1))
        sleep 1
    done

    # 本轮有实际提交则取消首轮标记，后续轮次严格限流
    if [ "$submitted" -gt 0 ]; then
        first_batch=0
    fi

    echo "本轮提交：$submitted 个，等待 ${wait_seconds} 秒后再次检查..."
    sleep $wait_seconds
done

# 创建完成标记，禁止重复运行
touch "$DONE_FILE"
echo
echo "🎉 所有无 log 目录提交完成！"
echo "ℹ️ 已创建完成标记 $DONE_FILE，再次运行本脚本将被拒绝。"
