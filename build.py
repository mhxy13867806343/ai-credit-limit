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

    is_mac = sys.platform == "darwin"
    is_win = sys.platform == "win32"

    # 打包前清理已在后台运行的旧版本内存进程，避免资源覆写锁
    if is_mac:
        subprocess.run(["killall", "-9", "AICreditLimit"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",  # GUI 应用，无终端控制台弹窗
        "--onedir",    # macOS 标准 App Bundle 打包模式
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

    sep = ";" if is_win else ":"
    cmd.append(f"--add-data={project_root / 'ai_credit_limit'}{sep}ai_credit_limit")

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
        if is_mac:
            plist_path = dist_dir / "AICreditLimit.app" / "Contents" / "Info.plist"
            if plist_path.exists():
                import plistlib

                try:
                    with open(plist_path, "rb") as f:
                        plist_data = plistlib.load(f)
                    plist_data["LSUIElement"] = True
                    with open(plist_path, "wb") as f:
                        plistlib.dump(plist_data, f)
                    print("✓ 已配置 0dcloud 同款 Info.plist [LSUIElement=True]，纯正右上角菜单栏常驻应用！")
                except Exception as exc:
                    print(f"提示: 修改 plist 提示 {exc}")

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
