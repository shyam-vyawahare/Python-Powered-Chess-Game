from dataclasses import dataclass
from .utils import Color, PieceType


unicode_white = {
    PieceType.KING: "♔",
    PieceType.QUEEN: "♕",
    PieceType.ROOK: "♖",
    PieceType.BISHOP: "♗",
    PieceType.KNIGHT: "♘",
    PieceType.PAWN: "♙",
}

unicode_black = {
    PieceType.KING: "♚",
    PieceType.QUEEN: "♛",
    PieceType.ROOK: "♜",
    PieceType.BISHOP: "♝",
    PieceType.KNIGHT: "♞",
    PieceType.PAWN: "♟",
}


piece_values = {
    PieceType.PAWN: 100,
    PieceType.KNIGHT: 320,
    PieceType.BISHOP: 330,
    PieceType.ROOK: 500,
    PieceType.QUEEN: 900,
    PieceType.KING: 20000,
}


@dataclass
class Piece:
    color: Color
    kind: PieceType
    has_moved: bool = False

    def symbol(self) -> str:
        if self.color is Color.WHITE:
            return unicode_white[self.kind]
        return unicode_black[self.kind]

    def letter(self) -> str:
        text = self.kind.value
        if self.color is Color.BLACK:
            return text.lower()
        return text

