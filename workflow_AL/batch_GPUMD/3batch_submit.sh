#!/bin/bash
# =============================================================================
# 脚本:        3batch_submit.sh
# 分类:        Slurm 批量作业提交脚本 (batch_GPUMD 工作流第 3 步)
# 功能:        扫描当前目录下所有 1_md* 文件夹，逐个进入并提交 sub_MD.sh
#              (sbatch)，每提交一个休眠 SLEEP_SEC 秒，避免瞬间打爆调度器。
# 使用方法:    ./3batch_submit.sh
# 参数:        无参数；SLEEP_SEC 等可改配置区
# 运行环境:    需在 train_xyz2model_xyzs.py 的输出根目录 (含 1_md* 文件夹)
#              中运行；在 Slurm 登录节点执行
# 输出:        终端实时打印每个文件夹的提交结果；不生成日志文件
# 防重复运行:  首次运行提交完成后生成完成标记 .batch_submit.done；此后再次
#              运行会被拒绝 (第二次、第三次...均退出)，如需重新提交先手动
#              删除标记文件 (rm .batch_submit.done)
# 作者:        Hongbo Sun
# 最后修改日期: 2026-08-24
# =============================================================================

# ============ 配置区 (可按需调整) ============
FOLDER_PATTERN="1_md*"          # 目标文件夹模式 (train_xyz2model_xyzs.py 输出)
JOB_SCRIPT="sub_MD.sh"          # 各文件夹内的作业提交脚本
SLEEP_SEC=5                     # 每次提交后休眠秒数
DONE_FILE=".batch_submit.done"  # 完成标记文件 (首次成功提交后创建)
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
# ====================================

# ============ 主流程 ============
# 收集真实存在的目标文件夹 (bash 无匹配时 for 会保留字面模式，需过滤)
folders=( $FOLDER_PATTERN )
dirs=()
for d in "${folders[@]}"; do
    [ -d "$d" ] && dirs+=("$d")
done

if [ ${#dirs[@]} -eq 0 ]; then
    echo "❌ 错误: 当前目录未找到 $FOLDER_PATTERN 文件夹。"
    echo "请确认已用 train_xyz2model_xyzs.py 抽取结构，并在其输出根目录运行。"
    exit 1
fi

echo "找到 ${#dirs[@]} 个待提交文件夹:"
printf '  %s\n' "${dirs[@]}"
echo

submitted=0
for d in "${dirs[@]}"; do
    if [ ! -f "$d/$JOB_SCRIPT" ]; then
        echo "⚠️ 跳过: $d 缺少 $JOB_SCRIPT"
        continue
    fi
    echo "提交: $d"
    (cd "$d" && sbatch "$JOB_SCRIPT")
    submitted=$((submitted + 1))
    sleep "$SLEEP_SEC"
done

# 创建完成标记，禁止重复运行
touch "$DONE_FILE"
echo
echo "🎉 完成: 共提交 $submitted 个作业 (间隔 ${SLEEP_SEC}s)。"
echo "ℹ️ 已创建完成标记 $DONE_FILE，再次运行本脚本将被拒绝。"
