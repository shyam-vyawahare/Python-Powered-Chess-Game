from typing import List, Optional, Tuple
from copy import deepcopy
from .pieces import Piece
from .utils import Color, PieceType, Move, file_labels


class Board:
    def __init__(self) -> None:
        self.grid: List[List[Optional[Piece]]] = [
            [None for _ in range(8)] for _ in range(8)
        ]
        self.current_player: Color = Color.WHITE
        self.castling_rights = {
            Color.WHITE: {"K": True, "Q": True},
            Color.BLACK: {"K": True, "Q": True},
        }
        self.en_passant_target: Optional[Tuple[int, int]] = None
        self.halfmove_clock: int = 0
        self.fullmove_number: int = 1

    def copy(self) -> "Board":
        clone = Board()
        clone.grid = deepcopy(self.grid)
        clone.current_player = self.current_player
        clone.castling_rights = {
            Color.WHITE: self.castling_rights[Color.WHITE].copy(),
            Color.BLACK: self.castling_rights[Color.BLACK].copy(),
        }
        clone.en_passant_target = self.en_passant_target
        clone.halfmove_clock = self.halfmove_clock
        clone.fullmove_number = self.fullmove_number
        return clone

    def setup_initial(self) -> None:
        for col in range(8):
            self.grid[1][col] = Piece(Color.BLACK, PieceType.PAWN)
            self.grid[6][col] = Piece(Color.WHITE, PieceType.PAWN)
        back_rank = [
            PieceType.ROOK,
            PieceType.KNIGHT,
            PieceType.BISHOP,
            PieceType.QUEEN,
            PieceType.KING,
            PieceType.BISHOP,
            PieceType.KNIGHT,
            PieceType.ROOK,
        ]
        for col, kind in enumerate(back_rank):
            self.grid[0][col] = Piece(Color.BLACK, kind)
            self.grid[7][col] = Piece(Color.WHITE, kind)

    def get_piece(self, row: int, col: int) -> Optional[Piece]:
        return self.grid[row][col]

    def set_piece(self, row: int, col: int, piece: Optional[Piece]) -> None:
        self.grid[row][col] = piece

    def iter_squares(self):
        for row in range(8):
            for col in range(8):
                yield row, col, self.grid[row][col]

    def to_fen(self) -> str:
        rows = []
        for r in range(8):
            empty_count = 0
            row_str = ""
            for c in range(8):
                piece = self.grid[r][c]
                if piece is None:
                    empty_count += 1
                else:
                    if empty_count > 0:
                        row_str += str(empty_count)
                        empty_count = 0
                    
                    symbol = piece.kind.value
                    if piece.color == Color.BLACK:
                        symbol = symbol.lower()
                    row_str += symbol
            if empty_count > 0:
                row_str += str(empty_count)
            rows.append(row_str)
            
        board_fen = "/".join(rows)
        
        active = "w" if self.current_player == Color.WHITE else "b"
        
        castling = ""
        if self.castling_rights[Color.WHITE]["K"]: castling += "K"
        if self.castling_rights[Color.WHITE]["Q"]: castling += "Q"
        if self.castling_rights[Color.BLACK]["K"]: castling += "k"
        if self.castling_rights[Color.BLACK]["Q"]: castling += "q"
        if not castling: castling = "-"
        
        ep = "-"
        if self.en_passant_target:
            r, c = self.en_passant_target
            file = file_labels[c]
            rank = 8 - r
            ep = f"{file}{rank}"
            
        return f"{board_fen} {active} {castling} {ep} {self.halfmove_clock} {self.fullmove_number}"

    def board_key(self) -> str:
        rows = []
        for row in range(8):
            parts = []
            for col in range(8):
                piece = self.grid[row][col]
                if piece is None:
                    parts.append(".")
                else:
                    parts.append(piece.letter())
            rows.append("".join(parts))
        pieces_part = "/".join(rows)
        turn_part = "w" if self.current_player is Color.WHITE else "b"
        rights = []
        if self.castling_rights[Color.WHITE]["K"]:
            rights.append("K")
        if self.castling_rights[Color.WHITE]["Q"]:
            rights.append("Q")
        if self.castling_rights[Color.BLACK]["K"]:
            rights.append("k")
        if self.castling_rights[Color.BLACK]["Q"]:
            rights.append("q")
        rights_part = "".join(rights) or "-"
        if self.en_passant_target is None:
            ep_part = "-"
        else:
            row, col = self.en_passant_target
            ep_part = f"{file_labels[col]}{8 - row}"
        return f"{pieces_part} {turn_part} {rights_part} {ep_part} {self.halfmove_clock} {self.fullmove_number}"

    def to_ascii(self, last_move: Optional[Move] = None) -> str:
        lines: List[str] = []
        header = "  " + " ".join(file_labels)
        lines.append(header)
        highlight_from = None
        highlight_to = None
        if last_move is not None:
            highlight_from = (last_move.from_row, last_move.from_col)
            highlight_to = (last_move.to_row, last_move.to_col)
        for row in range(8):
            rank = 8 - row
            parts = [str(rank)]
            for col in range(8):
                piece = self.grid[row][col]
                if piece is None:
                    symbol = "·"
                else:
                    symbol = piece.symbol()
                coord = (row, col)
                if coord == highlight_from or coord == highlight_to:
                    parts.append(f"[{symbol}]")
                else:
                    parts.append(symbol)
            parts.append(str(rank))
            lines.append(" ".join(parts))
        lines.append(header)
        return "\n".join(lines)

