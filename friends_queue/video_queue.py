import mpv
import yt_dlp

from typing import List
from dataclasses import dataclass
from threading import Thread


@dataclass
class VideoQueueItem:
    url: str
    title: str = None
    uploader: str = None
    duration: int = None
    duration_str: str = None
    stream_url: str = None
    thumbnail: str = None


# TODO: Lock queue
# TODO: Async ytdl fetch
class VideoQueue(List[VideoQueueItem]):
    def __init__(self, player: mpv.MPV, ytdl: yt_dlp.YoutubeDL):
        super().__init__()
        self._player = player
        self._ytdl = ytdl

    def append(self, item: VideoQueueItem):
        assert item is not None
        super().append(item)
        self._player.loadfile(item.url, mode="append-play")

    def append_url(self, url: str):
        self.append(fetch_video(self._ytdl, url))

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


class FetchVideoThread(Thread):
    def __init__(self, ytdl: yt_dlp.YoutubeDL, item: VideoQueueItem):
        super().__init__()
        self._ytdl = ytdl
        self._item = item

    def run(self):
        info = self._ytdl.extract_info(self._item.url, download=False)
        self._item.title = info.get("fulltitle")
        self._item.uploader = info.get("uploader")
        self._item.stream_url = None  # TODO
        self._item.duration = info.get("duration")
        self._item.duration_str = info.get("duration_string")
        self._item.thumbnail = info.get("thumbnail")  # TODO: Select thumbnail res


def fetch_video(ytdl: yt_dlp.YoutubeDL, url: str) -> VideoQueueItem:
    item = VideoQueueItem(url)

    FetchVideoThread(ytdl, item).start()

    return item
