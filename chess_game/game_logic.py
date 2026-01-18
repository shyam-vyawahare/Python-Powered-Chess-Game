from typing import List, Optional, Tuple, Dict
from .board import Board
from .pieces import Piece, piece_values
from .utils import Color, PieceType, Move, square_to_indices, indices_to_square, format_move_san_like


def in_bounds(row: int, col: int) -> bool:
    return 0 <= row < 8 and 0 <= col < 8


def locate_king(board: Board, color: Color) -> Optional[Tuple[int, int]]:
    for row, col, piece in board.iter_squares():
        if piece is not None and piece.color is color and piece.kind is PieceType.KING:
            return row, col
    return None


def is_square_attacked(board: Board, row: int, col: int, by_color: Color) -> bool:
    pawn_dir = -1 if by_color is Color.WHITE else 1
    for dc in (-1, 1):
        pr = row + pawn_dir
        pc = col + dc
        if in_bounds(pr, pc):
            piece = board.get_piece(pr, pc)
            if piece is not None and piece.color is by_color and piece.kind is PieceType.PAWN:
                return True
    knight_offsets = [
        (-2, -1),
        (-2, 1),
        (-1, -2),
        (-1, 2),
        (1, -2),
        (1, 2),
        (2, -1),
        (2, 1),
    ]
    for dr, dc in knight_offsets:
        r = row + dr
        c = col + dc
        if not in_bounds(r, c):
            continue
        piece = board.get_piece(r, c)
        if piece is not None and piece.color is by_color and piece.kind is PieceType.KNIGHT:
            return True
    directions_rook = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    directions_bishop = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    for dr, dc in directions_rook:
        r = row + dr
        c = col + dc
        while in_bounds(r, c):
            piece = board.get_piece(r, c)
            if piece is None:
                r += dr
                c += dc
                continue
            if piece.color is not by_color:
                break
            if piece.kind in (PieceType.ROOK, PieceType.QUEEN):
                return True
            break
    for dr, dc in directions_bishop:
        r = row + dr
        c = col + dc
        while in_bounds(r, c):
            piece = board.get_piece(r, c)
            if piece is None:
                r += dr
                c += dc
                continue
            if piece.color is not by_color:
                break
            if piece.kind in (PieceType.BISHOP, PieceType.QUEEN):
                return True
            break
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            r = row + dr
            c = col + dc
            if not in_bounds(r, c):
                continue
            piece = board.get_piece(r, c)
            if piece is not None and piece.color is by_color and piece.kind is PieceType.KING:
                return True
    return False


def is_in_check(board: Board, color: Color) -> bool:
    pos = locate_king(board, color)
    if pos is None:
        return False
    row, col = pos
    return is_square_attacked(board, row, col, color.opposite)


def generate_pawn_moves(board: Board, row: int, col: int, moves: List[Move]) -> None:
    piece = board.get_piece(row, col)
    if piece is None:
        return
    color = piece.color
    direction = -1 if color is Color.WHITE else 1
    start_row = 6 if color is Color.WHITE else 1
    one_step = row + direction
    if in_bounds(one_step, col) and board.get_piece(one_step, col) is None:
        if one_step == 0 or one_step == 7:
            for promo_kind in (PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT):
                moves.append(Move(row, col, one_step, col, promotion=promo_kind))
        else:
            moves.append(Move(row, col, one_step, col))
        two_step = row + 2 * direction
        if row == start_row and board.get_piece(two_step, col) is None:
            moves.append(Move(row, col, two_step, col))
    for dc in (-1, 1):
        tr = row + direction
        tc = col + dc
        if not in_bounds(tr, tc):
            continue
        target = board.get_piece(tr, tc)
        if target is not None and target.color is not color:
            if tr == 0 or tr == 7:
                for promo_kind in (PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT):
                    moves.append(Move(row, col, tr, tc, promotion=promo_kind))
            else:
                moves.append(Move(row, col, tr, tc))
    if board.en_passant_target is not None:
        ep_row, ep_col = board.en_passant_target
        if ep_row == row + direction and abs(ep_col - col) == 1:
            moves.append(
                Move(row, col, ep_row, ep_col, is_en_passant=True),
            )


def generate_knight_moves(board: Board, row: int, col: int, moves: List[Move]) -> None:
    piece = board.get_piece(row, col)
    if piece is None:
        return
    color = piece.color
    offsets = [
        (-2, -1),
        (-2, 1),
        (-1, -2),
        (-1, 2),
        (1, -2),
        (1, 2),
        (2, -1),
        (2, 1),
    ]
    for dr, dc in offsets:
        r = row + dr
        c = col + dc
        if not in_bounds(r, c):
            continue
        target = board.get_piece(r, c)
        if target is None or target.color is not color:
            moves.append(Move(row, col, r, c))


