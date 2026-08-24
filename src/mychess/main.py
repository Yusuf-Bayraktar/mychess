import ctypes as ct
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import chess
import chess.engine
from PIL import Image, ImageTk

from .const import (
    ALPHABET,
    BCOLOR,
    COLS,
    HCOLOR,
    HEIGHT,
    MBLACK,
    MWHITE,
    PIECES,
    ROWS,
    SQSIZE,
    WCOLOR,
    WIDTH,
)


def get_resource_path(relative_path: str | Path) -> Path:
    """Geliştirme ve PyInstaller (.exe) ortamlarında doğru kaynak yolunu çözümler."""
    rel = Path(relative_path)

    # 1. PyInstaller Onefile modu (_MEIPASS)
    if hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS)
        cand_pkg = base_dir / "mychess" / rel
        if cand_pkg.exists():
            return cand_pkg
        cand_root = base_dir / rel
        if cand_root.exists():
            return cand_root
        return cand_pkg

    # 2. PyInstaller Onedir modu (sys.executable dizini)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        cand_root = exe_dir / rel
        if cand_root.exists():
            return cand_root
        cand_pkg = exe_dir / "mychess" / rel
        if cand_pkg.exists():
            return cand_pkg
        cand_src = exe_dir / "src" / "mychess" / rel
        if cand_src.exists():
            return cand_src
        return cand_root

    # 3. Geliştirme ortamı (Source / uv run)
    package_dir = Path(__file__).resolve().parent
    project_root = package_dir.parent.parent

    candidate_pkg = package_dir / rel
    if candidate_pkg.exists():
        return candidate_pkg
    candidate_root = project_root / rel
    if candidate_root.exists():
        return candidate_root

    return candidate_pkg


def get_engine_path(
    engine_relative_path: str | Path = (
        "engines/stockfish_15.1_win_x64_avx2/stockfish-windows-2022-x86-64-avx2.exe"
    ),
) -> Path:
    """Stockfish motoru için çalıştırılabilir dosya yolunu belirler."""
    rel = Path(engine_relative_path)

    # 1. PyInstaller Onedir / Onefile modu
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        cand_root = exe_dir / rel
        if cand_root.exists():
            return cand_root
        if hasattr(sys, "_MEIPASS"):
            cand_mei = Path(sys._MEIPASS) / rel
            if cand_mei.exists():
                return cand_mei
        return cand_root

    # 2. Geliştirme ortamı
    package_dir = Path(__file__).resolve().parent
    project_root = package_dir.parent.parent
    candidate = project_root / rel
    if candidate.exists():
        return candidate

    return package_dir / rel


PIECE_TYPE_NAMES: dict[chess.PieceType, str] = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}


def dark_title_bar(window: tk.Tk) -> None:
    """Windows için koyu başlık çubuğu (Immersive Dark Mode) uygular."""
    if sys.platform != "win32":
        return
    try:
        window.update()
        dwmwa_use_immersive_dark_mode = 20
        set_window_attribute = ct.windll.dwmapi.DwmSetWindowAttribute
        get_parent = ct.windll.user32.GetParent
        hwnd = get_parent(window.winfo_id())
        value = ct.c_int(2)
        set_window_attribute(
            hwnd,
            dwmwa_use_immersive_dark_mode,
            ct.byref(value),
            ct.sizeof(value),
        )
    except (AttributeError, OSError):
        pass


class Popup(tk.Toplevel):
    """Piyon terfisi (pawn promotion) için seçim penceresi."""

    def __init__(
        self,
        parent: tk.Tk,
        player_side: bool,
        images: dict[str, ImageTk.PhotoImage],
    ) -> None:
        super().__init__(parent)
        self.title("Terfi")
        self.resizable(False, False)
        self.choice: str | None = None
        color = "white" if player_side else "black"

        ttk.Button(
            self,
            image=images[f"queen_{color}"],
            command=lambda: self.select("q"),
        ).pack(side=tk.RIGHT)
        ttk.Button(
            self,
            image=images[f"rook_{color}"],
            command=lambda: self.select("r"),
        ).pack(side=tk.RIGHT)
        ttk.Button(
            self,
            image=images[f"bishop_{color}"],
            command=lambda: self.select("b"),
        ).pack(side=tk.RIGHT)
        ttk.Button(
            self,
            image=images[f"knight_{color}"],
            command=lambda: self.select("n"),
        ).pack(side=tk.RIGHT)

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda _e: self.cancel())

        self.transient(parent)
        self.grab_set()

    def select(self, piece_char: str) -> None:
        self.choice = piece_char
        self.destroy()

    def cancel(self) -> None:
        """Terfi iptal edildiğinde seçimi sıfırlar ve pencereyi kapatır."""
        self.choice = None
        self.destroy()


