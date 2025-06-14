#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
编译翻译文件脚本
将.po文件编译为.mo文件，以供gettext使用
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def compile_translations():
    """编译所有翻译文件"""
    try:
        import polib
    except ImportError:
        print("错误: 需要安装polib库")
        print("请运行: uv add --dev polib")
        return False

    locale_dir = project_root / "ui_zero" / "locale"

    if not locale_dir.exists():
        print(f"错误: locale目录不存在: {locale_dir}")
        return False

    success_count = 0
    total_count = 0

    # 查找所有.po文件
    for po_file in locale_dir.rglob("*.po"):
        total_count += 1
        mo_file = po_file.with_suffix(".mo")

        try:
            print(
                f"编译 {po_file.relative_to(project_root)} -> {mo_file.relative_to(project_root)}"
            )

            # 加载.po文件
            po = polib.pofile(str(po_file))

            # 保存为.mo文件
            po.save_as_mofile(str(mo_file))

            print(f"  成功: {len(po)} 条消息")
            success_count += 1

        except Exception as e:
            print(f"  错误: {e}")

    print(f"\n编译完成: {success_count}/{total_count} 个文件成功")
    return success_count == total_count


def main():
    """主函数"""
    print("开始编译翻译文件...")
    success = compile_translations()

    if success:
        print("所有翻译文件编译成功!")
        sys.exit(0)
    else:
        print("编译过程中出现错误!")
        sys.exit(1)


if __name__ == "__main__":
    main()
