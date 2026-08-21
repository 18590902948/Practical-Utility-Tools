#!/bin/bash
# =============================================================================
# 脚本:        batch_submit.sh
# 分类:        Slurm批量作业提交脚本
# 功能:        扫描当前目录下所有数字命名子文件夹，筛选不存在*.log日志的任务目录；
#              按数字从小到大顺序逐批sbatch提交sub2.sh；
#              每次提交前检测目录文件完整性（INCAR、POSCAR、POTCAR、*.sh必需，KPOINTS可选），
#              不完整则跳过不提交；按照最大总任务数MAX_TOTAL_JOBS与每批提交数量BATCH_SIZE控制提交速率；
#              动态轮询间隔：队列有空位时每MIN_WAIT_SEC秒快速补位，长期满员时等待时间指数退避翻倍，
#              最长不超过MAX_WAIT_SEC秒，提交成功后立即重置为最短间隔。
#              直接执行 ./batch_submit.sh 等价于 nohup ./batch_submit.sh > submit.log 2>&1
# 使用方法:    ./batch_submit.sh
# 运行环境：脚本需放在包含众多数字子文件夹的父目录，如，放在a/下，或者b/下
# 参数:        无参数，直接运行；可修改脚本头部BATCH_SIZE、MAX_TOTAL_JOBS、MIN_WAIT_SEC、MAX_WAIT_SEC配置
# 输出:
#   submit.log      【批量脚本日志】batch_submit.sh自身运行日志，父目录仅生成一份
#   各数字子任务目录生成${JOBID}.log 【子任务日志】由sub2.sh的--output=%j.log生成，每个任务独立一份
# 作者:        Hongbo Sun
# 最后修改日期: 2026‑08‑22
# =============================================================================

# ============ 配置区（可按需调整） ============
BATCH_SIZE=9        # 每批最多提交数量
MAX_TOTAL_JOBS=18   # 集群上允许的最大总任务数（R+PD 全部算），并行云超算平台上限20个任务
MIN_WAIT_SEC=60     # 最短轮询间隔（秒）：队列有空位时快速补位，及时抓住空位
MAX_WAIT_SEC=900    # 最长轮询间隔（秒）：长期满员时指数退避上限（=15分钟）
# ==============================================

# # 目录树示例:
# # ============================================================================
# # .
# # ├── a/                      # batch_submit.sh运行所在父目录(字母目录)
# # │   ├── 1/                  # 单任务数字子文件夹
# # │   │   ├── POSCAR
# # │   │   ├── INCAR
# # │   │   ├── POTCAR
# # │   │   ├── sub2.sh
# # │   │   └── ${JOBID}.log    # 【子任务日志】sub2.sh中--output=%j.log生成，每个任务一份
# # │   ├── 2/
# # │   │   └── ...
# # │   └── ...
# # ├── b/
# # │   ├── 501/
# # │   │   └── ...
# # │   └── ...
# # ├── batch_submit.sh
# # └── submit.log               # 【批量脚本日志】batch_submit.sh自身nohup输出，父目录仅一份
# # ============================================================================

############## 新增：自动后台nohup + 防重复运行逻辑 ##############
LOCK_FILE="./.batch_submit.lock"

# 判断是否已经进入nohup后台子进程
if [[ ! "$NOHUP_INNER" == "1" ]];then
    # 检测是否已有正在运行的实例
    if [ -f "$LOCK_FILE" ];then
        old_pid=$(cat "$LOCK_FILE")
        if ps -p "$old_pid" > /dev/null 2>&1;then
            echo "❌ 检测到脚本已在后台运行，PID: ${old_pid}"
            echo "----------------------------------------"
            echo "查看实时日志：tail -f submit.log"
            echo "查看进程状态：ps aux | grep batch_submit.sh"
            echo "终止后台脚本：kill -9 ${old_pid}"
            echo "----------------------------------------"
            exit 1
        else
            # lock文件存在但进程已死亡，清理旧锁
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
# $$ 即后台进程自身PID，与前台终端打印的new_pid相同（bash直接执行不fork）
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

############## 前置校验：检查目录环境是否正确 ##############
# 仅检查是否存在数字子任务文件夹；各目录文件完整性在提交前逐个检测
if ! ls -d [0-9]*/ >/dev/null 2>&1; then
    echo "❌ 错误：当前目录未找到数字命名的子任务文件夹！"
    echo "请将 batch_submit.sh 放置在a/、b/这类任务父目录下运行。"
    exit 1
fi
####################################################

# ==========下面是原来全部业务代码============
# 检查任务目录文件是否完整：INCAR、POSCAR、POTCAR、*.sh 必需，KPOINTS 可选
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

task_list=()
for dir in [0-9]*/; do
  [ -d "$dir" ] || continue
  # 没有 log 才加入任务列表
  if ! ls "${dir}"*.log >/dev/null 2>&1; then
    task_list+=("${dir%/}")
  fi
done

# 按数字从小到大排序（1、2、3、…、100），确保按文件夹顺序提交
task_list=($(printf '%s\n' "${task_list[@]}" | sort -n))

total=${#task_list[@]}
echo "无 log、待提交目录总数：$total"

index=0
first_batch=1   # 首次提交标记：第一轮允许按 MAX_TOTAL_JOBS 全量提交（不受 BATCH_SIZE 限制）
wait_seconds=$MIN_WAIT_SEC   # 当前轮询间隔（秒）：满员时指数退避，有空位时重置为最短间隔

while [ $index -lt $total ]; do
  echo
  echo "=================================================="
  date
  echo "=================================================="

  # 统计当前总任务数（R+PD 全部算）
  total_jobs=$(squeue -u $USER -h | wc -l)
  echo "当前总任务数：$total_jobs / $MAX_TOTAL_JOBS"

  if [ "$total_jobs" -ge "$MAX_TOTAL_JOBS" ]; then
    echo "任务已满，等待 ${wait_seconds} 秒后重试..."
    sleep $wait_seconds
    # 指数退避：满员时等待时间翻倍，最长不超过 MAX_WAIT_SEC
    wait_seconds=$((wait_seconds * 2))
    if [ "$wait_seconds" -gt "$MAX_WAIT_SEC" ]; then
      wait_seconds=$MAX_WAIT_SEC
    fi
    continue
  fi

  # 本轮可提交数量
  can_submit=$((MAX_TOTAL_JOBS - total_jobs))
  # 首次提交不受 BATCH_SIZE 限制，按剩余额度全量提交；后续轮次每轮最多 BATCH_SIZE 个
  if [ "$first_batch" -eq 0 ] && [ "$can_submit" -gt "$BATCH_SIZE" ]; then
    can_submit=$BATCH_SIZE
  fi

  # 队列有空位：重置为最短间隔，及时抓住陆续出现的空位
  wait_seconds=$MIN_WAIT_SEC

  echo "本轮最多可提交：$can_submit"
  submitted=0

  while [ $submitted -lt $can_submit ] && [ $index -lt $total ]; do
    dir="${task_list[$index]}"
    index=$((index + 1))

    # 提交前检测文件完整性，不完整则跳过
    if ! check_files "$dir"; then
      echo "⚠️ 跳过：${dir} 文件不完整（需要 INCAR、POSCAR、POTCAR、*.sh，KPOINTS 可选）"
      continue
    fi

    echo "提交：$dir"
    (cd "$dir" && sbatch sub2.sh)
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

echo "所有无 log 目录提交完成！"