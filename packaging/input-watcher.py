"""Entry point for the separately frozen official ActivityWatch input watcher."""

import aw_watcher_input.main as watcher


class KeyboardListener(watcher.KeyboardListener):
    def next_event(self):
        event = super().next_event()
        # The pinned AFK listener counts key-downs only. Preserve the input watcher's
        # historical down+up count, which proki's keys_pressed divides by two.
        return {**event, "presses": event["presses"] * 2}


watcher.KeyboardListener = KeyboardListener

if __name__ == "__main__":
    watcher.main()
