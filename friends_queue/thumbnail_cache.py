import os.path
from dataclasses import dataclass
from urllib.request import urlopen
import hashlib
from http.client import HTTPResponse
from http.server import BaseHTTPRequestHandler
from collections.abc import MutableMapping
from io import FileIO
from shutil import copyfileobj
from time import time

THUMBNAIL_PREFIX = "/thumbnails/"

CACHE_MAX_AGE = 60 * 60 * 24  # 24 hours
CACHE_CONTROL = "private, max_age={}".format(CACHE_MAX_AGE)


@dataclass
class ThumbnailItem:
    file: FileIO
    content_type: str
    content_len: int
    timestamp: float


class ThumbnailCache:
    """A cache that manages fetching and storing thumbnails"""

    def __init__(self, cache_dir: str):
        """Create a thumbnail cache"""
        self._cache_dir = os.path.abspath(cache_dir)
        assert os.path.isdir(self._cache_dir)
        self._cached: MutableMapping[str, ThumbnailItem] = {}

    def cache_thumbnail(self, url: str) -> str:
        """Download an image from URL and return path to fetch from cache"""
        res: HTTPResponse = urlopen(url)
        if not isinstance(res, HTTPResponse):
            raise Exception("Expected HTTP response")
        if res.status != 200:
            raise Exception("Bad image status code")
        content_length = res.headers.get("content-length")
        if content_length is not None:
            content_length = int(content_length)
        content_type = res.headers.get_content_type()
        if content_type is None or not content_type.startswith("image/"):
            raise Exception(
                "Thumbnail URL returned content-type that is not an image: "
                + str(content_type)
            )
        thumb_hash = hashlib.sha512(bytes(url, "utf-8")).hexdigest()
        file_path = os.path.join(self._cache_dir, thumb_hash)
        with open(file_path, "wb") as file:
            copyfileobj(res, file, length=content_length)
        # pylint: disable=consider-using-with
        file = open(file_path, "rb")
        if content_length is None:
            file.seek(0, os.SEEK_END)
            content_length = file.tell()
        self._cached[thumb_hash] = ThumbnailItem(
            file, content_type, content_length, time()
        )
        return "." + THUMBNAIL_PREFIX + thumb_hash

    def handle_request(self, handler: BaseHTTPRequestHandler, path: str):
        """Handle a request, caller must check path is a thumbnail URL prior to calling"""
        thumb_hash = path[len(THUMBNAIL_PREFIX) :]
        if thumb_hash in self._cached:
            item = self._cached[thumb_hash]
            assert item is not None

            item_modified = handler.date_time_string(timestamp=item.timestamp)

            # Check if client has cached
            modified_since = handler.headers.get("If-Modified-Since")
            if modified_since is not None and modified_since == item_modified:
                handler.send_response(304)
                handler.send_header(
                    "Expires", handler.date_time_string(timestamp=time() + 30)
                )
                handler.send_header("Content-Type", item.content_type)
                handler.send_header("Content-Length", item.content_len)
                handler.send_header("Cache-Control", CACHE_CONTROL)
                handler.send_header("Last-Modified", item_modified)
                handler.end_headers()
                return

            # Send image
            handler.send_response(200)
            handler.send_header("Content-Type", item.content_type)
            handler.send_header("Content-Length", item.content_len)
            handler.send_header("Cache-Control", CACHE_CONTROL)
            handler.send_header("Last-Modified", item_modified)
            handler.end_headers()
            item.file.seek(0)
            copyfileobj(item.file, handler.wfile, length=item.content_len)
        else:
            handler.send_error(404)

    @staticmethod
    def is_thumbnail_url(path: str) -> bool:
        return path.startswith(THUMBNAIL_PREFIX)
