# MinerU Skill

一个可公开分享的 MinerU 文档处理 skill。它提供了：

- `SKILL.md`：给 AI agent 使用的技能说明
- `scripts/`：环境初始化、Token 管理、单文档处理、批量处理脚本
- `assets/accounts.yaml.example`：账号配置模板
- `references/api-reference.md`：接口和常见错误参考

这个仓库本身不包含真实账号、密码、Token 或个人目录依赖，克隆后按下面步骤配置即可使用。

## 适用场景

- 把 PDF、DOCX、PPTX、图片、HTML 转成 Markdown
- 批量处理一个目录下的文档
- 检查 MinerU Token 是否过期
- 自动登录 MinerU 并刷新 Token

## 环境要求

- Python 3.10+
- Windows、macOS 或 Linux
- 可访问 MinerU 官网和 API
- 首次初始化时需要联网安装依赖和 Playwright Chromium

## 仓库结构

```text
mineru-skill/
├─ SKILL.md
├─ README.md
├─ assets/
│  └─ accounts.yaml.example
├─ references/
│  └─ api-reference.md
└─ scripts/
   ├─ setup_env.py
   ├─ batch_login.py
   ├─ check_tokens.py
   ├─ process_document.py
   ├─ process_batch.py
   ├─ _config.py
   ├─ _api.py
   └─ requirements.txt
```

## 快速开始

### 1. 初始化环境

在仓库根目录执行：

```bash
python scripts/setup_env.py
```

这个脚本会自动完成：

- 创建 `scripts/.venv`
- 安装 `scripts/requirements.txt` 中的依赖
- 安装 Playwright Chromium
- 初始化数据目录
- 如果本地还没有配置文件，则复制 `assets/accounts.yaml.example` 到数据目录

默认数据目录是：

```text
~/.mineru
```

如果你不想使用默认目录，可以先设置环境变量：

```bash
MINERU_DATA_DIR=/your/custom/path
```

Windows PowerShell 示例：

```powershell
$env:MINERU_DATA_DIR = "D:\\mineru-data"
python scripts/setup_env.py
```

### 2. 配置账号

编辑数据目录中的 `accounts.yaml`，填入你的 MinerU 账号：

```yaml
accounts:
  - name: "main"
    email: "your_email@example.com"
    password: "your_password"
```

支持配置多个账号，脚本会随机选择 Token 做简单负载分摊。

### 3. 获取或刷新 Token

初始化完成后，使用虚拟环境里的 Python：

```text
Windows: scripts\.venv\Scripts\python.exe
Unix:    scripts/.venv/bin/python3
```

下面示例里的 `$PY` 代指上面的 Python 路径。

```bash
# 无界面模式
$PY scripts/batch_login.py

# 打开浏览器调试
$PY scripts/batch_login.py --headed
```

脚本会自动登录、删除旧 Token、创建新 Token，并把结果保存到：

```text
~/.mineru/all_tokens.json
```

如果设置了 `MINERU_DATA_DIR`，则保存到对应自定义目录。

### 4. 检查 Token 状态

```bash
$PY scripts/check_tokens.py
```

退出码约定：

- `0`：全部 Token 有效
- `1`：有 Token 过期、缺失或文件为空

### 5. 处理文档

单文件：

```bash
$PY scripts/process_document.py ./example.pdf
$PY scripts/process_document.py ./example.docx --output-dir ./output
$PY scripts/process_document.py https://example.com/demo.pdf
```

批量处理：

```bash
$PY scripts/process_batch.py ./docs
$PY scripts/process_batch.py ./docs --pattern "*.docx"
$PY scripts/process_batch.py ./docs --recursive --max-workers 3
```

输出结果通常是：

```text
output/
├─ example.md
└─ example_images/
```

## 作为 Skill 使用

如果你要把它放进 AI agent 的 skill 目录：

1. 保留仓库结构不变
2. 确保 `SKILL.md` 在 skill 根目录
3. 首次使用前先运行 `python scripts/setup_env.py`
4. 之后 agent 按 `SKILL.md` 中的工作流调用脚本即可

## 公开分享前已处理的内容

这个仓库已经做了最基本的公开发布整理：

- 去掉了个人绝对路径
- 不包含真实 `accounts.yaml`
- 不包含真实 `all_tokens.json`
- 不包含 Python `__pycache__`
- 增加了 `.gitignore`，避免把本地环境和缓存提交上去

## 已知限制

- 依赖 MinerU 网站结构和 API 行为，若官方页面改版，`batch_login.py` 可能需要调整
- 文件大小限制为 200MB
- 默认最多处理 600 页，超页数文件需要按 API 规则分段
- `batch_login.py` 依赖网页自动化和验证码交互，稳定性会受网络和风控影响

## 常见问题

### 找不到 `accounts.yaml`

先运行：

```bash
python scripts/setup_env.py
```

它会在数据目录初始化模板文件。

### `check_tokens.py` 报 Token 不存在

先运行：

```bash
$PY scripts/batch_login.py
```

### 脚本能否直接提交真实账号或 Token？

不建议。公开仓库只保留模板文件，真实账号和 Token 应放在本地数据目录，不要纳入版本控制。

## 参考

- 技能说明：[SKILL.md](./SKILL.md)
- API 参考：[references/api-reference.md](./references/api-reference.md)
