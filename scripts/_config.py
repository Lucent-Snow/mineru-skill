#!/usr/bin/env python3
"""
MinerU Skill 共享配置模块
定义数据目录、API地址、常量等，供其他脚本 import 使用。
"""
import os
from pathlib import Path

# ============================================================
# 数据目录（可通过环境变量 MINERU_DATA_DIR 覆盖）
# ============================================================
DATA_DIR = Path(os.environ.get("MINERU_DATA_DIR", Path.home() / ".mineru"))
TOKENS_FILE = DATA_DIR / "all_tokens.json"
ACCOUNTS_FILE = DATA_DIR / "accounts.yaml"

# ============================================================
# 脚本所在目录
# ============================================================
SCRIPTS_DIR = Path(__file__).parent.resolve()
VENV_DIR = SCRIPTS_DIR / ".venv"

# Windows / Unix 兼容
if os.name == "nt":
    VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
else:
    VENV_PYTHON = VENV_DIR / "bin" / "python3"

# ============================================================
# MinerU API
# ============================================================
API_BASE_URL = "https://mineru.net/api/v4"

# ============================================================
# 文件限制
# ============================================================
MAX_FILE_SIZE = 200 * 1024 * 1024   # 200 MB
MAX_PAGES = 600

# ============================================================
# 支持的文件格式（扩展名 → MIME 类型）
# ============================================================
SUPPORTED_FORMATS = {
    "pdf":  "application/pdf",
    "doc":  "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "ppt":  "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "png":  "image/png",
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "html": "text/html",
}

# 自动选择模型的规则
MODEL_AUTO_SELECT = {
    "pdf":  "vlm",
    "doc":  "vlm",
    "docx": "vlm",
    "ppt":  "vlm",
    "pptx": "vlm",
    "png":  "vlm",
    "jpg":  "vlm",
    "jpeg": "vlm",
    "html": "MinerU-HTML",
}


def ensure_data_dir():
    """确保数据目录存在"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
