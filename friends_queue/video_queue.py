import mpv
import yt_dlp

from typing import List
from dataclasses import dataclass
from threading import Thread
from urllib.request import urlopen
from http.client import HTTPResponse
import base64

from .thumbnail_cache import ThumbnailCache


@dataclass
class VideoQueueItem:
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
    def __init__(
        self, player: mpv.MPV, ytdl: yt_dlp.YoutubeDL, thumbnails: ThumbnailCache
    ):
        super().__init__()
        self._player = player
        self._ytdl = ytdl
        self._thumbs = thumbnails

    def append(self, item: VideoQueueItem):
        assert item is not None
        super().append(item)

        args = {}
        if item.audio_url is not None:
            args["audio_file"] = item.audio_url
        if item.title is not None:
            args["force_media_title"] = item.title
        self._player.loadfile(item.video_url or item.url, mode="append-play", **args)

    def append_url(self, url: str):
        """Fetch video URL and asyncronously append to queue"""
        fetch_video(self._ytdl, self._thumbs, self, url)

    def move(self, item: int, to: int):
        assert item >= 0 and item < len(self)
        assert to >= 0 and to < len(self)

        if item == to:
            return None

        item_value = self[item]
        if item < to:
            for i in range(item, to):
                self[i] = self[i + 1]
        else:
            for i in range(to + 1, item):
                self[i] = self[i - 1]
        self[to] = item_value

        self._player.playlist_move(item, to)


def choose_thumbnail(thumbnails):
    if thumbnails is None:
        return None
    for thumb in thumbnails:
        width = thumb.get("width")
        if width is not None and width > 300 and "url" in thumb:
            return thumb["url"]
    return None


def get_stream_urls(info):
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

    def run(self):
        # Fetch video info
        info = self._ytdl.extract_info(self._item.url, download=False)

        if info.get("_type") == "playlist":
            info = info.get("entries")[0]

        self._item.title = info.get("fulltitle")
        self._item.uploader = info.get("uploader")
        self._item.duration = info.get("duration")
        self._item.duration_str = info.get("duration_string")

        video, audio = get_stream_urls(info)
        self._item.video_url = video.get("url")
        self._item.audio_url = audio.get("url")
        # TODO: Add other metadata added by ytdl_hook e.g. subtitles, chapters, bitrate

        # Append before fetching thumbnail as that requires another request and is not required to
        # play the video
        self._queue.append(self._item)

        # Fetch video thumbnail (as base64)
        thumbnail = choose_thumbnail(info.get("thumbnails"))
        if thumbnail is not None:
            self._item.thumbnail = self._thumbs.cache_thumbnail(thumbnail)


def fetch_video(
    ytdl: yt_dlp.YoutubeDL, thumbnails: ThumbnailCache, queue: VideoQueue, url: str
) -> VideoQueueItem:
    item = VideoQueueItem(url)

    FetchVideoThread(ytdl, thumbnails, queue, item).start()

    return item
