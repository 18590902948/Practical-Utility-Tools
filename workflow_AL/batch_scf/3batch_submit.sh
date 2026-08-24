#!/bin/bash
# =============================================================================
# 脚本:        3batch_submit.sh
# 分类:        Slurm 批量作业提交脚本 (batch_scf 工作流第 3 步)
# 功能:        扫描当前目录下所有数字命名子文件夹，筛选不存在 *.log 日志的
#              任务目录，按数字从小到大顺序逐批 sbatch 提交 sub2.sh；每次
#              提交前检测目录文件完整性 (INCAR、POSCAR、POTCAR、*.sh 必需，
#              KPOINTS 可选)，不完整则跳过；按 MAX_TOTAL_JOBS 与 BATCH_SIZE
#              控制提交速率，队列满员时指数退避轮询 (MIN_WAIT_SEC 起步，
#              最长 MAX_WAIT_SEC)，有空位立即快速补位。
# 使用方法:    ./3batch_submit.sh
# 参数:        无参数；BATCH_SIZE 等可改配置区
# 运行环境:    需放在包含众多数字子文件夹 (如 1/、2/、...) 的任务父目录中
#              运行；在 Slurm 登录节点执行
# 输出:        终端实时打印提交进度；各任务目录的 %j.log 由 sub2.sh 生成
# 防重复运行:  全部提交完成后生成完成标记 .batch_submit.done；此后再次运行
#              会被拒绝 (第二次、第三次...均退出)，如需重新提交先手动删除
#              标记文件 (rm .batch_submit.done)
# 作者:        Hongbo Sun
# 最后修改日期: 2026-08-24
# =============================================================================

# ============ 配置区 (可按需调整) ============
BATCH_SIZE=9        # 每批最多提交数量
MAX_TOTAL_JOBS=18   # 集群上允许的最大总任务数 (R+PD 全部算)
MIN_WAIT_SEC=60     # 最短轮询间隔 (秒)：队列有空位时快速补位
MAX_WAIT_SEC=900    # 最长轮询间隔 (秒)：满员时指数退避上限 (=15 分钟)
DONE_FILE=".batch_submit.done"  # 完成标记文件 (全部提交完成后创建)
# ==============================================

# ============ 环境准备区 ============
# 依赖检查: sbatch 必须可用
if ! command -v sbatch >/dev/null 2>&1; then
    echo "❌ 错误: 未找到 sbatch 命令，请在 Slurm 登录节点运行。"
    exit 1
fi

# 防重复运行: 已有完成标记则拒绝执行
if [ -f "$DONE_FILE" ]; then
    echo "❌ 本脚本已完成批量提交，禁止重复运行。"
    echo "如需重新提交，请先删除完成标记: rm $DONE_FILE"
    exit 1
fi

# 前置校验: 当前目录必须存在数字命名的子任务文件夹
if ! ls -d [0-9]*/ >/dev/null 2>&1; then
    echo "❌ 错误: 当前目录未找到数字命名的子任务文件夹！"
    echo "请将 3batch_submit.sh 放在任务父目录 (含 1/、2/、... 子文件夹) 中运行。"
    exit 1
fi
# ====================================

# ============ 函数配置区 ============
# 检查任务目录文件是否完整: INCAR、POSCAR、POTCAR、*.sh 必需，KPOINTS 可选
check_files() {
    local dir="$1"
    for f in INCAR POSCAR POTCAR; do
        if [ ! -f "${dir}/${f}" ]; then
            return 1
        fi
    done
    if ! ls "${dir}"/*.sh >/dev/null 2>&1; then
        return 1
    fi
    return 0
}
# ====================================

# ============ 主流程 ============
# 收集无 log 的任务目录并排序
task_list=()
for dir in [0-9]*/; do
    [ -d "$dir" ] || continue
    if ! ls "${dir}"*.log >/dev/null 2>&1; then
        task_list+=("${dir%/}")
    fi
done
task_list=($(printf '%s\n' "${task_list[@]}" | sort -n))

total=${#task_list[@]}
echo "无 log、待提交目录总数: $total"

index=0
first_batch=1   # 首次提交标记: 第一轮允许按 MAX_TOTAL_JOBS 全量提交
wait_seconds=$MIN_WAIT_SEC   # 当前轮询间隔 (秒)

while [ $index -lt $total ]; do
    echo
    echo "=================================================="
    date
    echo "=================================================="

    # 统计当前总任务数 (R+PD 全部算)
    total_jobs=$(squeue -u $USER -h | wc -l)
    echo "当前总任务数: $total_jobs / $MAX_TOTAL_JOBS"

    # 队列满员: 指数退避等待
    if [ "$total_jobs" -ge "$MAX_TOTAL_JOBS" ]; then
        echo "任务已满，等待 ${wait_seconds} 秒后重试..."
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

    echo "本轮最多可提交: $can_submit"
    submitted=0

    while [ $submitted -lt $can_submit ] && [ $index -lt $total ]; do
        dir="${task_list[$index]}"
        index=$((index + 1))

        # 提交前检测文件完整性，不完整则跳过
        if ! check_files "$dir"; then
            echo "⚠️ 跳过: ${dir} 文件不完整 (需要 INCAR、POSCAR、POTCAR、*.sh，KPOINTS 可选)"
            continue
        fi

        echo "提交: $dir"
        (cd "$dir" && sbatch sub2.sh)
        submitted=$((submitted + 1))
        sleep 1
    done

    # 本轮有实际提交则取消首轮标记，后续轮次严格限流
    if [ "$submitted" -gt 0 ]; then
        first_batch=0
    fi

    echo "本轮提交: $submitted 个，等待 ${wait_seconds} 秒后再次检查..."
    sleep $wait_seconds
done

# 创建完成标记，禁止重复运行
touch "$DONE_FILE"
echo
echo "🎉 所有无 log 目录提交完成！"
echo "ℹ️ 已创建完成标记 $DONE_FILE，再次运行本脚本将被拒绝。"
