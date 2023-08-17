#!/usr/bin/env python3

from setuptools import setup

with open("README.md", "r") as f:
    long_description = f.read()

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
    package_data={"":["*.css"]},
    include_package_data=True,
    install_requires=["mpv", "yt-dlp"],
)
