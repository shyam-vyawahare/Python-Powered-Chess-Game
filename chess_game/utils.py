from enum import Enum
from dataclasses import dataclass
from typing import Optional, Tuple, List


class Color(Enum):
    WHITE = "white"
    BLACK = "black"

    @property
    def opposite(self) -> "Color":
        if self is Color.WHITE:
            return Color.BLACK
        return Color.WHITE


class PieceType(Enum):
    KING = "K"
    QUEEN = "Q"
    ROOK = "R"
    BISHOP = "B"
    KNIGHT = "N"
    PAWN = "P"


@dataclass(frozen=True)
class Move:
    from_row: int
    from_col: int
    to_row: int
    to_col: int
    promotion: Optional[PieceType] = None
    is_castling: bool = False
    is_en_passant: bool = False


file_labels = "abcdefgh"


def square_to_indices(square: str) -> Optional[Tuple[int, int]]:
    if len(square) != 2:
        return None
    file_char = square[0].lower()
    rank_char = square[1]
    if file_char not in file_labels:
        return None
    if not rank_char.isdigit():
        return None
    rank = int(rank_char)
    if rank < 1 or rank > 8:
        return None
    col = file_labels.index(file_char)
    row = 8 - rank
    return row, col


def indices_to_square(row: int, col: int) -> str:
    file_char = file_labels[col]
    rank_char = str(8 - row)
    return f"{file_char}{rank_char}"


def parse_move_input(text: str) -> Optional[Tuple[str, str, Optional[str]]]:
    cleaned = text.strip().lower()
    if not cleaned:
        return None
    for sep in ["-", "–", "—"]:
        cleaned = cleaned.replace(sep, " ")
    parts = [p for p in cleaned.split() if p]
    if len(parts) == 1 and len(parts[0]) == 4:
        parts = [parts[0][:2], parts[0][2:]]
    if len(parts) not in (2, 3):
        return None
    from_sq = parts[0]
    to_sq = parts[1]
    promo = None
    if len(parts) == 3:
        promo = parts[2]
    if square_to_indices(from_sq) is None or square_to_indices(to_sq) is None:
        return None
    if promo is not None:
        if promo not in {"q", "r", "b", "n"}:
            return None
    return from_sq, to_sq, promo


def format_move_san_like(
    from_sq: str,
    to_sq: str,
    promotion: Optional[PieceType],
    suffix: str = "",
) -> str:
    parts: List[str] = [from_sq, to_sq]
    if promotion is not None:
        parts.append(promotion.value.lower())
    text = "".join(parts)
    return f"{text}{suffix}"

