#!/usr/bin/env python3

import mpv
import yt_dlp

import threading
import sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, quote
import html
from math import floor
import os

from .video_queue import VideoQueue


# Address to listen on
ADDRESS = ("0.0.0.0", 8000)
# Specify which format to select https://github.com/yt-dlp/yt-dlp#format-selection
FORMAT_SPECIFIER = (
    "bv[height<=720][vbr<2000][fps<=30]+ba[abr<=62]/b[height<=720][fps<=30]"
)

STYLE = None
with open(os.path.join(os.path.dirname(__file__), "friends_queue.css"), "rb") as f:
    STYLE = f.read()


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


def seconds_duration(secs: float):
    """Convert time in seconds to duration of hh:mm:ss"""
    if secs is None:
        return ""
    hours, r = divmod(secs, 3600)
    mins, secs = divmod(r, 60)
    return "{:02}:{:02}:{:02}".format(floor(hours), floor(mins), floor(secs))


def http_handler(player: mpv.MPV, queue: VideoQueue):
    """Create a HTTPHandler class with encapsulated player"""

    class HTTPHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            text = ""
            i = self.path.find("?")
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
                b'<!DOCTYPE HTML>\n<html lang="en"><head><title>Friends Queue</title><meta name="viewport" content="width=device-width,initial-scale=1"/><style>'
            )
            self.wfile.write(STYLE)
            self.wfile.write(b"</style></head><body>")
            generate_page(self.wfile, player, queue, text)
            self.wfile.write(b"</body>")

    return HTTPHandler


def generate_action_button(wfile, action: str):
    return wfile.write(
        bytes('<input type="submit" name="a" value="{}">'.format(action), "utf-8")
    )


def generate_page(wfile, player: mpv.MPV, queue: VideoQueue, text: str):
    """Generate the body of a page"""
    if len(text) > 0:
        wfile.write(
            bytes("<p>{}</p>".format(html.escape(text)), "utf-8")
        )  # Yes this is XSS
    # Add to queue
    wfile.write(
        b'<form id="a"></form><form class="grid link"><input form="a" name="a" value="quit" type=submit><input type=text name=link placeholder="Play link"><input type=submit></form>'
    )
    if player.playlist_pos < 0:
        return None
    # Actions
    actions = [
        "info",
        "prev",
        "skip",
        "seek_backward",
        "seek_forward",
        "pause",
        "resume",
    ]
    wfile.write(b'<form class="actions">')
    for action in actions:
        generate_action_button(wfile, action)
    wfile.write(b"</form>")
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
                    '<form class="grid seek-bar"><span>{}</span><input name="seek" type="range" onchange="this.form.submit()" value="{}"><span>{}</span></form>'.format(
                        seconds_duration(player.time_pos),
                        player.percent_pos,
                        seconds_duration(player.time_remaining),
                    ),
                    "utf-8",
                )
            )
    # Volume
    if player.volume is not None:
        wfile.write(b'<form class="grid volume">')
        generate_action_button(wfile, "volume_down")
        wfile.write(bytes("<span>{:.0f}</span>".format(player.volume), "utf-8"))
        generate_action_button(wfile, "volume_up")
    wfile.write(b"</form>")
    # Playlist
    player_current = player.playlist_pos

    wfile.write(b"<ol>")
    for i in range(0, len(queue)):
        item = queue[i]
        current = i == player_current

        content = "<li>"
        if current:
            content += "<strong>"
        if item.title is not None:
            content += html.escape(
                "{} - {} ({}) {}".format(
                    item.uploader, item.title, item.url, item.duration_str
                )
            )
        else:
            content += html.escape(item.url)
        if current:
            content += "</strong>"
        content += "</li>"
        wfile.write(bytes(content, "utf-8"))
    wfile.write(b"</ol>")


def main(debug=False):
    extra_args = {}
    if debug:
        extra_args["log_handler"] = print
        extra_args["loglevel"] = "debug"
    player = mpv.MPV(
        ytdl=True,
        ytdl_format=FORMAT_SPECIFIER,
        input_default_bindings=True,
        input_vo_keyboard=True,
        osc=True,
        idle=True,
        **extra_args,
    )

    ytdl = yt_dlp.YoutubeDL({"format": FORMAT_SPECIFIER})

    queue = VideoQueue(player, ytdl)

    http = HTTPThread(ADDRESS, http_handler(player, queue))
    http.start()

    try:
        player.wait_for_shutdown()
    except Exception as e:
        print(e)

    del player

    print("Shutting down")
    http.shutdown()


if __name__ == "__main__":
    main()
