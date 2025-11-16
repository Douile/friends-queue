"""Manage the queue of videos"""

from typing import List, Optional
from dataclasses import dataclass
from threading import Thread
from collections.abc import Sequence
import traceback
import sys

import mpv
import yt_dlp

from .thumbnail_cache import ThumbnailCache


class VideoNotFoundException(Exception):
    """Thrown when a video was not found"""


@dataclass
class VideoQueueItem:
    """Video Queue item data"""

    url: str
    title: str = None
    uploader: str = None
    duration: int = None
    duration_str: str = None
    video_url: str = None
    audio_url: str = None
    thumbnail: str = None


# TODO: Lock queue
class VideoQueue(List[VideoQueueItem]):
    """Managed video queue"""

    def __init__(
        self, player: mpv.MPV, ytdl: yt_dlp.YoutubeDL, thumbnails: ThumbnailCache
    ):
        super().__init__()
        self._player = player
        self._ytdl = ytdl
        self._thumbs = thumbnails
        self._active: list[FetchVideoThread] = []
        self._errors: list[Exception] = []

    def append(self, item: VideoQueueItem):
        """Append a new video item to queue and add to mpv playlist"""
        assert item is not None

        args = {}
        # This is basically replicating [ytdl_hook][1] find a way to call into that
        # [1]: https://github.com/mpv-player/mpv/blob/8536aaac3c2c22b77a596d0645ac99be20c0186a/player/lua/ytdl_hook.lua#L545
        if item.audio_url is not None:
            args["audio_file"] = item.audio_url

        self._player.loadfile(item.video_url or item.url, mode="append-play", **args)

        # Append to self after as player might error
        super().append(item)

    def append_url(self, url: str):
        """Fetch video URL and asyncronously append to queue"""
        if len(url.strip()) == 0:
            return  # Early return if no request provided
        if self.has_been_queued(url):
            return  # Early return if URL already in queue
        thread = _fetch_video(self._ytdl, self._thumbs, self, url)
        self._active.append(thread)

    def move(self, item_index: int, new_index: int):
        """Move queue items"""
        assert 0 <= item_index < len(self)
        assert 0 <= new_index < len(self)

        if item_index == new_index:
            return

        item_value = self[item_index]
        if item_index < new_index:
            for i in range(item_index, new_index):
                self[i] = self[i + 1]
        else:
            for i in range(new_index + 1, item_index):
                self[i] = self[i - 1]
        self[new_index] = item_value

        self._player.playlist_move(item_index, new_index)

    def has_been_queued(self, url: str):
        """Check if a URL has already been queued"""

        for item in self:
            if item.url == url:
                return True

        for fetch_url in self.active_fetches():
            if fetch_url == url:
                return True

        return False

    def active_fetches(self) -> Sequence[str]:
        """Get currently active fetches"""
        for i, thread in enumerate(self._active):
            if not thread.has_started() or (
                not thread.is_in_queue() and thread.is_alive()
            ):
                yield thread.url()
            else:
                thread = self._active.pop(i)
                error = thread.get_error()
                if error is not None:
                    self._errors.append(error)

    def recent_errors(self) -> Sequence[Exception]:
        """Get recent fetch exceptions"""
        while len(self._errors) > 0:
            yield self._errors.pop()


@dataclass
class _ThumbURL:
    width: int
    height: int
    url: str


def _choose_thumbnail(thumbnails) -> _ThumbURL:
    if thumbnails is None:
        return None
    for thumb in thumbnails:
        width = thumb.get("width")
        if width is not None and width > 300 and "url" in thumb:
            return _ThumbURL(thumb["width"], thumb["height"], thumb["url"])
    return None


def _get_stream_urls(info):
    video = None
    audio = None

    streams = info.get("requested_formats")
    if streams is not None:
        for stream in streams:
            if stream.get("video_ext", "none") != "none":
                video = stream
            elif stream.get("audio_ext", "none") != "none":
                audio = stream

    return (video, audio)


class FetchVideoThread(Thread):
    """Thread to fetch video info with ytdl"""

    def __init__(
        self,
        ytdl: yt_dlp.YoutubeDL,
        thumbnails: ThumbnailCache,
        queue: VideoQueue,
        item: VideoQueueItem,
    ):
        super().__init__(daemon=True)
        self._ytdl = ytdl
        self._thumbs = thumbnails
        self._queue = queue
        self._item = item
        self._is_in_queue = False
        self._has_started = False
        self._error = None

    def run(self):
        self._has_started = True
        try:
            self._do_fetch()
        # pylint: disable=bare-except
        except:
            self._error = sys.exception()
            traceback.print_exception(self._error)

    def _do_fetch(self):
        # Fetch video info
        info = self._ytdl.extract_info(self._item.url, download=False)

        if info is None:
            raise VideoNotFoundException(
                f'Unable to find a video that matches "{self._item.url}"'
            )

        if info.get("_type") == "playlist":
            info = info.get("entries")[0]

        self._item.title = info.get("fulltitle")
        self._item.uploader = info.get("uploader")
        self._item.duration = info.get("duration")
        self._item.duration_str = info.get("duration_string")

        video, audio = _get_stream_urls(info)
        if video is not None:
            self._item.video_url = video.get("url")
        if audio is not None:
            self._item.audio_url = audio.get("url")
        # TODO: Add other metadata added by ytdl_hook e.g. subtitles, chapters, bitrate

        # Append before fetching thumbnail as that requires another request and is not required to
        # play the video
        self._queue.append(self._item)
        self._is_in_queue = True

        # Fetch video thumbnail (as base64)
        thumbnail = _choose_thumbnail(info.get("thumbnails"))
        if thumbnail is not None:
            self._item.thumbnail = self._thumbs.cache_thumbnail(thumbnail.url)
            self._item.thumbnail_width = thumbnail.width
            self._item.thumbnail_height = thumbnail.height

    def url(self) -> str:
        """Get the URL being fetched"""
        return self._item.url

    def is_in_queue(self) -> bool:
        """Whether enough info has been fetched to add item to video queue"""
        return self._is_in_queue

    def has_started(self) -> bool:
        """Whether the fetch has been started"""
        return self._has_started

    def get_error(self) -> Optional[Exception]:
        """Get the error this thread encountered"""
        return self._error


def _fetch_video(
    ytdl: yt_dlp.YoutubeDL, thumbnails: ThumbnailCache, queue: VideoQueue, url: str
) -> FetchVideoThread:
    item = VideoQueueItem(url)

    thread = FetchVideoThread(ytdl, thumbnails, queue, item)
    thread.start()

    return thread