def generate_sliding_moves(
    board: Board,
    row: int,
    col: int,
    directions: List[Tuple[int, int]],
    moves: List[Move],
) -> None:
    piece = board.get_piece(row, col)
    if piece is None:
        return
    color = piece.color
    for dr, dc in directions:
        r = row + dr
        c = col + dc
        while in_bounds(r, c):
            target = board.get_piece(r, c)
            if target is None:
                moves.append(Move(row, col, r, c))
            else:
                if target.color is not color:
                    moves.append(Move(row, col, r, c))
                break
            r += dr
            c += dc


def generate_king_moves(board: Board, row: int, col: int, moves: List[Move]) -> None:
    piece = board.get_piece(row, col)
    if piece is None:
        return
    color = piece.color
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            r = row + dr
            c = col + dc
            if not in_bounds(r, c):
                continue
            target = board.get_piece(r, c)
            if target is None or target.color is not color:
                moves.append(Move(row, col, r, c))
    if is_in_check(board, color):
        return
    row_back = 7 if color is Color.WHITE else 0
    if row != row_back or col != 4:
        return
    rights = board.castling_rights[color]
    if rights["K"]:
        if (
            board.get_piece(row, 5) is None
            and board.get_piece(row, 6) is None
            and not is_square_attacked(board, row, 5, color.opposite)
            and not is_square_attacked(board, row, 6, color.opposite)
        ):
            moves.append(Move(row, col, row, 6, is_castling=True))
    if rights["Q"]:
        if (
            board.get_piece(row, 1) is None
            and board.get_piece(row, 2) is None
            and board.get_piece(row, 3) is None
            and not is_square_attacked(board, row, 3, color.opposite)
            and not is_square_attacked(board, row, 2, color.opposite)
        ):
            moves.append(Move(row, col, row, 2, is_castling=True))


def generate_pseudo_legal_moves(board: Board, color: Color) -> List[Move]:
    moves: List[Move] = []
    for row, col, piece in board.iter_squares():
        if piece is None or piece.color is not color:
            continue
        if piece.kind is PieceType.PAWN:
            generate_pawn_moves(board, row, col, moves)
        elif piece.kind is PieceType.KNIGHT:
            generate_knight_moves(board, row, col, moves)
        elif piece.kind is PieceType.BISHOP:
            generate_sliding_moves(
                board,
                row,
                col,
                [(-1, -1), (-1, 1), (1, -1), (1, 1)],
                moves,
            )
        elif piece.kind is PieceType.ROOK:
            generate_sliding_moves(
                board,
                row,
                col,
                [(-1, 0), (1, 0), (0, -1), (0, 1)],
                moves,
            )
        elif piece.kind is PieceType.QUEEN:
            generate_sliding_moves(
                board,
                row,
                col,
                [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)],
                moves,
            )
        elif piece.kind is PieceType.KING:
            generate_king_moves(board, row, col, moves)
    return moves


def make_move(board: Board, move: Move) -> Optional[Piece]:
    piece = board.get_piece(move.from_row, move.from_col)
    captured = None
    if piece is None:
        return None
    target = board.get_piece(move.to_row, move.to_col)
    if move.is_en_passant:
        direction = -1 if piece.color is Color.WHITE else 1
        captured_row = move.to_row + direction
        captured_col = move.to_col
        captured = board.get_piece(captured_row, captured_col)
        board.set_piece(captured_row, captured_col, None)
    else:
        captured = target
    if move.is_castling and piece.kind is PieceType.KING:
        row = move.from_row
        if move.to_col == 6:
            rook_from_col = 7
            rook_to_col = 5
        else:
            rook_from_col = 0
            rook_to_col = 3
        rook = board.get_piece(row, rook_from_col)
        board.set_piece(row, rook_from_col, None)
        board.set_piece(row, rook_to_col, rook)
        if rook is not None:
            rook.has_moved = True
    board.set_piece(move.from_row, move.from_col, None)
    if move.promotion is not None and piece.kind is PieceType.PAWN:
        promoted = Piece(piece.color, move.promotion, has_moved=True)
        board.set_piece(move.to_row, move.to_col, promoted)
    else:
        piece.has_moved = True
        board.set_piece(move.to_row, move.to_col, piece)
    if piece.kind is PieceType.KING:
        rights = board.castling_rights[piece.color]
        rights["K"] = False
        rights["Q"] = False
    if piece.kind is PieceType.ROOK:
        if move.from_row == 7 and move.from_col == 0:
            board.castling_rights[Color.WHITE]["Q"] = False
        if move.from_row == 7 and move.from_col == 7:
            board.castling_rights[Color.WHITE]["K"] = False
        if move.from_row == 0 and move.from_col == 0:
            board.castling_rights[Color.BLACK]["Q"] = False
        if move.from_row == 0 and move.from_col == 7:
            board.castling_rights[Color.BLACK]["K"] = False
    if captured is not None and captured.kind is PieceType.ROOK:
        if move.to_row == 7 and move.to_col == 0:
            board.castling_rights[Color.WHITE]["Q"] = False
        if move.to_row == 7 and move.to_col == 7:
            board.castling_rights[Color.WHITE]["K"] = False
        if move.to_row == 0 and move.to_col == 0:
            board.castling_rights[Color.BLACK]["Q"] = False
        if move.to_row == 0 and move.to_col == 7:
            board.castling_rights[Color.BLACK]["K"] = False
    board.en_passant_target = None
    if piece.kind is PieceType.PAWN and abs(move.to_row - move.from_row) == 2:
        mid_row = (move.to_row + move.from_row) // 2
        board.en_passant_target = (mid_row, move.from_col)
    if piece.kind is PieceType.PAWN or captured is not None:
        board.halfmove_clock = 0
    else:
        board.halfmove_clock += 1
    if board.current_player is Color.BLACK:
        board.fullmove_number += 1
    board.current_player = board.current_player.opposite
    return captured


