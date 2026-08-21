"""
=============================================================================
脚本:        merge_xyz.py
功能:        在train顶层目录运行，按字母顺序拼接 a/b/c…/train.xyz
             行为等价 cat；处理完一个文件立刻释放内存，再处理下一个
使用方法:    python merge_xyz.py
运行位置:    /public5/home/t6s008728/MoTe2/vasp/train
输出:        ./merge_train.xyz
=============================================================================
"""
import os

def main():
    work_dir = os.getcwd()
    print(f"✅ 当前工作目录: {work_dir}")

    letter_dirs = []
    for char in "abcdefghijklmnopqrst":
        d = os.path.join(char)
        if os.path.isdir(d):
            letter_dirs.append(d)

    if not letter_dirs:
        print("❌ 没有找到a‑t字母子文件夹！")
        return

    print("\n📂 待拼接列表:")
    for d in letter_dirs:
        print(f"  {d}/train.xyz")

    out_file = "merge_train.xyz"
    buf_size = 1024 * 1024  # 1MB缓冲区

    with open(out_file, "w") as fout:
        for d in letter_dirs:
            xyz_path = os.path.join(d, "train.xyz")
            if not os.path.isfile(xyz_path):
                print(f"⏭ 跳过  {xyz_path} 不存在")
                continue

            print(f"🔄 处理  {xyz_path} ...", end=" ")
            with open(xyz_path, "r") as fin:
                while True:
                    chunk = fin.read(buf_size)
                    if not chunk:
                        break
                    fout.write(chunk)
            print("✅完成")

    print(f"\n🎉 全部拼接完成！")
    print(f"📁 输出文件: {os.path.abspath(out_file)}")

if __name__ == "__main__":
    main()