"""ChessApp akışları: motor hataları, saat, terfi, yeniden başlatma yarışı.

Gerçek Stockfish yerine sahte motor kullanılır; Tk ekranı yoksa testler atlanır.
"""

import importlib
import tkinter as tk
from collections.abc import Callable, Iterator

import chess
import chess.engine
import pytest
from fakes import FakeEngine, wait_for

from mychess import engine as engine_module
from mychess.engine import EngineController
from mychess.game import GameMode
from mychess.main import ChessApp
from mychess.widgets import Popup

# `from mychess import main` paketteki main() fonksiyonunu verir, modülü değil.
main_module = importlib.import_module("mychess.main")


@pytest.fixture
def errors(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Hata pencerelerinin başlıklarını toplar; diğer pencereleri susturur."""
    shown: list[str] = []

    def record(title: str, _message: str, **_kwargs: object) -> None:
        shown.append(title)

    monkeypatch.setattr(main_module.messagebox, "showerror", record)
    monkeypatch.setattr(main_module.messagebox, "showinfo", lambda *a, **kw: None)
    monkeypatch.setattr(main_module.messagebox, "askyesno", lambda *a, **kw: True)
    return shown


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, errors: list[str]) -> Iterator[ChessApp]:
    monkeypatch.setattr(engine_module, "engine_think_time", lambda *a, **kw: 0.0)
    # Açılışta gerçek Stockfish başlatılmasın; motoru her test kendisi verir.
    monkeypatch.setattr(EngineController, "start", lambda self: None)
    try:
        chess_app = ChessApp()
    except tk.TclError:
        pytest.skip("Tk ekranı yok")
    chess_app.root.withdraw()
    yield chess_app
    chess_app.on_closing()


def wait_until(app: ChessApp, cond: Callable[[], bool], timeout: float = 5.0) -> bool:
    return wait_for(cond, timeout, step=app.root.update)


def start_game(
    app: ChessApp,
    mode: GameMode = GameMode.PLAYER,
    side: chess.Color = chess.WHITE,
) -> None:
    app.mode_var.set(mode.value)
    app.side_var.set("Beyaz" if side == chess.WHITE else "Siyah")
    app.play()


def restart_installs(
    app: ChessApp, monkeypatch: pytest.MonkeyPatch, engine: FakeEngine | None
) -> None:
    """Motor yeniden başlatıldığında verilen sahte motoru kurar."""
    monkeypatch.setattr(app.engine, "start", lambda: setattr(app.engine, "client", engine))


# --- Motor hataları ---


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_unexpected_engine_exception_does_not_hang(
    app: ChessApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.engine.client = FakeEngine(fail_with=ValueError("beklenmeyen"))
    restart_installs(app, monkeypatch, FakeEngine())
    start_game(app, GameMode.STOCKFISH, chess.BLACK)

    assert wait_until(app, lambda: len(app.game.board.move_stack) == 1)
    assert not app.is_stockfish_thinking
    assert app.game.can_player_move


def test_dead_engine_is_restarted_mid_game(
    app: ChessApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = FakeEngine()
    app.engine.client = engine
    start_game(app, GameMode.STOCKFISH, chess.WHITE)
    engine.dead = True
    restart_installs(app, monkeypatch, FakeEngine())

    app.try_move(chess.E2, chess.E4)

    assert wait_until(app, lambda: len(app.game.board.move_stack) == 2)
    assert app.game.running and app.game.can_player_move


def test_game_stops_with_message_when_restart_fails(
    app: ChessApp, monkeypatch: pytest.MonkeyPatch, errors: list[str]
) -> None:
    engine = FakeEngine()
    app.engine.client = engine
    start_game(app, GameMode.STOCKFISH, chess.WHITE)
    engine.dead = True
    restart_installs(app, monkeypatch, None)

    app.try_move(chess.E2, chess.E4)

    assert wait_until(app, lambda: not app.game.running)
    assert wait_until(app, lambda: errors == ["Motor Hatası"])
    assert "durduruldu" in app.status_label["text"]
    assert app.game.clock.running is None

    # Ölü motorla "Play" istisna fırlatmamalı, hata göstermeli.
    app.play()
    assert errors[-1] == "Motor Hatası"


def test_play_restarts_engine_that_died_in_menu(
    app: ChessApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    dead = FakeEngine()
    dead.dead = True
    app.engine.client = dead
    restart_installs(app, monkeypatch, FakeEngine())

    start_game(app, GameMode.STOCKFISH, chess.BLACK)

    assert wait_until(app, lambda: len(app.game.board.move_stack) == 1)


def test_stale_engine_result_is_ignored_after_restart(app: ChessApp) -> None:
    # Motor düşünürken yeni oyun: eski oyunun hamlesi yeni tahtaya uygulanmamalı.
    app.engine.client = FakeEngine(delay=0.3)
    start_game(app, GameMode.STOCKFISH, chess.BLACK)
    assert wait_until(app, lambda: app.is_stockfish_thinking, timeout=2)

    app.restart()
    new_game = app.game
    assert wait_until(app, lambda: bool(new_game.board.move_stack), timeout=3)
    wait_until(app, lambda: False, timeout=0.5)  # eski sonuç da gelsin

    assert len(new_game.board.move_stack) == 1
    assert new_game.can_player_move


# --- Saat ---


def test_flag_fall_ends_game_and_stops_clock(app: ChessApp) -> None:
    start_game(app)
    app.game.clock.remaining[chess.WHITE] = 0.2

    assert wait_until(app, lambda: not app.game.running, timeout=2)
    assert app.status_label["text"] == "Süre bitti! Siyah kazandı."
    assert app.game.clock.running is None
    assert app.bottom_clock["text"] == "0:00"


def test_move_after_flag_fell_is_rejected(app: ChessApp) -> None:
    # Süre ekran döngüsü fark etmeden bittiyse hamle oynanmamalı.
    start_game(app)
    app.game.clock.remaining[chess.WHITE] = 0.0

    app.try_move(chess.E2, chess.E4)

    assert app.game.board.move_stack == []
    assert not app.game.running
    assert app.status_label["text"] == "Süre bitti! Siyah kazandı."


def test_confirm_dialog_pauses_clock(
    app: ChessApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    start_game(app)
    app.try_move(chess.E2, chess.E4)
    seen_running: list[chess.Color | None] = []

    def decline(*_args: object, **_kwargs: object) -> bool:
        seen_running.append(app.game.clock.running)
        return False

    monkeypatch.setattr(main_module.messagebox, "askyesno", decline)
    app.on_menu()

    assert seen_running == [None]  # soru açıkken saat durdu
    assert app.game.clock.running == chess.BLACK  # vazgeçince kaldığı yerden sürdü
    assert app.game.running


def test_clocks_follow_player_side(app: ChessApp) -> None:
    app.time_var.set("3+2")
    start_game(app, side=chess.BLACK)
    app.game.clock.remaining[chess.WHITE] = 65
    app.update_time_display()

    assert app.top_clock["text"] == "1:05"  # siyah altta: üst saat beyazın
    assert app.bottom_clock["text"] == "3:00"


# --- Hatalar, terfi, hamle kaydı ---


def test_callback_exception_is_logged_and_reported_once(
    app: ChessApp, errors: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    def boom() -> None:
        raise RuntimeError("geri çağrı patladı")

    app.root.after(0, boom)
    app.root.after(0, boom)
    wait_until(app, lambda: len(caplog.records) >= 2, timeout=1)

    logged = [r for r in caplog.records if "geri çağrısında" in r.getMessage()]
    assert len(logged) == 2
    assert logged[0].exc_info is not None
    assert errors == ["Beklenmeyen Hata"]


def test_promotion_popup_uses_color_of_side_to_move(
    app: ChessApp, monkeypatch: pytest.MonkeyPatch
) -> None:
    colors: list[chess.Color] = []

    class FakePopup:
        def __init__(self, _parent: tk.Tk, piece_color: chess.Color, _images: object) -> None:
            colors.append(piece_color)
            self.choice = "q"

    monkeypatch.setattr(main_module, "Popup", FakePopup)
    monkeypatch.setattr(app.root, "wait_window", lambda _w: None)
    start_game(app)
    app.game.board.set_fen("k7/8/8/8/8/8/4p3/K7 b - - 0 1")

    app.try_move(chess.E2, chess.E1)

    assert colors == [chess.BLACK]
    assert app.game.board.piece_at(chess.E1) == chess.Piece(chess.QUEEN, chess.BLACK)


def test_promotion_popup_without_images_uses_text_buttons(app: ChessApp) -> None:
    # Taş görselleri yüklenemese de terfi penceresi açılıp seçim yapılabilmeli.
    popup = Popup(app.root, chess.WHITE, {})
    try:
        texts = {str(w.cget("text")) for w in popup.winfo_children()}
        assert texts == {"Vezir", "Kale", "Fil", "At"}
    finally:
        popup.select("n")
    assert popup.choice == "n"


def test_move_log_rows(app: ChessApp) -> None:
    start_game(app)
    for src, dst in ((chess.E2, chess.E4), (chess.E7, chess.E5), (chess.G1, chess.F3)):
        app.try_move(src, dst)

    rows = [app.move_log.item(r, "values") for r in app.move_log.get_children()]
    assert [tuple(row) for row in rows] == [("1.", "e4", "e5"), ("2.", "Nf3", "")]


def test_checkmate_shows_result(app: ChessApp) -> None:
    start_game(app)
    for src, dst in (
        (chess.F2, chess.F3),
        (chess.E7, chess.E5),
        (chess.G2, chess.G4),
        (chess.D8, chess.H4),
    ):
        app.try_move(src, dst)

    assert not app.game.running
    assert app.status_label["text"] == "Şah mat! Siyah kazandı."


# --- Pencere boyutu ---


def clipped_widgets(app: ChessApp, container: tk.Misc) -> list[str]:
    """Pencere dışına taşan ya da istediğinden küçük çizilen widget'lar."""
    root = app.root
    right = root.winfo_rootx() + root.winfo_width()
    bottom = root.winfo_rooty() + root.winfo_height()
    bad: list[str] = []

    def walk(widget: tk.Misc) -> None:
        for child in widget.winfo_children():
            if not child.winfo_ismapped():
                continue
            if (
                child.winfo_rootx() + child.winfo_width() > right + 1
                or child.winfo_rooty() + child.winfo_height() > bottom + 1
                or child.winfo_width() < child.winfo_reqwidth() - 1
                or child.winfo_height() < child.winfo_reqheight() - 1
            ):
                bad.append(f"{child.winfo_class()} {child}")
            walk(child)

    walk(container)
    return bad


def test_minimum_window_fits_menu_and_sidebar(app: ChessApp) -> None:
    # Eskiden en küçük pencerede yan panelin sağ tarafı kırpılıyordu.
    app.root.deiconify()
    min_width, min_height = app.root.minsize()
    app.root.geometry(f"{min_width}x{min_height}")
    app.root.update()
    app.root.update()
    assert clipped_widgets(app, app.menu_box) == []

    start_game(app)
    app.root.update()
    assert app.board_view.size == main_module.MIN_BOARD_SIZE
    assert clipped_widgets(app, app.game_frame) == []


def test_board_leaves_room_for_sidebar(app: ChessApp) -> None:
    sidebar = app.sidebar_frame.winfo_reqwidth()
    assert app.board_size_for(sidebar + 600, 900) == 600  # genişlik sınırlar
    assert app.board_size_for(sidebar + 900, 700) == 700  # yükseklik sınırlar
    assert app.board_size_for(100, 100) == main_module.MIN_BOARD_SIZE
