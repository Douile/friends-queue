#!/usr/bin/env python3

from friends_queue.friends_queue import main

import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        "friends-queue", description="A web interface to queue videos in MPV"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable MPV debug messages"
    )
    parser.add_argument(
        "-s", "--no-search", action="store_true", help="Disable search functionality"
    )
    parser.add_argument("-l", "--listen", default="0.0.0.0", help="IP to listen on")
    parser.add_argument(
        "-p", "--port", default=8000, help="Port to listen on", type=int
    )
    parser.add_argument("--format", help="Override yt-dlp FORMAT SELECTOR")
    parser.add_argument(
        "--height", help="Max height of video (if --format not used)", type=int
    )
    parser.add_argument(
        "--width", help="Max width of video (if --format not used)", type=int
    )
    parser.add_argument(
        "--vbr", help="Max bitrate of video (if --format not used)", type=int
    )
    parser.add_argument(
        "--abr", help="Max bitrate of audio (if --format not used)", type=int
    )
    parser.add_argument(
        "--fps", help="Max FPS of video (if --format not used)", type=int
    )

    args = parser.parse_args()

    format_str = None
    if args.format is not None:
        format_str = args.format
    elif (
        args.height is not None
        or args.width is not None
        or args.vbr is not None
        or args.abr is not None
        or args.fps is not None
    ):
        video_args = ""
        if args.height is not None:
            video_args += f"[height<={args.height}]"
        if args.width is not None:
            video_args += f"[width<={args.width}]"
        if args.vbr is not None:
            video_args += f"[vbr<={args.vbr}]"
        if args.fps is not None:
            video_args += f"[fps<={args.fps}]"

        audio_args = ""
        if args.abr is not None:
            audio_args += f"[abr<={args.abr}]"

        format_str = f"bv{video_args}+ba{audio_args}/b{video_args}{audio_args}"
        print(f"Using format string: {format_str}")

    main(
        debug=args.debug,
        search=not args.no_search,
        format_specifier=format_str,
        host=args.listen,
        port=args.port,
    )
