"""Player actions"""

from collections.abc import Callable, Mapping
from math import floor

from mpv import MPV


def __pause(player):
    player.pause = True


def __resume(player):
    player.pause = False


def __volume_up(player):
    player.volume = floor(min(player.volume + 5, 100))


def __volume_down(player):
    player.volume = floor(max(player.volume - 5, 0))


ACTIONS: Mapping[str, Callable[[MPV], None]] = {
    "seek_backward": lambda player: player.seek("-10", "relative+keyframes"),
    "seek_forward": lambda player: player.seek("10", "relative+keyframes"),
    "prev": lambda player: player.playlist_prev("force"),
    "skip": lambda player: player.playlist_next("force"),
    "pause": __pause,
    "resume": __resume,
    "volume_up": __volume_up,
    "volume_down": __volume_down,
    "quit": lambda player: player.quit(0),
}
