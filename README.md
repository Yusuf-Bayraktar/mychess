# ♟️ mychess

A desktop chess game written in Python.

`mychess` is a Python-based chess application featuring a graphical interface, chess rule handling, and Stockfish engine integration. The project is built with a modern Python project structure and includes automated tests for core functionality.

## ✨ Features

- ♟️ Full chess gameplay
- 🧠 Stockfish engine integration
- 🖥️ Graphical user interface
- 📋 Legal move validation
- 👑 Standard chess rules and game states
- 🧪 Automated tests with `pytest`
- ⚡ Modern Python project structure
- 📦 Standalone executable support with PyInstaller
- 🔧 Code quality checks with Ruff

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| **Python 3.14+** | Core programming language |
| **python-chess** | Chess rules, board representation and move handling |
| **Pillow** | Image and graphical asset handling |
| **Stockfish** | Chess engine |
| **pytest** | Automated testing |
| **Ruff** | Linting and code quality |
| **PyInstaller** | Application packaging |
| **uv** | Python project and dependency management |

The project's dependencies and development tools are defined in `pyproject.toml`.

## 📁 Project Structure

```text
mychess/
├── engines/
│   └── stockfish_15.1_win_x64_avx2/
├── screenshots/
├── src/
│   └── mychess/
├── tests/
├── Chess.spec
├── pyproject.toml
├── uv.lock
└── README.md
```

## 🚀 Getting Started

### Requirements

- Python **3.14 or newer**
- Git
- `uv` (recommended)

### Clone the repository

```bash
git clone https://github.com/Yusuf-Bayraktar/mychess.git
cd mychess
```

### Install dependencies

Using `uv`:

```bash
uv sync
```

Or install the project with your preferred Python package manager.

### Run the game

After installing the dependencies:

```bash
uv run mychess
```

You can also run the application directly through Python:

```bash
uv run python -m mychess
```

The project exposes `mychess` as a console script that starts the game.

## 🧠 Chess Engine

`mychess` includes a Stockfish engine binary under the `engines/` directory.

The engine is used to provide computer-player functionality and chess analysis.

## 🧪 Testing

Tests are located in the `tests/` directory and can be executed with:

```bash
uv run pytest
```

## 🔍 Code Quality

Ruff is used for linting and maintaining code quality:

```bash
uv run ruff check .
```

## 📸 Screenshots

Screenshots of the application can be found in the [`screenshots`](./screenshots) directory.

## 📦 Building

The project includes a PyInstaller specification file:

```text
Chess.spec
```

This can be used to build a standalone executable for the application.

For example:

```bash
uv run pyinstaller Chess.spec
```

The exact output location depends on the PyInstaller configuration.

## 🗺️ Roadmap

Possible future improvements:

- [ ] Improved game settings
- [ ] Multiple difficulty levels
- [ ] Better engine configuration
- [ ] Game history and move notation
- [ ] Save and load games
- [ ] Additional chess themes
- [ ] More comprehensive test coverage
- [ ] Cross-platform builds

## 👤 Author

**Yusuf Bayraktar**

GitHub: [@Yusuf-Bayraktar](https://github.com/Yusuf-Bayraktar)

## 📄 License

This project is currently distributed without a specified open-source license.

If you plan to publish or redistribute the project, consider adding a `LICENSE` file.

---

> ♟️ Built with Python.
