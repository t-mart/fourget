"""fourget - Download/scrape media files from 4chan threads."""

from __future__ import annotations

import asyncio
import hashlib
import json
from base64 import b64decode
from collections.abc import AsyncIterator, Callable, Coroutine
from pathlib import Path
from typing import Any, Optional

import attr
import httpx
import typer
from rich.progress import TaskID
from yarl import URL

from fourget import __version__, log
from fourget.console import PROGRESS
from fourget.exception import (
    FourgetException,
    MalformedThreadURLException,
    ThreadNotFoundException,
)
from fourget.queue import Item, Queue, StopReason


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
class Thread:
    """Data class for threads."""

    board: str
    thread_id: int

    @classmethod
    def from_url(cls, url: str) -> Thread:
        """Create a new ThreadURL from a desktop URL."""
        parsed = URL(url)
        path = Path(parsed.path)
        try:
            # value error may occur on unpack if not enough parts
            _, board, _, thread_id = path.parts
            # value error may occur if thread_id is not numeric
            return Thread(board=board, thread_id=int(thread_id))
        except ValueError as value_error:
            raise MalformedThreadURLException(url) from value_error

    @property
    def api_endpoint_url(self) -> str:
        """Get the API endpoint URL."""
        return f"https://a.4cdn.org/{self.board}/thread/{self.thread_id}.json"

    def to_url(self) -> str:
        """Reconstruct the URL for this thread."""
        return f"https://boards.4channel.org/{self.board}/thread/{self.thread_id}"


async def md5_path(path: Path, max_chunk_size: int = 2 ** 20) -> bytes:
    """Return the md5 hash of a file from its path."""
    with path.open("rb") as f:
        md5_hash = hashlib.md5()
        while data := f.read(max_chunk_size):
            md5_hash.update(data)
        return md5_hash.digest()


async def download_file(
    client: httpx.AsyncClient, url: str, path: Path, max_chunk_size: int = 2 ** 20
) -> AsyncIterator[int]:
    """Download url to path with client, yielding chunk lengths as we go."""
    async with client.stream("GET", url) as response:
        with path.open("wb") as f:
            async for chunk in response.aiter_bytes(max_chunk_size):
                f.write(chunk)
                yield len(chunk)


# Set of characters blocked in filenames by nix/windows/osx.
# Source: https://stackoverflow.com/a/31976060/235992
BLOCKED_FILE_NAME_CHARS = {chr(i) for i in range(32)} | set(R'<>:"/\|?*')


def file_name_sanitize(name: str) -> str:
    """
    Return a file name that should be suitable on most OSes. Specifically, certain known
    bad characters will be filtered out.
    """
    return "".join(c for c in name if c not in BLOCKED_FILE_NAME_CHARS)


@attr.s(frozen=True, auto_attribs=True, kw_only=True, order=False)
class MediaDownloadItem(Item):
    """Item that downloads media files."""

    post_file: Post.File
    thread_dir: Path
    progress_task: TaskID
    client: httpx.AsyncClient

    async def process(
        self, enqueue: Callable[[Item], Coroutine[Any, Any, None]]
    ) -> None:
        """Download media files to local disk from URLs."""
        local_file_name = (
            file_name_sanitize(
                f"{self.post_file.timestamp} - {self.post_file.poster_stem}"
            )
            + self.post_file.extension
        )

        output_path = self.thread_dir / local_file_name

        if output_path.exists() and await md5_path(output_path) == self.post_file.md5:
            log.info(
                f"{self.post_file.url} already exists at "
                f"{output_path.absolute().as_uri()}"
            )
            PROGRESS.advance(self.progress_task, self.post_file.size)
        else:
            async for chunk_size in download_file(
                client=self.client, url=self.post_file.url, path=output_path
            ):
                PROGRESS.advance(self.progress_task, chunk_size)
            log.info(f"{self.post_file.url} -> {output_path.absolute().as_uri()}")


