"""Manage the queue of videos"""

from typing import List
from dataclasses import dataclass
from threading import Thread
from collections.abc import Sequence

import mpv
import yt_dlp

from .thumbnail_cache import ThumbnailCache


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

    def append(self, item: VideoQueueItem):
        """Append a new video item to queue and add to mpv playlist"""
        assert item is not None

        args = {}
        if item.audio_url is not None:
            args["audio_file"] = item.audio_url
        if item.title is not None:
            args["force_media_title"] = item.title
        self._player.loadfile(item.video_url or item.url, mode="append-play", **args)

        # Append to self after as player might error
        super().append(item)

    def append_url(self, url: str):
        """Fetch video URL and asyncronously append to queue"""
        if len(url.strip()) == 0:
            return  # Early return if no request provided
        _fetch_video(self._ytdl, self._thumbs, self, url)

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

    def active_fetches(self) -> Sequence[str]:
        """Get currently active fetches"""
        for i, thread in enumerate(self._active):
            if not thread.is_in_queue() and thread.is_alive():
                yield thread.url()
            else:
                self._active.pop(i)


def _choose_thumbnail(thumbnails):
    if thumbnails is None:
        return None
    for thumb in thumbnails:
        width = thumb.get("width")
        if width is not None and width > 300 and "url" in thumb:
            return thumb["url"]
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

    def run(self):
        self._queue._active.append(self)
        # Fetch video info
        info = self._ytdl.extract_info(self._item.url, download=False)

        if info is None:
            return  # TODO: handle error

        if info.get("_type") == "playlist":
            info = info.get("entries")[0]

        self._item.title = info.get("fulltitle")
        self._item.uploader = info.get("uploader")
        self._item.duration = info.get("duration")
        self._item.duration_str = info.get("duration_string")

        video, audio = _get_stream_urls(info)
        self._item.video_url = video.get("url")
        self._item.audio_url = audio.get("url")
        # TODO: Add other metadata added by ytdl_hook e.g. subtitles, chapters, bitrate

        # Append before fetching thumbnail as that requires another request and is not required to
        # play the video
        self._queue.append(self._item)
        self._is_in_queue = True

        # Fetch video thumbnail (as base64)
        thumbnail = _choose_thumbnail(info.get("thumbnails"))
        if thumbnail is not None:
            self._item.thumbnail = self._thumbs.cache_thumbnail(thumbnail)

    def url(self) -> str:
        """Get the URL being fetched"""
        return self._item.url

    def is_in_queue(self) -> bool:
        """Whether enough info has been fetched to add item to video queue"""
        return self._is_in_queue


def _fetch_video(
    ytdl: yt_dlp.YoutubeDL, thumbnails: ThumbnailCache, queue: VideoQueue, url: str
) -> VideoQueueItem:
    item = VideoQueueItem(url)

    FetchVideoThread(ytdl, thumbnails, queue, item).start()

    return item
