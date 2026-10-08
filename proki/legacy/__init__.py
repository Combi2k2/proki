"""The older proki: everything outside the signal language, still running the tray app.

The way forward is the signal language (outside this folder): primitives read from
ActivityWatch and the clock (core/primitives/), operators (core/ops/), rules
(core/rules.py), variables, all defined in config.json (compiler.py), and the services
they use (services/: ActivityWatch, jev). The labels of what's in focus (core/labels.py,
core/labeling.py here) feed the `label` and `depth` primitives (`Label.label_of`,
`Depth.depth_of`), which don't import them. Everything here came before it and keeps proki working
until it moves onto signals; the `proki` command starts this app.

    app.py, cli.py, config.py   the tray app, the command line, the settings
    commands/      CLI commands (check, focus, today, calibrate, categorize, track, autostart)
    core/          domain logic: the timeline (collector, timeline, categories, interpret),
                   sessions, tasks, routines, bedtime, the store, jev's questions, the AI helper
    focus/         the old focus score over the timeline
    metrics/       the scoreboard (deep minutes per day, ledgers, quota, consistency)
    rules/         rules and pipelines (suggest_session, shutdown, budget, ...)
    flows/         what proki did over time; no longer run: moved to proki/programs/ (and
                   assets/programs/), kept for their tests and helpers until removed
    ui/            the Qt tray, popups and windows
"""