@attr.s(frozen=True, auto_attribs=True, kw_only=True, order=False)
class ThreadReadItem(Item):
    """Item that reads the thread."""

    thread: Thread
    root_output_dir: Path
    progress_task: TaskID
    client: httpx.AsyncClient

    async def process(
        self, enqueue: Callable[[Item], Coroutine[Any, Any, None]]
    ) -> None:
        """Read the thread json and enqueue media downloads for posts with files."""
        response = await self.client.get(self.thread.api_endpoint_url)

        if response.status_code == 404:
            raise ThreadNotFoundException(self.thread.to_url())

        json_body = response.json()

        posts = [
            Post.from_json(board=self.thread.board, json_resp=post)
            for post in json_body["posts"]
        ]

        total_file_size = sum(post.file.size for post in posts if post.file)
        PROGRESS.update(self.progress_task, total=total_file_size)

        orig_post = posts[0]
        assert orig_post

        if orig_post.description is None:
            trailer = ""
        else:
            trailer = f" - {orig_post.description}"

        output_dir_name = file_name_sanitize(
            f"4chan - {self.thread.board} - {orig_post.post_id}{trailer}"
        )

        thread_dir = self.root_output_dir / output_dir_name

        await enqueue(JSONSaveItem(thread_path=thread_dir, json_object=json_body))

        if not thread_dir.exists():
            thread_dir.mkdir(parents=True)
            log.debug(f"Created thread directory {thread_dir.absolute().as_uri()}")

        for post in posts:
            if post.file is None:
                continue
            await enqueue(
                MediaDownloadItem(
                    post_file=post.file,
                    thread_dir=thread_dir,
                    progress_task=self.progress_task,
                    client=self.client,
                )
            )


@attr.s(frozen=True, auto_attribs=True, kw_only=True, order=False)
class JSONSaveItem(Item):
    """Item to save the thread's json."""

    thread_path: Path
    json_object: Any

    async def process(
        self, enqueue: Callable[[Item], Coroutine[Any, Any, None]]
    ) -> None:
        """Save the thread's json to 'thread.json' in the thread directory."""
        json_path = self.thread_path / "thread.json"

        with json_path.open("w") as f:
            f.write(json.dumps(self.json_object, indent=2))

        log.info(f"Saved thread json to {json_path.absolute().as_uri()}")


async def start_queue(
    thread: Thread,
    root_output_dir: Path,
    queue_maxsize: int,
    worker_count: int,
    progress_task: TaskID,
) -> None:
    """Create a DownloadItem queue and start producers and consumers for it."""
    log.info(f"Downloading files from {thread.api_endpoint_url}")

    queue: Queue = Queue.create(
        queue_maxsize=queue_maxsize,
        stop_reason_callback=lambda sr: log.info(str(sr)),
        joined_stop_reason=StopReason(
            reason=f"All media files of {thread.to_url()} have been gotten"
        ),
    )

    async with httpx.AsyncClient() as client:
        await queue.complete(
            initial_items=[
                ThreadReadItem(
                    thread=thread,
                    root_output_dir=root_output_dir,
                    progress_task=progress_task,
                    client=client,
                ),
            ],
            worker_count=worker_count,
        )

    PROGRESS.stop_task(progress_task)


app = typer.Typer()


def version_callback(value: bool) -> None:
    """Print the version and exit."""
    if value:
        typer.echo(f"fourget v{__version__}")
        raise typer.Exit()


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
    worker_count: int = typer.Option(
        default=3,
        help=(
            "Number of concurrent worker tasks to run asynchronously. Setting too "
            "low will reduce performance, while too high will cause requestor "
            "starvation."
        ),
    ),
    asyncio_debug: bool = typer.Option(
        default=False,
        help="Turn on asyncio debugging.",
    ),
    # pylint: disable-next=unused-argument
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
    ),
) -> int:
    """
    Download media files from a 4chan thread located at URL.

    URL should be in the form "https://boards.4channel.org/<board>/thread/<post_id>",
    such as "https://boards.4channel.org/g/thread/76759434". The "4chan.org" domain may
    also be used.
    """
    # do initialization of the progress bar out here, because we need to reference it
    # to clean it up when we're finished or an exception is raised
    PROGRESS.start()
    progress_task = PROGRESS.add_task(description="Downloading")
    try:
        asyncio.run(
            start_queue(
                thread=Thread.from_url(url),
                root_output_dir=output_dir,
                queue_maxsize=queue_maxsize,
                worker_count=worker_count,
                progress_task=progress_task,
            ),
            debug=asyncio_debug,
        )
    except FourgetException as fourget_exception:
        log.error(fourget_exception.msg)
        PROGRESS.update(progress_task, visible=False)
        raise typer.Exit(1)
    else:
        raise typer.Exit(0)
    finally:
        PROGRESS.stop()


if __name__ == "__main__":
    app()
