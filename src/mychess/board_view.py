"""Satranç tahtasının çizimi ve fare etkileşimi (tıkla-tıkla, sürükle-bırak)."""

import logging
import tkinter as tk
from collections.abc import Callable
from pathlib import Path

import chess
from PIL import Image, ImageTk

from .const import ALPHABET, BCOLOR, COLS, HCOLOR, MBLACK, MWHITE, PIECES, ROWS, WCOLOR

logger = logging.getLogger(__name__)

PIECE_TYPE_NAMES: dict[chess.PieceType, str] = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}

# Fare bu kadar pikselden fazla kayarsa tıklama sürüklemeye dönüşür.
DRAG_THRESHOLD: int = 4


def cell_to_square(col: int, row: int, white_bottom: bool) -> chess.Square:
    """Tahta hücresini (sütun, satır) python-chess karesine çevirir."""
    if white_bottom:
        return chess.square(col, 7 - row)
    return chess.square(7 - col, row)


def square_to_cell(square: chess.Square, white_bottom: bool) -> tuple[int, int]:
    """python-chess karesini tahta hücresine (sütun, satır) çevirir."""
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    if white_bottom:
        return file, 7 - rank
    return 7 - file, rank


def load_piece_images(images_dir: Path) -> dict[str, Image.Image]:
    """Taş görsellerini (`<renk>_<taş>.png`) bir kez belleğe yükler; anahtar `<taş>_<renk>`."""
    images: dict[str, Image.Image] = {}
    for piece in PIECES:
        for color in ("white", "black"):
            path = images_dir / f"{color}_{piece}.png"
            if path.exists():
                images[f"{piece}_{color}"] = Image.open(str(path)).convert("RGBA")
            else:
                logger.warning("Taş görseli bulunamadı: %s", path)
    return images


