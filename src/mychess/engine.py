"""Stockfish: motoru bulma, zorluk ayarı, düşünme süresi ve arka planda arama."""

import concurrent.futures
import logging
import os
import queue
import random
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import chess
import chess.engine

logger = logging.getLogger(__name__)

ENGINE_ENV_VAR: str = "MYCHESS_STOCKFISH"
WINDOWS_ENGINE: Path = Path(
    "engines/stockfish_15.1_win_x64_avx2/stockfish-windows-2022-x86-64-avx2.exe"
)
BUNDLED_ENGINE: Path = Path("engines/stockfish")
# Finder'dan açılan .app kullanıcının PATH'ini görmez; Homebrew dizinlerine ayrıca bakılır.
SYSTEM_ENGINE_DIRS: tuple[Path, ...] = (
    Path("/opt/homebrew/bin"),
    Path("/usr/local/bin"),
    Path("/usr/games"),
)

# Motor komutlarının (başlatma, ping, ayar, kapatma) yanıt bekleme süresi (saniye).
# Bu çağrılar ana thread'de yapılır; takılan bir motor arayüzü en fazla bu kadar
# dondurur. play() için python-chess bu süreyi düşünme süresine ekler.
ENGINE_TIMEOUT: float = 3.0

# EngineTerminatedError EngineError'ın, TimeoutError/FileNotFoundError OSError'ın alt sınıfı.
ENGINE_ERRORS: tuple[type[Exception], ...] = (chess.engine.EngineError, OSError)


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def _bundled_engine_candidates(rel: Path) -> list[Path]:
    """Paketle gelen motor için olası konumları döndürür (PyInstaller ve geliştirme)."""
    candidates: list[Path] = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / rel)
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / rel)
    package_dir = Path(__file__).resolve().parent
    candidates.append(package_dir.parent.parent / rel)
    candidates.append(package_dir / rel)
    return candidates


def get_engine_path() -> Path | None:
    """Stockfish çalıştırılabilir dosyasını bulur; bulunamazsa None döner.

    Arama sırası: MYCHESS_STOCKFISH ortam değişkeni, paketle gelen motor
    (Windows'ta engines/ altındaki .exe, diğer platformlarda engines/stockfish),
    PATH üzerindeki `stockfish`, son olarak Homebrew/Linux varsayılan dizinleri.
    """
    env_path = os.environ.get(ENGINE_ENV_VAR)
    if env_path:
        candidate = Path(env_path).expanduser()
        if _is_executable(candidate):
            return candidate

    rel = WINDOWS_ENGINE if sys.platform == "win32" else BUNDLED_ENGINE
    for candidate in _bundled_engine_candidates(rel):
        if _is_executable(candidate):
            return candidate

    found = shutil.which("stockfish")
    if found:
        return Path(found)

    for directory in SYSTEM_ENGINE_DIRS:
        candidate = directory / "stockfish"
        if _is_executable(candidate):
            return candidate
    return None


@dataclass(frozen=True)
class EngineSettings:
    """Seçilen zorluk için motor seçenekleri ve arama sınırı."""

    options: dict[str, int | bool]
    depth: int | None


# Motorun UCI_Elo alt sınırının altındaki seviyeler: (ELO, Skill Level, derinlik)
LOW_ELO_LEVELS: tuple[tuple[int, int, int], ...] = (
    (400, 0, 1),
    (800, 0, 2),
    (1000, 1, 4),
    (1300, 3, 6),
)


