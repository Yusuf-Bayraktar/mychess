"""Satranç saati: süreyi tik sayarak değil, gerçekten geçen zamanla ölçer."""

import math
import time
from collections.abc import Callable

import chess


class GameClock:
    """İki taraflı satranç saati.

    Yalnızca çalışan tarafın süresi akar. Geçen süre `now()` ile (varsayılan
    `time.monotonic`) ölçülür; böylece Tk zamanlayıcısının gecikmesi ya da
    macOS'un arka plandaki uygulamayı yavaşlatması saati şaşırtmaz.
    `remaining`, saat durmuşken her tarafın kalan süresidir (saniye).
    """

    def __init__(
        self,
        initial: float,
        increment: float = 0.0,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self.increment = increment
        self.remaining: dict[chess.Color, float] = {
            chess.WHITE: initial,
            chess.BLACK: initial,
        }
        self._now = now
        self._running: chess.Color | None = None
        self._started_at: float = 0.0

    @property
    def running(self) -> chess.Color | None:
        """Saati akan taraf; saat durmuşsa None."""
        return self._running

    def start(self, color: chess.Color) -> None:
        """Verilen tarafın saatini başlatır; çalışan saat varsa önce durdurur."""
        self.stop()
        self._running = color
        self._started_at = self._now()

    def stop(self) -> None:
        """Çalışan saati durdurur ve geçen süreyi o taraftan düşer."""
        if self._running is None:
            return
        self.remaining[self._running] -= self._now() - self._started_at
        self._running = None

    def press(self, mover: chess.Color) -> None:
        """Hamle sonrası: hamleyi yapanın süresini düşer, artışı ekler, rakibi başlatır."""
        self.stop()
        self.remaining[mover] += self.increment
        self.start(not mover)

    def time_left(self, color: chess.Color) -> float:
        """Tarafın şu anki kalan süresi (saniye); süre bittiyse sıfır ya da negatif."""
        left = self.remaining[color]
        if self._running == color:
            left -= self._now() - self._started_at
        return left

    def flagged(self) -> chess.Color | None:
        """Süresi biten taraf (yalnızca saati akan taraf bitebilir); yoksa None."""
        if self._running is not None and self.time_left(self._running) <= 0:
            return self._running
        return None


def format_clock(seconds: float) -> str:
    """Kalan süreyi `d:ss` biçiminde yazar; yukarı yuvarlar, "0:00" süre bitti demektir."""
    whole = max(0, math.ceil(seconds))
    return f"{whole // 60}:{whole % 60:02d}"
