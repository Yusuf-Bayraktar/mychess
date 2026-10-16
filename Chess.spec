# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
import sys

datas = [
    ('src/mychess/assets', 'assets'),
    ('src/mychess/ForestTheme', 'ForestTheme'),
    # GPL: lisans ve üçüncü parti bildirimleri pakete girer.
    ('LICENSE', 'licenses'),
    ('THIRD_PARTY_NOTICES.md', 'licenses'),
]
binaries = []

if sys.platform == 'win32':
    datas.append(('engines', 'engines'))
else:
    # macOS/Linux: build makinesindeki Stockfish'i engines/stockfish adıyla paketle
    # (MYCHESS_STOCKFISH ya da PATH; macOS'ta `brew install stockfish`).
    stockfish = os.environ.get('MYCHESS_STOCKFISH') or shutil.which('stockfish')
    if stockfish:
        staged = os.path.join('build', 'engine', 'stockfish')
        os.makedirs(os.path.dirname(staged), exist_ok=True)
        # Homebrew dosyası salt okunur; copy2 izni de kopyaladığı için önceki
        # derlemenin kopyası üzerine yazılamaz, önce silinir.
        if os.path.exists(staged):
            os.chmod(staged, 0o755)
            os.remove(staged)
        shutil.copy2(os.path.realpath(stockfish), staged)
        binaries.append((staged, 'engines'))
        # Motorun kendi lisans/yazar dosyaları (Homebrew: Cellar/stockfish/<sürüm>/)
        engine_root = os.path.dirname(os.path.dirname(os.path.realpath(stockfish)))
        for name in ('Copying.txt', 'COPYING', 'AUTHORS'):
            path = os.path.join(engine_root, name)
            if os.path.isfile(path):
                datas.append((path, 'licenses/stockfish'))
    else:
        print('UYARI: stockfish bulunamadı; paket Stockfish modu olmadan oluşacak.')


a = Analysis(
    ['src/mychess/__main__.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Chess',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Chess',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Chess.app',
        icon=None,
        bundle_identifier=None,
        info_plist={'NSHighResolutionCapable': True},
    )
