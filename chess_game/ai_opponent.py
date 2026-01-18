import math
import random
from typing import Optional, List, Tuple
from .board import Board
from .pieces import PieceType, piece_values
from .utils import Color, Move
from .game_logic import generate_legal_moves, make_move, is_in_check


center_squares = {(3, 3), (3, 4), (4, 3), (4, 4)}


AI_SETTINGS = {
    "Easy": {"depth": 2, "randomness": 0.3},
    "Medium": {"depth": 3, "randomness": 0.1},
    "Hard": {"depth": 4, "randomness": 0.0},
}


def evaluate_board(board: Board, color: Color) -> int:
    material = 0
    center_control = 0
    for row in range(8):
        for col in range(8):
            piece = board.get_piece(row, col)
            if piece is None:
                continue
            value = piece_values[piece.kind]
            sign = 1 if piece.color is color else -1
            material += sign * value
            if (row, col) in center_squares:
                center_control += sign * 15
    return material + center_control


def evaluate_terminal(board: Board, color_to_move: Color, root_color: Color) -> Optional[int]:
    moves = generate_legal_moves(board, color_to_move)
    if moves:
        return None
    if is_in_check(board, color_to_move):
        if color_to_move is root_color:
            return -100000
        return 100000
    return 0


def order_moves(moves: List[Move], board: Board, color_to_move: Color) -> List[Move]:
    scored: List[Tuple[int, Move]] = []
    for move in moves:
        score = 0
        moving_piece = board.get_piece(move.from_row, move.from_col)
        captured_piece = None
        if move.is_en_passant and moving_piece is not None:
            direction = -1 if moving_piece.color is Color.WHITE else 1
            captured_row = move.to_row + direction
            captured_piece = board.get_piece(captured_row, move.to_col)
        else:
            captured_piece = board.get_piece(move.to_row, move.to_col)
        if captured_piece is not None:
            score += 1000 + piece_values[captured_piece.kind] - piece_values[moving_piece.kind] // 10
        clone = board.copy()
        make_move(clone, move)
        opponent = color_to_move.opposite
        if is_in_check(clone, opponent):
            score += 500
        if moving_piece is not None and moving_piece.kind is PieceType.KING and move.is_castling:
            score += 300
        scored.append((score, move))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [m for _, m in scored]


def minimax(
    board: Board,
    depth: int,
    alpha: int,
    beta: int,
    maximizing: bool,
    color_to_move: Color,
    root_color: Color,
) -> int:
    terminal_score = evaluate_terminal(board, color_to_move, root_color)
    if depth == 0 or terminal_score is not None:
        if terminal_score is not None:
            return terminal_score
        return evaluate_board(board, root_color)
    moves = generate_legal_moves(board, color_to_move)
    if not moves:
        return evaluate_board(board, root_color)
    moves = order_moves(moves, board, color_to_move)
    if maximizing:
        value = -math.inf
        for move in moves:
            clone = board.copy()
            make_move(clone, move)
            score = minimax(
                clone,
                depth - 1,
                alpha,
                beta,
                False,
                clone.current_player,
                root_color,
            )
            if score > value:
                value = score
            if value > alpha:
                alpha = value
            if alpha >= beta:
                break
        return int(value)
    value = math.inf
    for move in moves:
        clone = board.copy()
        make_move(clone, move)
        score = minimax(
            clone,
            depth - 1,
            alpha,
            beta,
            True,
            clone.current_player,
            root_color,
        )
        if score < value:
            value = score
        if value < beta:
            beta = value
        if beta <= alpha:
            break
    return int(value)


def choose_ai_move(
    board: Board,
    color: Color,
    depth: int,
    randomness: float = 0.0,
) -> Optional[Move]:
    moves = generate_legal_moves(board, color)
    if not moves:
        return None
    if depth <= 0:
        return random.choice(moves)
    scored: List[Tuple[int, Move]] = []
    alpha = -math.inf
    beta = math.inf
    for move in moves:
        clone = board.copy()
        make_move(clone, move)
        score = minimax(
            clone,
            depth - 1,
            alpha,
            beta,
            False,
            clone.current_player,
            color,
        )
        scored.append((score, move))
        if score > alpha:
            alpha = score
    scored.sort(key=lambda t: t[0], reverse=True)
    if randomness > 0 and len(scored) > 1:
        top_count = max(1, int(len(scored) * randomness))
        top_moves = [m for _, m in scored[:top_count]]
        return random.choice(top_moves)
    return scored[0][1]
