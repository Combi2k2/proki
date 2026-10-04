"""The alarm sound, played with Qt's audio support (same code on every OS)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

BUILT_IN = Path(__file__).resolve().parents[2] / "assets" / "sounds" / "alarm-clock.mp3"  # proki/assets


class Alarm:
    """Loops a sound until stopped: used while focus is slipping or the user is away."""

    def __init__(self, sound: Path | None = None, volume: float = 1.0):
        self._output = QAudioOutput()
        self._output.setVolume(volume)
        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._output)
        self._player.setSource(QUrl.fromLocalFile(str(sound or BUILT_IN)))
        self._player.setLoops(QMediaPlayer.Loops.Infinite)

    @property
    def ringing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def start(self) -> None:
        """Ring until stopped."""
        if not self.ringing:
            self._player.setPosition(0)
            self._player.play()

    def stop(self) -> None:
        self._player.stop()
