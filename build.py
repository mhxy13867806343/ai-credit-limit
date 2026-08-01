#!/usr/bin/env python3
"""Build script for packaging AI Credit Limit on macOS and Windows."""

import os
import platform
import subprocess
import sys
from pathlib import Path


def main() -> None:
    print("==========================================")
    print("🚀 AI Credit Limit 打包构建脚本")
    print(f"当前操作系统: {platform.system()} ({platform.machine()})")
    print("==========================================")

    # 1. 检查/安装 PyInstaller
    try:
        import PyInstaller  # type: ignore
        print("✓ 已检测到 PyInstaller")
    except ImportError:
        print("📦 正在安装 PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    # 2. 构建 PyInstaller 参数
    project_root = Path(__file__).parent.resolve()
    entry_point = project_root / "main.py"
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",  # GUI 应用，无终端控制台弹窗
        "--name=AICreditLimit",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        str(entry_point),
    ]

    is_mac = platform.system() == "Darwin"
    is_win = platform.system() == "Windows"

    if is_mac:
        print("\n🍎 开始构建 macOS .app bundle...")
        cmd.extend([
            "--osx-bundle-identifier=com.aicreditlimit.app",
        ])
    elif is_win:
        print("\n🪟 开始构建 Windows .exe 应用...")

    print("执行打包命令:", " ".join(cmd))

    res = subprocess.run(cmd)

    if res.returncode == 0:
        print("\n==========================================")
        print("🎉 打包成功！产物已生成至 dist 目录:")
        if is_mac:
            print(f"   macOS App: {dist_dir / 'AICreditLimit.app'}")
        elif is_win:
            print(f"   Windows Executable: {dist_dir / 'AICreditLimit' / 'AICreditLimit.exe'}")
        print("==========================================")
    else:
        print("\n❌ 打包失败，请检查报错日志！")
        sys.exit(res.returncode)


if __name__ == "__main__":
    main()
