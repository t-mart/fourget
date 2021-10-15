"""fourget - Download/scrape media files from 4chan threads."""

from __future__ import annotations

import asyncio
import hashlib
import sys
from base64 import b64decode
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import aiofiles
import attr
import httpx
import typer
from tqdm import tqdm
from yarl import URL

from fourget import log

# Set of characters blocked in filenames by nix/windows/osx.
# Source: https://stackoverflow.com/a/31976060/235992
BLOCKED_FILE_NAME_CHARS = {chr(i) for i in range(32)} | set(R'<>:"/\|?*')


@attr.s(frozen=True, auto_attribs=True, kw_only=True, order=False)
class Post:
    """
    Data class representing 4chan posts.

    Note the optional attributes.
    """

    board: str
    post_id: int
    subject_text: Optional[str]
    comment: Optional[str]
    file: Optional[Post.File]

    @attr.s(frozen=True, auto_attribs=True, kw_only=True, order=False)
    class File:
        """Data class representing attachments to 4chan posts."""

        timestamp: int
        extension: str
        size: int
        md5: bytes
        board: str
        poster_stem: str

        @property
        def name(self) -> str:
            """Concatenation of timestamp and extension."""
            return f"{self.timestamp}{self.extension}"

        @property
        def url(self) -> str:
            """Location of the media file on 4chan's servers."""
            return f"https://i.4cdn.org/{self.board}/{self.name}"

    @classmethod
    def from_json(cls, board: str, json_resp: dict[str, Any]) -> Post:
        """Create a new post from a 4chan JSON post object."""
        post_id = json_resp["no"]

        subject_text = None
        if "sub" in json_resp:
            subject_text = json_resp["sub"]

        comment = None
        if "com" in json_resp:
            comment = json_resp["com"]

        file_timestamp = None
        if "tim" in json_resp:
            file_timestamp = json_resp["tim"]

        file_extension = None
        if "ext" in json_resp:
            file_extension = json_resp["ext"]

        file_size = None
        if "fsize" in json_resp:
            file_size = json_resp["fsize"]

        file_md5 = None
        if "md5" in json_resp:
            file_md5 = b64decode(json_resp["md5"])

        file_poster_stem = None
        if "filename" in json_resp:
            file_poster_stem = json_resp["filename"]

        if (
            file_timestamp is None
            or file_extension is None
            or file_size is None
            or file_md5 is None
            or file_poster_stem is None
        ):
            file = None
        else:
            file = Post.File(
                timestamp=file_timestamp,
                extension=file_extension,
                size=file_size,
                md5=file_md5,
                poster_stem=file_poster_stem,
                board=board,
            )

        return Post(
            board=board,
            post_id=post_id,
            subject_text=subject_text,
            comment=comment,
            file=file,
        )

    @property
    def description(self) -> Optional[str]:
        """
        Try to generate some textual description of the thread.

        First, if there is a post subject, use the first 80 characters of it. If not and
        if there is a comment, use the first 80 characters of the comment. Otherwise,
        return None.
        """
        max_length = 80

        if self.subject_text:
            return self.subject_text[:max_length]

        if self.comment:
            return self.comment[:max_length]

        return None


@attr.s(frozen=True, auto_attribs=True, kw_only=True, order=False)
class DownloadItem:
    """An enqueueable piece of work for the consumer tasks."""

    post_file: Post.File
    output_dir: Path


@attr.s(frozen=True, auto_attribs=True, kw_only=True, order=False)
class ThreadURL:
    """Data class for thread URLs."""

    board: str
    thread_id: int

    @classmethod
    def from_url(cls, url: str) -> ThreadURL:
        """Create a new ThreadURL from a desktop URL."""
        parsed = URL(url)
        path = Path(parsed.path)
        _, board, _, thread_id = path.parts
        return ThreadURL(board=board, thread_id=int(thread_id))

    @property
    def api_endpoint_url(self) -> str:
        """Get the API endpoint URL."""
        return f"https://a.4cdn.org/{self.board}/thread/{self.thread_id}.json"


async def md5_path(path: Path, max_chunk_size: int = 2 ** 20) -> bytes:
    """Return the md5 hash of a file from its path."""
    async with aiofiles.open(path, "rb") as f:
        md5_hash = hashlib.md5()
        while data := await f.read(max_chunk_size):
            md5_hash.update(data)
        return md5_hash.digest()


