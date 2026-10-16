# mychess

Tkinter tabanlı masaüstü satranç oyunu. Kurallar ve hamle doğrulama `python-chess` (`chess.Board`) ile, rakip Stockfish (UCI, `chess.engine.SimpleEngine`), arayüz Tkinter + Forest teması, taş görselleri Pillow ile.

## Komutlar

```bash
uv sync --managed-python   # bağımlılıklar (.venv); ilk sefer: uv python install 3.14
uv run mychess             # oyunu başlat (console script → mychess:main)
uv run python -m mychess   # aynısı (src/mychess/__main__.py)
uv run pytest              # testler (Tk testleri ekran ister; yoksa atlanır)
uv run ruff check .        # lint
uv run mypy                # tip denetimi (strict, src + tests; ayar pyproject.toml)
uv run pyinstaller Chess.spec --noconfirm   # paketleme: dist/Chess/ (+ macOS'ta dist/Chess.app)
```

- Python `>=3.14` (`.python-version`). Build backend `uv_build` (src layout).
- CI: `.github/workflows/ci.yml` — ruff + mypy, ve Linux (xvfb) / macOS / Windows'ta pytest; Stockfish kurulur.

## Platform notları

- Proje Windows'ta yazıldı, macOS'ta da çalışıyor. macOS'ta **Homebrew python@3.14'te `_tkinter` yok**; uv'nin yönettiği Python'u kullan (`--managed-python` ya da `uv python install 3.14`). `.venv` Homebrew Python'una bağlanırsa sil ve yeniden `uv sync --managed-python`.
- uv'nin Python 3.14'ü **Tk 9.0** ile gelir. `ForestTheme/forest-dark.tcl` bu yüzden `package require Tk 8.6-` (8.6 veya üstü) diyor; `8.6` yazılırsa tema sessizce yüklenmez.
- Stockfish `engine.get_engine_path()` ile bulunur, sıra: `MYCHESS_STOCKFISH` ortam değişkeni → paketle gelen motor (Windows: `engines/stockfish_15.1_win_x64_avx2/...exe`, diğerleri: `engines/stockfish`) → PATH → `/opt/homebrew/bin`, `/usr/local/bin`, `/usr/games`. macOS'ta `brew install stockfish`. Bulunamazsa Stockfish modu hata gösterir, iki kişilik mod çalışır.
- `Chess.spec`: Windows'ta `engines/` klasörünü paketler; macOS/Linux'ta build makinesindeki stockfish'i `engines/stockfish` adıyla `binaries`'e ekler ve macOS'ta `BUNDLE` ile `Chess.app` üretir. Giriş betiği `src/mychess/__main__.py` (mutlak import şart; PyInstaller betiği paket dışı çalıştırır).
- `dark_title_bar()` ve `STARTUPINFO` yalnız `win32`'de çalışır; diğer platformlarda atlanır.

## Mimari (`src/mychess/`)

- `main.py` — `ChessApp`: pencere, menü, kenar çubuğu (saatler, durum, hamle kaydı) ve oyun akışı; parçaları birbirine bağlar. `start_game()` loglamayı kurar.
  - Pencere boyutu: yan panel genişliği sabit varsayılmaz; `fit_window()` yan panelin ve menünün (`menu_box`, ortada `place` ile) istediği boyutu Tk'den ölçüp `minsize`'ı ayarlar. Tahta `board_size_for()` ile yan panele yer bırakarak boyutlanır, en az `MIN_BOARD_SIZE`. Yan panele/menüye widget eklersen `test_minimum_window_fits_menu_and_sidebar` kırpılmayı yakalar.
