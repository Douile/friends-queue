#!/usr/bin/env python3

import re
from setuptools import setup

REQ_PATTERN = re.compile(
    "(?P<name>[^=<>]+)(?P<comp>[<=>]{1,2})(?P<spec>[^;]+)"
    "(?:(;\W*python_version\W*(?P<pycomp>[<=>]{1,2})\W*"
    "(?P<pyspec>[0-9\.]+)))?"
)


# Taken from:
# https://github.com/sagivo/zipline/blob/18aba63da968ea1b913ed049ff14685eb3830f5b/setup.py#L119
def _filter_requirements(lines_iter):
    for line in lines_iter:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        match = REQ_PATTERN.match(line)
        if match is None:
            raise AssertionError("Could not parse requirement: '%s'" % line)

        yield line


with open("README.md", "r") as f:
    long_description = f.read()

with open("requirements.txt", "r") as f:
    install_requires = list(_filter_requirements(f.readlines()))

setup(
    name="friends-queue",
    version="0.1",
    description="Share a video queue with your friends",
    long_description=long_description,
    license="AGPL-3.0-or-later",
    author="Douile",
    author_email="douile@douile.com",
    url="https://github.com/Douile/friends-queue",
    packages=["friends_queue"],
    package_data={"": ["*.css"]},
    include_package_data=True,
    install_requires=install_requires,
)