def generate_legal_moves(board: Board, color: Optional[Color] = None) -> List[Move]:
    if color is None:
        color = board.current_player
    moves = generate_pseudo_legal_moves(board, color)
    legal: List[Move] = []
    for move in moves:
        clone = board.copy()
        make_move(clone, move)
        if not is_in_check(clone, color):
            legal.append(move)
    return legal


def has_any_legal_moves(board: Board, color: Color) -> bool:
    moves = generate_legal_moves(board, color)
    return len(moves) > 0


def material_balance(board: Board, color: Color) -> int:
    score = 0
    for _, _, piece in board.iter_squares():
        if piece is None:
            continue
        value = piece_values[piece.kind]
        if piece.color is color:
            score += value
        else:
            score -= value
    return score


class Game:
    def __init__(self) -> None:
        self.board = Board()
        self.board.setup_initial()
        self.history: List[Board] = [self.board.copy()]
        self.move_log: List[str] = []
        self.captured_white: List[Piece] = []
        self.captured_black: List[Piece] = []
        self.repetition: Dict[str, int] = {}
        self.draw_offered_by: Optional[Color] = None
        self.result: Optional[str] = None
        self._update_repetition()
        self.last_move: Optional[Move] = None

    def _update_repetition(self) -> None:
        key = self.board.board_key()
        self.repetition[key] = self.repetition.get(key, 0) + 1

    def get_legal_moves(self) -> List[Move]:
        return generate_legal_moves(self.board, self.board.current_player)

    def is_in_check(self, color: Optional[Color] = None) -> bool:
        if color is None:
            color = self.board.current_player
        return is_in_check(self.board, color)

    def is_checkmate(self) -> bool:
        color = self.board.current_player
        return self.is_in_check(color) and not has_any_legal_moves(self.board, color)

    def is_stalemate(self) -> bool:
        color = self.board.current_player
        return not self.is_in_check(color) and not has_any_legal_moves(self.board, color)

    def can_claim_fifty_move_draw(self) -> bool:
        return self.board.halfmove_clock >= 100

    def can_claim_threefold_draw(self) -> bool:
        key = self.board.board_key()
        return self.repetition.get(key, 0) >= 3

    def apply_move(self, move: Move) -> bool:
        color = self.board.current_player
        legal_moves = self.get_legal_moves()
        if move not in legal_moves:
            return False
        from_sq = indices_to_square(move.from_row, move.from_col)
        to_sq = indices_to_square(move.to_row, move.to_col)
        captured = make_move(self.board, move)
        self.history.append(self.board.copy())
        if captured is not None:
            if captured.color is Color.WHITE:
                self.captured_white.append(captured)
            else:
                self.captured_black.append(captured)
        text = f"{from_sq}-{to_sq}"
        if move.promotion is not None:
            text = f"{from_sq}-{to_sq}={move.promotion.value}"
        prefix = "W" if color is Color.WHITE else "B"
        self.move_log.append(f"{prefix}: {text}")
        self._update_repetition()
        self.last_move = move
        self.update_result_after_move()
        self.draw_offered_by = None
        return True

    def update_result_after_move(self) -> None:
        if self.is_checkmate():
            winner = self.board.current_player.opposite
            name = "White" if winner is Color.WHITE else "Black"
            self.result = f"{name} wins by checkmate"
            return
        if self.is_stalemate():
            self.result = "Draw by stalemate"
            return
        if self.can_claim_fifty_move_draw():
            self.result = "Draw by fifty-move rule"
            return
        if self.can_claim_threefold_draw():
            self.result = "Draw by threefold repetition"
            return

    def undo_last_move(self) -> bool:
        if len(self.history) <= 1:
            return False
        self.history.pop()
        self.board = self.history[-1].copy()
        if self.move_log:
            self.move_log.pop()
        self.result = None
        self.last_move = None
        return True


def self_test() -> None:
    game = Game()
    moves = game.get_legal_moves()
    print("Initial legal moves for White:", len(moves))
    if len(moves) < 20:
        raise SystemExit("Too few initial moves")
