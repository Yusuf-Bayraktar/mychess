import sys
import threading
import time
from pathlib import Path

import chess
import chess.engine
import pytest
from fakes import FakeEngine, wait_for

from mychess import engine as engine_module
from mychess.engine import (
    ENGINE_ENV_VAR,
    ENGINE_TIMEOUT,
    MAX_THINK_TIME,
    MIN_THINK_TIME,
    EngineController,
    engine_settings,
    engine_think_time,
    get_engine_path,
)


@pytest.fixture
def instant_think(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine_module, "engine_think_time", lambda *a, **kw: 0.0)


def poll_one(ctl: EngineController) -> tuple[int, chess.Move | None]:
    results: list[tuple[int, chess.Move | None]] = []

    def collect() -> bool:
        results.extend(ctl.poll())
        return bool(results)

    assert wait_for(collect, timeout=10)
    return results[0]


# --- Motor yolu ---


def test_engine_path_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "my-stockfish"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setenv(ENGINE_ENV_VAR, str(fake))
    assert get_engine_path() == fake


def test_found_engine_is_runnable_on_this_platform() -> None:
    # Motor kurulu olmayabilir; bulunduysa bu platformda çalıştırılabilir olmalı.
    path = get_engine_path()
    if path is None:
        pytest.skip("Stockfish kurulu değil")
    assert path.is_file()
    if sys.platform != "win32":
        assert path.suffix != ".exe"


# --- Zorluk ve düşünme süresi ---


def test_engine_settings_uses_uci_elo_in_range() -> None:
    settings = engine_settings(1600, (1320, 3190))
    assert settings.options["UCI_LimitStrength"] is True
    assert settings.options["UCI_Elo"] == 1600
    assert settings.depth is None


def test_engine_settings_clamps_to_engine_max() -> None:
    # Stockfish 15.1 en fazla 2850 kabul eder
    assert engine_settings(3000, (1350, 2850)).options["UCI_Elo"] == 2850


def test_engine_settings_below_uci_elo_minimum() -> None:
    weakest = engine_settings(400, (1320, 3190))
    assert weakest.options == {"UCI_LimitStrength": False, "Skill Level": 0}
    assert weakest.depth == 1

    # 1300, Stockfish 15.1'in (1350) ve 19'un (1320) alt sınırının altında
    settings = engine_settings(1300, (1350, 2850))
    assert settings.options["UCI_LimitStrength"] is False
    assert "UCI_Elo" not in settings.options

    # Seviyeler ELO arttıkça zayıflamamalı
    levels = [engine_settings(elo, (1320, 3190)) for elo in (400, 800, 1000, 1300)]
    depths = [s.depth or 0 for s in levels]
    skills = [int(s.options["Skill Level"]) for s in levels]
    assert depths == sorted(depths)
    assert skills == sorted(skills)


def test_engine_settings_without_uci_elo_option() -> None:
    settings = engine_settings(2000, None)
    assert settings.options["UCI_LimitStrength"] is False
    assert settings.depth is not None


def test_engine_think_time_follows_clock() -> None:
    # 3+2 oyun ortası: 180/60 + 2/2 = 4 sn
    assert engine_think_time(180, 2, 20) == 4.0
    # Açılışta daha hızlı
    assert engine_think_time(180, 2, 1) < engine_think_time(180, 2, 20)
    # Saat azaldıkça daha az düşünür ama hiç düşünmeden oynamaz
    assert engine_think_time(10, 0, 30) == MIN_THINK_TIME
    # Uzun kontrollerde üst sınır
    assert engine_think_time(600, 0, 20, jitter=1.5) == MAX_THINK_TIME
    assert engine_think_time(180, 2, 20, jitter=0.5) == 2.0


# --- EngineController (sahte motorla) ---


def test_configure_uses_engine_elo_range() -> None:
    ctl = EngineController()
    fake = FakeEngine()
    ctl.client = fake

    assert ctl.configure(1600)
    assert fake.configured[-1] == {
        "UCI_LimitStrength": True,
        "UCI_Elo": 1600,
        "Skill Level": 20,
    }
    assert ctl.settings.depth is None