class ChessApp:
    """Satranç uygulaması ana kontrolcüsü ve grafik arayüz yöneticisi."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.geometry(f"{WIDTH + 200}x{HEIGHT}")
        self.root.minsize(WIDTH, HEIGHT)
        self.root.title("Chess by Yusuf")

        # Tema ve Pencere Ayarları
        theme_path = get_resource_path("ForestTheme/forest-dark.tcl")
        if theme_path.exists():
            try:
                self.root.tk.call("source", str(theme_path))
                ttk.Style().theme_use("forest-dark")
            except tk.TclError:
                pass
        dark_title_bar(self.root)

        # Oyun Durumu
        self.board = chess.Board()
        self.moves: list[chess.Move] = []
        self.legal_moves: list[chess.Move] = []
        self.is_resume: bool = False
        self.player_side: bool = True  # True: White, False: Black
        self.game_mode: str = "Player"
        self.is_stockfish_thinking: bool = False

        # Zamanlayıcılar (Saniye)
        self.white_time: int = 600
        self.black_time: int = 600
        self.time_plus: int = 0
        self.after_time_id: str | None = None

        # Etkileşim ve Sürükleme Durumu
        self.closest: int | None = None
        self.prev_col: int | None = None
        self.prev_row: int | None = None

        # Motor ve Görsel Önbelleği
        self.engine: chess.engine.SimpleEngine | None = None
        self.engine_path = get_engine_path()
        self.assets_dir = get_resource_path("assets")
        self.raw_images: dict[str, Image.Image] = {}
        self.re_images: dict[str, ImageTk.PhotoImage] = {}

        # Menü Seçenekleri
        self.mode_list = ["Player", "Stockfish"]
        self.time_list = ["1+0", "3+2", "10+0"]
        self.elo_list = [
            "400",
            "800",
            "1000",
            "1300",
            "1600",
            "2000",
            "2400",
            "2850",
        ]
        self.side_list = ["white", "black"]
        self.depth_list = [1, 1, 3, 5, 7, 10, 13, 16, 20]

        self.mode_var = tk.StringVar(value=self.mode_list[0])
        self.time_var = tk.StringVar(value=self.time_list[0])
        self.elo_var = tk.StringVar(value=self.elo_list[3])
        self.side_var = tk.StringVar(value=self.side_list[0])

        self.load_raw_images()
        self.init_engine()
        self.setup_ui()
        self.resize_pieces()
        self.redraw()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after_time_id = self.root.after(1000, self.time_update)

    def load_raw_images(self) -> None:
        """Taş görsellerini diskten yalnızca 1 kez RAM'e yükler (Disk I/O Optimizasyonu)."""
        for piece in PIECES:
            for color in ("white", "black"):
                img_path = (
                    self.assets_dir / "images" / "imgs-80px" / f"{color}_{piece}.png"
                )
                if img_path.exists():
                    self.raw_images[f"{piece}_{color}"] = Image.open(
                        str(img_path)
                    ).convert("RGBA")

    def resize_pieces(self) -> None:
        """Yalnızca RAM'deki görselleri yeniden ölçeklendirir (Disk okuması yapmaz)."""
        for key, raw_img in self.raw_images.items():
            self.re_images[key] = ImageTk.PhotoImage(
                raw_img.resize((SQSIZE, SQSIZE), Image.Resampling.BILINEAR)
            )

    def init_engine(self) -> None:
        """Stockfish motorunu güvenli bir şekilde başlatır."""
        try:
            if self.engine_path.exists():
                startupinfo = (
                    subprocess.STARTUPINFO(
                        dwFlags=subprocess.STARTF_USESHOWWINDOW
                    )
                    if sys.platform == "win32"
                    else None
                )
                self.engine = chess.engine.SimpleEngine.popen_uci(
                    str(self.engine_path),
                    startupinfo=startupinfo,
                )
        except (
            chess.engine.EngineError,
            FileNotFoundError,
            PermissionError,
            OSError,
        ):
            self.engine = None

    def setup_ui(self) -> None:
        """Tüm arayüz bileşenlerini ve düzeni oluşturur."""
        self.root.rowconfigure(0, minsize=HEIGHT)
        self.root.columnconfigure(0, minsize=WIDTH + 200)

        # 1. Ana Menü Ekranı (main_frame)
        self.main_frame = tk.Frame(self.root)
        self.main_frame.grid(row=0, column=0, sticky="news")

        self.title_label = tk.Label(
            self.main_frame, text="Chess", font=("", 30, "bold")
        )
        self.title_label.pack(pady=(30, 20))

        # Mod Menüsü
        mode_frame = tk.Frame(self.main_frame, width=200)
        mode_frame.pack(pady=10)
        tk.Label(mode_frame, text="Mode:").pack(side=tk.LEFT, padx=5)
        ttk.OptionMenu(
            mode_frame, self.mode_var, self.mode_list[0], *self.mode_list
        ).pack(side=tk.RIGHT, padx=5)

        # Zaman Menüsü
        time_frame = tk.Frame(self.main_frame)
        time_frame.pack(pady=10)
        tk.Label(time_frame, text="Time:").pack(side=tk.LEFT, padx=5)
        ttk.OptionMenu(
            time_frame, self.time_var, self.time_list[0], *self.time_list
        ).pack(side=tk.RIGHT, padx=5)

        # ELO Menüsü
        elo_frame = tk.Frame(self.main_frame)
        elo_frame.pack(pady=10)
        tk.Label(elo_frame, text="Rating:").pack(side=tk.LEFT, padx=5)
        ttk.OptionMenu(
            elo_frame, self.elo_var, self.elo_list[3], *self.elo_list
        ).pack(side=tk.RIGHT, padx=5)

        # Taraf Seçimi
        side_frame = tk.Frame(self.main_frame)
        side_frame.pack(pady=10)
        tk.Label(side_frame, text="Side:").pack(side=tk.LEFT, padx=5)
        ttk.OptionMenu(
            side_frame, self.side_var, self.side_list[0], *self.side_list
        ).pack(side=tk.RIGHT, padx=5)

        # Oyna Butonu
        ttk.Button(
            self.main_frame,
            text="Play",
            style="Accent.TButton",
            command=self.play,
        ).pack(pady=(50, 0))

        # 2. Oyun Ekranı (game_frame)
        self.game_frame = tk.Frame(self.root)
        self.game_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.tkraise()

        self.chessboard = tk.Canvas(self.game_frame, width=WIDTH, height=HEIGHT)
        self.chessboard.pack(anchor="center", side=tk.LEFT)

        sidebar_frame = tk.Frame(self.game_frame)
        sidebar_frame.pack(side=tk.RIGHT, fill="both", expand=True)

        top_frame = tk.Frame(sidebar_frame)
        top_frame.pack(side=tk.TOP, fill="x", expand=True)
        self.b_time = tk.Label(
            top_frame,
            text="10:00",
            bg="black",
            fg="white",
            font=("Calibri", WIDTH // 20, "bold"),
        )
        self.b_time.pack(side=tk.LEFT)

        log_frame = tk.Frame(sidebar_frame)
        log_frame.pack(expand=True, fill="both")
        self.move_log = tk.Label(
            log_frame, text="", anchor=tk.NW, font=("Calibri", 17)
        )
        self.move_log.pack()

        bottom_frame = tk.Frame(sidebar_frame)
        bottom_frame.pack(side=tk.BOTTOM, fill="x", expand=True)
        self.w_time = tk.Label(
            bottom_frame,
            text="10:00",
            bg="black",
            fg="white",
            font=("Calibri", WIDTH // 20, "bold"),
        )
        self.w_time.pack(side=tk.LEFT)

        # Event Bağlantıları
        self.chessboard.bind("<Button-1>", self.on_click)
        self.root.bind("<Configure>", self.on_resize)

    def play(self) -> None:
        """Oyunu başlatır ve seçilen ayarları uygular."""
        self.game_frame.tkraise()
        self.player_side = self.side_var.get() == "white"
        self.game_mode = self.mode_var.get()

        if self.game_mode == "Stockfish":
            engine = self.engine
            if engine is None:
                messagebox.showerror(
                    "Motor Hatası",
                    "Stockfish motoru başlatılamadı. Lütfen iki kişilik (Player) modda oynayın.",
                )
                self.main_frame.tkraise()
                return

            try:
                raw_elo = self.elo_var.get()
                elo_val = int(raw_elo) if raw_elo else 1300
            except (ValueError, TypeError):
                elo_val = 1300

            elo = max(elo_val, 1350)
            skill_idx = (
                self.elo_list.index(self.elo_var.get())
                if self.elo_var.get() in self.elo_list
                else 0
            )
            try:
                engine.configure({
                    "Skill Level": skill_idx,
                    "UCI_LimitStrength": "false",
                    "UCI_Elo": elo,
                })
            except (
                chess.engine.EngineError,
                chess.engine.EngineTerminatedError,
                OSError,
            ):
                pass

        self.restart()

    def restart(self) -> None:
        """Tahtayı ve zamanlayıcıları sıfırlayarak yeni oyun başlatır."""
        self.is_stockfish_thinking = False
        self.board = chess.Board()
        self.moves = []
        self.legal_moves = []
        self.move_log["text"] = ""
        self.is_resume = True

        time_val = self.time_var.get()
        if time_val == "1+0":
            self.white_time = 60
            self.black_time = 60
            self.time_plus = 0
        elif time_val == "3+2":
            self.white_time = 180
            self.black_time = 180
            self.time_plus = 2
        elif time_val == "10+0":
            self.white_time = 600
            self.black_time = 600
            self.time_plus = 0

        self.update_time_display()
        self.redraw()

        if self.game_mode == "Stockfish" and self.board.turn != self.player_side:
            self.root.after(500, self.stockfish_turn)

    def update_time_display(self) -> None:
        """Zamanlayıcı etiketlerini günceller."""
        w_str = f"{self.white_time // 60}:{self.white_time % 60:0>2}"
        b_str = f"{self.black_time // 60}:{self.black_time % 60:0>2}"
        if self.player_side:
            self.w_time["text"] = w_str
            self.b_time["text"] = b_str
        else:
            self.w_time["text"] = b_str
            self.b_time["text"] = w_str

    def time_update(self) -> None:
        """Saniyede bir çalışarak sırası gelen tarafın süresini düşürür."""
        if self.is_resume:
            if self.board.turn == chess.WHITE:
                self.white_time -= 1
                if self.white_time <= 0:
                    self.handle_timeout("Siyah")
            else:
                self.black_time -= 1
                if self.black_time <= 0:
                    self.handle_timeout("Beyaz")

            self.update_time_display()

        if self.white_time > 0 and self.black_time > 0:
            self.after_time_id = self.root.after(1000, self.time_update)

    def handle_timeout(self, winner: str) -> None:
        """Süre bittiğinde mesaj gösterir."""
        self.is_resume = False
        result = messagebox.askretrycancel(
            "Süre Bitti!",
            f"{winner} kazandı. Yeniden başlatmak ister misiniz?",
        )
        if result:
            self.restart()
        elif self.after_time_id:
            try:
                self.root.after_cancel(self.after_time_id)
            except (tk.TclError, RuntimeError):
                pass
            self.after_time_id = None

    def draw_board(self) -> None:
        """Satranç tahtası karelerini ve koordinat yazılarını çizer."""
        coords: list[tuple[int, int]] = []
        if self.moves:
            last_move = self.moves[-1]
            for sq in (last_move.from_square, last_move.to_square):
                f = chess.square_file(sq)
                r = chess.square_rank(sq)
                col = f if self.player_side else 7 - f
                row = 7 - r if self.player_side else r
                coords.append((row, col))

        for row in range(ROWS):
            for col in range(COLS):
                color = WCOLOR if (row + col) % 2 == 0 else BCOLOR
                if (row, col) in coords:
                    color = MWHITE if (row + col) % 2 == 0 else MBLACK
                self.chessboard.create_rectangle(
                    col * SQSIZE,
                    row * SQSIZE,
                    (col + 1) * SQSIZE,
                    (row + 1) * SQSIZE,
                    fill=color,
                    width=0,
                    tags="rect",
                )

        alphabet_list = ALPHABET if self.player_side else ALPHABET[::-1]
        for i, file_letter in enumerate(alphabet_list):
            i_color = BCOLOR if i % 2 == 0 else WCOLOR
            a_color = WCOLOR if i % 2 == 0 else BCOLOR
            rank_number = str(8 - i) if self.player_side else str(i + 1)

            self.chessboard.create_text(
                SQSIZE // 6,
                i * SQSIZE + SQSIZE // 6,
                text=rank_number,
                fill=i_color,
                font=("Calibri", SQSIZE // 6),
                tags="text",
            )
            self.chessboard.create_text(
                (i + 1) * SQSIZE - SQSIZE // 6,
                HEIGHT - SQSIZE // 6,
                text=file_letter,
                fill=a_color,
                font=("Calibri", SQSIZE // 6),
                tags="text",
            )

    def draw_pieces(self) -> None:
        """Taşları doğrudan python-chess tahta modelinden okuyarak çizer (Model Birleştirme)."""
        for row in range(ROWS):
            for col in range(COLS):
                sq = (
                    chess.square(col, 7 - row)
                    if self.player_side
                    else chess.square(7 - col, row)
                )
                piece = self.board.piece_at(sq)
                if piece is not None:
                    piece_type = PIECE_TYPE_NAMES[piece.piece_type]
                    color_name = (
                        "white" if piece.color == chess.WHITE else "black"
                    )
                    img = self.re_images.get(f"{piece_type}_{color_name}")
                    if img:
                        self.chessboard.create_image(
                            col * SQSIZE,
                            row * SQSIZE,
                            image=img,
                            anchor=tk.NW,
                            tags=piece_type,
                        )

    def draw_legal_moves(self) -> None:
        """Seçili taş için hedef yasal hamle noktalarını çizer."""
        size = SQSIZE // 3
        for move in self.legal_moves:
            target_sq = move.to_square
            target_file = chess.square_file(target_sq)
            target_rank = chess.square_rank(target_sq)

            col = target_file if self.player_side else 7 - target_file
            row = 7 - target_rank if self.player_side else target_rank

            x = col * SQSIZE + SQSIZE // 2
            y = row * SQSIZE + SQSIZE // 2
            self.chessboard.create_oval(
                x - size // 2,
                y - size // 2,
                x + size // 2,
                y + size // 2,
                fill=HCOLOR,
                width=0,
                tags="circle",
            )

    def redraw(self) -> None:
        """Tahtayı ve taşları baştan temizleyip çizer."""
        self.chessboard.delete("all")
        self.draw_board()
        self.draw_pieces()

    def on_drag(self, e: tk.Event) -> None:
        """Sürüklenen taşı fare imlecini ortalayarak hareket ettirir."""
        if self.closest is not None:
            self.chessboard.moveto(
                self.closest, x=e.x - SQSIZE // 2, y=e.y - SQSIZE // 2
            )
            self.chessboard.tag_bind(
                self.closest, "<ButtonRelease-1>", self.on_release
            )
            self.chessboard.tag_raise(self.closest)

    def on_click(self, e: tk.Event) -> None:
        """Kullanıcının tahtaya tıklama olayını yönetir."""
        if not self.is_resume:
            return
        if (
            self.game_mode == "Stockfish"
            and self.board.turn != self.player_side
        ):
            return

        items = self.chessboard.find_closest(e.x, e.y)
        if not items:
            return
        self.closest = items[0]
        tags = self.chessboard.gettags(self.closest)
        if not tags or tags[0] in ("rect", "text", "circle"):
            return

        item_coords = self.chessboard.coords(self.closest)
        if not item_coords:
            return

        col = int(item_coords[0] // SQSIZE)
        row = int(item_coords[1] // SQSIZE)
        self.prev_col = col
        self.prev_row = row

        source_sq = (
            chess.square(col, 7 - row)
            if self.player_side
            else chess.square(7 - col, row)
        )
        piece = self.board.piece_at(source_sq)

        if piece is None or piece.color != self.board.turn:
            return

        # Yasal hamleleri tek bir döngüde topla (Mükerrer döngü kaldırıldı)
        self.legal_moves = [
            m for m in self.board.legal_moves if m.from_square == source_sq
        ]

        self.draw_legal_moves()
        self.chessboard.tag_bind(self.closest, "<B1-Motion>", self.on_drag)
        self.chessboard.tag_raise(self.closest)

    def on_release(self, e: tk.Event) -> None:
        """Taş bırakıldığında hamlenin geçerliliğini denetler ve uygular."""
        if (
            self.closest is None
            or self.prev_col is None
            or self.prev_row is None
        ):
            return

        col = int(e.x // SQSIZE)
        row = int(e.y // SQSIZE)

        if 0 <= col < COLS and 0 <= row < ROWS:
            source_sq = (
                chess.square(self.prev_col, 7 - self.prev_row)
                if self.player_side
                else chess.square(7 - self.prev_col, self.prev_row)
            )
            target_sq = (
                chess.square(col, 7 - row)
                if self.player_side
                else chess.square(7 - col, row)
            )

            normal_move = chess.Move(source_sq, target_sq)
            promo_move = chess.Move(source_sq, target_sq, promotion=chess.QUEEN)

            if normal_move in self.board.legal_moves:
                self.execute_player_move(normal_move, col, row)
            elif promo_move in self.board.legal_moves:
                chosen_piece = self.prompt_promotion()
                if chosen_piece is not None:
                    final_move = chess.Move(
                        source_sq, target_sq, promotion=chosen_piece
                    )
                    self.execute_player_move(final_move, col, row)
                else:
                    self.chessboard.moveto(
                        self.closest,
                        self.prev_col * SQSIZE,
                        self.prev_row * SQSIZE,
                    )
            else:
                self.chessboard.moveto(
                    self.closest, self.prev_col * SQSIZE, self.prev_row * SQSIZE
                )
        else:
            self.chessboard.moveto(
                self.closest, self.prev_col * SQSIZE, self.prev_row * SQSIZE
            )

        self.chessboard.tag_unbind(self.closest, "<B1-Motion>")
        self.legal_moves = []
        self.redraw()

    def prompt_promotion(self) -> int | None:
        """Terfi seçimi penceresini açar."""
        popup = Popup(self.root, self.player_side, self.re_images)
        self.root.wait_window(popup)
        choice_map = {
            "q": chess.QUEEN,
            "r": chess.ROOK,
            "b": chess.BISHOP,
            "n": chess.KNIGHT,
        }
        return choice_map.get(popup.choice) if popup.choice else None

    def execute_player_move(
        self, move: chess.Move, col: int, row: int
    ) -> None:
        """Geçerli hamleyi tahtaya ve geçmişe işler."""
        if self.board.turn == chess.WHITE:
            self.white_time += self.time_plus
        else:
            self.black_time += self.time_plus

        self.update_time_display()
        self.board.push(move)
        self.moves.append(move)
        self.move_log["text"] = chess.Board().variation_san(self.moves)

        if self.closest is not None:
            self.chessboard.moveto(self.closest, col * SQSIZE, row * SQSIZE)
            self.chessboard.tag_raise(self.closest)

        self.check_game_status()

    def check_game_status(self) -> None:
        """Mat, pat ve berabere durumlarını denetler."""
        result = None
        self.is_resume = False

        if self.board.is_checkmate():
            result = messagebox.askretrycancel(
                "Şah mat!", "Yeniden başlatmak ister misiniz?"
            )
        elif self.board.is_stalemate():
            result = messagebox.askretrycancel(
                "Pat!", "Yeniden başlatmak ister misiniz?"
            )
        elif self.board.is_variant_draw() or self.board.is_insufficient_material():
            result = messagebox.askretrycancel(
                "Berabere!", "Yeniden başlatmak ister misiniz?"
            )

        self.is_resume = True

        if result is not None:
            if result:
                self.restart()
            else:
                self.is_resume = False
                if self.after_time_id:
                    try:
                        self.root.after_cancel(self.after_time_id)
                    except (tk.TclError, RuntimeError):
                        pass
                    self.after_time_id = None
        elif (
            self.game_mode == "Stockfish"
            and self.board.turn != self.player_side
            and self.is_resume
        ):
            self.root.after(500, self.stockfish_turn)

    def stockfish_turn(self) -> None:
        """Stockfish hamle hesaplamasını arka planda (Worker Thread) başlatır."""
        engine = self.engine
        if not self.is_resume or self.game_mode != "Stockfish" or engine is None:
            return

        if (
            self.board.turn != self.player_side
            and not self.is_stockfish_thinking
            and not self.board.is_game_over()
        ):
            self.is_stockfish_thinking = True
            board_copy = self.board.copy()
            depth_idx = (
                self.elo_list.index(self.elo_var.get())
                if self.elo_var.get() in self.elo_list
                else 0
            )
            current_depth = (
                self.depth_list[depth_idx]
                if depth_idx < len(self.depth_list)
                else 1
            )

            def run_engine() -> None:
                try:
                    res = engine.play(
                        board_copy,
                        chess.engine.Limit(time=1, depth=current_depth),
                    )
                    best_move = res.move
                    self.root.after(
                        0, lambda m=best_move: self.apply_stockfish_move(m)
                    )
                except (
                    chess.engine.EngineError,
                    chess.engine.EngineTerminatedError,
                    OSError,
                ):
                    self.root.after(0, self.handle_stockfish_error)

            threading.Thread(target=run_engine, daemon=True).start()

    def handle_stockfish_error(self) -> None:
        """Motor hesaplama hatası durumunu yönetir."""
        self.is_stockfish_thinking = False

    def apply_stockfish_move(self, move: chess.Move | None) -> None:
        """Motor hamlesini UI thread üzerinde uygular."""
        self.is_stockfish_thinking = False
        if not self.is_resume or move is None or self.game_mode != "Stockfish":
            return

        self.board.push(move)
        self.moves.append(move)
        self.move_log["text"] = chess.Board().variation_san(self.moves)
        self.redraw()
        self.check_game_status()

    def on_resize(self, e: tk.Event) -> None:
        """Pencere boyutu değiştiğinde tahta ve bileşenleri yeniden boyutlandırır."""
        if not isinstance(e.widget, tk.Tk):
            return

        global WIDTH, HEIGHT, SQSIZE
        new_dim = min(int(e.width), int(e.height))
        if new_dim < 200:
            return

        WIDTH = new_dim
        HEIGHT = new_dim
        SQSIZE = WIDTH // ROWS

        self.chessboard.configure(width=WIDTH, height=HEIGHT)
        self.w_time.configure(font=("Calibri", WIDTH // 20, "bold"))
        self.b_time.configure(font=("Calibri", WIDTH // 20, "bold"))
        self.move_log.configure(wraplength=max((e.width - WIDTH) - 30, 100))
        self.title_label.pack_configure(pady=(HEIGHT // 8, 30))

        self.root.rowconfigure(0, minsize=e.height)
        self.root.columnconfigure(0, minsize=e.width)

        self.resize_pieces()
        self.redraw()

    def on_closing(self) -> None:
        """Pencere kapatıldığında tüm kaynakları ve motor süreçlerini temizler."""
        self.is_resume = False
        if self.after_time_id is not None:
            try:
                self.root.after_cancel(self.after_time_id)
            except (tk.TclError, RuntimeError):
                pass
            self.after_time_id = None

        if self.engine is not None:
            try:
                self.engine.quit()
            except (
                chess.engine.EngineError,
                chess.engine.EngineTerminatedError,
                OSError,
            ):
                pass
            try:
                self.engine.close()
            except (
                chess.engine.EngineError,
                chess.engine.EngineTerminatedError,
                OSError,
            ):
                pass
            self.engine = None

        try:
            self.root.destroy()
        except (tk.TclError, RuntimeError):
            pass

    def run(self) -> None:
        """Uygulama döngüsünü başlatır."""
        try:
            self.root.mainloop()
        finally:
            self.on_closing()


def start_game() -> None:
    app = ChessApp()
    app.run()


def main() -> None:
    start_game()


if __name__ == "__main__":
    main()
