"""Фоновый опрос БД, чтобы экраны обновлялись без ручного refresh."""
import threading
from typing import Callable

import db


class LiveSync:
    """Раз в interval секунд сравнивает db.change_fingerprint() и вызывает on_change() при изменении."""

    def __init__(self, on_change: Callable[[], None], interval: float = 3.0):
        self._on_change = on_change
        self._interval = interval
        self._last = db.change_fingerprint()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            current = db.change_fingerprint()
            if current != self._last:
                self._last = current
                self._on_change()
