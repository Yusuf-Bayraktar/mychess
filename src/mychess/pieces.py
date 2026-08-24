from pathlib import Path

from PIL import Image


class Piece:
    def __init__(
        self,
        name: str,
        color: str,
        tag: str,
        texture: Image.Image | None = None,
    ) -> None:
        self.name: str = name
        self.color: str = color
        self.tag: str = tag.upper() if color == "white" else tag.lower()
        self.texture: Image.Image | None = texture

    def set_texture(
        self, size: int = 80, assets_dir: Path | None = None
    ) -> None:
        base_dir = assets_dir or Path("assets")
        img_path = (
            base_dir / "images" / f"imgs-{size}px" / f"{self.color}_{self.name}.png"
        )
        if img_path.exists():
            self.texture = Image.open(str(img_path)).convert("RGBA")


class Pawn(Piece):
    def __init__(self, color: str) -> None:
        super().__init__("pawn", color, "P")


class Knight(Piece):
    def __init__(self, color: str) -> None:
        super().__init__("knight", color, "N")


class Bishop(Piece):
    def __init__(self, color: str) -> None:
        super().__init__("bishop", color, "B")


class Rook(Piece):
    def __init__(self, color: str) -> None:
        super().__init__("rook", color, "R")


class Queen(Piece):
    def __init__(self, color: str) -> None:
        super().__init__("queen", color, "Q")


class King(Piece):
    def __init__(self, color: str) -> None:
        super().__init__("king", color, "K")
