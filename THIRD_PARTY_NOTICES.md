# Third-party notices

mychess is licensed under the GNU General Public License v3.0 or later
(see `LICENSE`). It uses or bundles the following third-party components.

## Stockfish (bundled in packaged builds)

- License: GNU General Public License v3.0 (full text in `LICENSE`; the
  Windows engine folder also ships it as `engines/stockfish_15.1_win_x64_avx2/Copying.txt`).
- Source code: <https://github.com/official-stockfish/Stockfish>
  - Windows build in this repository: Stockfish 15.1 — source included under
    `engines/stockfish_15.1_win_x64_avx2/src`, authors in `AUTHORS`.
  - macOS/Linux packaged builds bundle the Stockfish binary found on the build
    machine (e.g. Homebrew `stockfish`); its version is shown in the app log
    and its source is available from the tag of the same version at the URL
    above.
- Stockfish runs as a separate process and talks to mychess over the UCI
  protocol.

## python-chess (`chess`)

- License: GNU General Public License v3.0 or later
- Source: <https://github.com/niklasf/python-chess>

## Pillow

- License: MIT-CMU (HPND)
- Source: <https://github.com/python-pillow/Pillow>

## Forest ttk theme (`src/mychess/ForestTheme`)

- Copyright (c) 2021 rdbende
- Source: <https://github.com/rdbende/Forest-ttk-theme>
- License: MIT

  Permission is hereby granted, free of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in
  all copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
  SOFTWARE.

## Python and Tcl/Tk (bundled by PyInstaller)

- Python: Python Software Foundation License — <https://docs.python.org/3/license.html>
- Tcl/Tk: BSD-style license — <https://www.tcl.tk/software/tcltk/license.html>

## Piece images and sounds (`src/mychess/assets`)

- Origin and license: **not documented yet.** Add the source and license here
  before redistributing the packaged app.
