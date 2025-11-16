"""Serve static files"""

import os.path
import os
from http.server import BaseHTTPRequestHandler
from collections.abc import MutableMapping, Sequence
from io import FileIO
from dataclasses import dataclass
from shutil import copyfileobj
from time import time
from mimetypes import guess_type

STATIC_PREFIX = "/static/"

CACHE_MAX_AGE = 60 * 60 * 3  # 3 hours
CACHE_CONTROL = "private, max_age={}".format(CACHE_MAX_AGE)


@dataclass
class File:
    """Data about a static file"""

    file: FileIO
    content_type: str
    content_len: int


class StaticFiles:
    """Manage serving static files"""

    def __init__(self, base_path: str, files: Sequence[str], use_sendfile=True):
        assert os.path.isdir(base_path)
        self._files: MutableMapping[str, FileIO] = {}
        self._use_sendfile = use_sendfile
        self._modified = None

        # Open files
        for file_name in files:
            path = os.path.join(base_path, file_name)
            assert os.path.isfile(path)

            print("Loading", file_name, path)

            # pylint: disable=consider-using-with
            file = open(path, "rb")
            file.seek(0, os.SEEK_END)
            self._files[file_name] = File(
                file=file, content_type=guess_type(path)[0], content_len=file.tell()
            )

    def handle_request(self, handler: BaseHTTPRequestHandler, path: str):
        """Handle a request, caller must check path is a static URL prior to calling"""
        file_name = path[len(STATIC_PREFIX) :]

        if not file_name in self._files:
            print("Static not found", file_name)
            handler.send_error(404)
            return

        file = self._files[file_name]
        assert file is not None

        if self._modified is None:
            self._modified = handler.date_time_string(timestamp=time())

        # Check if client has cached
        modified_since = handler.headers.get("If-Modified-Since")
        if modified_since is not None and modified_since == self._modified:
            handler.send_response(304)
            handler.send_header(
                "Expires", handler.date_time_string(timestamp=time() + 30)
            )
            handler.send_header("Content-Type", file.content_type)
            handler.send_header("Content-Length", file.content_len)
            handler.send_header("Cache-Control", CACHE_CONTROL)
            handler.send_header("Last-Modified", self._modified)
            handler.end_headers()
            return

        # Send image
        handler.send_response(200)
        handler.send_header("Content-Type", file.content_type)
        handler.send_header("Content-Length", file.content_len)
        handler.send_header("Cache-Control", CACHE_CONTROL)
        handler.send_header("Last-Modified", self._modified)
        handler.end_headers()
        if self._use_sendfile:
            handler.request.sendfile(file.file, offset=0, count=file.content_len)
        else:
            file.file.seek(0)
            copyfileobj(file.file, handler.wfile, length=file.content_len)

    @staticmethod
    def is_static_url(path: str) -> bool:
        """Check if a path references a static file"""
        return path.startswith(STATIC_PREFIX)
