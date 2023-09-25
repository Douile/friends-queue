#!/usr/bin/env python3
"""Friend's Queue"""

import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, quote
import os.path

import mpv
import yt_dlp

from .actions import ACTIONS
from .cache import make_cache_dirs
from .generate import generate_page
from .static_files import StaticFiles
from .thumbnail_cache import ThumbnailCache
from .types import Config, RequestState, State
from .video_queue import VideoQueue
from .utils import parse_search_query

SRC_DIR = os.path.dirname(__file__)

# Address to listen on
ADDRESS = ("0.0.0.0", 8000)
# Specify which format to select https://github.com/yt-dlp/yt-dlp#format-selection
FORMAT_SPECIFIER = (
    "bv[height<=720][vbr<2000][fps<=30]+ba[abr<=62]/b[height<=720][fps<=30]"
)


class HTTPThread(threading.Thread):
    """Run threaded HTTP server in a thread"""

    def __init__(self, address: (str, int), handler):
        super().__init__()
        self.address = address
        self.httpd = ThreadingHTTPServer(address, handler)

    def run(self):
        print("Listening...", self.address)
        self.httpd.serve_forever()

    def shutdown(self):
        """Shut down http listening thread"""
        self.httpd.shutdown()


class PlayerThread(threading.Thread):
    """Thread that waits for player to exit"""

    def __init__(self, state: State):
        super().__init__()
        self._state = state

    def run(self):
        self._state.player.wait_for_shutdown()

        with self._state.close_condition:
            self._state.close_condition.notify_all()


def http_handler(app: State):
    """Create a HTTPHandler class with encapsulated state"""

    class HTTPHandler(BaseHTTPRequestHandler):
        """Custom HTTP request handler"""

        # pylint: disable-next=invalid-name
        def do_GET(self):
            """Handle get requests"""

            state = RequestState()
            i = self.path.find("?")

            path = self.path[:i] if i > -1 else self.path
            if ThumbnailCache.is_thumbnail_url(path):
                app.thumbnails.handle_request(self, path)
                return
            if StaticFiles.is_static_url(path):
                app.static.handle_request(self, path)
                return
            if path != "/":
                # 404
                self.send_error(404)
                self.end_headers()
                return

            if i > -1:
                query = self.path[i + 1 :]
                state.options = parse_search_query(query)
                handle_options(state, app.player, app.queue)
                if state.redirect:
                    self.send_response(302)
                    path = self.path[:i]
                    if len(state.location_extra) > 1:
                        path += state.location_extra
                    self.send_header("Location", path)
                    self.end_headers()
                    return

            # Normal response
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            # Document headings
            self.wfile.write(
                b'<!DOCTYPE HTML>\n<html lang="en"><head>'
                + b"<title>Friends Queue</title>"
                + b'<meta name="viewport" content="width=device-width,initial-scale=1">'
                + b'<meta charset="utf-8">'
                + b'<link rel="stylesheet" href="./static/friends_queue.css">'
                + b'<script async src="./static/friends_queue.js"></script>'
                + b"</head><body>"
            )
            # Page content
            generate_page(self.wfile, app, state)
            self.wfile.write(b"</body></html>")

    return HTTPHandler


def handle_options(state: RequestState, player: mpv.MPV, queue: VideoQueue):
    """Handle request query options"""
    opts = state.options
    if "link" in opts:
        state.redirect = True
        print("Adding to queue", opts["link"])
        queue.append_url(opts["link"])
    if "a" in opts:
        state.redirect = True
        action = opts["a"]
        if action == "info":
            state.location_extra += (
                "text="
                + quote(
                    f"Playing {player.media_title} {player.percent_pos}% ({player.video_format} {player.video_codec} {player.hwdec_current} {player.width}x{player.height}) Drop(dec={player.decoder_frame_drop_count}, frame={player.frame_drop_count})"
                )
                + "&"
            )
        else:
            act = ACTIONS.get(action)
            if act is not None:
                act(player)
    if "text" in opts:
        state.text = unquote(opts["text"])
    if "seek" in opts:
        state.redirect = True
        player.seek(opts["seek"], "absolute-percent+keyframes")
    if "pos" in opts:
        state.redirect = True
        new_pos = int(opts["pos"])
        if player.playlist_pos != new_pos:
            player.playlist_pos = new_pos
    if "show_skipped" in opts:
        state.show_skipped_items = opts["show_skipped"] == "1"


def main(config: Config = Config()):
    """Main func"""

    assert isinstance(config, Config)

    close_condition = threading.Condition()

    cache_dirs = make_cache_dirs()

    extra_args = {}
    if config.debug:
        extra_args["log_handler"] = print
        extra_args["loglevel"] = "debug"
    extra_args["script_opts"] = "ytdl_hook-cachedir=" + cache_dirs.ytdl
    player = mpv.MPV(
        ytdl=True,
        ytdl_format=config.format_specifier or FORMAT_SPECIFIER,
        input_default_bindings=True,
        input_vo_keyboard=True,
        osc=True,
        idle=True,
        **extra_args,
    )

    yt_args = {
        "format": config.format_specifier or FORMAT_SPECIFIER,
        "skip_download": True,
        "cachedir": cache_dirs.ytdl,
    }
    if config.search:
        yt_args["default_search"] = "auto"

    ytdl = yt_dlp.YoutubeDL(yt_args)

    static = StaticFiles(
        os.path.dirname(__file__), ["friends_queue.css", "friends_queue.js"]
    )
    thumbnails = ThumbnailCache(cache_dirs.thumbs)
    queue = VideoQueue(player, ytdl, thumbnails)

    state = State(config, player, ytdl, static, thumbnails, queue, close_condition)

    listen_address = ADDRESS
    if config.host is not None:
        listen_address = (config.host, listen_address[1])
    if config.port is not None:
        listen_address = (listen_address[0], config.port)

    http = HTTPThread(
        listen_address,
        http_handler(state),
    )
    http.start()

    PlayerThread(state).start()

    with close_condition:
        try:
            close_condition.wait()
        except KeyboardInterrupt:
            pass

    del player

    print("Shutting down")
    http.shutdown()

    print("Deleting cache")
    del cache_dirs


if __name__ == "__main__":
    main()
