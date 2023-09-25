"""Utility functions"""

from collections.abc import Mapping
from urllib.parse import unquote
from math import floor


def parse_search_query(query: str) -> Mapping[str, str]:
    """Parse search query options"""
    opts = {}
    for part in query.split("&"):
        parts = part.split("=")
        if len(parts) == 2:
            [key, value] = parts
            opts[key] = unquote(value)
    return opts


def seconds_duration(secs: float) -> str:
    """Convert time in seconds to duration of hh:mm:ss"""
    if secs is None:
        return ""
    hours, remains = divmod(secs, 3600)
    mins, secs = divmod(remains, 60)
    return f"{floor(hours):02}:{floor(mins):02}:{floor(secs):02}"