def engine_settings(elo: int, elo_range: tuple[int, int] | None) -> EngineSettings:
    """ELO seçimini Stockfish ayarlarına çevirir.

    Motorun UCI_Elo aralığına giren değerlerde gerçek ELO sınırlaması
    (UCI_LimitStrength) kullanılır. Aralığın altındaki değerlerde
    (Stockfish 15.1'de 1350, 19'da 1320) yaklaşık güç, Skill Level ve
    arama derinliği kısıtlanarak elde edilir.
    """
    if elo_range is not None and elo >= elo_range[0]:
        return EngineSettings(
            options={
                "UCI_LimitStrength": True,
                "UCI_Elo": min(elo, elo_range[1]),
                "Skill Level": 20,
            },
            depth=None,
        )

    _, skill, depth = LOW_ELO_LEVELS[0]
    for level_elo, level_skill, level_depth in LOW_ELO_LEVELS:
        if elo >= level_elo:
            skill, depth = level_skill, level_depth
    return EngineSettings(
        options={"UCI_LimitStrength": False, "Skill Level": skill},
        depth=depth,
    )


# Motorun hamle başına düşünme süresi sınırları (saniye)
MIN_THINK_TIME: float = 0.3
MAX_THINK_TIME: float = 8.0
OPENING_MOVES: int = 5


def engine_think_time(
    remaining: float, increment: float, move_number: int, jitter: float = 1.0
) -> float:
    """Motorun bu hamlede harcayacağı süreyi saate göre belirler.

    Kalan sürenin ~1/60'ı ve artışın yarısı kadar düşünür; açılışta daha
    hızlı oynar. `jitter` (ör. 0.5–1.5) süreyi doğal göstermek için çarpan.
    Süre saatle birlikte azaldığı için uzun oyunlarda motor da süreden
    kaybedebilir.
    """
    think = remaining / 60 + increment / 2
    if move_number <= OPENING_MOVES:
        think *= 0.4
    think *= jitter
    return min(MAX_THINK_TIME, max(MIN_THINK_TIME, think))


class UciEngine(Protocol):
    """Uygulamanın kullandığı SimpleEngine arayüzü (testlerde sahtesi verilir)."""

    @property
    def id(self) -> Mapping[str, str]: ...

    @property
    def options(self) -> Mapping[str, chess.engine.Option]: ...

    def ping(self) -> None: ...

    def configure(self, options: chess.engine.ConfigMapping) -> None: ...

    def play(
        self, board: chess.Board, limit: chess.engine.Limit
    ) -> chess.engine.PlayResult: ...

    def quit(self) -> None: ...

    def close(self) -> None: ...


