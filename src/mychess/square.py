
from .pieces import Piece


class Square:
    def __init__(
        self, row: int, col: int, piece: Piece | None = None
    ) -> None:
        if piece is None:
            piece = Piece("", "", ".")
        self.row: int = row
        self.col: int = col
        self.piece: Piece = piece

    def has_piece(self) -> bool:
        return self.piece.name != ""
