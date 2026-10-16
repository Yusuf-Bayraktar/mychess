import chess
import pytest
from fakes import FakeTime

from mychess.clock import GameClock, format_clock


def test_only_running_side_loses_time(fake_time: FakeTime) -> None:
    clock = GameClock(60, now=fake_time)
    clock.start(chess.WHITE)
    fake_time.now += 2.5

    assert clock.time_left(chess.WHITE) == pytest.approx(57.5)
    assert clock.time_left(chess.BLACK) == 60


def test_sub_second_thinking_is_charged(fake_time: FakeTime) -> None:
    # Eski tik sayan saatte 1 saniyeden kısa hamleler bazen hiç süre harcamıyordu.
    clock = GameClock(60, now=fake_time)
    clock.start(chess.WHITE)
    for _ in range(10):
        fake_time.now += 0.4
        clock.press(chess.WHITE)
        clock.press(chess.BLACK)

    assert clock.time_left(chess.WHITE) == pytest.approx(56.0)
    assert clock.time_left(chess.BLACK) == 60


def test_press_adds_increment_and_switches(fake_time: FakeTime) -> None:
    clock = GameClock(180, increment=2, now=fake_time)
    clock.start(chess.WHITE)
    fake_time.now += 5
    clock.press(chess.WHITE)

    assert clock.running == chess.BLACK
    assert clock.time_left(chess.WHITE) == pytest.approx(177)
    fake_time.now += 1
    assert clock.time_left(chess.BLACK) == pytest.approx(179)


def test_stop_freezes_time(fake_time: FakeTime) -> None:
    clock = GameClock(60, now=fake_time)
    clock.start(chess.BLACK)
    fake_time.now += 3
    clock.stop()
    fake_time.now += 100

    assert clock.running is None
    assert clock.time_left(chess.BLACK) == pytest.approx(57)
    assert clock.flagged() is None


def test_flagged_reports_running_side_only(fake_time: FakeTime) -> None:
    clock = GameClock(1, now=fake_time)
    clock.start(chess.WHITE)
    assert clock.flagged() is None

    fake_time.now += 1.0
    assert clock.flagged() == chess.WHITE

    clock.stop()
    assert clock.flagged() is None  # durmuş saat bayrak düşürmez


def test_format_clock_rounds_up() -> None:
    assert format_clock(600) == "10:00"
    assert format_clock(179.2) == "3:00"
    assert format_clock(65) == "1:05"
    assert format_clock(0.01) == "0:01"
    assert format_clock(0) == "0:00"
    assert format_clock(-3) == "0:00"
