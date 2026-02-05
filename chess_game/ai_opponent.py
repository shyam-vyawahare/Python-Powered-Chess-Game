import math
import random
import time
from typing import Optional, List, Tuple, Dict
from .board import Board
from .pieces import PieceType, piece_values
from .utils import Color, Move
from .game_logic import generate_legal_moves, make_move, is_in_check

# Center squares for positional bonus
center_squares = {(3, 3), (3, 4), (4, 3), (4, 4)}

# Transposition Table
# Key: board_key
# Value: (depth, score, flag, best_move_index)
# flag: 0=EXACT, 1=LOWERBOUND, 2=UPPERBOUND
TRANSPOSITION_TABLE: Dict[str, Tuple[int, int, int, Optional[Move]]] = {}

# Constants for TT flags
FLAG_EXACT = 0
FLAG_LOWERBOUND = 1
FLAG_UPPERBOUND = 2

# Maximum time buffer to ensure we don't overrun (seconds)
TIME_BUFFER = 0.05

class TimeLimitExceeded(Exception):
    pass

AI_SETTINGS = {
    "Easy": {"depth": 2, "randomness": 0.3, "time_limit": 0.1},
    "Medium": {"depth": 4, "randomness": 0.1, "time_limit": 0.5},
    "Hard": {"depth": 6, "randomness": 0.0, "time_limit": 1.0},
}

def clear_ai_cache() -> None:
    """Clears the transposition table to free memory."""
    TRANSPOSITION_TABLE.clear()

def evaluate_board(board: Board, color: Color) -> int:
    """
    Simplified evaluation function.
    Positive score favors 'color'.
    """
    material = 0
    center_control = 0
    
    # We can iterate grid directly or pieces if available.
    # Board grid is 8x8.
    for row in range(8):
        for col in range(8):
            piece = board.grid[row][col]
            if piece is None:
                continue
            
            # Material
            value = piece_values[piece.kind]
            if piece.color is color:
                material += value
                if (row, col) in center_squares:
                    center_control += 15
            else:
                material -= value
                if (row, col) in center_squares:
                    center_control -= 15
                    
    return material + center_control

def evaluate_terminal(board: Board, color_to_move: Color, root_color: Color) -> Optional[int]:
    moves = generate_legal_moves(board, color_to_move)
    if moves:
        return None # Not terminal
        
    if is_in_check(board, color_to_move):
        # Checkmate
        # If it is 'color_to_move' turn and they are in check, they lost.
        # If root_color is color_to_move, root_color lost -> -100000
        if color_to_move is root_color:
            return -100000
        else:
            return 100000
    else:
        # Stalemate
        return 0

def order_moves(moves: List[Move], board: Board) -> List[Move]:
    """
    Sort moves by estimated potential:
    1. Captures (MVV-LVA)
    2. Promotions
    3. Others
    """
    scored: List[Tuple[int, Move]] = []
    
    for move in moves:
        score = 0
        
        # 1. Captures
        target = board.grid[move.to_row][move.to_col]
        if target is not None:
            attacker = board.grid[move.from_row][move.from_col]
            attacker_val = piece_values[attacker.kind] if attacker else 100
            victim_val = piece_values[target.kind]
            # MVV-LVA: Most Valuable Victim - Least Valuable Aggressor
            score += 10000 + (victim_val * 10) - attacker_val
        elif move.is_en_passant:
             score += 10000 + (piece_values[PieceType.PAWN] * 10) - piece_values[PieceType.PAWN]
             
        # 2. Promotions
        if move.promotion:
            score += 9000 + piece_values[move.promotion]
            
        # 3. Castling (good for safety)
        if move.is_castling:
            score += 500
            
        scored.append((score, move))
        
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored]