class EngineController:
    """Stockfish sürecini yönetir: başlatma, yoklama, zorluk ayarı, arka planda arama.

    Tk'ye hiç dokunmaz. `search()` hamleyi ayrı bir thread'de hesaplar ve
    sonucu `(oyun kimliği, hamle)` olarak kuyruğa koyar; ana thread `poll()`
    ile okur. Hamle None ise motor hata vermiştir (ya da arama iptal edilmiştir).
    """

    def __init__(self) -> None:
        self.client: UciEngine | None = None
        self.path: Path | None = None
        self.settings: EngineSettings = engine_settings(1300, None)
        self._results: queue.Queue[tuple[int, chess.Move | None]] = queue.Queue()
        self._starter: threading.Thread | None = None

    def start_in_background(self) -> None:
        """Motoru ayrı bir thread'de başlatır; pencere motoru beklemeden açılır.

        Motoru kullanan ilk çağrı (`ensure`, `shutdown`) başlatmanın bitmesini bekler.
        """
        self._starter = threading.Thread(
            target=self.start, name="stockfish-start", daemon=True
        )
        self._starter.start()

    def _wait_for_start(self) -> None:
        starter, self._starter = self._starter, None
        if starter is not None:
            starter.join()

    def start(self) -> None:
        """Motoru bulup başlatır; başaramazsa `client` None kalır."""
        self.path = get_engine_path()
        if self.path is None:
            logger.warning("Stockfish bulunamadı; yalnızca iki kişilik mod çalışır")
            return
        try:
            if sys.platform == "win32":
                self.client = chess.engine.SimpleEngine.popen_uci(
                    str(self.path),
                    timeout=ENGINE_TIMEOUT,
                    startupinfo=subprocess.STARTUPINFO(
                        dwFlags=subprocess.STARTF_USESHOWWINDOW
                    ),
                )
            else:
                self.client = chess.engine.SimpleEngine.popen_uci(
                    str(self.path), timeout=ENGINE_TIMEOUT
                )
        except ENGINE_ERRORS:
            logger.warning("Stockfish başlatılamadı: %s", self.path, exc_info=True)
            self.client = None
        else:
            logger.info(
                "Stockfish başlatıldı: %s (%s)",
                self.path,
                self.client.id.get("name", "?"),
            )

    def shutdown(self) -> None:
        """Motor sürecini kapatır; ölmüş bir motorda da güvenle çağrılabilir."""
        self._wait_for_start()
        client = self.client
        self.client = None
        if client is None:
            return
        try:
            client.quit()
        except ENGINE_ERRORS:
            logger.debug("Motora quit gönderilemedi", exc_info=True)
        try:
            client.close()
        except ENGINE_ERRORS:
            logger.debug("Motor kapatılamadı", exc_info=True)

    def ensure(self) -> bool:
        """Motor yanıt veriyorsa True döner; ölmüşse yeniden başlatmayı dener."""
        self._wait_for_start()
        if self.client is not None:
            try:
                self.client.ping()
                return True
            except ENGINE_ERRORS:
                logger.warning(
                    "Stockfish yanıt vermiyor; yeniden başlatılıyor", exc_info=True
                )
                self.shutdown()
        self.start()
        return self.client is not None

    def configure(self, elo: int) -> bool:
        """ELO'yu motor ayarlarına uygular; başarıyı döndürür."""
        client = self.client
        if client is None:
            return False
        try:
            elo_option = client.options.get("UCI_Elo")
            elo_range = (
                (int(elo_option.min), int(elo_option.max))
                if elo_option is not None
                and elo_option.min is not None
                and elo_option.max is not None
                else None
            )
            self.settings = engine_settings(elo, elo_range)
            options = {
                name: value
                for name, value in self.settings.options.items()
                if name in client.options
            }
            client.configure(options)
        except ENGINE_ERRORS:
            logger.warning("Stockfish ayarlanamadı (ELO %s)", elo, exc_info=True)
            return False
        logger.info("Stockfish ayarları: %s", self.settings)
        return True

    def search(
        self, board: chess.Board, game_id: int, remaining: float, increment: float
    ) -> bool:
        """Hamle aramasını arka planda başlatır; motor yoksa False döner."""
        client = self.client
        if client is None:
            return False

        board_copy = board.copy()
        think_time = engine_think_time(
            remaining,
            increment,
            board.fullmove_number,
            jitter=random.uniform(0.5, 1.5),
        )
        limit = chess.engine.Limit(time=think_time, depth=self.settings.depth)

        def run() -> None:
            # Sonuç `finally` içinde gönderilir: beklenmeyen bir hatada bile ana
            # thread "düşünüyor" durumunda takılı kalmaz (None = motor hatası).
            started = time.monotonic()
            move: chess.Move | None = None
            try:
                move = client.play(board_copy, limit).move
                # Derinlik sınırlı arama erken biterse süre dolana kadar "düşünür".
                time.sleep(max(0.0, think_time - (time.monotonic() - started)))
            except concurrent.futures.CancelledError:
                # Yeni komut gelince python-chess süren aramayı iptal eder.
                logger.debug("Motor araması iptal edildi (oyun %s)", game_id)
            except ENGINE_ERRORS:
                logger.warning("Motor hamle üretemedi", exc_info=True)
            finally:
                self._results.put((game_id, move))

        threading.Thread(target=run, name="stockfish-search", daemon=True).start()
        return True

    def poll(self) -> list[tuple[int, chess.Move | None]]:
        """Biriken arama sonuçlarını döndürür (ana thread'den çağrılır)."""
        results: list[tuple[int, chess.Move | None]] = []
        while True:
            try:
                results.append(self._results.get_nowait())
            except queue.Empty:
                return results
