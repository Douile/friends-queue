#!/usr/bin/env python3
"""Friend's Queue"""

import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, quote
import html
from math import floor
import os.path
from collections.abc import Mapping
from dataclasses import dataclass

import mpv
import yt_dlp

from .actions import ACTIONS
from .cache import make_cache_dirs
from .video_queue import VideoQueue
from .thumbnail_cache import ThumbnailCache
from .utils import parse_search_query

SRC_DIR = os.path.dirname(__file__)

# Address to listen on
ADDRESS = ("0.0.0.0", 8000)
# Specify which format to select https://github.com/yt-dlp/yt-dlp#format-selection
FORMAT_SPECIFIER = (
    "bv[height<=720][vbr<2000][fps<=30]+ba[abr<=62]/b[height<=720][fps<=30]"
)

with open(os.path.join(SRC_DIR, "friends_queue.css"), "rb") as f:
    STYLE = f.read()
with open(os.path.join(SRC_DIR, "friends_queue.js"), "rb") as f:
    JS = f.read()


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


def seconds_duration(secs: float) -> str:
    """Convert time in seconds to duration of hh:mm:ss"""
    if secs is None:
        return ""
    hours, remains = divmod(secs, 3600)
    mins, secs = divmod(remains, 60)
    return f"{floor(hours):02}:{floor(mins):02}:{floor(secs):02}"


@dataclass
class RequestState:
    """Active request state"""

    options: Mapping[str, str] = None
    redirect: bool = False
    location_extra: str = "?"
    text: str = ""


def http_handler(player: mpv.MPV, queue: VideoQueue, thumbs: ThumbnailCache):
    """Create a HTTPHandler class with encapsulated player"""

    class HTTPHandler(BaseHTTPRequestHandler):
        """Custom HTTP request handler"""

        # pylint: disable-next=invalid-name
        def do_GET(self):
            """Handle get requests"""

            state = RequestState()
            i = self.path.find("?")

            path = self.path[:i] if i > -1 else self.path
            if ThumbnailCache.is_thumbnail_url(path):
                thumbs.handle_request(self, path)
                return
            if path != "/":
                # 404
                self.send_error(404)
                self.end_headers()
                return

            if i > -1:
                query = self.path[i + 1 :]
                state.options = parse_search_query(query)
                handle_options(state, player, queue)
                if state.redirect:
                    self.send_response(302)
                    path = self.path[:i]
                    if len(state.extra) > 1:
                        path += state.extra
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
            )
            # Stylesheet and javascript
            self.wfile.write(b"<style>")
            self.wfile.write(STYLE)
            self.wfile.write(b"</style><script>")
            self.wfile.write(JS)
            self.wfile.write(b"</script></head><body>")
            # Page content
            generate_page(self.wfile, player, queue, state.text)
            self.wfile.write(b"</body>")

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


def generate_action_button(wfile, action: str, text: str = None, extra: str = None):
    """Generate a button that can be clicked to trigger an action"""
    return wfile.write(
        bytes(
            '<button {} type="submit" name="a" value="{}">{}</button>'.format(
                extra or "",
                html.escape(action, quote=True),
                html.escape(text or action),
            ),
            "utf-8",
        )
    )


