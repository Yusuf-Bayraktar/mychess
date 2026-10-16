"""Testlerde kullanılan sahte motor, sahte zaman ve bekleme yardımcıları."""

import time
from collections.abc import Callable, Mapping

import chess
import chess.engine

STOCKFISH_OPTIONS: dict[str, chess.engine.Option] = {
    "UCI_Elo": chess.engine.Option("UCI_Elo", "spin", 1320, 1320, 3190, []),
    "UCI_LimitStrength": chess.engine.Option(
        "UCI_LimitStrength", "check", False, None, None, []
    ),
    "Skill Level": chess.engine.Option("Skill Level", "spin", 20, 0, 20, []),
}


class FakeEngine:
    """SimpleEngine'in uygulamanın kullandığı kısmını (UciEngine) taklit eder."""

    def __init__(
        self,
        fail_with: Exception | None = None,
        options: Mapping[str, chess.engine.Option] | None = None,
        delay: float = 0.0,
    ) -> None:
        self.fail_with = fail_with
        self.dead = False
        self.delay = delay
        self.configured: list[chess.engine.ConfigMapping] = []
        self._options = dict(STOCKFISH_OPTIONS if options is None else options)

    @property
    def id(self) -> Mapping[str, str]:
        return {"name": "FakeFish"}

    @property
    def options(self) -> Mapping[str, chess.engine.Option]:
        return self._options

    def _check_alive(self) -> None:
        if self.dead:
            raise chess.engine.EngineTerminatedError("engine process dead")

    def ping(self) -> None:
        self._check_alive()

    def configure(self, options: chess.engine.ConfigMapping) -> None:
        self._check_alive()
        self.configured.append(options)

    def play(
        self, board: chess.Board, limit: chess.engine.Limit
    ) -> chess.engine.PlayResult:
        self._check_alive()
        if self.fail_with is not None:
            raise self.fail_with
        time.sleep(self.delay)
        return chess.engine.PlayResult(next(iter(board.legal_moves)), None)

    def quit(self) -> None:
        pass

    def close(self) -> None:
        pass


class FakeTime:
    """Elle ilerletilen monotonic zaman."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def wait_for(
    cond: Callable[[], bool],
    timeout: float = 5.0,
    step: Callable[[], object] | None = None,
) -> bool:
    """Koşul sağlanana kadar bekler; `step` her turda çağrılır (ör. root.update)."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if step is not None:
            step()
        if cond():
            return True
        time.sleep(0.01)
    return False
