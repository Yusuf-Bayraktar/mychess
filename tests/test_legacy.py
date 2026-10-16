"""Sabitler, kaynak yolları ve eski (kullanılmayan) tahta modeli."""

from mychess.board import Board
from mychess.const import ALPHABET, COLS, PIECES, ROWS, TAGS
from mychess.pieces import Pawn
from mychess.resources import get_resource_path
from mychess.square import Square


def test_constants() -> None:
    assert len(ALPHABET) == 8
    assert len(PIECES) == 6
    assert len(TAGS) == 6
    assert ROWS == 8
    assert COLS == 8


def test_resource_paths() -> None:
    assets_path = get_resource_path("assets")
    assert assets_path.exists()
    for color in ("white", "black"):
        for piece in PIECES:
            assert (assets_path / "images" / "imgs-128px" / f"{color}_{piece}.png").exists()
    assert get_resource_path("ForestTheme/forest-dark.tcl").exists()


def test_legacy_oop_classes() -> None:
    pawn = Pawn("white")
    assert pawn.name == "pawn"
    assert pawn.color == "white"
    assert pawn.tag == "P"

    square = Square(6, 4, pawn)
    assert square.has_piece() is True
    assert square.row == 6
    assert square.col == 4

    board = Board()
    assert len(board.board) == 8
    assert len(board.board[0]) == 8
    assert board.board[6][4].piece.name == "pawn"
    assert board.board[7][4].piece.name == "king"
