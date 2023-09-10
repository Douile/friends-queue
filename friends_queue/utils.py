"""Utility functions"""

from collections.abc import Mapping
from urllib.parse import unquote


def parse_search_query(query: str) -> Mapping[str, str]:
    """Parse search query options"""
    opts = {}
    for part in query.split("&"):
        parts = part.split("=")
        if len(parts) == 2:
            [key, value] = parts
            opts[key] = unquote(value)
    return opts
