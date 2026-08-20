import os
import datetime
import tkinter as tk
from tkinter import messagebox, ttk
import subprocess
import ctypes
import sys


class ShutdownTool:
    def __init__(self, root):
        self.root = root
        self.root.title("定时关机工具")
        self.root.geometry("500x500")  # 增加高度容纳更多日志
        self.root.resizable(False, False)

        # 检查管理员权限
        self.is_admin = self.check_admin()
        if not self.is_admin:
            messagebox.showwarning("权限提示", "建议以管理员身份运行以获得完整功能！")

        self.zh_font = ("楷体", 12)
        self.author_font = ("楷体", 10)
        self.en_font = ("Times New Roman", 11)
        self.status_history = []
        self.max_history = 30
        self.shutdown_exe = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "shutdown.exe")
        self.create_widgets()

    def check_admin(self):
        """检查是否以管理员身份运行"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def create_widgets(self):
        # 标题区域（美化）
        title_frame = ttk.Frame(self.root, padding=(10, 8))
        title_frame.pack(fill=tk.X, pady=8)
        ttk.Label(title_frame, text="🖥️ 电脑定时关机工具", font=("微软雅黑", 16, "bold")).pack()

        # 作者信息
        author_frame = ttk.Frame(self.root)
        author_frame.pack()
        ttk.Label(author_frame, text="作者：隼蝶 | QQ：2982867842@qq.com", font=self.author_font, foreground='#666').pack()

        # 操作类型
        op_frame = ttk.Frame(self.root)
        op_frame.pack(pady=10)
        op_inner_frame = ttk.Frame(op_frame)
        op_inner_frame.pack()
        ttk.Label(op_inner_frame, text="操作类型：", font=self.zh_font).pack(side=tk.LEFT, padx=5)
        self.operation_var = tk.StringVar(value="关机")
        op_combo = ttk.Combobox(
            op_inner_frame,
            textvariable=self.operation_var,
            values=["关机", "重启", "休眠", "锁定"],
            font=self.en_font,
            width=10,
            state="readonly"
        )
        op_combo.pack(side=tk.LEFT)
        op_combo.bind('<<ComboboxSelected>>', self.on_operation_change)

        # 定时设置
        timer_frame = ttk.Frame(self.root, padding=(10, 5))
        timer_frame.pack(pady=8)
        ttk.Label(timer_frame, text="定时设置", font=self.zh_font).grid(row=0, column=0, columnspan=5, padx=5)
        self.hour1 = tk.Spinbox(timer_frame, from_=0, to=23, width=3, font=self.en_font, justify=tk.CENTER)
        self.hour1.grid(row=1, column=0, padx=2)
        ttk.Label(timer_frame, text="时", font=self.zh_font).grid(row=1, column=1, padx=2)
        self.minute1 = tk.Spinbox(timer_frame, from_=0, to=59, width=3, font=self.en_font, justify=tk.CENTER)
        self.minute1.grid(row=1, column=2, padx=2)
        ttk.Label(timer_frame, text="分", font=self.zh_font).grid(row=1, column=3, padx=2)
        ttk.Button(
            timer_frame,
            text="定时设置",
            command=self.set_timer_shutdown,
            width=12,
            style='Accent.TButton'
        ).grid(row=1, column=4, padx=5)
        # 定时默认值（0时0分）
        self.hour1.delete(0, tk.END)
        self.hour1.insert(0, "0")
        self.minute1.delete(0, tk.END)
        self.minute1.insert(0, "0")

        # 定点设置
        time_frame = ttk.Frame(self.root, padding=(10, 5))
        time_frame.pack(pady=8)
        ttk.Label(time_frame, text="定点设置", font=self.zh_font).grid(row=0, column=0, columnspan=5, padx=5)
        self.hour2 = tk.Spinbox(time_frame, from_=0, to=23, width=3, font=self.en_font, justify=tk.CENTER)
        self.hour2.grid(row=1, column=0, padx=2)
        ttk.Label(time_frame, text="时", font=self.zh_font).grid(row=1, column=1, padx=2)
        self.minute2 = tk.Spinbox(time_frame, from_=0, to=59, width=3, font=self.en_font, justify=tk.CENTER)
        self.minute2.grid(row=1, column=2, padx=2)
        ttk.Label(time_frame, text="分", font=self.zh_font).grid(row=1, column=3, padx=2)
        ttk.Button(
            time_frame,
            text="定点设置",
            command=self.set_time_shutdown,
            width=12,
            style='Accent.TButton'
        ).grid(row=1, column=4, padx=5)
        # 定点默认值为当前时间
        current_time = datetime.datetime.now()
        self.hour2.delete(0, tk.END)
        self.hour2.insert(0, str(current_time.hour))
        self.minute2.delete(0, tk.END)
        self.minute2.insert(0, str(current_time.minute))

        # 取消计划按钮
        cancel_frame = ttk.Frame(self.root)
        cancel_frame.pack(pady=12)
        ttk.Button(
            cancel_frame,
            text="取消所有计划",
            width=15,
            style='Danger.TButton',
            command=self.cancel_shutdown
        ).pack()

        # 操作历史
        hist_frame = ttk.Frame(self.root)
        hist_frame.pack(pady=10, fill=tk.BOTH, expand=True)
        ttk.Label(hist_frame, text="操作历史：", font=self.zh_font).pack(anchor=tk.CENTER, pady=2)
        hist_container = ttk.Frame(hist_frame)
        hist_container.pack(fill=tk.BOTH, expand=True, padx=12)
        self.status_text = tk.Text(
            hist_container,
            height=10,
            width=60,
            font=("宋体", 10),
            state=tk.DISABLED
        )
        scrollbar = tk.Scrollbar(hist_container, orient=tk.VERTICAL, command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=scrollbar.set)
        self.status_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 状态栏（显示管理员权限等）
        status_frame = ttk.Frame(self.root, padding=(6, 4))
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.admin_label = ttk.Label(status_frame, text=f"管理员权限: {'是' if self.is_admin else '否'}", font=self.author_font, foreground='#666')
        self.admin_label.pack(side=tk.LEFT, padx=10)
        self.next_action_label = ttk.Label(status_frame, text="未设置操作", font=self.author_font, foreground='#333')
        self.next_action_label.pack(side=tk.RIGHT, padx=10)

    def on_operation_change(self, event=None):
        pass

    def show_status(self, message):
        current_time = datetime.datetime.now().strftime('%H:%M:%S')
        status_line = f"{current_time} - {message}"
        self.status_history.insert(0, status_line)
        if len(self.status_history) > self.max_history:
            self.status_history.pop()
        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete(1.0, tk.END)
        for line in self.status_history:
            self.status_text.insert(tk.END, line + "\n")
        self.status_text.config(state=tk.DISABLED)
        self.status_text.see(tk.END)

    def get_support_status(self):
        op = self.operation_var.get()
        if op in ["关机", "重启"]:
            return (True, True)
        elif op in ["休眠", "锁定"]:
            return (True, False)
        return (False, False)

    def get_shutdown_command(self):
        op = self.operation_var.get()
        if op == "锁定":
            return 'rundll32.exe user32.dll,LockWorkStation'
        if op == "休眠":
            return 'rundll32.exe powrprof.dll,SetSuspendState 0,1,0'
        base_cmd = f'"{self.shutdown_exe}"'
        if op == "关机":
            return f"{base_cmd} -s"
        elif op == "重启":
            return f"{base_cmd} -r"
        return f"{base_cmd} -s"

    def run_command(self, cmd, require_admin=False):
        """增强版命令执行：返回详细输出（含stdout和stderr）"""
        try:
            if require_admin and not self.is_admin:
                return False, "需要管理员权限"

            result = subprocess.run(
                cmd,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30  # 延长超时时间，确保计划任务创建完成
            )
            # 返回成功信息+stdout（便于调试）
            return True, f"成功：{result.stdout.strip()}"
        except subprocess.CalledProcessError as e:
            # 捕获命令执行失败（返回码非0），包含stdout和stderr
            error_msg = f"命令返回码错误：{e.returncode}，错误输出：{e.stderr.strip()}，标准输出：{e.stdout.strip()}"
            return False, error_msg
        except Exception as e:
            return False, f"执行错误：{str(e)}"

    def set_timer_shutdown(self):
        support_timer, _ = self.get_support_status()
        if not support_timer:
            op = self.operation_var.get()
            messagebox.showinfo("提示", f"{op}操作不支持定时设置！")
            return

        try:
            hour = int(self.hour1.get())
            minute = int(self.minute1.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字！")
            return

        total_seconds = hour * 3600 + minute * 60
        op = self.operation_var.get()

        if total_seconds == 0:
            if op in ["关机", "重启"]:
                cmd = self.get_shutdown_command()
                success, msg = self.run_command(cmd, require_admin=True)
            else:
                cmd = self.get_shutdown_command()
                success, msg = self.run_command(cmd, require_admin=False)

            if success:
                self.show_status(f"立即执行{op}操作")
                if op in ["关机", "重启"]:
                    messagebox.showinfo("提示", f"{op}操作将立即执行！")
            else:
                self.show_status(f"立即{op}失败：{msg}")
                if "需要管理员权限" in msg:
                    messagebox.showerror("权限不足", f"立即{op}需要管理员权限！")
                else:
                    messagebox.showerror("操作失败", msg)
            return

        if op in ["关机", "重启"]:
            cmd = self.get_shutdown_command()
            cmd += f" -t {total_seconds}"
            success, msg = self.run_command(cmd, require_admin=True)
        else:
            messagebox.showinfo("提示", f"{op}操作只支持立即执行（0时0分）！")
            return

        if success:
            exec_time = datetime.datetime.now() + datetime.timedelta(seconds=total_seconds)
            self.show_status(f"已设置 {hour}时{minute}分后{op}，预计时间：{exec_time.strftime('%H:%M:%S')}")
        else:
            self.show_status(f"定时设置失败：{msg}")
            if "需要管理员权限" in msg:
                messagebox.showerror("权限不足", "定时设置需要管理员权限！")

    def set_time_shutdown(self):
        """优化定点设置：以系统权限创建计划任务，增加详细日志"""
        _, support_time = self.get_support_status()
        op = self.operation_var.get()
        if not support_time:
            messagebox.showinfo("提示", f"{op}操作不支持定点设置！")
            return

        if not self.is_admin:
            messagebox.showerror("权限错误", "定点设置必须以管理员身份运行！请右键程序→「以管理员身份运行」")
            self.show_status("定点设置失败：需要管理员身份")
            return

        try:
            hour = int(self.hour2.get())
            minute = int(self.minute2.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字！")
            return

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            messagebox.showerror("错误", "请输入有效的时间（小时0-23，分钟0-59）！")
            return

        # 计算目标时间（确保不小于当前时间）
        now = datetime.datetime.now()
        target_time = datetime.datetime(now.year, now.month, now.day, hour, minute)
        if target_time <= now:
            target_time += datetime.timedelta(days=1)  # 若时间已过，自动设为明天
        self.show_status(f"计算目标时间：当前{now.strftime('%H:%M')}，定点{target_time.strftime('%m-%d %H:%M')}")

        # 计划任务核心配置（以系统权限运行，确保权限足够）
        task_name = f"ShutdownTool_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"  # 毫秒级唯一名称
        shutdown_full_path = os.path.join(os.environ["SystemRoot"], "System32", "shutdown.exe")
        if op == "关机":
            action = f'"{shutdown_full_path}" /s /f /t 0'  # 立即执行，避免延迟
        else:  # 重启
            action = f'"{shutdown_full_path}" /r /f /t 0'

        # 创建计划任务命令（关键优化：增加/ru SYSTEM以系统权限运行）
        create_cmd = (
            f'schtasks /create /tn "{task_name}" '
            f'/tr "{action}" '  # 执行的命令
            f'/sc once '  # 仅执行一次
            f'/st {hour:02d}:{minute:02d} '  # 执行时间
            f'/ru "SYSTEM" '  # 以系统权限运行（核心优化）
            f'/f'  # 强制覆盖同名任务
        )
        self.show_status(f"执行计划任务命令：{create_cmd}")  # 显示完整命令，方便调试

        # 执行命令并获取详细结果
        success, msg = self.run_command(create_cmd, require_admin=True)
        if success:
            self.show_status(f"定点{op}设置成功！任务名称：{task_name}，执行时间：{target_time.strftime('%Y-%m-%d %H:%M')}")
            messagebox.showinfo("成功", f"已设置定点{op}，时间：{target_time.strftime('%Y-%m-%d %H:%M')}")
        else:
            self.show_status(f"定点{op}设置失败：{msg}")
            messagebox.showerror("失败", f"定点设置失败：{msg}\n请查看操作历史获取详细信息")

    def cancel_shutdown(self):
        """增强取消逻辑：同时删除计划任务"""
        op = self.operation_var.get()
        if op in ["关机", "重启"]:
            # 1. 取消即时定时任务（shutdown -a）
            cmd = f'"{self.shutdown_exe}" -a'
            success, msg = self.run_command(cmd, require_admin=True)
            if success:
                self.show_status("已取消即时定时关机/重启计划")
            else:
                self.show_status(f"取消即时计划失败：{msg}（可能无即时计划）")

            # 2. 删除所有ShutdownTool创建的计划任务（关键优化）
            try:
                # 查询所有ShutdownTool相关任务
                query_cmd = 'schtasks /query /fo list /tn "ShutdownTool_*"'
                result = subprocess.run(
                    query_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                # 提取任务名称并删除
                for line in result.stdout.splitlines():
                    if "TaskName:" in line and "ShutdownTool_" in line:
                        task_name = line.split(":", 1)[1].strip()
                        delete_cmd = f'schtasks /delete /tn "{task_name}" /f'
                        subprocess.run(delete_cmd, shell=True, check=True)
                        self.show_status(f"已删除计划任务：{task_name}")
                self.show_status("所有定点计划任务已取消")
                messagebox.showinfo("成功", "已取消所有关机/重启计划（包括定点任务）")
            except Exception as e:
                self.show_status(f"删除计划任务失败：{str(e)}")
        else:
            messagebox.showinfo("提示", f"{op}操作没有可取消的计划任务")


if __name__ == "__main__":
    root = tk.Tk()
    app = ShutdownTool(root)
    root.mainloop()