- `game.py` — `Game` (Tk'siz): `board`, `clock`, `mode` (`GameMode` enum), `player_side`, `running`, `result`. Her hamle `Game.push()`'tan geçer: süre hamleden önce bittiyse reddeder, saate basar (artış), `automatic_outcome()` ile oyun sonunu denetler. `check_flag()` süre bitimi. `TIME_CONTROLS`, sonuç metinleri (`outcome_message`, `timeout_message`) burada.
  - Beraberlik: `board.outcome(claim_draw=True)` **kullanma**; o bir *sonraki* hamleyle oluşabilecek tekrarı da sayar, oyunu erken bitirir. `automatic_outcome()` yalnızca gerçekleşen üç tekrar / 50 hamleyi sayar.
- `clock.py` — `GameClock`: süreyi `time.monotonic()` ile ölçer (`now` enjekte edilebilir). `press(mover)` artışı ekleyip rakibi başlatır. `ChessApp.time_update()` (`CLOCK_TICK_MS`) yalnızca ekranı yeniler ve `check_flag()` çağırır.
- `board_view.py` — `BoardView`: canvas çizimi, taş görselleri (`assets/images/imgs-128px`, LANCZOS ile kare boyutuna küçültülür; `piece_images`, terfi penceresi de kullanır), koordinatlar (`cell_to_square`/`square_to_cell`), tıkla-tıkla + sürükle-bırak. Hamle oynamaz; `on_move(kaynak, hedef)` ile `ChessApp.try_move`'u çağırır, `can_interact()` False iken girişi yok sayar. Boyut `BoardView.size`'da (global yok); `resize()` boyut aynıysa hiçbir şey yapmaz.
- `engine.py` — motor bulma, zorluk (`engine_settings`, `LOW_ELO_LEVELS`), düşünme süresi (`engine_think_time`), `EngineController`: `start/ensure/configure/shutdown`, `search()` ayrı thread'de hesaplar, sonucu `finally` içinde kuyruğa koyar; ana thread `poll()` ile okur. Worker Tk'ye dokunmaz. Sonuç `(game_id, move)`; `move is None` = motor hatası. `client` `UciEngine` protokolüne uyar (testte `FakeEngine`).
  - Zorluk: ELO motorun `UCI_Elo` aralığındaysa `UCI_LimitStrength` + `UCI_Elo`; altındaysa `Skill Level` + derinlik sınırı. Aralık motordan okunur (SF 15.1: 1350–2850, SF 19: 1320–3190).
  - Motor istisnaları için `ENGINE_ERRORS` kullan.
  - Başlatma: `ChessApp` açılışta `start_in_background()` çağırır (pencere motoru beklemez); `ensure()` ve `shutdown()` başlatma thread'inin bitmesini bekler. `ENGINE_TIMEOUT` (3 sn) `popen_uci`'ye verilir: ana thread'deki ping/configure/quit en fazla bu kadar dondurur, `play()`'in sınırı düşünme süresi + bu süre. Zaman aşımı `TimeoutError` (OSError) olarak `ENGINE_ERRORS`'a düşer.
- Motor hata politikası (`ChessApp`): eski oyuna ait sonuçlar `game_id` ile atılır (her yeni oyun/menü yeni `Game` ve kimlik). Mevcut oyunda `None` → `handle_engine_failure()` motoru `MAX_ENGINE_RESTARTS` kez yeniden başlatıp dener, olmazsa `game.stop()` + hata penceresi. `play()` (ve "Yeni Oyun") `engine.ensure()` ile motoru yoklar.
- Uyarı pencerelerini `show_dialog_later()` ile aç: macOS'ta yerel uyarı açıkken Tk ekranı boyamaz.
- `widgets.py` — terfi `Popup` (rengi sıradaki taraftan, `board.turn`); görsel eksikse düğmeler metinle (`PROMOTION_CHOICES`) çizilir, `dark_title_bar()`.
- `resources.py` — `get_resource_path()`: PyInstaller onefile (`_MEIPASS`), onedir (`sys.executable` dizini), geliştirme (`src/mychess/` ya da proje kökü). Yeni asset eklersen `Chess.spec` `datas` listesine de ekle.
- `logging_config.py` — `setup_logging()` (yalnız `start_game()` çağırır; testlerde kapalı) → macOS `~/Library/Logs/mychess/mychess.log` (Windows `%LOCALAPPDATA%\mychess\logs`, Linux `$XDG_STATE_HOME/mychess`), dönen dosya. Thread ve üst seviye yakalanmayan hatalar loglanır; Tk geri çağrı hataları `ChessApp.on_callback_error`. Modüllerde `logger = logging.getLogger(__name__)`; `except ...: pass` yazma, en az `logger.debug(..., exc_info=True)`. Kullanıcıya gösterilen hata mesajlarına `log_hint()` ekle.
- `const.py`: başlangıç tahta boyutu (`WIDTH`/`HEIGHT` 512), renkler. `SQSIZE` artık kullanılmıyor (`BoardView.square_size`).
- `board.py`, `pieces.py`, `square.py`: eski kendi tahta modeli; uygulama kullanmıyor, sadece `tests/test_legacy.py` import ediyor. `assets/sounds/*.wav` ve `imgs-80px` de kullanılmıyor. Bilerek bırakıldı.

## Testler (`tests/`)

- `test_game.py`, `test_clock.py`, `test_engine.py`: Tk'siz; sahte zaman (`FakeTime`) ve sahte motor (`FakeEngine`) `tests/fakes.py`'de. `test_engine.py` Stockfish kuruluysa gerçek motorla da dener.
- `test_board_view.py`, `test_app.py`: gerçek Tk (gizli pencere); ekran yoksa atlanır (CI'da Linux xvfb). `test_app` motoru `EngineController.start`'ı yamalayıp `FakeEngine` vererek sınar; mesaj kutuları yamalanır.
- `from mychess import main` / `import mychess.main as m` modülü değil paketteki `main()` fonksiyonunu verir; modül lazımsa `importlib.import_module("mychess.main")`.

## Arayüz dili ve lisans

- Arayüz metinleri Türkçe (menü dahil). Menü değerleri koda bağlı: mod adları `GameMode` değerleri, taraf adları `main.SIDE_CHOICES`; metni değiştirirsen oradan değiştir, string karşılaştırma yazma.
- Lisans GPL-3.0-or-later (`LICENSE`); python-chess GPL olduğu için dağıtılan uygulama GPL olmak zorunda. Yeni bir üçüncü parti bileşen/asset eklersen `THIRD_PARTY_NOTICES.md`'ye ekle; `Chess.spec` ikisini de `licenses/` altına paketler.

## Kod stili

- Tip ipuçları her yerde (`X | None`, `list[...]`), docstring'ler Türkçe. mypy strict temiz kalmalı.
- Değişiklikten sonra `uv run pytest`, `uv run ruff check .` ve `uv run mypy` çalıştır.
- GUI değişikliklerini `uv run mychess` ile açıp gör; testler etkileşimi kapsar ama görünümü değil.
