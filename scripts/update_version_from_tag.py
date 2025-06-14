#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
从Git标签自动更新包版本号
用于GitHub Actions发布流程中自动设置版本号
"""

import os
import re
import sys
from pathlib import Path


def get_version_from_tag(tag_name: str) -> str:
    """
    从Git标签名提取版本号
    支持格式: v1.2.3, 1.2.3, release-1.2.3等
    """
    # 移除常见前缀
    version = tag_name
    for prefix in ['v', 'version-', 'release-', 'rel-']:
        if version.lower().startswith(prefix):
            version = version[len(prefix):]
            break
    
    # 验证版本号格式 (semantic versioning)
    version_pattern = r'^\d+\.\d+\.\d+(?:-[\w\.-]+)?(?:\+[\w\.-]+)?$'
    if not re.match(version_pattern, version):
        raise ValueError(f"Invalid version format: {version}")
    
    return version


def update_pyproject_version(version: str) -> None:
    """更新pyproject.toml中的版本号"""
    project_root = Path(__file__).parent.parent
    pyproject_path = project_root / "pyproject.toml"
    
    if not pyproject_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found at {pyproject_path}")
    
    # 读取文件内容
    content = pyproject_path.read_text(encoding='utf-8')
    
    # 替换版本号
    new_content = re.sub(
        r'^version\s*=\s*["\'][^"\']*["\']',
        f'version = "{version}"',
        content,
        flags=re.MULTILINE
    )
    
    if new_content == content:
        # 检查是否版本已经是目标版本
        current_version_match = re.search(r'^version\s*=\s*["\']([^"\']*)["\']', content, re.MULTILINE)
        if current_version_match:
            current_version = current_version_match.group(1)
            if current_version == version:
                print(f"pyproject.toml version is already {version}, no update needed")
                return
        raise ValueError("Failed to find version field in pyproject.toml")
    
    # 写回文件
    pyproject_path.write_text(new_content, encoding='utf-8')
    print(f"Updated pyproject.toml version to {version}")


def update_init_version(version: str) -> None:
    """更新__init__.py中的版本号"""
    project_root = Path(__file__).parent.parent
    init_path = project_root / "ui_zero" / "__init__.py"
    
    if not init_path.exists():
        raise FileNotFoundError(f"__init__.py not found at {init_path}")
    
    # 读取文件内容
    content = init_path.read_text(encoding='utf-8')
    
    # 替换版本号
    new_content = re.sub(
        r'^__version__\s*=\s*["\'][^"\']*["\']',
        f'__version__ = "{version}"',
        content,
        flags=re.MULTILINE
    )
    
    if new_content == content:
        # 检查是否版本已经是目标版本
        current_version_match = re.search(r'__version__\s*=\s*["\']([^"\']*)["\']', content)
        if current_version_match:
            current_version = current_version_match.group(1)
            if current_version == version:
                print(f"__init__.py version is already {version}, no update needed")
                return
        raise ValueError("Failed to find __version__ field in __init__.py")
    
    # 写回文件
    init_path.write_text(new_content, encoding='utf-8')
    print(f"Updated __init__.py version to {version}")


def update_cli_version(version: str) -> None:
    """更新cli.py中的版本号"""
    project_root = Path(__file__).parent.parent
    cli_path = project_root / "ui_zero" / "cli.py"
    
    if not cli_path.exists():
        raise FileNotFoundError(f"cli.py not found at {cli_path}")
    
    # 读取文件内容
    content = cli_path.read_text(encoding='utf-8')
    
    # 替换版本号
    new_content = re.sub(
        r'version="UI-Zero v[^"]*"',
        f'version="UI-Zero v{version}"',
        content
    )
    
    if new_content == content:
        # 检查是否版本已经是目标版本
        current_version_match = re.search(r'version="UI-Zero v([^"]*)"', content)
        if current_version_match:
            current_version = current_version_match.group(1)
            if current_version == version:
                print(f"cli.py version is already {version}, no update needed")
                return
        raise ValueError("Failed to find version field in cli.py")
    
    # 写回文件
    cli_path.write_text(new_content, encoding='utf-8')
    print(f"Updated cli.py version to {version}")


def main():
    """主函数"""
    # 从环境变量或命令行参数获取标签名
    tag_name = os.environ.get('GITHUB_REF_NAME') or (sys.argv[1] if len(sys.argv) > 1 else None)
    
    if not tag_name:
        print("Error: No tag name provided")
        print("Usage: python update_version_from_tag.py <tag_name>")
        print("Or set GITHUB_REF_NAME environment variable")
        sys.exit(1)
    
    try:
        # 提取版本号
        version = get_version_from_tag(tag_name)
        print(f"Extracted version {version} from tag {tag_name}")
        
        # 更新所有文件中的版本号
        update_pyproject_version(version)
        update_init_version(version)
        update_cli_version(version)
        
        print(f"Successfully updated all version references to {version}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()