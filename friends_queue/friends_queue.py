#!/usr/bin/env python3

import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, quote
import html
from math import floor
import os.path

import mpv
import yt_dlp

from .cache import make_cache_dirs
from .video_queue import VideoQueue
from .thumbnail_cache import ThumbnailCache

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
        self.httpd.shutdown()


def seconds_duration(secs: float) -> str:
    """Convert time in seconds to duration of hh:mm:ss"""
    if secs is None:
        return ""
    hours, r = divmod(secs, 3600)
    mins, secs = divmod(r, 60)
    return "{:02}:{:02}:{:02}".format(floor(hours), floor(mins), floor(secs))


def http_handler(player: mpv.MPV, queue: VideoQueue, thumbs: ThumbnailCache):
    """Create a HTTPHandler class with encapsulated player"""

    class HTTPHandler(BaseHTTPRequestHandler):
        # pylint: disable=invalid-name
        def do_GET(self):
            text = ""
            i = self.path.find("?")

            path = self.path[:i] if i > -1 else self.path
            if ThumbnailCache.is_thumbnail_url(path):
                return thumbs.handle_request(self, path)
            if path != "/":
                # 404
                self.send_error(404)
                self.end_headers()
                return None

            if i > -1:
                query = self.path[i + 1 :]
                opts = {}
                for part in query.split("&"):
                    parts = part.split("=")
                    if len(parts) == 2:
                        [key, value] = parts
                        opts[key] = unquote(value)
                redir = False
                extra = "?"
                if "link" in opts:
                    redir = True
                    print("Adding to queue", opts["link"])
                    queue.append_url(opts["link"])
                if "a" in opts:
                    redir = True
                    a = opts["a"]
                    if a == "info":
                        extra += (
                            "text="
                            + quote(
                                "Playing {} {}% ({} {} {} {}x{}) Drop(dec={}, frame={})".format(
                                    player.media_title,
                                    player.percent_pos,
                                    player.video_format,
                                    player.video_codec,
                                    player.hwdec_current,
                                    player.width,
                                    player.height,
                                    player.decoder_frame_drop_count,
                                    player.frame_drop_count,
                                )
                            )
                            + "&"
                        )
                    elif a == "seek_backward":
                        player.seek("-10", "relative+keyframes")
                    elif a == "seek_forward":
                        player.seek("10", "relative+keyframes")
                    elif a == "prev":
                        player.playlist_prev("force")
                    elif a == "skip":
                        player.playlist_next("force")
                    elif a == "pause":
                        player.pause = True
                    elif a == "resume":
                        player.pause = False
                    elif a == "volume_up":
                        player.volume = floor(min(player.volume + 5, 100))
                    elif a == "volume_down":
                        player.volume = floor(max(player.volume - 5, 0))
                    elif a == "quit":
                        player.quit(0)
                if "text" in opts:
                    text = unquote(opts["text"])
                if "seek" in opts:
                    redir = True
                    player.seek(opts["seek"], "absolute-percent+keyframes")
                if "pos" in opts:
                    redir = True
                    new_pos = int(opts["pos"])
                    if player.playlist_pos != new_pos:
                        player.playlist_pos = new_pos
                if redir:
                    self.send_response(302)
                    path = self.path[:i]
                    if len(extra) > 1:
                        path += extra
                    self.send_header("Location", path)
                    self.end_headers()
                    return None

            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b'<!DOCTYPE HTML>\n<html lang="en"><head><title>Friends Queue</title><meta name="viewport" content="width=device-width,initial-scale=1"/><meta charset="utf-8"><style>'
            )
            self.wfile.write(STYLE)
            self.wfile.write(b"</style><script>")
            self.wfile.write(JS)
            self.wfile.write(b"</script></head><body>")
            generate_page(self.wfile, player, queue, text)
            self.wfile.write(b"</body>")

    return HTTPHandler


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
            wfile.write(
                bytes(
                    '<form class="grid seek-bar"><span>{}</span><input name="seek" type="range" onchange="this.form.submit()" oninput="updateSeekTimes(this)" data-duration="{}" value="{}"><span>{}</span></form>'.format(
                        seconds_duration(player.time_pos),
                        player.duration,
                        player.percent_pos,
                        seconds_duration(player.time_remaining),
                    ),
                    "utf-8",
                )
            )
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
    for i in range(0, len(queue)):
        item = queue[i]
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
    except Exception as e:
        print(e)

    del player

    print("Shutting down")
    http.shutdown()

    print("Deleting cache")
    del cache_dirs


if __name__ == "__main__":
    main()
