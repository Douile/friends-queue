"""Cache dir management"""

from os import mkdir
import os.path
import tempfile
from dataclasses import dataclass
from shutil import rmtree


@dataclass
class CacheDirs:
    """Cache dir locations, will be deleted on object deletion"""

    base: str
    thumbs: str
    ytdl: str

    def __del__(self):
        rmtree(self.base)


def __make_cache_dir(base: str, name: str) -> str:
    directory = os.path.join(base, name)
    mkdir(directory)
    return directory


def make_cache_dirs(base_dir: str = None):
    """Make cache_dirs"""
    if base_dir is None:
        base_dir = tempfile.mkdtemp(prefix="friends-queue-")
    else:
        base_dir = os.path.abspath(base_dir)
    return CacheDirs(
        base_dir,
        __make_cache_dir(base_dir, "thumbnails"),
        __make_cache_dir(base_dir, "ytdl"),
    )
