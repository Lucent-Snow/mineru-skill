# MinerU API 参考文档

## API 基础信息

- 服务地址: `https://mineru.net/api/v4`
- 认证方式: `Authorization: Bearer <token>`
- Token 有效期: 约 90 天
- 负载均衡: 多账户随机选择 Token

## process_document.py 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `file_path` | string | 是 | - | 本地文件路径或 URL |
| `--output-dir` | string | 否 | 源文件同目录 | 输出目录 |
| `--model` | string | 否 | 自动选择 | vlm / pipeline / MinerU-HTML |
| `--no-formula` | flag | 否 | - | 禁用公式识别 |
| `--no-table` | flag | 否 | - | 禁用表格识别 |

### 模型自动选择规则

| 文件格式 | 默认模型 |
|----------|----------|
| PDF | vlm |
| DOC/DOCX | vlm |
| PPT/PPTX | vlm |
| PNG/JPG/JPEG | vlm |
| HTML | MinerU-HTML |

## process_batch.py 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `directory` | string | 是 | - | 目录路径 |
| `--pattern` | string | 否 | `*.pdf` | 文件匹配模式 |
| `--max-workers` | int | 否 | 5 | 最大并发数（建议 3-5） |
| `--recursive` | flag | 否 | - | 递归扫描子目录 |

## 支持的文件格式

| 格式 | 扩展名 | MIME 类型 | 特性 |
|------|--------|-----------|------|
| PDF | `.pdf` | application/pdf | 公式、表格、图片识别 |
| Word | `.doc`, `.docx` | application/msword | 完整文档结构 |
| PowerPoint | `.ppt`, `.pptx` | application/vnd.ms-powerpoint | 幻灯片内容提取 |
| 图片 | `.png`, `.jpg`, `.jpeg` | image/png, image/jpeg | OCR 文字识别 |
| HTML | `.html` | text/html | 网页内容提取 |

## 处理场景

### 场景 1: 普通文件（< 200MB，< 600 页）

直接上传处理，无需拆分。

### 场景 2: 超页数文件（< 200MB，> 600 页）

API 使用 `page_ranges` 参数分段处理，无需物理拆分文件。

分段算法:
```
chunk_count = (total_pages + 599) // 600
```

### 场景 3: 超大文件（> 200MB）

当前 process_document.py 对超过 200MB 的文件会报错提示。
需要手动拆分后分别处理。

### 场景 4: URL 文件

- 支持直接传入 URL
- 自动下载到临时目录后上传处理
- 格式识别优先使用扩展名，fallback 到 magic bytes

## 输出结构

处理完成后，在输出目录生成:

```
输出目录/
├── {文件名}.md          # Markdown 正文
└── {文件名}_images/     # 提取的图片
    ├── image_0.png
    ├── image_1.png
    └── ...
```

## API 请求流程

```
1. POST /file-urls/batch     → 获取上传链接 + batch_id
2. PUT  {upload_url}         → 上传文件二进制
3. GET  /extract-results/batch/{batch_id}  → 轮询任务状态
4. GET  {full_zip_url}       → 下载结果 ZIP
5. 解压 → 整理 Markdown + 图片
```

### 任务状态值

| 状态 | 含义 |
|------|------|
| pending | 等待处理 |
| waiting-file | 等待文件上传 |
| converting | 转换中 |
| running | 处理中（可获取进度） |
| done | 完成 |
| failed | 失败 |

## Token 管理

### all_tokens.json 格式

```json
{
  "user@example.com": {
    "name": "主账号",
    "token_name": "token-20260125013352",
    "token": "eyJ...",
    "created_at": "2026-01-25 01:33:52",
    "expired_at": "2026-04-25T01:33:52Z"
  }
}
```

### accounts.yaml 格式

```yaml
accounts:
  - name: "主账号"
    email: "user@example.com"
    password: "password"
```

## 错误排查

### Token 文件不存在

```
Token 文件不存在: ~/.mineru/all_tokens.json
```

解决: 运行 `batch_login.py` 获取初始 Token。

### Token 过期

```
ERROR: 1 token(s) expired, run batch_login.py first
```

解决: 运行 `batch_login.py` 续期。

### 文件超过 200MB

```
文件超过200MB限制 (xxx.xMB)
```

解决: 手动拆分 PDF 后分别处理。

### 上传失败

```
获取上传链接失败: ...
```

可能原因: Token 无效、网络问题、API 限流。
解决: 检查 Token 状态，重试。

### 处理超时

```
任务超时
```

默认超时 600 秒（10 分钟）。大文件可能需要更长时间。

### Playwright 浏览器未安装

```
playwright install chromium
```

解决: 运行 `setup_env.py` 或手动安装:
```
.venv\Scripts\python.exe -m playwright install chromium
```

### 验证码未通过

batch_login.py 自动点击阿里云验证码，但偶尔可能失败。
解决:
1. 使用 `--headed` 参数手动观察
2. 减少短时间内登录的账户数量
3. 脚本已内置最多 2 次重试
