#!/usr/bin/env python3
"""
QWeSDK 版本检测和安装脚本
自动检测当前安装的版本与本地包版本是否一致，不一致则重新安装
"""

import os
import re
import subprocess
import sys
from pathlib import Path


def extract_version_from_filename(filename):
    """从文件名中提取版本号"""
    match = re.search(r'qwesdk-(\d+\.\d+\.\d+)\.tar\.gz', filename)
    if match:
        return match.group(1)
    return None


def get_installed_version():
    """获取已安装的QWeSDK版本"""
    try:
        result = subprocess.run(
            ['pip', 'show', 'qwesdk'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.startswith('Version:'):
                    return line.split(':')[1].strip()
    except Exception:
        pass
    return None


def install_package(package_path):
    """安装QWeSDK包"""
    print(f"安装新版本: {package_path}")
    result = subprocess.run(
        ['pip', 'install', '--no-cache-dir', package_path],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("安装成功!")
        return True
    else:
        print(f"安装失败: {result.stderr}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("QWeSDK 版本检测和安装")
    print("=" * 60)

    # 查找本地QWeSDK包
    app_dir = Path('/app')
    package_files = list(app_dir.glob('qwesdk-*.tar.gz'))

    if not package_files:
        print("未找到QWeSDK安装包，跳过版本检测")
        print("继续执行原有命令...")
        return True

    # 使用第一个找到的包（如果有多个，取版本号最高的）
    package_files.sort(key=lambda x: extract_version_from_filename(x.name) or '0.0.0', reverse=True)
    local_package = package_files[0]
    local_version = extract_version_from_filename(local_package.name)

    print(f"本地包: {local_package.name}")
    print(f"本地版本: {local_version}")

    # 获取已安装版本
    installed_version = get_installed_version()
    print(f"已安装版本: {installed_version}")

    # 版本检测
    if installed_version == local_version:
        print("\n✓ 版本一致，无需重新安装")
        print(f"当前版本: {installed_version}")
    else:
        print("\n⚠ 版本不一致，需要重新安装")
        print(f"  本地版本: {local_version}")
        print(f"  已安装版本: {installed_version or '无'}")

        # 卸载旧版本（如果存在）
        if installed_version:
            print("\n卸载旧版本...")
            subprocess.run(['pip', 'uninstall', '-y', 'qwesdk'], capture_output=True)

        # 安装新版本
        print("\n安装新版本...")
        if install_package(str(local_package)):
            print("\n✓ 版本更新完成!")
            new_version = get_installed_version()
            print(f"当前版本: {new_version}")
        else:
            print("\n✗ 版本更新失败!")
            return False

    print("=" * 60)
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
