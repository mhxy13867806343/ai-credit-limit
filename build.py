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

    icon_icns = project_root / "assets" / "icon.icns"
    icon_ico = project_root / "assets" / "icon.ico"
    icon_png = project_root / "assets" / "icon.png"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",  # GUI 应用，无终端控制台弹窗
        "--onefile",   # 单文件打包模式，解决双击工作目录缺失引发的闪退
        "--name=AICreditLimit",
        f"--paths={project_root}",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
    ]

    hidden_imports = [
        "ai_credit_limit",
        "ai_credit_limit.app",
        "ai_credit_limit.config",
        "ai_credit_limit.detectors",
        "ai_credit_limit.models",
        "ai_credit_limit.parsers",
        "ai_credit_limit.theme",
        "ai_credit_limit.ui_tray",
        "ai_credit_limit.ui_utils",
        "ai_credit_limit.ui_auto_refresh",
        "ai_credit_limit.ui_usage_card",
        "ai_credit_limit.ui_dialogs",
        "ai_credit_limit.codex_account",
        "ai_credit_limit.codex_sessions",
        "ai_credit_limit.antigravity_account",
        "ai_credit_limit.claude_sessions",
    ]
    for sub in hidden_imports:
        cmd.append(f"--hidden-import={sub}")

    is_mac = platform.system() == "Darwin"
    is_win = platform.system() == "Windows"

    if is_mac:
        print("\n🍎 开始构建 macOS .app bundle...")
        cmd.append("--osx-bundle-identifier=com.aicreditlimit.app")
        if icon_icns.exists():
            cmd.append(f"--icon={icon_icns}")
    elif is_win:
        print("\n🪟 开始构建 Windows .exe 应用...")
        if icon_ico.exists():
            cmd.append(f"--icon={icon_ico}")
    elif icon_png.exists():
        cmd.append(f"--icon={icon_png}")

    cmd.append(str(entry_point))

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
