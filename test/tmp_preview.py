# -*- coding: utf-8 -*-
"""临时预览脚本 v2：修正中文对齐（用后即删）"""

skip_dirs = [
    ('2',  '未找到OUTCAR'),
    ('3',  '未检测到自洽标记，计算未收敛或计算出错，自洽计数=0'),
    ('7',  '自洽计数=3'),
    ('9',  '读取OUTCAR异常'),
]
total_dirs = 12
success_n = 8


def classify(reason):
    if '未找到OUTCAR' in reason:
        return '缺少OUTCAR'
    if '自洽计数=0' in reason or '未检测到' in reason:
        return '未收敛'
    if '自洽计数' in reason:
        return '自洽异常'
    if '异常' in reason:
        return '读取异常'
    return '其他'


def dw(s):
    """显示宽度：中文等宽字符按2列计"""
    return sum(2 if ord(c) > 127 else 1 for c in str(s))


def pad(s, w, align='<'):
    """按显示宽度填充空格对齐: align='<'左对齐, '>'右对齐"""
    s = str(s)
    n = w - dw(s)
    return s + ' ' * n if align == '<' else ' ' * n + s


def col(s, w, align='<'):
    """单列: 按宽度对齐 + 列间2空格分隔"""
    return pad(s, w, align) + '  '


W = 60
bar = '=' * W
line = '-' * W

# 列宽: 序号6 / 文件夹8 / 状态10 / 原因(不固定)
hdr = col('序号', 6, '>') + col('文件夹', 8, '>') + col('状态', 10) + '原因'
sep = col('-' * 6, 6, '>') + col('-' * 8, 8, '>') + col('-' * 10, 10) + '-' * 30

print(bar)
print('📊 未收集文件夹列表 (共 %d 个):' % len(skip_dirs))
print(line)
print(hdr)
print(sep)
for i, (d, reason) in enumerate(skip_dirs, 1):
    st = classify(reason)
    print(col(i, 6, '>') + col(d, 8, '>') + col(st, 10) + reason)
print(sep)
print('✅ 成功收集 {}/{}，未收集 {} 个，详情见 collect_info.txt'.format(
    success_n, total_dirs, len(skip_dirs)))
print(bar)
print()
print('===== 全部收集成功时的样式 =====')
print(bar)
print('📊 未收集文件夹列表: 0 个，全部收集成功 🎉')
print(bar)
