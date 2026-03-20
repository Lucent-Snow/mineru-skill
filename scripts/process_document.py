#!/usr/bin/env python3
"""
MinerU 单文档处理
将 PDF/DOCX/PPTX/图片/HTML 转换为 Markdown + 图片。

用法：
  python process_document.py <文件路径或URL>
  python process_document.py <文件路径> --output-dir <输出目录>
  python process_document.py <文件路径> --model vlm
  python process_document.py <URL>

参数：
  file_path           文件路径或 URL（必需）
  --output-dir DIR    输出目录（默认与源文件同目录）
  --model MODEL       模型版本: vlm / pipeline / MinerU-HTML（默认自动选择）
  --no-formula        禁用公式识别
  --no-table          禁用表格识别
"""
import argparse
import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from niquests import AsyncSession

from _config import MODEL_AUTO_SELECT
from _api import (
    load_tokens,
    get_random_token,
    check_tokens_valid,
    validate_file,
    validate_url,
    upload_file,
    wait_for_completion,
    download_and_extract,
    find_markdown,
    is_url,
)


async def process_document(
    file_path: str,
    output_dir: str = None,
    model_version: str = None,
    enable_formula: bool = True,
    enable_table: bool = True,
) -> dict:
    """
    处理单个文档，返回结果字典。
    """
    print(f"\n  file: {file_path}")

    # 1. 加载并检查 Token
    tokens = load_tokens()
    if not tokens:
        print("  ERROR: no tokens found, run batch_login.py first")
        return {"status": "error", "message": "no tokens"}

    all_valid, expired = check_tokens_valid(tokens)
    if not all_valid:
        print(f"  ERROR: {len(expired)} token(s) expired, run batch_login.py first")
        return {"status": "token_expired", "expired": expired}

    token = get_random_token(tokens)

    async with AsyncSession() as session:
        # 2. 验证文件
        if is_url(file_path):
            print("  validating URL...")
            ok, err, info = await validate_url(session, file_path)
        else:
            print("  validating file...")
            ok, err, info = validate_file(file_path)

        if not ok:
            print(f"  ERROR: {err}")
            return {"status": "error", "message": err}

        fmt = info["format"]
        size_mb = info["size"] / 1024 / 1024
        pages = info.get("pages")
        print(f"  format: {fmt.upper()}, size: {size_mb:.1f}MB", end="")
        if pages:
            print(f", pages: {pages}")
        else:
            print()

        # 3. 确定模型
        if not model_version:
            model_version = MODEL_AUTO_SELECT.get(fmt, "vlm")

        upload_options = {
            "model_version": model_version,
            "enable_formula": enable_formula,
            "enable_table": enable_table,
        }

        # 4. URL 文件需要先下载到本地
        local_path = file_path
        if info["is_url"]:
            print("  downloading URL file...")
            file_name = info["name"]
            if "." not in file_name:
                file_name = f"{file_name}.{fmt}"
            tmp_path = Path(tempfile.gettempdir()) / file_name

            resp = await session.get(file_path, timeout=120)
            if resp.status_code != 200:
                print(f"  ERROR: download failed, HTTP {resp.status_code}")
                return {"status": "error", "message": f"download failed: {resp.status_code}"}

            tmp_path.write_bytes(resp.content)
            local_path = str(tmp_path)
            print(f"  downloaded: {tmp_path.stat().st_size / 1024 / 1024:.1f}MB")

        # 5. 上传
        print("  uploading...")
        batch_id = await upload_file(session, token, local_path, **upload_options)
        if not batch_id:
            return {"status": "error", "message": "upload failed"}
        print(f"  uploaded, batch_id: {batch_id}")

        # 6. 等待处理
        print("  processing...")
        results = await wait_for_completion(session, token, batch_id)
        if not results or len(results) == 0:
            return {"status": "error", "message": "processing failed"}

        result = results[0]
        if result.get("state") != "done":
            msg = result.get("err_msg", "unknown error")
            print(f"  ERROR: {msg}")
            return {"status": "error", "message": msg}

        zip_url = result.get("full_zip_url")
        print("  processing done")

        # 7. 下载并解压
        if output_dir is None:
            if info["is_url"]:
                output_dir = str(Path.cwd())
            else:
                output_dir = str(Path(file_path).parent)

        chunk_dir = Path(output_dir) / f"{Path(local_path).stem}_result"
        chunk_dir.mkdir(parents=True, exist_ok=True)

        print("  downloading result...")
        extracted = await download_and_extract(session, zip_url, str(chunk_dir))
        if not extracted:
            return {"status": "error", "message": "download failed"}

        # 8. 整理输出
        file_stem = Path(local_path).stem
        out_path = Path(output_dir)
        md_file = out_path / f"{file_stem}.md"
        images_dir = out_path / f"{file_stem}_images"

        source_md = find_markdown(extracted)
        if source_md:
            shutil.copy(source_md, md_file)

        source_images = Path(extracted) / "images"
        image_count = 0
        if source_images.exists():
            if images_dir.exists():
                shutil.rmtree(images_dir)
            shutil.copytree(source_images, images_dir)
            image_count = len(list(images_dir.glob("*")))

        # 清理临时目录
        shutil.rmtree(chunk_dir, ignore_errors=True)

        print(f"\n  DONE")
        if md_file.exists():
            print(f"  markdown: {md_file}")
        if images_dir.exists():
            print(f"  images:   {images_dir} ({image_count} files)")

        return {
            "status": "done",
            "source": file_path,
            "markdown": str(md_file) if md_file.exists() else None,
            "images": str(images_dir) if images_dir.exists() else None,
            "image_count": image_count,
        }


def main():
    parser = argparse.ArgumentParser(
        description="MinerU document processor - convert documents to Markdown"
    )
    parser.add_argument("file_path", help="file path or URL")
    parser.add_argument("--output-dir", "-o", help="output directory")
    parser.add_argument(
        "--model", "-m",
        choices=["vlm", "pipeline", "MinerU-HTML"],
        help="model version (default: auto)",
    )
    parser.add_argument("--no-formula", action="store_true", help="disable formula recognition")
    parser.add_argument("--no-table", action="store_true", help="disable table recognition")

    args = parser.parse_args()

    result = asyncio.run(
        process_document(
            file_path=args.file_path,
            output_dir=args.output_dir,
            model_version=args.model,
            enable_formula=not args.no_formula,
            enable_table=not args.no_table,
        )
    )

    if result["status"] != "done":
        sys.exit(1)


if __name__ == "__main__":
    main()
