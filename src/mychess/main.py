import logging
import sys
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk
from types import TracebackType

import chess

from .board_view import BoardView
from .clock import format_clock
from .const import HEIGHT, WIDTH
from .engine import ENGINE_ENV_VAR, EngineController
from .game import COLOR_NAMES, TIME_CONTROLS, Game, GameMode, MoveRecord
from .logging_config import log_hint, setup_logging
from .resources import get_resource_path
from .widgets import Popup, dark_title_bar

logger = logging.getLogger(__name__)

ENGINE_POLL_MS: int = 50
# Saat gerçek zamanla ölçülür; bu yalnızca ekranın ve süre bitiminin kontrol sıklığı.
CLOCK_TICK_MS: int = 100
# Motor hamle üretemezse oyun durdurulmadan önce kaç kez yeniden başlatılır.
MAX_ENGINE_RESTARTS: int = 1
# Pencere küçültülünce tahta en fazla buraya kadar küçülür (kare 50 px).
MIN_BOARD_SIZE: int = 400
# Saat yazısı tahtayla büyür; çok büyüyüp yan paneli genişletmesin diye üst sınır.
MAX_CLOCK_FONT: int = 32
MOVE_LOG_ROWS: int = 6


def clock_font_size(board_size: int) -> int:
    """Saat yazısı tahtayla büyür ama `MAX_CLOCK_FONT`'u aşmaz."""
    return min(board_size // 20, MAX_CLOCK_FONT)
ELO_CHOICES: list[str] = ["400", "800", "1000", "1300", "1600", "2000", "2400", "2850"]
DEFAULT_ELO: int = 1300
# Menüde gösterilen taraf adı -> oyuncunun rengi
SIDE_CHOICES: dict[str, chess.Color] = {"Beyaz": chess.WHITE, "Siyah": chess.BLACK}


class ChessApp:
    """Uygulama penceresi: menü, kenar çubuğu ve oyun akışı.

    Oyun kuralları ve saat `Game`'de, tahta çizimi ve fare girişi
    `BoardView`'da, Stockfish süreci `EngineController`'da; bu sınıf onları
    birbirine bağlar ve kullanıcıya gösterir.
    """

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Chess by Yusuf")
        self.load_theme()
        dark_title_bar(self.root)
        self.root.report_callback_exception = self.on_callback_error
        self.callback_error_shown: bool = False

        # Menüde gösterilen oyun dışı "boş" oyun; her yeni oyun yeni kimlik alır.
        self.last_game_id: int = 0
        self.game = Game(self.last_game_id)
        self.is_stockfish_thinking: bool = False
        self.engine_restarts: int = 0
        self.engine = EngineController()

        self.mode_list = [mode.value for mode in GameMode]
        self.time_list = list(TIME_CONTROLS)
        self.elo_list = ELO_CHOICES
        self.side_list = list(SIDE_CHOICES)
        self.mode_var = tk.StringVar(value=self.mode_list[0])
        self.time_var = tk.StringVar(value=self.time_list[0])
        self.elo_var = tk.StringVar(value=str(DEFAULT_ELO))
        self.side_var = tk.StringVar(value=self.side_list[0])

        self.engine.start_in_background()
        self.setup_ui()
        self.fit_window()
        self.board_view.show(self.game.board, white_bottom=True)

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after_time_id: str | None = self.root.after(
            CLOCK_TICK_MS, self.time_update
        )
        self.after_poll_id: str | None = self.root.after(
            ENGINE_POLL_MS, self.poll_engine
        )

    def load_theme(self) -> None:
        """Forest (koyu) ttk temasını yükler; olmazsa varsayılan temayla devam eder."""
        theme_path = get_resource_path("ForestTheme/forest-dark.tcl")
        if not theme_path.exists():
            logger.warning("Tema dosyası bulunamadı: %s", theme_path)
            return
        try:
            self.root.tk.call("source", str(theme_path))
            ttk.Style().theme_use("forest-dark")
        except tk.TclError:
            logger.warning("Tema yüklenemedi: %s", theme_path, exc_info=True)

    def on_callback_error(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: TracebackType | None,
    ) -> None:
        """Tk geri çağrısında yakalanmayan hatayı loglar; kullanıcıya bir kez bildirir."""
        logger.error(
            "Arayüz geri çağrısında yakalanmayan hata",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        if self.callback_error_shown:
            return
        self.callback_error_shown = True
        messagebox.showerror(
            "Beklenmeyen Hata",
            "Beklenmeyen bir hata oluştu; uygulama çalışmaya devam etmeye "
            "çalışacak." + log_hint(),
        )

    def setup_ui(self) -> None:
        """Tüm arayüz bileşenlerini ve düzeni oluşturur."""
        # Menü ve oyun ekranı aynı hücrede üst üste; hücre pencereyle esner.
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        # 1. Ana Menü Ekranı (main_frame): içerik pencerenin ortasında
        self.main_frame = tk.Frame(self.root)
        self.main_frame.grid(row=0, column=0, sticky="news")
        self.menu_box = menu_box = tk.Frame(self.main_frame)
        menu_box.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(menu_box, text="Satranç", font=("", 30, "bold")).pack(pady=(20, 20))

        for label, var, choices in (
            ("Mod:", self.mode_var, self.mode_list),
            ("Süre:", self.time_var, self.time_list),
            ("Seviye (ELO):", self.elo_var, self.elo_list),
            ("Taraf:", self.side_var, self.side_list),
        ):
            row = tk.Frame(menu_box)
            row.pack(pady=10)
            tk.Label(row, text=label).pack(side=tk.LEFT, padx=5)
            ttk.OptionMenu(row, var, var.get(), *choices).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            menu_box,
            text="Oyna",
            style="Accent.TButton",
            command=self.play,
        ).pack(pady=(40, 20))

        # 2. Oyun Ekranı (game_frame)
        self.game_frame = tk.Frame(self.root)
        self.game_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.tkraise()

        self.board_view = BoardView(
            self.game_frame,
            WIDTH,
            get_resource_path("assets") / "images" / "imgs-128px",
            can_interact=lambda: self.game.can_player_move,
            on_move=self.try_move,
        )
        self.board_view.canvas.pack(anchor="center", side=tk.LEFT)

        self.sidebar_frame = sidebar_frame = tk.Frame(self.game_frame)
        sidebar_frame.pack(side=tk.RIGHT, fill="both", expand=True)

        # Üst saat rakibin, alt saat oyuncunun (alttaki tarafın) süresidir.
        top_frame = tk.Frame(sidebar_frame)
        top_frame.pack(side=tk.TOP, fill="x")
        self.top_clock = self.make_clock_label(top_frame)

        bottom_frame = tk.Frame(sidebar_frame)
        bottom_frame.pack(side=tk.BOTTOM, fill="x")
        self.bottom_clock = self.make_clock_label(bottom_frame)

        controls_frame = tk.Frame(sidebar_frame)
        controls_frame.pack(side=tk.BOTTOM, fill="x", pady=8)
        ttk.Button(
            controls_frame, text="Yeni Oyun", command=self.on_new_game
        ).pack(side=tk.LEFT, padx=(0, 4), expand=True, fill="x")
        ttk.Button(
            controls_frame, text="Ana Menü", command=self.on_menu
        ).pack(side=tk.LEFT, padx=(4, 8), expand=True, fill="x")

        self.status_label = tk.Label(
            sidebar_frame, text="", anchor=tk.W, justify=tk.LEFT
        )
        self.status_label.pack(side=tk.TOP, fill="x", pady=(8, 4))

        # Hamle Kaydı: hamle numarası başına bir satır, kaydırılabilir
        log_frame = tk.Frame(sidebar_frame)
        log_frame.pack(side=tk.TOP, expand=True, fill="both", padx=(0, 8))
        self.move_log = ttk.Treeview(
            log_frame,
            columns=("no", "white", "black"),
            show="headings",
            selectmode="none",
            height=MOVE_LOG_ROWS,
        )
        self.move_log.heading("no", text="#")
        self.move_log.heading("white", text="Beyaz")
        self.move_log.heading("black", text="Siyah")
        self.move_log.column("no", width=36, minwidth=30, stretch=False, anchor=tk.E)
        self.move_log.column("white", width=70, minwidth=50)
        self.move_log.column("black", width=70, minwidth=50)
        log_scroll = ttk.Scrollbar(
            log_frame, orient=tk.VERTICAL, command=self.move_log.yview
        )
        self.move_log.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side=tk.RIGHT, fill="y")
        self.move_log.pack(side=tk.LEFT, expand=True, fill="both")

        self.root.bind("<Configure>", self.on_resize)

    def make_clock_label(self, parent: tk.Misc) -> tk.Label:
        # En uzun süre metniyle başlar ki yan panel genişliği doğru ölçülsün.
        longest = max(initial for initial, _ in TIME_CONTROLS.values())
        label = tk.Label(
            parent,
            text=format_clock(longest),
            bg="black",
            fg="white",
            font=("Calibri", clock_font_size(self.board_view.size), "bold"),
        )
        label.pack(side=tk.LEFT)
        return label

    def fit_window(self) -> None:
        """Pencerenin ilk ve en küçük boyutunu yan panelin gerçek ihtiyacına göre ayarlar.

        Yan panelin genişliği temaya ve yazı tipine bağlıdır; sabit bir değer
        varsaymak küçük pencerede sağ tarafı kırpıyordu. En küçük pencerede
        tahta `MIN_BOARD_SIZE` olur ve yan panel ile menü tam sığar.
        """
        self.root.update_idletasks()
        sidebar_width = self.sidebar_frame.winfo_reqwidth()
        min_height = max(
            MIN_BOARD_SIZE,
            self.sidebar_frame.winfo_reqheight(),
            self.menu_box.winfo_reqheight(),
        )
        min_width = max(
            MIN_BOARD_SIZE + sidebar_width, self.menu_box.winfo_reqwidth()
        )
        self.root.minsize(min_width, min_height)
        self.root.geometry(f"{WIDTH + sidebar_width}x{max(HEIGHT, min_height)}")

    def board_size_for(self, width: int, height: int) -> int:
        """Pencere boyutunda, yan panele yer bırakarak sığan en büyük tahta."""
        available = width - self.sidebar_frame.winfo_reqwidth()
        return max(MIN_BOARD_SIZE, min(available, height))

    def selected_elo(self) -> int:
        try:
            return int(self.elo_var.get())
        except ValueError:
            return DEFAULT_ELO

    def play(self) -> None:
        """Menüdeki ayarlarla oyunu başlatır; Stockfish modunda motoru hazırlar."""
        mode = GameMode(self.mode_var.get())
        if mode is GameMode.STOCKFISH and not (
            self.engine.ensure() and self.engine.configure(self.selected_elo())
        ):
            messagebox.showerror(
                "Motor Hatası",
                "Stockfish bulunamadı ya da başlatılamadı.\n\n"
                "macOS'ta `brew install stockfish` ile kurabilir veya "
                f"{ENGINE_ENV_VAR} ortam değişkeniyle motorun yolunu "
                "belirtebilirsiniz. Bu arada iki kişilik modda "
                "oynayabilirsiniz." + log_hint(),
            )
            return

        self.game_frame.tkraise()
        self.restart()

    def new_game_id(self) -> int:
        self.last_game_id += 1
        return self.last_game_id

    def restart(self) -> None:
        """Menüdeki ayarlarla tahtayı ve saati sıfırlayıp yeni oyun başlatır."""
        self.game.stop()
        self.game = Game(
            self.new_game_id(),
            mode=GameMode(self.mode_var.get()),
            player_side=SIDE_CHOICES.get(self.side_var.get(), chess.WHITE),
            time_control=self.time_var.get(),
        )
        self.is_stockfish_thinking = False
        self.engine_restarts = 0
        self.move_log.delete(*self.move_log.get_children())
        logger.info(
            "Yeni oyun: mod=%s süre=%s taraf=%s ELO=%s",
            self.game.mode,
            self.time_var.get(),
            self.side_var.get(),
            self.selected_elo() if self.game.mode is GameMode.STOCKFISH else "-",
        )

        self.game.start()
        self.board_view.show(self.game.board, self.game.player_side)
        self.update_time_display()
        self.update_status()

        if self.game.is_engine_turn:
            self.root.after(500, self.stockfish_turn)

    def confirm_abandon(self, title: str, question: str) -> bool:
        """Süren oyun varsa bırakmak için onay ister; soru açıkken saat durur."""
        if not self.game.in_progress:
            return True
        clock = self.game.clock
        running = clock.running
        clock.stop()
        confirmed = messagebox.askyesno(title, question)
        if not confirmed and running is not None:
            clock.start(running)
        return confirmed

    def on_new_game(self) -> None:
        """Aynı ayarlarla yeni oyun başlatır; süren oyun varsa onay ister."""
        if not self.confirm_abandon(
            "Yeni Oyun", "Oyun devam ediyor. Yeni oyun başlatılsın mı?"
        ):
            return
        # play() motoru da yoklar; ölmüşse yeniden başlatır.
        self.play()

    def on_menu(self) -> None:
        """Ana menüye döner; süren oyun varsa onay ister."""
        if not self.confirm_abandon(
            "Ana Menü", "Oyun devam ediyor. Oyunu bırakıp menüye dönülsün mü?"
        ):
            return
        self.game.stop()
        # Yeni kimlik: eski oyuna ait motor sonuçları ve bekleyen uyarılar atılır.
        self.game = Game(self.new_game_id())
        self.is_stockfish_thinking = False
        self.board_view.clear_selection()
        self.main_frame.tkraise()

    def update_time_display(self) -> None:
        """Saat etiketlerini günceller; oyuncunun tarafı altta gösterilir."""
        clock = self.game.clock
        side = self.game.player_side
        self.bottom_clock["text"] = format_clock(clock.time_left(side))
        self.top_clock["text"] = format_clock(clock.time_left(not side))

    def update_status(self) -> None:
        """Sıranın kimde olduğunu ve motorun durumunu gösterir."""
        if self.is_stockfish_thinking:
            text = "Stockfish düşünüyor…"
        else:
            board = self.game.board
            text = f"Sıra: {COLOR_NAMES[board.turn]}"
            if board.is_check():
                text += " (Şah!)"
        self.status_label["text"] = text

    def time_update(self) -> None:
        """Saat ekranını yeniler ve süre bitimini yakalar.

        Süreyi kendisi düşmez; GameClock gerçek zamanla ölçer. Bu döngü
        gecikse bile (ör. macOS arka planda yavaşlatınca) hesap doğru kalır.
        """
        self.after_time_id = self.root.after(CLOCK_TICK_MS, self.time_update)
        if not self.game.running:
            return
        self.update_time_display()
        if self.game.check_flag():
            self.show_game_over()

    def show_game_over(self) -> None:
        """Bitmiş oyunun sonucunu gösterir; tahta görünür kalır."""
        game = self.game
        message = game.result or "Oyun bitti."
        self.is_stockfish_thinking = False
        self.board_view.clear_selection()
        self.board_view.redraw()
        self.update_time_display()
        self.status_label["text"] = message
        logger.info(
            "Oyun bitti: %s | hamleler: %s",
            message,
            " ".join(move.uci() for move in game.board.move_stack),
        )
        self.show_dialog_later(messagebox.showinfo, "Oyun Bitti", message)

    def show_dialog_later(
        self, show: Callable[[str, str], object], title: str, message: str
    ) -> None:
        """Uyarıyı, olay döngüsü ekranı çizdikten sonra açar.

        macOS'ta yerel uyarı penceresi açıkken Tk ekranı boyamaz; son hamle ve
        durum metni görünsün diye uyarı ertelenir. Bu arada yeni oyun
        başladıysa uyarı hiç açılmaz.
        """
        game = self.game

        def show_now() -> None:
            if game is self.game:
                show(title, message)

        self.root.after(100, show_now)

    def try_move(self, source: chess.Square, target: chess.Square) -> None:
        """Kullanıcının hamlesini oynar; gerekirse terfi taşını sorar."""
        game = self.game
        candidates = [
            m
            for m in game.board.legal_moves
            if m.from_square == source and m.to_square == target
        ]
        if not candidates:
            return
        move = candidates[0]

        if move.promotion is not None:
            promotion = self.prompt_promotion()
            # Terfi penceresi açıkken süre bitmiş ya da oyun değişmiş olabilir.
            if game is not self.game or not game.running:
                return
            if promotion is None:
                self.board_view.clear_selection()
                self.board_view.redraw()
                return
            move = chess.Move(source, target, promotion=promotion)

        self.push_move(move)

    def prompt_promotion(self) -> chess.PieceType | None:
        """Terfi seçimi penceresini açar."""
        # İki kişilik modda terfi eden taraf, tahtanın alttaki tarafı olmayabilir.
        popup = Popup(self.root, self.game.board.turn, self.board_view.piece_images)
        self.root.wait_window(popup)
        choice_map = {
            "q": chess.QUEEN,
            "r": chess.ROOK,
            "b": chess.BISHOP,
            "n": chess.KNIGHT,
        }
        return choice_map.get(popup.choice) if popup.choice else None

    def push_move(self, move: chess.Move) -> None:
        """Hamleyi oyuna işler, ekranı günceller ve sırayı sonraki tarafa verir."""
        record = self.game.push(move)
        if record is not None:
            self.append_move_log(record)
            self.board_view.show(self.game.board, self.game.player_side)
            self.update_time_display()
            self.update_status()

        if self.game.result is not None:
            self.show_game_over()
        elif self.game.is_engine_turn:
            self.root.after(300, self.stockfish_turn)

    def append_move_log(self, record: MoveRecord) -> None:
        """Hamleyi kayda ekler: beyaz yeni satır açar, siyah son satırı tamamlar."""
        rows = self.move_log.get_children()
        if record.color == chess.BLACK and rows:
            row = rows[-1]
            self.move_log.set(row, "black", record.san)
        else:
            white = record.san if record.color == chess.WHITE else "…"
            black = "" if record.color == chess.WHITE else record.san
            row = self.move_log.insert(
                "", tk.END, values=(f"{record.number}.", white, black)
            )
        self.move_log.see(row)

    def stockfish_turn(self) -> None:
        """Sıra motordaysa hamle aramasını arka planda başlatır."""
        game = self.game
        if (
            self.is_stockfish_thinking
            or not game.is_engine_turn
            or game.board.is_game_over()
        ):
            return
        if not self.engine.search(
            game.board,
            game.id,
            game.clock.time_left(game.board.turn),
            game.clock.increment,
        ):
            self.handle_engine_failure()
            return
        self.is_stockfish_thinking = True
        self.update_status()

    def poll_engine(self) -> None:
        """Motor sonuçlarını ana thread'de düzenli olarak okur."""
        self.after_poll_id = self.root.after(ENGINE_POLL_MS, self.poll_engine)
        for game_id, move in self.engine.poll():
            self.apply_stockfish_move(game_id, move)

    def apply_stockfish_move(self, game_id: int, move: chess.Move | None) -> None:
        """Motor hamlesini uygular; eski oyunlardan gelenleri atar."""
        if game_id != self.game.id:
            return
        self.is_stockfish_thinking = False
        if not self.game.is_engine_turn:
            # Motor düşünürken süre bitmiş olabilir.
            return
        if move is None or move not in self.game.board.legal_moves:
            if move is not None:
                logger.warning("Motor yasal olmayan hamle döndürdü: %s", move)
            self.handle_engine_failure()
            return
        self.engine_restarts = 0
        self.push_move(move)

    def handle_engine_failure(self) -> None:
        """Motor hamle üretemedi: yeniden başlatıp tekrar dener, olmazsa oyunu durdurur."""
        if self.engine_restarts < MAX_ENGINE_RESTARTS:
            self.engine_restarts += 1
            logger.warning(
                "Stockfish hamle üretemedi; yeniden başlatılıyor (%s/%s)",
                self.engine_restarts,
                MAX_ENGINE_RESTARTS,
            )
            self.engine.shutdown()
            if self.engine.ensure() and self.engine.configure(self.selected_elo()):
                self.status_label["text"] = "Stockfish yeniden başlatıldı…"
                self.root.after(300, self.stockfish_turn)
                return

        logger.error("Stockfish yeniden başlatılamadı; oyun durduruldu")
        self.game.stop()
        self.status_label["text"] = "Stockfish hata verdi; oyun durduruldu."
        self.show_dialog_later(
            messagebox.showerror,
            "Motor Hatası",
            "Stockfish yanıt vermiyor ve yeniden başlatılamadı. Oyun durduruldu.\n\n"
            "'Yeni Oyun' ile tekrar deneyebilir ya da 'Ana Menü'den iki kişilik "
            "moda geçebilirsiniz." + log_hint(),
        )

    def on_resize(self, e: tk.Event) -> None:
        """Pencere boyutu değiştiğinde tahtayı ve saat yazılarını ölçekler."""
        if not isinstance(e.widget, tk.Tk):
            return
        size = self.board_size_for(int(e.width), int(e.height))
        self.board_view.resize(size)
        for label in (self.top_clock, self.bottom_clock):
            label.configure(font=("Calibri", clock_font_size(size), "bold"))

    def on_closing(self) -> None:
        """Pencere kapatıldığında zamanlayıcıları ve motor sürecini temizler."""
        self.game.stop()
        for after_id in (self.after_time_id, self.after_poll_id):
            if after_id is None:
                continue
            try:
                self.root.after_cancel(after_id)
            except (tk.TclError, RuntimeError):
                pass
        self.after_time_id = None
        self.after_poll_id = None
        self.engine.shutdown()

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
    log_path = setup_logging()
    logger.info(
        "mychess başlıyor: Python %s, Tk %s, %s, log: %s",
        sys.version.split()[0],
        tk.TkVersion,
        sys.platform,
        log_path,
    )
    app = ChessApp()
    app.run()


def main() -> None:
    start_game()


if __name__ == "__main__":
    main()
