#!/bin/bash
# =============================================================================
# 脚本:        batch_submit.sh
# 分类:        Slurm批量作业提交脚本
# 功能:        扫描当前目录下所有数字命名子文件夹，筛选不存在*.log日志的任务目录；
#              按照最大总任务数MAX_TOTAL_JOBS与每批提交数量BATCH_SIZE控制提交速率，
#              循环分批sbatch提交sub2.sh，任务满时自动休眠等待。
#              直接执行 ./batch_submit.sh 等价于 nohup ./batch_submit.sh > submit.log 2>&1
# 使用方法:    ./batch_submit.sh
# 运行环境：脚本需放在包含众多数字子文件夹的父目录，如，放在a/下，或者b/下
# 参数:        无参数，直接运行；可修改脚本头部BATCH_SIZE、WAIT_MIN、MAX_TOTAL_JOBS配置
# 输出:
#   submit.log      【批量脚本日志】batch_submit.sh自身运行日志，父目录仅生成一份
#   各数字子任务目录生成${JOBID}.log 【子任务日志】由sub2.sh的--output=%j.log生成，每个任务独立一份
# 作者:        Hongbo Sun
# 最后修改日期: 2026‑08‑20
# =============================================================================
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
    nohup "$0" "$@" > submit.log 2>&1 &
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

# 脚本正常退出时自动删除锁文件
trap 'rm -f "$LOCK_FILE"' EXIT
####################################################

############## 前置校验：检查目录环境是否正确 ##############
# 取第一个数字子文件夹作为样例校验
sample_dir=$(ls -1 [0-9]*/ 2>/dev/null | head -n1)
if [ -z "${sample_dir}" ];then
    echo "❌ 错误：当前目录未找到数字命名的子任务文件夹！"
    echo "请将 batch_submit.sh 放置在a/、b/这类任务父目录下运行。"
    exit 1
fi

required_files=("INCAR" "POSCAR" "POTCAR")
missing_flag=0
for f in "${required_files[@]}"; do
    if [ ! -f "${sample_dir}${f}" ];then
        echo "❌ 样例目录 ${sample_dir} 缺失必要文件：${f}"
        missing_flag=1
    fi
done

if [ ${missing_flag} -eq 1 ];then
    echo "❗运行路径不正确，请确认各子任务目录已经准备好 INCAR POSCAR POTCAR"
    exit 1
fi
echo "✅ 环境校验通过，任务目录文件齐全"
####################################################

# ==========下面是原来全部业务代码============
BATCH_SIZE=8
WAIT_MIN=20
MAX_TOTAL_JOBS=10

task_list=()
for dir in [0-9]*/; do
  [ -d "$dir" ] || continue
  # 没有 log 才加入任务列表
  if ! ls "${dir}"*.log >/dev/null 2>&1; then
    task_list+=("$dir")
  fi
done

total=${#task_list[@]}
echo "无 log、待提交目录总数：$total"

index=0

while [ $index -lt $total ]; do
  echo
  echo "=================================================="
  date
  echo "=================================================="

  # 统计当前总任务数（R+PD 全部算）
  total_jobs=$(squeue -u $USER -h | wc -l)
  echo "当前总任务数：$total_jobs / $MAX_TOTAL_JOBS"

  if [ "$total_jobs" -ge "$MAX_TOTAL_JOBS" ]; then
    echo "任务已满，等待 $WAIT_MIN 分钟..."
    sleep 1200
    continue
  fi

  # 本轮可提交数量
  can_submit=$((MAX_TOTAL_JOBS - total_jobs))
  if [ "$can_submit" -gt "$BATCH_SIZE" ]; then
    can_submit=$BATCH_SIZE
  fi

  echo "本轮最多可提交：$can_submit"
  submitted=0

  while [ $submitted -lt $can_submit ] && [ $index -lt $total ]; do
    dir="${task_list[$index]}"
    echo "提交：$dir"
    (cd "$dir" && sbatch sub2.sh)
    submitted=$((submitted + 1))
    index=$((index + 1))
    sleep 1
  done

  echo "本轮提交：$submitted 个，等待 $WAIT_MIN 分钟..."
  sleep 1200
done

echo "所有无 log 目录提交完成！"