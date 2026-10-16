import gc
import tkinter as tk
from collections.abc import Iterator

import pytest
from fakes import FakeTime


@pytest.fixture(autouse=True)
def collect_tk_garbage() -> Iterator[None]:
    """Her testten sonra çöpü ana thread'de toplar.

    Kapatılmış uygulamaların Tk nesneleri (ör. StringVar) aksi halde GC'nin
    tesadüfen çalıştığı başka bir thread'de (python-chess'in motor thread'i)
    temizlenir; `Variable.__del__` Tcl'i ana thread'den bekler, ana thread de
    o sırada motoru beklediği için test kilitlenir.
    """
    yield
    gc.collect()


@pytest.fixture
def fake_time() -> FakeTime:
    return FakeTime()


@pytest.fixture
def tk_root() -> Iterator[tk.Tk]:
    """Gizli bir Tk kök penceresi; ekran yoksa (ör. CI'da xvfb'siz) test atlanır."""
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk ekranı yok")
    root.withdraw()
    yield root
    root.destroy()
