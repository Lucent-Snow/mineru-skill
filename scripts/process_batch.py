#!/usr/bin/env python3
"""
MinerU 批量文档处理
扫描目录下所有匹配文件，并行处理转换为 Markdown。

用法：
  python process_batch.py <目录>
  python process_batch.py <目录> --pattern "*.pdf"
  python process_batch.py <目录> --pattern "*.docx" --max-workers 3

参数：
  directory            目录路径（必需）
  --pattern PATTERN    文件匹配模式（默认 "*.pdf"）
  --max-workers N      最大并发数（默认 5）
  --recursive          递归扫描子目录
"""
import argparse
import asyncio
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from niquests import AsyncSession

from _config import MODEL_AUTO_SELECT
from _api import (
    load_tokens,
    get_random_token,
    check_tokens_valid,
    validate_file,
    upload_file,
    wait_for_completion,
    download_and_extract,
    find_markdown,
)


@dataclass
class FileTask:
    """单个文件的处理任务"""
    file_path: str
    file_info: Dict
    status: str = "pending"
    batch_id: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0


async def process_one_file(
    task: FileTask,
    token: str,
    semaphore: asyncio.Semaphore,
    index: int,
    total: int,
) -> FileTask:
    """处理单个文件（受信号量控制并发）"""
    async with semaphore:
        task.start_time = time.time()
        name = task.file_info["name"]
        fmt = task.file_info["format"]

        print(f"  [{index}/{total}] {name} - uploading...")

        try:
            async with AsyncSession() as session:
                # 上传
                model = MODEL_AUTO_SELECT.get(fmt, "vlm")
                options = {
                    "model_version": model,
                    "enable_formula": True,
                    "enable_table": True,
                }
                batch_id = await upload_file(session, token, task.file_path, **options)
                if not batch_id:
                    task.status = "failed"
                    task.error = "upload failed"
                    task.end_time = time.time()
                    print(f"  [{index}/{total}] {name} - FAILED (upload)")
                    return task

                task.batch_id = batch_id
                print(f"  [{index}/{total}] {name} - processing...")

                # 等待处理
                results = await wait_for_completion(session, token, batch_id, max_wait=300)
                if not results or len(results) == 0:
                    task.status = "failed"
                    task.error = "processing failed"
                    task.end_time = time.time()
                    print(f"  [{index}/{total}] {name} - FAILED (process)")
                    return task

                r = results[0]
                if r.get("state") != "done":
                    task.status = "failed"
                    task.error = r.get("err_msg", "unknown error")
                    task.end_time = time.time()
                    print(f"  [{index}/{total}] {name} - FAILED ({task.error})")
                    return task

                zip_url = r.get("full_zip_url")
                print(f"  [{index}/{total}] {name} - downloading...")

                # 下载
                output_path = Path(task.file_path).parent
                chunk_dir = output_path / f"{Path(task.file_path).stem}_result"
                chunk_dir.mkdir(exist_ok=True)

                extracted = await download_and_extract(session, zip_url, str(chunk_dir))
                if not extracted:
                    task.status = "failed"
                    task.error = "download failed"
                    task.end_time = time.time()
                    print(f"  [{index}/{total}] {name} - FAILED (download)")
                    return task

                # 整理输出
                stem = Path(task.file_path).stem
                md_file = output_path / f"{stem}.md"
                images_dir = output_path / f"{stem}_images"

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

                task.status = "done"
                task.result = {
                    "markdown": str(md_file),
                    "images": str(images_dir),
                    "image_count": image_count,
                }
                task.end_time = time.time()
                elapsed = task.end_time - task.start_time
                print(f"  [{index}/{total}] {name} - DONE ({elapsed:.1f}s)")
                return task

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.end_time = time.time()
            print(f"  [{index}/{total}] {name} - FAILED ({e})")
            return task


async def process_batch(
    directory: str,
    pattern: str = "*.pdf",
    max_workers: int = 5,
    recursive: bool = False,
) -> List[FileTask]:
    """批量处理目录下所有匹配文件"""

    # 1. 检查 Token
    tokens = load_tokens()
    if not tokens:
        print("  ERROR: no tokens found, run batch_login.py first")
        return []

    all_valid, expired = check_tokens_valid(tokens)
    if not all_valid:
        print(f"  ERROR: {len(expired)} token(s) expired, run batch_login.py first")
        return []

    token = get_random_token(tokens)

    # 2. 扫描文件
    dir_path = Path(directory).expanduser().resolve()
    if not dir_path.is_dir():
        print(f"  ERROR: not a directory: {dir_path}")
        return []

    if recursive:
        files = sorted(str(f) for f in dir_path.rglob(pattern))
    else:
        files = sorted(str(f) for f in dir_path.glob(pattern))

    if not files:
        print(f"  no files matching '{pattern}' in {dir_path}")
        return []

    # 3. 验证文件
    tasks = []
    for fp in files:
        ok, err, info = validate_file(fp)
        if ok:
            tasks.append(FileTask(file_path=fp, file_info=info))
            print(f"    {info['name']} ({info['size']/1024/1024:.1f}MB)")
        else:
            print(f"    {Path(fp).name} - SKIP: {err}")

    if not tasks:
        print("  no valid files")
        return []

    print(f"\n  {len(tasks)} file(s) to process, max_workers={max_workers}\n")

    # 4. 并行处理
    semaphore = asyncio.Semaphore(max_workers)
    total = len(tasks)

    results = await asyncio.gather(
        *[
            process_one_file(task, token, semaphore, i + 1, total)
            for i, task in enumerate(tasks)
        ]
    )

    # 5. 汇总
    success = [t for t in results if t.status == "done"]
    failed = [t for t in results if t.status == "failed"]

    print(f"\n{'='*55}")
    print(f"  SUMMARY")
    print(f"{'='*55}")
    print(f"  total:   {len(results)}")
    print(f"  success: {len(success)}")
    print(f"  failed:  {len(failed)}")

    if success:
        total_time = max(t.end_time - t.start_time for t in results if t.end_time > 0)
        print(f"  time:    {total_time:.1f}s")

    if failed:
        print(f"\n  FAILED FILES:")
        for t in failed:
            print(f"    {t.file_info['name']}: {t.error}")

    print(f"{'='*55}")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="MinerU batch processor - convert all documents in a directory"
    )
    parser.add_argument("directory", help="directory path")
    parser.add_argument("--pattern", "-p", default="*.pdf", help='file pattern (default: "*.pdf")')
    parser.add_argument("--max-workers", "-w", type=int, default=5, help="max concurrency (default: 5)")
    parser.add_argument("--recursive", "-r", action="store_true", help="scan subdirectories")

    args = parser.parse_args()

    results = asyncio.run(
        process_batch(
            directory=args.directory,
            pattern=args.pattern,
            max_workers=args.max_workers,
            recursive=args.recursive,
        )
    )

    success = sum(1 for t in results if t.status == "done")
    if success == len(results) and results:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
