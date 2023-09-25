"""Data classes"""

from dataclasses import dataclass
from collections.abc import Mapping

import mpv
import yt_dlp

from .static_files import StaticFiles
from .thumbnail_cache import ThumbnailCache
from .video_queue import VideoQueue


@dataclass
class Config:
    """Config options for the app

    Attributes:
        debug               Enable MPV debug messages
        search              Enable yt-dlp search
        format_specifier    Override the yt-dl FORMAT SPECIFIER
        host                Set the IP address to listen on
        port                Set the port to listen on
    """

    debug: bool = False
    search: bool = True
    format_specifier: str = None
    host: str = None
    port: int = None


@dataclass
class State:
    """App state"""

    config: Config
    player: mpv.MPV
    ytdl: yt_dlp.YoutubeDL
    static: StaticFiles
    thumbnails: ThumbnailCache
    queue: VideoQueue


@dataclass
class RequestState:
    """Active request state"""

    options: Mapping[str, str] = None
    redirect: bool = False
    location_extra: str = "?"
    text: str = ""
