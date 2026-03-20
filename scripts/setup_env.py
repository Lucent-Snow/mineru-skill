#!/usr/bin/env python3
"""
MinerU Skill 环境初始化
一键完成：创建虚拟环境 → 安装依赖 → 初始化数据目录 → 安装 Playwright 浏览器

用法：
  python setup_env.py
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.resolve()
VENV_DIR = SCRIPTS_DIR / ".venv"
REQUIREMENTS = SCRIPTS_DIR / "requirements.txt"
ASSETS_DIR = SCRIPTS_DIR.parent / "assets"

# 数据目录
DATA_DIR = Path(os.environ.get("MINERU_DATA_DIR", Path.home() / ".mineru"))
ACCOUNTS_EXAMPLE = ASSETS_DIR / "accounts.yaml.example"
ACCOUNTS_TARGET = DATA_DIR / "accounts.yaml"

# Windows / Unix 兼容
if os.name == "nt":
    VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
    VENV_PIP = VENV_DIR / "Scripts" / "pip.exe"
else:
    VENV_PYTHON = VENV_DIR / "bin" / "python3"
    VENV_PIP = VENV_DIR / "bin" / "pip"


def run(cmd, **kwargs):
    """执行命令并打印"""
    print(f"  > {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"  FAILED (exit {result.returncode})")
        sys.exit(1)
    return result


def main():
    print(f"{'='*55}")
    print(f"  MinerU Skill setup")
    print(f"{'='*55}\n")

    # 1. 创建虚拟环境
    print("[1/4] virtual environment")
    if VENV_DIR.exists():
        print(f"  already exists: {VENV_DIR}")
    else:
        # 优先使用 uv（更快），fallback 到 venv
        uv_path = shutil.which("uv")
        if uv_path:
            run([uv_path, "venv", str(VENV_DIR)])
        else:
            run([sys.executable, "-m", "venv", str(VENV_DIR)])
        print(f"  created: {VENV_DIR}")

    # 2. 安装依赖
    print(f"\n[2/4] dependencies")
    uv_path = shutil.which("uv")
    if uv_path:
        run([uv_path, "pip", "install", "-r", str(REQUIREMENTS), "--python", str(VENV_PYTHON)])
    else:
        run([str(VENV_PIP), "install", "-r", str(REQUIREMENTS)])
    print("  dependencies installed")

    # 3. 初始化数据目录
    print(f"\n[3/4] data directory")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  created: {DATA_DIR}")

    if not ACCOUNTS_TARGET.exists() and ACCOUNTS_EXAMPLE.exists():
        shutil.copy(ACCOUNTS_EXAMPLE, ACCOUNTS_TARGET)
        print(f"  copied accounts.yaml.example -> {ACCOUNTS_TARGET}")
        print(f"  >>> EDIT {ACCOUNTS_TARGET} with your MinerU credentials <<<")
    elif ACCOUNTS_TARGET.exists():
        print(f"  accounts.yaml already exists: {ACCOUNTS_TARGET}")
    else:
        print(f"  WARNING: accounts.yaml.example not found")

    # 4. 安装 Playwright Chromium
    print(f"\n[4/4] playwright browser")
    run([str(VENV_PYTHON), "-m", "playwright", "install", "chromium"])
    print("  chromium installed")

    # 完成
    print(f"\n{'='*55}")
    print(f"  SETUP COMPLETE")
    print(f"{'='*55}")
    print(f"  venv python: {VENV_PYTHON}")
    print(f"  data dir:    {DATA_DIR}")
    print(f"\n  Next steps:")
    print(f"  1. Edit {ACCOUNTS_TARGET}")
    print(f"  2. Run: {VENV_PYTHON} {SCRIPTS_DIR / 'batch_login.py'}")
    print(f"  3. Run: {VENV_PYTHON} {SCRIPTS_DIR / 'check_tokens.py'}")


if __name__ == "__main__":
    main()
