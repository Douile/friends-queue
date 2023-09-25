"""Functions related to generating HTML page, essentially templates"""

from io import BufferedIOBase
import html

from .types import State
from .utils import seconds_duration
from .video_queue import VideoQueueItem


def generate_action_button(
    wfile: BufferedIOBase, action: str, text: str = None, extra: str = None
):
    """Generate HTML for a button that can be clicked to trigger an action"""
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


def generate_page_actions(wfile: BufferedIOBase):
    """Generate HTML for action buttons"""
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


def generate_page_player_status(wfile: BufferedIOBase, state: State):
    """Generate HTML for currently playing video status"""
    wfile.write(b"<p>")
    if state.player.pause:
        wfile.write(b"Paused")
    else:
        wfile.write(bytes("Playing {}".format(state.player.media_title[:40]), "utf-8"))
    wfile.write(b"</p>")


def generate_page_seek_bar(wfile: BufferedIOBase, state: State):
    """Generate HTML for seek bar"""
    wfile.write(b'<form class="grid seek-bar">')
    wfile.write(
        bytes(
            "<span>{}</span>".format(seconds_duration(state.player.time_pos)), "utf-8"
        )
    )
    wfile.write(
        bytes(
            '<input name="seek" type="range" onchange="this.form.submit()" oninput="updateSeekTimes(this)" data-duration="{}" value="{}">'.format(
                state.player.duration,
                state.player.percent_pos,
            ),
            "utf-8",
        )
    )
    wfile.write(
        bytes(
            "<span>{}</span>".format(seconds_duration(state.player.time_remaining)),
            "utf-8",
        )
    )
    wfile.write(b"</form>")


def generate_page_volume_slider(wfile: BufferedIOBase, state: State):
    """Generate HTML for a volume slider"""
    wfile.write(b'<form class="grid volume">')
    generate_action_button(wfile, "volume_down", "Decrease Volume")
    wfile.write(bytes("<span>{:.0f}</span>".format(state.player.volume), "utf-8"))
    generate_action_button(wfile, "volume_up", "Increase Volume")
    wfile.write(b"</form>")


def generate_page_queue_item(
    wfile: BufferedIOBase, item: VideoQueueItem, i: int, current: bool
):
    """Generate HTML for an active queue item"""
    content = '<button type="submit" name="pos" value="{}" class="queue-item'.format(i)
    if current:
        content += " current"
    content += '">'

    if item.title is not None:
        if item.thumbnail is not None:
            content += '<img src="{}"'.format(html.escape(item.thumbnail, True))
            if item.thumbnail_height is not None:
                height = html.escape(str(item.thumbnail_height), True)
                content += f' height="{height}"'
            if item.thumbnail_width is not None:
                width = html.escape(str(item.thumbnail_width), True)
                content += f' width="{width}"'
            content += ">"
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
    content += "</button>"
    wfile.write(bytes(content, "utf-8"))


def generate_page_queue_items_active(
    wfile: BufferedIOBase, state: State, player_current: int, skip_before: int
) -> (int, int):
    """Generate HTML for active items in queue"""
    time_before = 0
    time_after = 0
    after_current = False

    for i, item in enumerate(state.queue):
        current = i == player_current
        # Sum queue timings
        if current:
            after_current = True
            pos = state.player.time_pos
            if pos is not None:
                time_before += pos
                time_after += state.player.time_remaining
            elif item.duration is not None:
                time_after += item.duration
        elif after_current and item.duration is not None:
            time_after += item.duration
        elif item.duration is not None:
            time_before += item.duration

        # Only show one item before current item
        if not after_current and i < skip_before:
            continue

        generate_page_queue_item(wfile, item, i, current)

    return (time_before, time_after)


def generate_page_queue_items_loading(wfile: BufferedIOBase, state: State):
    """Generate HTML for loading queue items"""
    for active in state.queue.active_fetches():
        wfile.write(
            bytes(
                '<div class="queue-item loading">{}</div>'.format(html.escape(active)),
                "utf-8",
            )
        )


def generate_page_queue_items_errors(wfile: BufferedIOBase, state: State):
    """Generate HTML for loading errors"""
    for error in state.queue.recent_errors():
        wfile.write(
            bytes(
                '<div class="queue-item error">{}</div>'.format(
                    html.escape(str(error))
                ),
                "utf-8",
            )
        )


def generate_page_queue(wfile: BufferedIOBase, state: State) -> (int, int):
    """Generate HTML for current queue items"""
    player_current = state.player.playlist_pos
    skip_before = player_current - 1

    wfile.write(
        bytes(
            f'<form class="queue" style="counter-reset: section {max(skip_before, 0)}">',
            "utf-8",
        )
    )
    # TODO: If skipping add button to show previous
    time_before, time_after = generate_page_queue_items_active(
        wfile, state, player_current, skip_before
    )

    # Currently fetching
    generate_page_queue_items_loading(wfile, state)

    # Recent errors
    generate_page_queue_items_errors(wfile, state)

    wfile.write(b"</form>")

    return (time_before, time_after)


def generate_page_watch_times(wfile: BufferedIOBase, time_before: int, time_after: int):
    """Generate HTML for watched and remaining durations"""
    wfile.write(
        bytes(
            '<div class="timings"><span>Watched: {}</span><span>Remaining: {}</span></div>'.format(
                seconds_duration(time_before), seconds_duration(time_after)
            ),
            "utf-8",
        )
    )


def generate_page(wfile: BufferedIOBase, state: State, text: str):
    """Generate the body of a page"""
    if len(text) > 0:
        wfile.write(
            bytes("<p>{}</p>".format(html.escape(text)), "utf-8")
        )  # Yes this is XSS

    generate_page_actions(wfile)

    if state.player.playlist_pos >= 0:
        generate_page_player_status(wfile, state)

    # If currently playing show seek bar
    if (
        not state.player.pause
        and state.player.time_pos is not None
        and state.player.seekable
    ):
        generate_page_seek_bar(wfile, state)

    # Volume
    if state.player.volume is not None:
        generate_page_volume_slider(wfile, state)

    # Playlist
    time_before, time_after = generate_page_queue(wfile, state)

    generate_page_watch_times(wfile, time_before, time_after)