def alpha_beta(
    board: Board,
    depth: int,
    alpha: int,
    beta: int,
    maximizing: bool,
    color_to_move: Color,
    root_color: Color,
    end_time: float
) -> int:
    # 1. Check Time
    if time.time() > end_time:
        raise TimeLimitExceeded
        
    # 2. Transposition Table Lookup
    board_key = board.board_key()
    tt_entry = TRANSPOSITION_TABLE.get(board_key)
    
    if tt_entry is not None:
        tt_depth, tt_score, tt_flag, _ = tt_entry
        if tt_depth >= depth:
            if tt_flag == FLAG_EXACT:
                return tt_score
            elif tt_flag == FLAG_LOWERBOUND:
                alpha = max(alpha, tt_score)
            elif tt_flag == FLAG_UPPERBOUND:
                beta = min(beta, tt_score)
            if alpha >= beta:
                return tt_score

    # 3. Terminal Check
    terminal_score = evaluate_terminal(board, color_to_move, root_color)
    if terminal_score is not None:
        return terminal_score
        
    if depth == 0:
        return evaluate_board(board, root_color)

    # 4. Generate & Order Moves
    moves = generate_legal_moves(board, color_to_move)
    # Note: evaluate_terminal handles empty moves (stalemate/mate), so moves is not empty here unless logic error
    
    # Move ordering
    moves = order_moves(moves, board)
    
    best_move = None
    
    # 5. Search
    if maximizing:
        value = -math.inf
        for move in moves:
            clone = board.copy()
            make_move(clone, move)
            score = alpha_beta(
                clone, depth - 1, alpha, beta, False, clone.current_player, root_color, end_time
            )
            
            if score > value:
                value = score
                best_move = move
                
            alpha = max(alpha, value)
            if alpha >= beta:
                break # Beta cutoff
    else:
        value = math.inf
        for move in moves:
            clone = board.copy()
            make_move(clone, move)
            score = alpha_beta(
                clone, depth - 1, alpha, beta, True, clone.current_player, root_color, end_time
            )
            
            if score < value:
                value = score
                best_move = move
                
            beta = min(beta, value)
            if beta <= alpha:
                break # Alpha cutoff
                
    # 6. Store in Transposition Table
    tt_flag = FLAG_EXACT
    if value <= alpha:
        tt_flag = FLAG_UPPERBOUND
    elif value >= beta:
        tt_flag = FLAG_LOWERBOUND
        
    TRANSPOSITION_TABLE[board_key] = (depth, int(value), tt_flag, best_move)
    
    return int(value)

def choose_ai_move(
    board: Board,
    color: Color,
    max_depth: int,
    randomness: float = 0.0,
    time_limit: float = 1.0
) -> Optional[Move]:
    """
    Iterative Deepening Search with Time Limit.
    """
    moves = generate_legal_moves(board, color)
    if not moves:
        return None
        
    # If only one move, just play it
    if len(moves) == 1:
        return moves[0]

    start_time = time.time()
    end_time = start_time + time_limit - TIME_BUFFER
    
    best_move = random.choice(moves) # Default fallback
    
    # Search Loop
    # We start from depth 1 up to max_depth
    # We always keep the best move from the previous completed depth
    
    for current_depth in range(1, max_depth + 1):
        try:
            # We want to find the move that maximizes score for 'color'
            # So root call is maximizing=True
            
            best_score = -math.inf
            current_best_move = None
            
            # Root level move ordering
            # Use results from previous iteration if available (TT)
            moves = order_moves(moves, board)
            
            alpha = -math.inf
            beta = math.inf
            
            for move in moves:
                if time.time() > end_time:
                    raise TimeLimitExceeded
                
                clone = board.copy()
                make_move(clone, move)
                
                score = alpha_beta(
                    clone, 
                    current_depth - 1, 
                    alpha, 
                    beta, 
                    False, # Next is minimizing (opponent)
                    clone.current_player, 
                    color, # Root color
                    end_time
                )
                
                if score > best_score:
                    best_score = score
                    current_best_move = move
                
                alpha = max(alpha, best_score)
                
            # If we completed this depth, update best_move
            if current_best_move:
                best_move = current_best_move
                
        except TimeLimitExceeded:
            # Time is up, stop searching and use best_move from previous depth (or current if partial found?)
            # Usually safer to use previous depth's best move unless we found a better one at root already.
            # But here we updated best_move only after full depth completion? 
            # Actually, let's stick to the best completed depth result.
            break
            
    # Apply randomness if requested (only for Easy/Medium usually)
    # For high randomness, we might ignore the search result, but that defeats the optimization purpose.
    # The existing logic did: if randomness > 0, pick from top moves.
    # With iterative deepening, getting "top N moves" is harder unless we store them.
    # For now, if randomness > 0.2 (Easy), we might just pick a random move from the legal ones 
    # periodically, OR we can add noise to the evaluation.
    # Let's keep it simple: strict best move for Hard, slight chance of sub-optimal for Easy.
    
    if randomness > 0:
        # Simple implementation: with probability 'randomness', pick a random 2nd best move?
        # Or just return random move if randomness is high?
        if random.random() < randomness:
             return random.choice(moves)
             
    return best_move
