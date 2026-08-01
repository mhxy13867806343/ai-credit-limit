import os
import sys
from pathlib import Path

# PyInstaller 运行时 bundle 解压根路径
base_dir = getattr(sys, "_MEIPASS", Path(__file__).parent.resolve())
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from ai_credit_limit.app import main


if __name__ == "__main__":
    raise SystemExit(main())