class BoardView:
    """Tahtayı canvas'a çizer ve fare girişini hamle isteğine çevirir.

    Tahtanın sahibi değildir: gösterilecek `chess.Board`'u `show()` ile alır.
    Hamleyi kendisi oynamaz; kullanıcı yasal bir hedef seçince
    `on_move(kaynak, hedef)` çağrılır. `can_interact()` False iken giriş yok sayılır.
    """

    def __init__(
        self,
        parent: tk.Misc,
        size: int,
        images_dir: Path,
        can_interact: Callable[[], bool],
        on_move: Callable[[chess.Square, chess.Square], None],
    ) -> None:
        self.canvas = tk.Canvas(parent, width=size, height=size, highlightthickness=0)
        self.size = size
        self.board = chess.Board()
        self.white_bottom = True
        self._can_interact = can_interact
        self._on_move = on_move

        self.selected: chess.Square | None = None
        self.legal_moves: list[chess.Move] = []
        self._reselected = False
        self._piece_items: dict[chess.Square, int] = {}
        self._drag_item: int | None = None
        self._drag_origin: tuple[int, int] = (0, 0)
        self._dragging = False

        self._raw_images = load_piece_images(images_dir)
        # Terfi penceresi de kullanır; anahtar `<taş>_<renk>`.
        self.piece_images: dict[str, ImageTk.PhotoImage] = {}
        self._scale_images()

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    @property
    def square_size(self) -> int:
        return self.size // ROWS

    def show(self, board: chess.Board, white_bottom: bool) -> None:
        """Verilen tahtayı verilen yönden gösterir; seçimi temizler."""
        self.board = board
        self.white_bottom = white_bottom
        self.clear_selection()
        self.redraw()

    def resize(self, size: int) -> None:
        """Tahta boyutunu değiştirir; boyut aynıysa hiçbir şey yapmaz."""
        if size == self.size:
            return
        self.size = size
        self.canvas.configure(width=size, height=size)
        self._scale_images()
        self.redraw()

    def _scale_images(self) -> None:
        """Bellekteki 128 px görselleri kare boyutuna ölçekler (diskten okumaz).

        LANCZOS küçültmede keskin kalır; 128 px kaynak tipik kare boyutlarından
        (50–100 px) büyük olduğu için görseller neredeyse hep küçültülür.
        """
        sq = self.square_size
        for key, raw in self._raw_images.items():
            self.piece_images[key] = ImageTk.PhotoImage(
                raw.resize((sq, sq), Image.Resampling.LANCZOS)
            )

    def redraw(self) -> None:
        """Tahtayı, taşları ve seçili taşın yasal hamlelerini baştan çizer."""
        self.canvas.delete("all")
        self._draw_squares()
        self._draw_pieces()
        self._draw_legal_moves()

    def _draw_squares(self) -> None:
        """Kareleri (son hamle ve seçim vurgusuyla) ve koordinat yazılarını çizer."""
        sq = self.square_size
        highlighted: set[tuple[int, int]] = set()
        if self.board.move_stack:
            last_move = self.board.peek()
            for square in (last_move.from_square, last_move.to_square):
                highlighted.add(square_to_cell(square, self.white_bottom))
        if self.selected is not None:
            highlighted.add(square_to_cell(self.selected, self.white_bottom))

        for row in range(ROWS):
            for col in range(COLS):
                light = (row + col) % 2 == 0
                if (col, row) in highlighted:
                    color = MWHITE if light else MBLACK
                else:
                    color = WCOLOR if light else BCOLOR
                self.canvas.create_rectangle(
                    col * sq,
                    row * sq,
                    (col + 1) * sq,
                    (row + 1) * sq,
                    fill=color,
                    width=0,
                    tags="rect",
                )

        files = ALPHABET if self.white_bottom else ALPHABET[::-1]
        for i, file_letter in enumerate(files):
            rank_color = BCOLOR if i % 2 == 0 else WCOLOR
            file_color = WCOLOR if i % 2 == 0 else BCOLOR
            rank_number = str(8 - i) if self.white_bottom else str(i + 1)
            self.canvas.create_text(
                sq // 6,
                i * sq + sq // 6,
                text=rank_number,
                fill=rank_color,
                font=("Calibri", sq // 6),
                tags="text",
            )
            self.canvas.create_text(
                (i + 1) * sq - sq // 6,
                self.size - sq // 6,
                text=file_letter,
                fill=file_color,
                font=("Calibri", sq // 6),
                tags="text",
            )

    def _draw_pieces(self) -> None:
        """Taşları python-chess tahtasından okuyarak çizer."""
        sq = self.square_size
        self._piece_items = {}
        for square, piece in self.board.piece_map().items():
            col, row = square_to_cell(square, self.white_bottom)
            color_name = "white" if piece.color == chess.WHITE else "black"
            img = self.piece_images.get(
                f"{PIECE_TYPE_NAMES[piece.piece_type]}_{color_name}"
            )
            if img:
                self._piece_items[square] = self.canvas.create_image(
                    col * sq,
                    row * sq,
                    image=img,
                    anchor=tk.NW,
                    tags=PIECE_TYPE_NAMES[piece.piece_type],
                )

    def _draw_legal_moves(self) -> None:
        """Seçili taş için hedef yasal hamle noktalarını çizer."""
        sq = self.square_size
        radius = sq // 6
        for move in self.legal_moves:
            col, row = square_to_cell(move.to_square, self.white_bottom)
            x = col * sq + sq // 2
            y = row * sq + sq // 2
            self.canvas.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                fill=HCOLOR,
                width=0,
                tags="circle",
            )

    def square_at(self, x: int, y: int) -> chess.Square | None:
        """Canvas koordinatındaki kareyi döndürür; tahta dışındaysa None."""
        col, row = x // self.square_size, y // self.square_size
        if 0 <= col < COLS and 0 <= row < ROWS:
            return cell_to_square(col, row, self.white_bottom)
        return None

    def select(self, square: chess.Square) -> None:
        """Kareyi seçer ve oradaki taşın yasal hamlelerini hazırlar."""
        self.selected = square
        self.legal_moves = [
            m for m in self.board.legal_moves if m.from_square == square
        ]

    def clear_selection(self) -> None:
        self.selected = None
        self.legal_moves = []
        self._drag_item = None
        self._dragging = False

    def is_legal_target(self, square: chess.Square) -> bool:
        return any(m.to_square == square for m in self.legal_moves)

    def _request_move(self, target: chess.Square) -> None:
        if self.selected is not None:
            self._on_move(self.selected, target)

    def _on_press(self, e: tk.Event) -> None:
        """Tıklama: seçili taşın hedefine tıklandıysa hamle ister, değilse taş seçer.

        Seçilen taş aynı zamanda sürüklenmeye hazırlanır; böylece hem
        tıkla-tıkla hem sürükle-bırak çalışır.
        """
        if not self._can_interact():
            return
        square = self.square_at(e.x, e.y)
        if square is None:
            return

        if self.selected is not None and self.is_legal_target(square):
            self._request_move(square)
            return

        piece = self.board.piece_at(square)
        if piece is None or piece.color != self.board.turn:
            self.clear_selection()
            self.redraw()
            return

        self._reselected = self.selected == square
        self.select(square)
        self.redraw()
        self._drag_item = self._piece_items.get(square)
        self._drag_origin = (e.x, e.y)
        if self._drag_item is not None:
            self.canvas.tag_raise(self._drag_item)

    def _on_drag(self, e: tk.Event) -> None:
        """Sürüklenen taşı fare imlecini ortalayarak hareket ettirir."""
        if self._drag_item is None:
            return
        if not self._dragging:
            dx = abs(e.x - self._drag_origin[0])
            dy = abs(e.y - self._drag_origin[1])
            if dx < DRAG_THRESHOLD and dy < DRAG_THRESHOLD:
                return
            self._dragging = True
        half = self.square_size // 2
        self.canvas.moveto(self._drag_item, x=e.x - half, y=e.y - half)

    def _on_release(self, e: tk.Event) -> None:
        """Sürükleme bittiğinde hamle ister; basit tıklamada seçim korunur."""
        if self._drag_item is None:
            return
        was_dragging = self._dragging
        self._drag_item = None
        self._dragging = False

        if not was_dragging:
            # Seçili taşa ikinci kez tıklamak seçimi kaldırır.
            if self._reselected:
                self.clear_selection()
                self.redraw()
            return

        square = self.square_at(e.x, e.y)
        if (
            square is not None
            and square != self.selected
            and self.is_legal_target(square)
        ):
            self._request_move(square)
            return
        if square != self.selected:
            self.clear_selection()
        self.redraw()