def generate_page(wfile, player: mpv.MPV, queue: VideoQueue, text: str):
    """Generate the body of a page"""
    # TODO: Separate into smaller functions
    # pylint: disable=too-many-branches,too-many-statements,too-many-locals

    if len(text) > 0:
        wfile.write(
            bytes("<p>{}</p>".format(html.escape(text)), "utf-8")
        )  # Yes this is XSS
    # Add to queue
    wfile.write(b'<form id="a"></form><form class="grid link">')
    generate_action_button(wfile, "quit", "Quit", "form=a")
    wfile.write(b'<input type=text name=link placeholder="Play link">')
    generate_action_button(wfile, "play", "Play")
    wfile.write(b"</form>")
    # Actions
    actions = [
        ("info", "Info"),
        ("prev", "⏮︎ Previous"),
        ("skip", "⏭︎ Next"),
        ("seek_backward", "⏪︎Seek -10s"),
        ("seek_forward", " ⏩︎Seek +10s"),
        ("pause", "⏸︎ Pause"),
        ("resume", "⏵︎ Resume"),
    ]
    wfile.write(b'<form class="actions">')
    for action, action_text in actions:
        generate_action_button(wfile, action, action_text)
    wfile.write(b"</form>")

    if player.playlist_pos < 0:
        return
    # Status
    wfile.write(b"<p>")
    if player.pause:
        wfile.write(b"Paused")
    else:
        wfile.write(bytes("Playing {}".format(player.media_title), "utf-8"))
    wfile.write(b"</p>")
    # If currently playing show seek bar and volume
    if not player.pause and player.time_pos is not None:
        # Seek bar
        if player.seekable:
            wfile.write(b'<form class="grid seek-bar">')
            wfile.write(
                bytes(
                    "<span>{}</span>".format(seconds_duration(player.time_pos)), "utf-8"
                )
            )
            wfile.write(
                bytes(
                    '<input name="seek" type="range" onchange="this.form.submit()" oninput="updateSeekTimes(this)" data-duration="{}" value="{}">'.format(
                        player.duration,
                        player.percent_pos,
                    ),
                    "utf-8",
                )
            )
            wfile.write(
                bytes(
                    "<span>{}</span>".format(seconds_duration(player.time_remaining)),
                    "utf-8",
                )
            )
            wfile.write(b"</form>")
    # Volume
    if player.volume is not None:
        wfile.write(b'<form class="grid volume">')
        generate_action_button(wfile, "volume_down", "Decrease Volume")
        wfile.write(bytes("<span>{:.0f}</span>".format(player.volume), "utf-8"))
        generate_action_button(wfile, "volume_up", "Increase Volume")
        wfile.write(b"</form>")
    # Playlist
    player_current = player.playlist_pos
    time_before = 0
    time_after = 0
    after_current = False

    wfile.write(b'<div class="queue">')
    for i, item in enumerate(queue):
        current = i == player_current
        if current:
            after_current = True
            pos = player.time_pos
            if pos is not None:
                time_before += pos
                time_after += player.time_remaining
            elif item.duration is not None:
                time_after += item.duration
        elif after_current and item.duration is not None:
            time_after += item.duration
        elif item.duration is not None:
            time_before += item.duration

        content = '<a href="?pos={}" class="queue-item'.format(i)
        if current:
            content += " current"
        content += '">'

        if item.title is not None:
            if item.thumbnail is not None:
                content += '<img src="{}">'.format(html.escape(item.thumbnail, True))
            content += '<span class="title">'
            if item.uploader is not None:
                content += "{} - ".format(html.escape(item.uploader))
            content += "{}</span>".format(html.escape(item.title))
            content += '<span class="duration">{}</span>'.format(
                html.escape(item.duration_str)
            )
            content += '<span class="link">{0}</span>'.format(html.escape(item.url))
        else:
            content += html.escape(item.url)
        content += "</a>"
        wfile.write(bytes(content, "utf-8"))
    wfile.write(b"</div>")
    wfile.write(
        bytes(
            '<div class="timings"><span>Watched: {}</span><span>Remaining: {}</span></div'.format(
                seconds_duration(time_before), seconds_duration(time_after)
            ),
            "utf-8",
        )
    )


def main(debug=False, search=True):
    """Main func"""
    cache_dirs = make_cache_dirs()

    extra_args = {}
    if debug:
        extra_args["log_handler"] = print
        extra_args["loglevel"] = "debug"
    extra_args["script_opts"] = "ytdl_hook-cachedir=" + cache_dirs.ytdl
    player = mpv.MPV(
        ytdl=True,
        ytdl_format=FORMAT_SPECIFIER,
        input_default_bindings=True,
        input_vo_keyboard=True,
        osc=True,
        idle=True,
        **extra_args,
    )

    yt_args = {
        "format": FORMAT_SPECIFIER,
        "skip_download": True,
        "cachedir": cache_dirs.ytdl,
    }
    if search:
        yt_args["default_search"] = "auto"

    ytdl = yt_dlp.YoutubeDL(yt_args)

    thumbnails = ThumbnailCache(cache_dirs.thumbs)
    queue = VideoQueue(player, ytdl, thumbnails)

    http = HTTPThread(ADDRESS, http_handler(player, queue, thumbnails))
    http.start()

    try:
        player.wait_for_shutdown()
    except Exception as error:  # pylint: disable=broad-exception-caught
        print(error)

    del player

    print("Shutting down")
    http.shutdown()

    print("Deleting cache")
    del cache_dirs


if __name__ == "__main__":
    main()
