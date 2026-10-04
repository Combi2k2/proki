"""Entry point. `proki` alone starts the tray app, which is how proki is meant to be used.

The subcommands are developer tools for inspecting the data processing
(timeline, categories, focus scores) from a terminal.
"""

from __future__ import annotations

import argparse

import sys

from dotenv import load_dotenv

from proki.legacy import config as config_mod
from proki.legacy.core.events import Category


def main(argv: list[str] | None = None) -> int:
    config_mod.move_from_old_name()
    parser = argparse.ArgumentParser(
        prog="proki", description="procrastination killer. Run without arguments to start the tray app."
    )
    sub = parser.add_subparsers(dest="command", title="developer tools")
    sub.add_parser("start", help="run the daemon (tray app) in the foreground")
    check = sub.add_parser("check", help="show recent activity with categories, and findings")
    check.add_argument("--all", action="store_true", help="list every segment, not just the last 15")
    focus = sub.add_parser("focus", help="focus intensity now and over the last hour, or for a past day")
    focus.add_argument("--span", type=int, default=60, help="minutes of history to chart (default 60)")
    focus.add_argument("--date", help="replay a whole day hour by hour, e.g. 2026-09-28")
    sub.add_parser("today", help="today's scoreboard, as the tray shows it")
    sub.add_parser("week", help="the scoreboard for the last 7 days")
    sub.add_parser("calibrate", help="how well the focus score agrees with your 1–5 ratings")
    categorize = sub.add_parser("categorize", help="list remembered categories, or set one")
    categorize.add_argument("key", nargs="?", help='an app like "Slack", or a website domain like "github.com"')
    categorize.add_argument("category", nargs="?", choices=[c.value for c in Category])
    track = sub.add_parser("track", help="list tracked apps, or track one")
    track.add_argument("app", nargs="?")
    untrack = sub.add_parser("untrack", help="stop tracking an app added with `track` or a popup")
    untrack.add_argument("app")
    sub.add_parser("config", help="print the config file path")
    autostart = sub.add_parser("autostart", help="start proki automatically at login")
    autostart.add_argument("action", choices=["install", "uninstall", "status"])
    args = parser.parse_args(argv)

    if sys.stdout is None:  # started without a console (Windows pythonw): log to a file instead
        from platformdirs import user_log_path

        log = user_log_path("proki") / "proki.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(log, "a", buffering=1, encoding="utf-8")
    load_dotenv(config_mod.CONFIG_PATH.parent / ".env")
    load_dotenv()  # a .env in the current directory, for development

    if args.command == "config":
        config_mod.load()  # creates the default file on first run
        print(config_mod.CONFIG_PATH)
        return 0
    config = config_mod.load()

    # Imported per command, so e.g. Qt only loads for `start`.
    from proki.legacy.commands.data import ActivityWatchUnavailable

    try:
        if args.command in (None, "start"):
            from proki.legacy.app import run

            return run(config)
        if args.command == "check":
            from proki.legacy.commands import check as command

            return command.run(config, show_all=args.all)
        if args.command == "focus":
            from proki.legacy.commands import focus as command

            return command.run(config, span_minutes=args.span, day=args.date)
        if args.command in ("today", "week"):
            from proki.legacy.commands import today as command

            return command.run_today(config) if args.command == "today" else command.run_week(config)
        if args.command == "calibrate":
            from proki.legacy.commands import calibrate as command

            return command.run(config)
        if args.command in ("track", "untrack"):
            from proki.legacy.commands import track as command

            return command.run(config, args.app, remove=args.command == "untrack")
        if args.command == "categorize":
            from proki.legacy.commands import categorize as command

            return command.run(args.key, args.category)
        from proki.legacy.commands import autostart as command

        return command.run(args.action)
    except ActivityWatchUnavailable as e:
        print(e)
        return 1
