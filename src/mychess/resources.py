"""Paketle gelen dosyaların (görseller, tema) yolunu çözer."""

import sys
from pathlib import Path


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
