"""Player actions"""

from collections.abc import Callable, Mapping
from math import floor

from mpv import MPV


def _pause(player):
    player.pause = True


def _resume(player):
    player.pause = False


def _volume_up(player):
    player.volume = floor(min(player.volume + 5, 100))


def _volume_down(player):
    player.volume = floor(max(player.volume - 5, 0))


ACTIONS: Mapping[str, Callable[[MPV], None]] = {
    "seek_backward": lambda player: player.seek("-10", "relative+keyframes"),
    "seek_forward": lambda player: player.seek("10", "relative+keyframes"),
    "prev": lambda player: player.playlist_prev("force"),
    "skip": lambda player: player.playlist_next("force"),
    "pause": _pause,
    "resume": _resume,
    "volume_up": _volume_up,
    "volume_down": _volume_down,
    # TODO: Make use of state close condition
    "quit": lambda player: player.quit(0),
}
