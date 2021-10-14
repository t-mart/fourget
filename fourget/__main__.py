from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from typing import Any, Optional

import aiofiles
import attr
import httpx
import typer
from tqdm import tqdm
from yarl import URL
from fourget import log


@attr.s(frozen=True, auto_attribs=True, kw_only=True, order=False)
class MediaDownload:
    url: str
    output_path: Path


@attr.s(frozen=True, auto_attribs=True, kw_only=True, order=False)
class Post:
    board: str
    post_id: int
    subject_text: Optional[str]
    media_timestamp: Optional[int]
    media_extension: Optional[str]
    file_size: Optional[int]

    @classmethod
    def from_json(cls, board: str, json_resp: dict[str, Any]) -> Post:
        post_id = json_resp["no"]

        subject_text = None
        if "sub" in json_resp:
            subject_text = json_resp["sub"]

        media_timestamp = None
        if "tim" in json_resp:
            media_timestamp = json_resp["tim"]

        media_extension = None
        if "ext" in json_resp:
            media_extension = json_resp["ext"]

        file_size = None
        if "fsize" in json_resp:
            file_size = json_resp["fsize"]

        return Post(
            board=board,
            post_id=post_id,
            subject_text=subject_text,
            media_timestamp=media_timestamp,
            media_extension=media_extension,
            file_size=file_size,
        )

    @property
    def media_filename(self) -> Optional[str]:
        if self.media_timestamp is None or self.media_extension is None:
            return None

        return f"{self.media_timestamp}{self.media_extension}"

    @property
    def media_url(self) -> Optional[str]:
        if self.media_filename is None:
            return None

        return f"https://i.4cdn.org/{self.board}/{self.media_filename}"


@attr.s(frozen=True, auto_attribs=True, kw_only=True, order=False)
class SiteURL:
    board: str
    thread_id: int

    @classmethod
    def from_url(cls, url: str) -> SiteURL:
        parsed = URL(url)
        path = Path(parsed.path)
        _, board, _, thread_id = path.parts
        return SiteURL(board=board, thread_id=int(thread_id))

    @property
    def api_endpoint_url(self) -> str:
        return f"https://a.4cdn.org/{self.board}/thread/{self.thread_id}.json"


async def consumer(
    queue: asyncio.Queue[MediaDownload],
    pbar: tqdm,
) -> None:
    """
    TODO
    """
    log.debug("Starting media download worker...")

    async with httpx.AsyncClient() as client:

        while True:
            media_download = await queue.get()

            async with client.stream("GET", media_download.url) as response:
                async with aiofiles.open(media_download.output_path, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        await f.write(chunk)
                        pbar.update(len(chunk))

            queue.task_done()
            pbar.set_postfix_str(
                f"file={media_download.output_path.name[:10]: <10}", refresh=False
            )
            pbar.update()
            log.info(f"{media_download.url} -> {media_download.output_path}")


async def producer(
    site_url: SiteURL,
    root_output_dir: Path,
    queue: asyncio.Queue[MediaDownload],
    pbar: tqdm,
) -> None:
    """
    TODO
    """
    log.debug("Starting thread reader worker...")
    async with httpx.AsyncClient() as client:
        response = await client.get(site_url.api_endpoint_url)
    json_body = response.json()
    posts = [
        Post.from_json(board=site_url.board, json_resp=post)
        for post in json_body["posts"]
    ]

    total_media_size = sum(post.file_size for post in posts if post.file_size)
    pbar.total = total_media_size

    assert posts[0] and posts[0].subject_text

    output_dir = root_output_dir / "4chan" / site_url.board / f"{posts[0].post_id}"

    output_dir.mkdir(parents=True, exist_ok=True)
    log.debug(f"Created output directory {output_dir}")

    for post in posts:
        if not post.media_url or not post.media_filename:
            continue
        await queue.put(
            MediaDownload(
                url=post.media_url, output_path=output_dir / post.media_filename
            )
        )

    await queue.join()


async def process_all(
    site_url: SiteURL,
    root_output_dir: Path,
    queue_maxsize: int,
    consumer_count: int,
) -> bool:
    """
    TODO
    """
    log.info(f"Downloading media files from {site_url}")

    queue: asyncio.Queue[MediaDownload] = asyncio.Queue(maxsize=queue_maxsize)
    pbar = tqdm(unit="B", unit_scale=True, unit_divisor=1024, leave=False)

    all_tasks = set()

    for _ in range(consumer_count):
        consumer_task = asyncio.create_task(
            consumer(
                queue=queue,
                pbar=pbar,
            ),
        )
        all_tasks.add(consumer_task)

    producer_task = asyncio.create_task(
        producer(
            site_url=site_url, root_output_dir=root_output_dir, queue=queue, pbar=pbar
        ),
    )
    all_tasks.add(producer_task)

    done, pending = await asyncio.wait(all_tasks, return_when="FIRST_COMPLETED")

    # we want exceptions to be raised if they've occured in a task. calling
    # Task.result() will do that (or just return the value of the coro if none was
    # raised).
    for task in done:
        task.result()

    pbar.close()

    for task in pending:
        if not task.done():
            task.cancel()

    await asyncio.gather(*pending, return_exceptions=True)

    return True


app = typer.Typer()


@app.command()
def main(
    url: str,
    output_dir: Path = typer.Option(
        default=Path("."),
        help=(
            "Directory in which to store downloaded media. Will be placed in "
            'heirarchy of "<output_dir>/4chan/<board>/<post_id>"'
        ),
    ),
    queue_maxsize: int = typer.Option(
        default=10_000,
        help=(
            "Maximum urls to keep in memory. Setting too low will "
            "reduce performance, while too high might fill up all your RAM."
        ),
    ),
    requestor_count: int = typer.Option(
        default=3,
        help=(
            "Number of concurrent requestors to run asynchronously. Setting too low "
            "will reduce performance, while too high will cause requestor starvation."
        ),
    ),
    asyncio_debug: bool = typer.Option(
        default=False,
        help="Turn on asyncio debugging.",
    ),
) -> int:
    """
    TODO
    """
    found = asyncio.run(
        process_all(
            site_url=SiteURL.from_url(url),
            root_output_dir=output_dir,
            queue_maxsize=queue_maxsize,
            consumer_count=requestor_count,
        ),
        debug=asyncio_debug,
    )

    if found:
        sys.exit(0)

    sys.exit(1)


if __name__ == "__main__":
    app()