def test_configure_skips_options_engine_does_not_have() -> None:
    ctl = EngineController()
    fake = FakeEngine(options={})
    ctl.client = fake

    assert ctl.configure(1600)
    assert fake.configured[-1] == {}
    assert ctl.settings.depth is not None  # UCI_Elo yok: Skill Level/derinlik yolu


def test_configure_reports_dead_engine() -> None:
    ctl = EngineController()
    fake = FakeEngine()
    fake.dead = True
    ctl.client = fake
    assert not ctl.configure(1600)
    assert not EngineController().configure(1600)  # motor hiç yok


def test_ensure_restarts_dead_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    ctl = EngineController()
    dead = FakeEngine()
    dead.dead = True
    ctl.client = dead
    fresh = FakeEngine()
    monkeypatch.setattr(ctl, "start", lambda: setattr(ctl, "client", fresh))

    assert ctl.ensure()
    assert ctl.client is fresh


def test_ensure_waits_for_background_start(monkeypatch: pytest.MonkeyPatch) -> None:
    ctl = EngineController()
    release = threading.Event()
    fake = FakeEngine()

    def slow_start() -> None:
        release.wait(5)
        ctl.client = fake

    monkeypatch.setattr(ctl, "start", slow_start)
    ctl.start_in_background()
    assert ctl.client is None  # başlatma sürüyor; çağıran beklemedi
    threading.Timer(0.05, release.set).start()

    assert ctl.ensure()
    assert ctl.client is fake


def test_shutdown_waits_for_background_start(monkeypatch: pytest.MonkeyPatch) -> None:
    # Başlatma bitmeden kapatılırsa sonradan açılan motor süreci arkada kalmamalı.
    ctl = EngineController()
    started = threading.Event()

    def slow_start() -> None:
        time.sleep(0.05)
        ctl.client = FakeEngine()
        started.set()

    monkeypatch.setattr(ctl, "start", slow_start)
    ctl.start_in_background()
    ctl.shutdown()
    assert started.is_set()
    assert ctl.client is None


def test_search_returns_move_with_game_id(instant_think: None) -> None:
    ctl = EngineController()
    ctl.client = FakeEngine()
    board = chess.Board()

    assert ctl.search(board, game_id=7, remaining=60, increment=0)
    game_id, move = poll_one(ctl)
    assert game_id == 7
    assert move is not None and board.is_legal(move)


def test_search_without_engine_returns_false() -> None:
    assert not EngineController().search(chess.Board(), 1, 60, 0)


def test_search_reports_engine_error_as_none(instant_think: None) -> None:
    ctl = EngineController()
    ctl.client = FakeEngine(fail_with=chess.engine.EngineError("bozuk"))
    ctl.search(chess.Board(), 3, 60, 0)
    assert poll_one(ctl) == (3, None)


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_search_reports_unexpected_error_as_none(instant_think: None) -> None:
    # Beklenmeyen hata thread'i öldürse de sonuç gelmeli; yoksa UI takılır.
    ctl = EngineController()
    ctl.client = FakeEngine(fail_with=ValueError("beklenmeyen"))
    ctl.search(chess.Board(), 4, 60, 0)
    assert poll_one(ctl) == (4, None)
    # Thread sonucu koyduktan sonra ölür; uyarı bu teste düşsün, sonrakine değil.
    for thread in threading.enumerate():
        if thread.name == "stockfish-search":
            thread.join(timeout=5)


# --- Gerçek Stockfish (kuruluysa) ---


@pytest.mark.skipif(get_engine_path() is None, reason="Stockfish kurulu değil")
@pytest.mark.parametrize("elo", [400, 1600])
def test_real_stockfish_plays_legal_move(instant_think: None, elo: int) -> None:
    ctl = EngineController()
    ctl.start_in_background()  # uygulama gibi: motor ana thread dışında açılır
    try:
        assert ctl.ensure()
        assert ctl.client is not None
        assert getattr(ctl.client, "timeout", None) == ENGINE_TIMEOUT
        assert ctl.configure(elo)
        board = chess.Board()
        board.push_san("e4")
        assert ctl.search(board, game_id=1, remaining=60, increment=0)
        game_id, move = poll_one(ctl)
        assert game_id == 1
        assert move is not None and board.is_legal(move)
    finally:
        ctl.shutdown()
