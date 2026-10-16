"""Küçük arayüz parçaları: terfi penceresi ve Windows koyu başlık çubuğu."""

import ctypes as ct
import logging
import sys
import tkinter as tk
from functools import partial
from tkinter import ttk

import chess
from PIL import ImageTk

logger = logging.getLogger(__name__)


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
        logger.debug("Koyu başlık çubuğu uygulanamadı", exc_info=True)


# (görsel adı, UCI harfi, görsel yoksa düğme metni)
PROMOTION_CHOICES: tuple[tuple[str, str, str], ...] = (
    ("queen", "q", "Vezir"),
    ("rook", "r", "Kale"),
    ("bishop", "b", "Fil"),
    ("knight", "n", "At"),
)


class Popup(tk.Toplevel):
    """Piyon terfisi (pawn promotion) için seçim penceresi."""

    def __init__(
        self,
        parent: tk.Tk,
        piece_color: chess.Color,
        images: dict[str, ImageTk.PhotoImage],
    ) -> None:
        super().__init__(parent)
        self.title("Terfi")
        self.resizable(False, False)
        self.choice: str | None = None
        color = "white" if piece_color == chess.WHITE else "black"

        # pack(side=RIGHT) sırayı ters çevirir: soldan sağa at, fil, kale, vezir.
        for name, char, label in PROMOTION_CHOICES:
            command = partial(self.select, char)
            image = images.get(f"{name}_{color}")
            if image is not None:
                button = ttk.Button(self, image=image, command=command)
            else:
                # Görsel eksikse (yüklenemediyse) terfi yine de yapılabilsin.
                button = ttk.Button(self, text=label, command=command)
            button.pack(side=tk.RIGHT)

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