async def download_file(
    client: httpx.AsyncClient, url: str, path: Path, max_chunk_size: int = 2 ** 20
) -> AsyncIterator[int]:
    """Download url to path with client, yielding chunk lengths as we go."""
    async with client.stream("GET", url) as response:
        async with aiofiles.open(path, "wb") as f:
            async for chunk in response.aiter_bytes(max_chunk_size):
                await f.write(chunk)
                yield len(chunk)


def file_name_santize(name: str) -> str:
    """Return a file name that should be suitable as a file name on most OSes."""
    return "".join(c for c in name if c not in BLOCKED_FILE_NAME_CHARS)


async def consumer(
    queue: asyncio.Queue[DownloadItem],
    pbar: tqdm,
    new_download_event: asyncio.Event,
) -> None:
    """Remove DownloadItems from the queue and download them, if needed."""
    log.debug("Starting file download worker...")

    async with httpx.AsyncClient() as client:

        while True:
            download_item = await queue.get()

            post_file = download_item.post_file

            local_file_name = file_name_santize(
                f"{post_file.timestamp} - {post_file.poster_stem}{post_file.extension}"
            )

            output_path = download_item.output_dir / local_file_name

            if output_path.exists() and await md5_path(output_path) == post_file.md5:
                log.info(f"Not downloading {post_file.url} because it already exists")
                pbar.update(post_file.size)
            else:
                async for chunk_size in download_file(
                    client=client, url=post_file.url, path=output_path
                ):
                    pbar.update(chunk_size)
                log.info(f"{post_file.url} -> {output_path}")
                new_download_event.set()

            queue.task_done()


async def producer(
    site_url: ThreadURL,
    root_output_dir: Path,
    queue: asyncio.Queue[DownloadItem],
    pbar: tqdm,
) -> None:
    """HTTP get a 4chan thread and create DownloadItem objects for each post."""
    log.debug("Starting thread reader worker...")
    async with httpx.AsyncClient() as client:
        response = await client.get(site_url.api_endpoint_url)
    json_body = response.json()
    posts = [
        Post.from_json(board=site_url.board, json_resp=post)
        for post in json_body["posts"]
    ]

    total_file_size = sum(post.file.size for post in posts if post.file)
    pbar.total = total_file_size

    op = posts[0]
    assert op

    if op.description is None:
        trailer = ""
    else:
        trailer = f" - {op.description}"

    output_dir_name = file_name_santize(
        f"4chan - {site_url.board} - {op.post_id}{trailer}"
    )

    output_dir = root_output_dir / output_dir_name

    if not output_dir.exists():
        output_dir.mkdir(parents=True)
        log.debug(f"Created output directory {output_dir}")

    for post in posts:
        if post.file is None:
            continue
        await queue.put(DownloadItem(post_file=post.file, output_dir=output_dir))

    await queue.join()


async def start_queue(
    site_url: ThreadURL,
    root_output_dir: Path,
    queue_maxsize: int,
    consumer_count: int,
) -> bool:
    """Create a DownloadItem queue and start producers and consumers for it."""
    log.info(f"Downloading files from {site_url.api_endpoint_url}")

    queue: asyncio.Queue[DownloadItem] = asyncio.Queue(maxsize=queue_maxsize)
    pbar = tqdm(unit="B", unit_scale=True, unit_divisor=1024, leave=False)
    new_download_event = asyncio.Event()

    all_tasks = set()

    for _ in range(consumer_count):
        consumer_task = asyncio.create_task(
            consumer(
                queue=queue,
                pbar=pbar,
                new_download_event=new_download_event,
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

    return new_download_event.is_set()


app = typer.Typer()


@app.command()
def main(
    url: str,
    output_dir: Path = typer.Option(
        default=Path("."),
        help=(
            "Directory in which to store downloaded media files. Will be placed in "
            'heirarchy of "<output_dir>/4chan - <board> - <post_id> - '
            '<post_description>"'
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
    Download media files from a 4chan thread located at URL.

    URL should be in the form "https://boards.4channel.org/<board>/thread/<post_id>",
    such as "https://boards.4channel.org/g/thread/76759434". The "4chan.org" domain may
    also be used.
    """
    new_download = asyncio.run(
        start_queue(
            site_url=ThreadURL.from_url(url),
            root_output_dir=output_dir,
            queue_maxsize=queue_maxsize,
            consumer_count=requestor_count,
        ),
        debug=asyncio_debug,
    )

    sys.exit(0 if new_download else 1)


if __name__ == "__main__":
    app()
