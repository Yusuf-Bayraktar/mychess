import chess

from mychess.board import Board
from mychess.const import ALPHABET, COLS, PIECES, ROWS, TAGS
from mychess.main import PIECE_TYPE_NAMES
from mychess.pieces import Pawn
from mychess.square import Square


def test_constants():
    assert len(ALPHABET) == 8
    assert len(PIECES) == 6
    assert len(TAGS) == 6
    assert ROWS == 8
    assert COLS == 8


def test_piece_type_mapping():
    assert PIECE_TYPE_NAMES[chess.PAWN] == "pawn"
    assert PIECE_TYPE_NAMES[chess.KNIGHT] == "knight"
    assert PIECE_TYPE_NAMES[chess.BISHOP] == "bishop"
    assert PIECE_TYPE_NAMES[chess.ROOK] == "rook"
    assert PIECE_TYPE_NAMES[chess.QUEEN] == "queen"
    assert PIECE_TYPE_NAMES[chess.KING] == "king"


def test_coordinate_mapping_white_perspective():
    # When playing as white:
    # col=0, row=0 -> a8 (file=0, rank=7)
    # col=4, row=6 -> e2 (file=4, rank=1)
    # col=7, row=7 -> h1 (file=7, rank=0)
    col, row = 0, 0
    sq_a8 = chess.square(col, 7 - row)
    assert chess.square_name(sq_a8) == "a8"

    col, row = 4, 6
    sq_e2 = chess.square(col, 7 - row)
    assert chess.square_name(sq_e2) == "e2"

    col, row = 7, 7
    sq_h1 = chess.square(col, 7 - row)
    assert chess.square_name(sq_h1) == "h1"


def test_coordinate_mapping_black_perspective():
    # When playing as black (board flipped):
    # col=0, row=0 -> h1 (file=7, rank=0)
    # col=3, row=1 -> e2 (file=4, rank=1)
    # col=7, row=7 -> a8 (file=0, rank=7)
    col, row = 0, 0
    sq_h1 = chess.square(7 - col, row)
    assert chess.square_name(sq_h1) == "h1"

    col, row = 3, 1
    sq_e2 = chess.square(7 - col, row)
    assert chess.square_name(sq_e2) == "e2"

    col, row = 7, 7
    sq_a8 = chess.square(7 - col, row)
    assert chess.square_name(sq_a8) == "a8"


def test_legal_moves_filtering():
    board = chess.Board()
    e2_square = chess.E2
    legal_moves_from_e2 = [m for m in board.legal_moves if m.from_square == e2_square]
    
    # Pawn at e2 can move to e3 or e4
    destinations = {chess.square_name(m.to_square) for m in legal_moves_from_e2}
    assert destinations == {"e3", "e4"}


def test_pawn_promotion_moves():
    # Setup board with white pawn on e7 ready to promote to e8
    board = chess.Board("8/4P3/8/8/8/8/8/k6K w - - 0 1")
    e7_square = chess.E7
    promotion_moves = [m for m in board.legal_moves if m.from_square == e7_square]

    # Should have 4 promotion options: Q, R, B, N
    assert len(promotion_moves) == 4
    promotions = {m.promotion for m in promotion_moves}
    assert promotions == {chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT}


def test_game_status_checkmate():
    # Fool's Mate (2 moves checkmate)
    board = chess.Board()
    board.push_san("f3")
    board.push_san("e5")
    board.push_san("g4")
    board.push_san("Qh4#")

    assert board.is_checkmate() is True
    assert board.is_game_over() is True


def test_game_status_stalemate():
    # Famous stalemate position: Black king on a8, white queen on c7, white king on a6
    board = chess.Board("k7/2Q5/K7/8/8/8/8/8 b - - 0 1")
    assert board.is_stalemate() is True
    assert board.is_game_over() is True


def test_game_status_insufficient_material():
    # King vs King
    board = chess.Board("8/8/8/4k3/8/8/4K3/8 w - - 0 1")
    assert board.is_insufficient_material() is True


def test_time_formatting():
    def format_time(seconds: int) -> str:
        return f"{seconds // 60}:{seconds % 60:0>2}"

    assert format_time(600) == "10:00"
    assert format_time(180) == "3:00"
    assert format_time(65) == "1:05"
    assert format_time(9) == "0:09"
    assert format_time(0) == "0:00"


def test_legacy_oop_classes():
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


def test_resource_and_engine_paths():
    from mychess.main import get_engine_path, get_resource_path

    assets_path = get_resource_path("assets")
    assert assets_path.exists()
    assert (assets_path / "images" / "imgs-80px").exists()

    theme_path = get_resource_path("ForestTheme/forest-dark.tcl")
    assert theme_path.exists()

    engine_path = get_engine_path()
    assert engine_path.exists()
