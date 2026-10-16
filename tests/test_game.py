import chess
import pytest
from fakes import FakeTime

from mychess.game import (
    DEFAULT_TIME_CONTROL,
    TIME_CONTROLS,
    Game,
    GameMode,
    MoveRecord,
    outcome_message,
    timeout_message,
)


def play_san(game: Game, *sans: str) -> list[MoveRecord | None]:
    return [game.push(game.board.parse_san(san)) for san in sans]


def started(
    fake_time: FakeTime,
    mode: GameMode = GameMode.PLAYER,
    player_side: chess.Color = chess.WHITE,
    time_control: str = DEFAULT_TIME_CONTROL,
) -> Game:
    game = Game(1, mode, player_side, time_control, now=fake_time)
    game.start()
    return game


def test_push_records_move_and_presses_clock(fake_time: FakeTime) -> None:
    game = started(fake_time, time_control="3+2")
    fake_time.now += 5

    record = game.push(chess.Move.from_uci("e2e4"))

    assert record == MoveRecord(number=1, san="e4", color=chess.WHITE)
    assert game.clock.running == chess.BLACK
    assert game.clock.time_left(chess.WHITE) == pytest.approx(177)  # 180 - 5 + 2


def test_black_move_record_keeps_move_number(fake_time: FakeTime) -> None:
    game = started(fake_time)
    records = play_san(game, "e4", "e5", "Nf3")
    assert [(r.number, r.color) for r in records if r] == [
        (1, chess.WHITE),
        (1, chess.BLACK),
        (2, chess.WHITE),
    ]


def test_checkmate_finishes_game(fake_time: FakeTime) -> None:
    game = started(fake_time)
    records = play_san(game, "f3", "e5", "g4", "Qh4#")

    assert records[-1] is not None  # mat hamlesi de kayda girer
    assert game.result == "Şah mat! Siyah kazandı."
    assert not game.running
    assert game.clock.running is None


def test_threefold_repetition_ends_game(fake_time: FakeTime) -> None:
    game = started(fake_time)
    play_san(game, "Nf3", "Nf6", "Ng1", "Ng8", "Nf3", "Nf6", "Ng1")
    # Siyah Ng8 ile üçüncü tekrarı yapabilir ama yapmadı: oyun sürmeli.
    # (Eski claim_draw=True kontrolü oyunu burada erken bitiriyordu.)
    assert game.running
    play_san(game, "Ng8")
    assert game.result == "Berabere: aynı pozisyon üç kez tekrarlandı."


def test_fifty_move_rule_ends_game(fake_time: FakeTime) -> None:
    game = started(fake_time)
    game.board.set_fen("4k3/8/8/8/8/8/8/R3K3 w - - 98 80")
    play_san(game, "Ra2")
    assert game.running  # 99. yarım hamle: sınır henüz dolmadı
    play_san(game, "Kd7")
    assert game.result == "Berabere: 50 hamle kuralı."


def test_move_after_flag_fell_is_rejected(fake_time: FakeTime) -> None:
    game = started(fake_time, time_control="1+0")
    fake_time.now += 60.5

    assert game.push(chess.Move.from_uci("e2e4")) is None
    assert game.board.move_stack == []
    assert game.result == "Süre bitti! Siyah kazandı."


def test_check_flag(fake_time: FakeTime) -> None:
    game = started(fake_time, time_control="1+0")
    fake_time.now += 59
    assert not game.check_flag()
    fake_time.now += 1
    assert game.check_flag()
    assert game.result == "Süre bitti! Siyah kazandı."
    assert not game.running


def test_stop_freezes_clock_without_result(fake_time: FakeTime) -> None:
    game = started(fake_time)
    game.stop()
    fake_time.now += 1000
    assert game.result is None
    assert not game.check_flag()
    assert not game.can_player_move


def test_engine_turn_depends_on_mode_side_and_running(fake_time: FakeTime) -> None:
    vs_engine = Game(1, GameMode.STOCKFISH, player_side=chess.BLACK, now=fake_time)
    assert not vs_engine.is_engine_turn  # başlamadı
    vs_engine.start()
    assert vs_engine.is_engine_turn
    assert not vs_engine.can_player_move

    two_players = started(fake_time, mode=GameMode.PLAYER, player_side=chess.BLACK)
    assert not two_players.is_engine_turn
    assert two_players.can_player_move


def test_in_progress_needs_a_move(fake_time: FakeTime) -> None:
    game = started(fake_time)
    assert not game.in_progress
    play_san(game, "e4")
    assert game.in_progress


def test_time_controls(fake_time: FakeTime) -> None:
    for name, (initial, increment) in TIME_CONTROLS.items():
        game = Game(1, time_control=name, now=fake_time)
        assert game.clock.time_left(chess.WHITE) == initial
        assert game.clock.increment == increment
    # Bilinmeyen kontrol varsayılana düşer
    assert Game(1, time_control="?", now=fake_time).clock.time_left(chess.WHITE) == 600


def test_outcome_messages() -> None:
    stalemate = chess.Board("k7/2Q5/K7/8/8/8/8/8 b - - 0 1").outcome()
    assert stalemate is not None
    assert outcome_message(stalemate) == "Pat! Oyun berabere."

    bare_kings = chess.Board("8/8/8/4k3/8/8/4K3/8 w - - 0 1").outcome()
    assert bare_kings is not None
    assert outcome_message(bare_kings) == "Berabere: yetersiz materyal."


def test_timeout_messages() -> None:
    assert timeout_message(chess.Board(), chess.WHITE) == "Süre bitti! Siyah kazandı."

    # Beyazın süresi bitti ama siyahta sadece şah var: berabere
    lone_king = chess.Board("4k3/8/8/8/8/8/8/R3K3 w - - 0 1")
    assert "Berabere" in timeout_message(lone_king, chess.WHITE)
    assert "Beyaz kazandı" in timeout_message(lone_king, chess.BLACK)
