import tkinter as tk
from collections.abc import Iterator

import chess
import pytest

from mychess.board_view import BoardView, cell_to_square, square_to_cell
from mychess.const import COLS, ROWS
from mychess.resources import get_resource_path

IMAGES_DIR = get_resource_path("assets") / "images" / "imgs-128px"


def test_cell_square_round_trip() -> None:
    for white_bottom in (True, False):
        for sq in chess.SQUARES:
            col, row = square_to_cell(sq, white_bottom)
            assert 0 <= col < COLS and 0 <= row < ROWS
            assert cell_to_square(col, row, white_bottom) == sq


def test_cell_to_square_orientation() -> None:
    # Beyaz altta: sol üst a8, sağ alt h1. Siyah altta tersi.
    assert cell_to_square(0, 0, True) == chess.A8
    assert cell_to_square(7, 7, True) == chess.H1
    assert cell_to_square(4, 6, True) == chess.E2
    assert cell_to_square(0, 0, False) == chess.H1
    assert cell_to_square(3, 1, False) == chess.E2


class ViewHarness:
    """BoardView'u gerçek canvas'la kurar, fare olaylarını doğrudan verir."""

    def __init__(self, root: tk.Tk) -> None:
        self.interactive = True
        self.moves: list[tuple[chess.Square, chess.Square]] = []
        self.view = BoardView(
            root,
            512,
            IMAGES_DIR,
            can_interact=lambda: self.interactive,
            on_move=lambda src, dst: self.moves.append((src, dst)),
        )
        self.view.canvas.pack()
        self.view.show(chess.Board(), white_bottom=True)

    def center(self, square: chess.Square) -> tuple[int, int]:
        col, row = square_to_cell(square, self.view.white_bottom)
        size = self.view.square_size
        return col * size + size // 2, row * size + size // 2

    @staticmethod
    def event(x: int, y: int) -> tk.Event:
        ev: tk.Event = tk.Event()
        ev.x, ev.y = x, y
        return ev

    def click(self, square: chess.Square) -> None:
        x, y = self.center(square)
        self.view._on_press(self.event(x, y))
        self.view._on_release(self.event(x, y))

    def drag(self, src: chess.Square, dst: chess.Square) -> None:
        x0, y0 = self.center(src)
        x1, y1 = self.center(dst)
        self.view._on_press(self.event(x0, y0))
        self.view._on_drag(self.event((x0 + x1) // 2, (y0 + y1) // 2))
        self.view._on_drag(self.event(x1, y1))
        self.view._on_release(self.event(x1, y1))


@pytest.fixture
def harness(tk_root: tk.Tk) -> Iterator[ViewHarness]:
    yield ViewHarness(tk_root)


def test_click_click_requests_move(harness: ViewHarness) -> None:
    harness.click(chess.E2)
    assert harness.view.selected == chess.E2
    assert {m.to_square for m in harness.view.legal_moves} == {chess.E3, chess.E4}

    harness.click(chess.E4)
    assert harness.moves == [(chess.E2, chess.E4)]


def test_drag_and_drop_requests_move(harness: ViewHarness) -> None:
    harness.drag(chess.G1, chess.F3)
    assert harness.moves == [(chess.G1, chess.F3)]


def test_drop_on_illegal_square_cancels(harness: ViewHarness) -> None:
    harness.drag(chess.G1, chess.G4)
    assert harness.moves == []
    assert harness.view.selected is None


def test_second_click_on_selected_piece_deselects(harness: ViewHarness) -> None:
    harness.click(chess.D2)
    harness.click(chess.D2)
    assert harness.view.selected is None
    assert harness.view.legal_moves == []


def test_cannot_select_opponent_piece(harness: ViewHarness) -> None:
    harness.click(chess.D7)
    assert harness.view.selected is None


def test_input_ignored_when_not_interactive(harness: ViewHarness) -> None:
    harness.interactive = False
    harness.click(chess.E2)
    harness.click(chess.E4)
    assert harness.view.selected is None
    assert harness.moves == []


def test_black_at_bottom_maps_clicks(harness: ViewHarness) -> None:
    board = chess.Board()
    board.push_san("e4")
    harness.view.show(board, white_bottom=False)

    harness.click(chess.E7)
    harness.click(chess.E5)
    assert harness.moves == [(chess.E7, chess.E5)]
    assert harness.center(chess.H1) == (32, 32)  # siyah altta: h1 sol üstte


def test_resize_rescales_only_when_size_changes(harness: ViewHarness) -> None:
    before = dict(harness.view.piece_images)
    harness.view.resize(512)
    assert harness.view.piece_images == before  # aynı boyut: yeniden ölçekleme yok

    harness.view.resize(640)
    assert harness.view.square_size == 80
    assert harness.view.piece_images["king_white"] is not before["king_white"]
    assert harness.view.piece_images["king_white"].width() == 80
