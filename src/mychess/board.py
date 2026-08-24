from .const import COLS, ROWS
from .pieces import Bishop, King, Knight, Pawn, Piece, Queen, Rook
from .square import Square


class Board:
    def __init__(self) -> None:
        self.board: list[list[Square]] = []
        self.create_board()
        self.add_pieces("white")
        self.add_pieces("black")

    def create_board(self) -> None:
        for row in range(ROWS):
            self.board.append(
                [Square(row, col, Piece("", "", ".")) for col in range(COLS)]
            )

    def add_pieces(self, color: str) -> None:
        row_pawns, row_other = (1, 0) if color == "black" else (6, 7)

        for col in range(COLS):
            self.board[row_pawns][col] = Square(row_pawns, col, Pawn(color))

        self.board[row_other][1] = Square(row_other, 1, Knight(color))
        self.board[row_other][6] = Square(row_other, 6, Knight(color))

        self.board[row_other][2] = Square(row_other, 2, Bishop(color))
        self.board[row_other][5] = Square(row_other, 5, Bishop(color))

        self.board[row_other][0] = Square(row_other, 0, Rook(color))
        self.board[row_other][7] = Square(row_other, 7, Rook(color))

        self.board[row_other][3] = Square(row_other, 3, Queen(color))
        self.board[row_other][4] = Square(row_other, 4, King(color))
