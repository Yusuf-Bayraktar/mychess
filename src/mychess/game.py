"""Bir satranç oyununun durumu ve kuralları: tahta, saat, mod, sonuç (Tk'siz)."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

import chess

from .clock import GameClock


class GameMode(StrEnum):
    """Oyun modu; değerler menüde gösterilen adlardır."""

    PLAYER = "İki Kişilik"
    STOCKFISH = "Stockfish"


# Süre kontrolleri: menüdeki ad -> (başlangıç saniyesi, hamle başı artış)
TIME_CONTROLS: dict[str, tuple[int, int]] = {
    "1+0": (60, 0),
    "3+2": (180, 2),
    "10+0": (600, 0),
}
DEFAULT_TIME_CONTROL: str = "10+0"

COLOR_NAMES: dict[chess.Color, str] = {chess.WHITE: "Beyaz", chess.BLACK: "Siyah"}


def outcome_message(outcome: chess.Outcome) -> str:
    """Oyun sonucunu kullanıcıya gösterilecek metne çevirir."""
    match outcome.termination:
        case chess.Termination.CHECKMATE if outcome.winner is not None:
            return f"Şah mat! {COLOR_NAMES[outcome.winner]} kazandı."
        case chess.Termination.STALEMATE:
            return "Pat! Oyun berabere."
        case chess.Termination.INSUFFICIENT_MATERIAL:
            return "Berabere: yetersiz materyal."
        case (
            chess.Termination.THREEFOLD_REPETITION
            | chess.Termination.FIVEFOLD_REPETITION
        ):
            return "Berabere: aynı pozisyon üç kez tekrarlandı."
        case chess.Termination.FIFTY_MOVES | chess.Termination.SEVENTYFIVE_MOVES:
            return "Berabere: 50 hamle kuralı."
        case _:
            return "Oyun bitti."


def automatic_outcome(board: chess.Board) -> chess.Outcome | None:
    """Oyunu bitiren sonucu döndürür; üç tekrar ve 50 hamlede otomatik berabere.

    `board.outcome(claim_draw=True)` kullanılmaz: o, bir *sonraki* hamleyle
    talep edilebilecek beraberliği de sayar ve oyunu bir hamle erken bitirir.
    Burada yalnızca gerçekten oluşmuş durumlar sayılır.
    """
    outcome = board.outcome()
    if outcome is not None:
        return outcome
    if board.is_repetition(3):
        return chess.Outcome(chess.Termination.THREEFOLD_REPETITION, None)
    if board.halfmove_clock >= 100:
        return chess.Outcome(chess.Termination.FIFTY_MOVES, None)
    return None


def timeout_message(board: chess.Board, flagged: chess.Color) -> str:
    """Süresi biten taraf için sonucu döndürür; rakip mat edemiyorsa berabere."""
    winner = not flagged
    if board.has_insufficient_material(winner):
        return (
            f"Süre bitti! Berabere: {COLOR_NAMES[winner]} "
            "mat edecek materyale sahip değil."
        )
    return f"Süre bitti! {COLOR_NAMES[winner]} kazandı."


@dataclass(frozen=True)
class MoveRecord:
    """Hamle kaydına yazılacak bir hamle."""

    number: int
    san: str
    color: chess.Color


class Game:
    """Tek bir oyunun durumu: tahta, saat, mod, oyuncunun tarafı ve sonuç.

    `running` oyun sürerken True'dur; bitince (`finish`) ya da durdurulunca
    (`stop`) False olur ve saat durur. `result` bitmiş oyunun sonuç metnidir.
    """

    def __init__(
        self,
        game_id: int,
        mode: GameMode = GameMode.PLAYER,
        player_side: chess.Color = chess.WHITE,
        time_control: str = DEFAULT_TIME_CONTROL,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        initial, increment = TIME_CONTROLS.get(
            time_control, TIME_CONTROLS[DEFAULT_TIME_CONTROL]
        )
        self.id = game_id
        self.mode = mode
        self.player_side = player_side
        self.board = chess.Board()
        self.clock = GameClock(initial, increment, now=now)
        self.running = False
        self.result: str | None = None

    @property
    def is_engine_turn(self) -> bool:
        return (
            self.running
            and self.mode is GameMode.STOCKFISH
            and self.board.turn != self.player_side
        )

    @property
    def can_player_move(self) -> bool:
        return self.running and not self.is_engine_turn

    @property
    def in_progress(self) -> bool:
        """En az bir hamle oynanmış ve henüz bitmemiş mi?"""
        return self.running and bool(self.board.move_stack)

    def start(self) -> None:
        """Oyunu başlatır; saat sırası gelen taraf için akmaya başlar."""
        self.running = True
        self.clock.start(self.board.turn)

    def stop(self) -> None:
        """Oyunu sonuçsuz durdurur (menüye dönüş, motor hatası)."""
        self.running = False
        self.clock.stop()

    def finish(self, message: str) -> None:
        """Oyunu verilen sonuçla bitirir."""
        self.result = message
        self.stop()

    def push(self, move: chess.Move) -> MoveRecord | None:
        """Hamleyi saatle birlikte işler ve oyun sonunu denetler.

        Süre hamleden önce bitmişse hamle oynanmaz, oyun süreden biter ve
        None döner. Hamle mat/pat/beraberlik getirirse oyun bitirilir
        (`result` dolar) ama kayıt yine döner.
        """
        mover = self.board.turn
        if self.clock.time_left(mover) <= 0:
            self.finish(timeout_message(self.board, mover))
            return None

        record = MoveRecord(self.board.fullmove_number, self.board.san(move), mover)
        self.clock.press(mover)
        self.board.push(move)

        outcome = automatic_outcome(self.board)
        if outcome is not None:
            self.finish(outcome_message(outcome))
        return record

    def check_flag(self) -> bool:
        """Saati akan tarafın süresi bittiyse oyunu bitirir ve True döner."""
        flagged = self.clock.flagged()
        if flagged is None:
            return False
        self.finish(timeout_message(self.board, flagged))
        return True
