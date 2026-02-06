import math
import random
import time
from typing import Optional, List, Tuple, Dict
from .board import Board
from .pieces import PieceType, piece_values, Piece
from .utils import Color, Move
from .game_logic import generate_legal_moves, make_move, is_in_check, get_algebraic_notation
from .learning import ChessLearningSystem

LEARNING_SYSTEM = ChessLearningSystem()

# Center squares for positional bonus
center_squares = {(3, 3), (3, 4), (4, 3), (4, 4)}

# Transposition Table
# Key: board_key
# Value: (depth, score, flag, best_move_index)
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
    "Easy": {"depth": 1, "randomness": 0.2, "time_limit": 0.03},
    "Medium": {"depth": 2, "randomness": 0.1, "time_limit": 0.08},
    "Hard": {"depth": 3, "randomness": 0.0, "time_limit": 0.15},
}

# --- Piece-Square Tables ---
# Values are for WHITE from bottom (row 7) to top (row 0).
# For BLACK, we flip the row index (row = 7 - row).

PST_PAWN = [
    [0,  0,  0,  0,  0,  0,  0,  0],
    [50, 50, 50, 50, 50, 50, 50, 50],
    [10, 10, 20, 30, 30, 20, 10, 10],
    [5,  5, 10, 25, 25, 10,  5,  5],
    [0,  0,  0, 20, 20,  0,  0,  0],
    [5, -5,-10,  0,  0,-10, -5,  5],
    [5, 10, 10,-20,-20, 10, 10,  5],
    [0,  0,  0,  0,  0,  0,  0,  0]
]

PST_KNIGHT = [
    [-50,-40,-30,-30,-30,-30,-40,-50],
    [-40,-20,  0,  0,  0,  0,-20,-40],
    [-30,  0, 10, 15, 15, 10,  0,-30],
    [-30,  5, 15, 20, 20, 15,  5,-30],
    [-30,  0, 15, 20, 20, 15,  0,-30],
    [-30,  5, 10, 15, 15, 10,  5,-30],
    [-40,-20,  0,  5,  5,  0,-20,-40],
    [-50,-40,-30,-30,-30,-30,-40,-50]
]

PST_BISHOP = [
    [-20,-10,-10,-10,-10,-10,-10,-20],
    [-10,  0,  0,  0,  0,  0,  0,-10],
    [-10,  0,  5, 10, 10,  5,  0,-10],
    [-10,  5,  5, 10, 10,  5,  5,-10],
    [-10,  0, 10, 10, 10, 10,  0,-10],
    [-10, 10, 10, 10, 10, 10, 10,-10],
    [-10,  5,  0,  0,  0,  0,  5,-10],
    [-20,-10,-10,-10,-10,-10,-10,-20]
]

PST_ROOK = [
    [0,  0,  0,  0,  0,  0,  0,  0],
    [5, 10, 10, 10, 10, 10, 10,  5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [0,  0,  0,  5,  5,  0,  0,  0]
]

PST_QUEEN = [
    [-20,-10,-10, -5, -5,-10,-10,-20],
    [-10,  0,  0,  0,  0,  0,  0,-10],
    [-10,  0,  5,  5,  5,  5,  0,-10],
    [-5,  0,  5,  5,  5,  5,  0, -5],
    [0,  0,  5,  5,  5,  5,  0, -5],
    [-10,  5,  5,  5,  5,  5,  0,-10],
    [-10,  0,  5,  0,  0,  0,  0,-10],
    [-20,-10,-10, -5, -5,-10,-10,-20]
]

PST_KING_MID = [
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-20,-30,-30,-40,-40,-30,-30,-20],
    [-10,-20,-20,-20,-20,-20,-20,-10],
    [20, 20,  0,  0,  0,  0, 20, 20],
    [20, 30, 10,  0,  0, 10, 30, 20]
]

PST_KING_END = [
    [-50,-40,-30,-20,-20,-30,-40,-50],
    [-30,-20,-10,  0,  0,-10,-20,-30],
    [-30,-10, 20, 30, 30, 20,-10,-30],
    [-30,-10, 30, 40, 40, 30,-10,-30],
    [-30,-10, 30, 40, 40, 30,-10,-30],
    [-30,-10, 20, 30, 30, 20,-10,-30],
    [-30,-30,  0,  0,  0,  0,-30,-30],
    [-50,-30,-30,-30,-30,-30,-30,-50]
]

def get_pst_value(piece_type: PieceType, row: int, col: int, color: Color, is_endgame: bool = False) -> int:
    table = None
    if piece_type == PieceType.PAWN: table = PST_PAWN
    elif piece_type == PieceType.KNIGHT: table = PST_KNIGHT
    elif piece_type == PieceType.BISHOP: table = PST_BISHOP
    elif piece_type == PieceType.ROOK: table = PST_ROOK
    elif piece_type == PieceType.QUEEN: table = PST_QUEEN
    elif piece_type == PieceType.KING: 
        table = PST_KING_END if is_endgame else PST_KING_MID
    
    if table is None:
        return 0
        
    if color == Color.WHITE:
        return table[row][col]
    else:
        # Mirror for Black
        return table[7 - row][col]

def clear_ai_cache() -> None:
    """Clears the transposition table to free memory."""
    TRANSPOSITION_TABLE.clear()

def is_endgame_phase(board: Board) -> bool:
    # Simple endgame detection: No Queens or few pieces
    queens = 0
    pieces_count = 0
    for r in range(8):
        for c in range(8):
            p = board.grid[r][c]
            if p:
                pieces_count += 1
                if p.kind == PieceType.QUEEN:
                    queens += 1
    return queens == 0 or pieces_count < 12

def evaluate_king_safety(board: Board, color: Color) -> int:
    # Basic King Safety: Pawn Shield and Position
    # Find King
    king_pos = None
    for r in range(8):
        for c in range(8):
            p = board.grid[r][c]
            if p and p.kind == PieceType.KING and p.color == color:
                king_pos = (r, c)
                break
        if king_pos: break
    
    if not king_pos: return -10000 # Should not happen
    
    score = 0
    r, c = king_pos
    
    # Castling Bonus / Position Safety
    if color == Color.WHITE:
        if r == 7 and (c == 6 or c == 2): score += 100 # Castled (Stronger bonus)
        elif r == 7 and c == 4: score -= 50 # Stuck in center (Stronger penalty)
    else:
        if r == 0 and (c == 6 or c == 2): score += 100
        elif r == 0 and c == 4: score -= 50
        
    # Pawn Shield (only relevant if back rank)
    if (color == Color.WHITE and r == 7) or (color == Color.BLACK and r == 0):
        # Check pawns in front of king
        direction = -1 if color == Color.WHITE else 1
        shield_row = r + direction
        
        if 0 <= shield_row < 8:
            for col_offset in [-1, 0, 1]:
                check_c = c + col_offset
                if 0 <= check_c < 8:
                    p = board.grid[shield_row][check_c]
                    if p and p.kind == PieceType.PAWN and p.color == color:
                        score += 30 # Good shield (Stronger)
                    else:
                        # Check one more step forward for pushed pawn
                        shield_row_2 = r + (direction * 2)
                        if 0 <= shield_row_2 < 8:
                             p2 = board.grid[shield_row_2][check_c]
                             if p2 and p2.kind == PieceType.PAWN and p2.color == color:
                                 score += 15 # Slightly advanced
                             else:
                                 score -= 25 # Open file/No shield (Stronger penalty)
    
    return score

def evaluate_board(board: Board, color: Color) -> int:
    """
    Enhanced evaluation function.
    Positive score favors 'color'.
    Includes: Material, PST, King Safety, Mobility (Implicit), Tactics.
    """
    material = 0
    positional = 0
    is_endgame = is_endgame_phase(board)
    
    # Development Bonus (Minor pieces)
    dev_bonus = 0
    
    for row in range(8):
        for col in range(8):
            piece = board.grid[row][col]
            if piece is None:
                continue
            
            # Base Material
            val = piece_values[piece.kind]
            # Positional Bonus from PST
            pst = get_pst_value(piece.kind, row, col, piece.color, is_endgame)
            
            total_piece_val = val + pst
            
            if piece.color is color:
                material += total_piece_val
                
                # Development Bonus
                if not is_endgame:
                    if piece.kind in (PieceType.KNIGHT, PieceType.BISHOP):
                        # Bonus if not on starting rank
                        start_rank = 7 if color == Color.WHITE else 0
                        if row != start_rank:
                            dev_bonus += 20 # Increased bonus
            else:
                material -= total_piece_val
                
                if not is_endgame:
                    if piece.kind in (PieceType.KNIGHT, PieceType.BISHOP):
                        start_rank = 7 if piece.color == Color.WHITE else 0
                        if row != start_rank:
                            dev_bonus -= 20
    
    # King Safety
    material += evaluate_king_safety(board, color)
    material -= evaluate_king_safety(board, color.opposite)
    
    # Tactical Awareness: Bonus for giving check / Threatening
    # Check if opponent is in check
    if is_in_check(board, color.opposite):
        material += 75 # Bonus for checking opponent (Increased)
    
    # Check if we are in check (Penalty)
    if is_in_check(board, color):
        material -= 75
    
    return material + positional + dev_bonus

def evaluate_terminal(board: Board, color_to_move: Color, root_color: Color) -> Optional[int]:
    moves = generate_legal_moves(board, color_to_move)
    if moves:
        return None # Not terminal
        
    if is_in_check(board, color_to_move):
        # Checkmate
        if color_to_move is root_color:
            return -1000000 # Root lost
        else:
            return 1000000 # Root won
    else:
        # Stalemate
        return 0

def order_moves(moves: List[Move], board: Board) -> List[Move]:
    """
    Sort moves by estimated potential:
    1. Checkmates (Instant Win)
    2. Captures (MVV-LVA)
    3. Checks
    4. Promotions
    5. Threatening moves (Attacking high value piece)
    6. Center Control / Development
    """
    scored: List[Tuple[int, Move]] = []
    
    for move in moves:
        score = 0
        
        # 1. Captures (MVV-LVA)
        target = board.grid[move.to_row][move.to_col]
        is_capture = target is not None or move.is_en_passant
        
        if is_capture:
            attacker = board.grid[move.from_row][move.from_col]
            attacker_val = piece_values[attacker.kind] if attacker else 100
            victim_val = piece_values[target.kind] if target else piece_values[PieceType.PAWN]
            # Base 100,000 for captures
            score += 100000 + (victim_val * 10) - attacker_val

        # 2. Checks and Checkmates
        # We simulate the move to check if it gives check.
        clone = board.copy()
        make_move(clone, move)
        if is_in_check(clone, board.current_player.opposite):
            # It's a check. Check for Mate (Expensive but critical)
            opp_moves = generate_legal_moves(clone, board.current_player.opposite)
            if not opp_moves:
                score += 10000000 # Checkmate! Priority #1
            else:
                score += 50000 # Priority #3 (Below Captures usually, but depends on values)
        
        # 3. Promotions
        if move.promotion:
            score += 25000 + piece_values[move.promotion]
            
        # 4. Threats (Attacking higher value piece)
        # Simplified threat: Do we attack a Queen or Rook?
        # Skipped for performance as 'Checks' covers the most immediate tactical threats
        
        # 5. Castling
        if move.is_castling:
            score += 1000

        # 6. Center Control
        if (move.to_row, move.to_col) in center_squares:
            score += 100
            
        scored.append((score, move))
        
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored]

def is_obvious_blunder(board: Board, move: Move, color: Color) -> bool:
    """
    Fast check if a move is a disastrous blunder.
    Checks if:
    1. It hangs a Queen or Rook for free (or bad trade).
    2. It leads to immediate checkmate (Depth 1 check).
    """
    # Simulate move
    clone = board.copy()
    make_move(clone, move)
    opponent = color.opposite
    
    opp_moves = generate_legal_moves(clone, opponent)
    if not opp_moves:
        if is_in_check(clone, opponent):
             return False # Checkmate delivered!
        return False # Stalemate
        
    # Check for immediate threats from opponent
    my_queen_pos = None
    my_rooks_pos = []
    
    # Locate my major pieces
    for r in range(8):
        for c in range(8):
            p = clone.grid[r][c]
            if p and p.color == color:
                if p.kind == PieceType.QUEEN:
                    my_queen_pos = (r, c)
                elif p.kind == PieceType.ROOK:
                    my_rooks_pos.append((r, c))
    
    # Check if we left our King in check (Illegal, but generate_legal_moves shouldn't produce it)
    if is_in_check(clone, color):
        return True

    for opp_move in opp_moves:
        attacker = clone.grid[opp_move.from_row][opp_move.from_col]
        attacker_val = piece_values[attacker.kind] if attacker else 100
        
        # Check 1: Does opponent capture Queen?
        if my_queen_pos and (opp_move.to_row, opp_move.to_col) == my_queen_pos:
            # Queen Value = 900.
            # If captured by anything less than Queen -> Blunder (Bad trade).
            if attacker_val < 900:
                return True
            
            # If captured by Queen -> Check recapture.
            # Can we recapture on my_queen_pos?
            clone2 = clone.copy()
            make_move(clone2, opp_move)
            # Check if any of our moves land on my_queen_pos
            can_recapture = False
            my_replies = generate_legal_moves(clone2, color)
            for reply in my_replies:
                if (reply.to_row, reply.to_col) == my_queen_pos:
                    can_recapture = True
                    break
            
            if not can_recapture:
                return True # Hanging Queen for free
            
        # Check 2: Does opponent capture Rook?
        for r_pos in my_rooks_pos:
             if (opp_move.to_row, opp_move.to_col) == r_pos:
                 # Rook Value = 500.
                 if attacker_val < 500:
                     return True
                 
                 # If captured by Rook/Queen -> Check recapture
                 if attacker_val >= 500: # Actually if captured by Queen (900), it's a good trade for us!
                     # If captured by Queen (900) vs Rook (500) -> Opponent blunder, not ours.
                     # If captured by Rook (500) vs Rook (500) -> Check recapture.
                     if attacker_val == 500:
                         clone2 = clone.copy()
                         make_move(clone2, opp_move)
                         can_recapture = False
                         my_replies = generate_legal_moves(clone2, color)
                         for reply in my_replies:
                             if (reply.to_row, reply.to_col) == r_pos:
                                 can_recapture = True
                                 break
                         if not can_recapture:
                             return True
                 
        # Check 3: Immediate Checkmate
        clone2 = clone.copy()
        make_move(clone2, opp_move)
        if is_in_check(clone2, color):
            our_reply_moves = generate_legal_moves(clone2, color)
            if not our_reply_moves:
                return True # Mate found

    return False

def alpha_beta(
    board: Board,
    depth: int,
    alpha: int,
    beta: int,
    maximizing: bool,
    color_to_move: Color,
    root_color: Color,
    end_time: float,
    learning_mode: str = "standard"
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
    moves = order_moves(moves, board)
    
    best_move = None
    
    # 5. Search
    if maximizing:
        value = -math.inf
        for move in moves:
            clone = board.copy()
            make_move(clone, move)
            score = alpha_beta(
                clone, depth - 1, alpha, beta, False, clone.current_player, root_color, end_time, learning_mode
            )
            
            # Apply Learning Influence
            if learning_mode in ("standard", "full"):
                # Blunder Avoidance
                penalty = LEARNING_SYSTEM.get_blunder_penalty(board_key, move)
                score -= penalty
                
            if learning_mode == "full":
                # Tactical Awareness
                bonus = LEARNING_SYSTEM.get_tactical_bonus(board_key, move)
                score += bonus

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
                clone, depth - 1, alpha, beta, True, clone.current_player, root_color, end_time, learning_mode
            )

            # Apply Learning Influence
            if learning_mode in ("standard", "full"):
                # Blunder Avoidance (Penalty makes move worse for minimizer -> Higher score)
                penalty = LEARNING_SYSTEM.get_blunder_penalty(board_key, move)
                score += penalty
            
            if learning_mode == "full":
                 # Tactical Bonus (Makes move better for minimizer -> Lower score)
                 bonus = LEARNING_SYSTEM.get_tactical_bonus(board_key, move)
                 score -= bonus

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
    time_limit: float = 0.1,
    move_history: Optional[List[str]] = None
) -> Optional[Move]:
    """
    Iterative Deepening Search with Strict Time Limit.
    """
    start_time = time.time()
    end_time = start_time + time_limit - 0.005 # 5ms buffer
    
    moves = generate_legal_moves(board, color)
    if not moves:
        return None
        
    # Fail-safe: Pick a random move immediately
    best_move_so_far = random.choice(moves)

    # 0. Opening Book Learning (Only if enough time)
    if move_history is not None and len(move_history) < 20 and randomness < 0.5:
        opening_move_str = LEARNING_SYSTEM.get_opening_move(move_history)
        if opening_move_str:
            for m in moves:
                if get_algebraic_notation(board, m) == opening_move_str:
                    return m
        
    if len(moves) == 1:
        return moves[0]

    # Filter Blunders (Global Check)
    safe_moves = []
    try:
        for move in moves:
            if time.time() > end_time:
                break
            if not is_obvious_blunder(board, move, color):
                safe_moves.append(move)
    except:
        pass
    
    if safe_moves:
        moves = safe_moves
        best_move_so_far = random.choice(moves)

    # Determine Learning Mode
    learning_mode = "minimal"
    if max_depth >= 3:
        learning_mode = "full"
    elif max_depth >= 2:
        learning_mode = "standard"
    
    # Iterative Deepening
    try:
        current_depth = 1
        while current_depth <= max_depth:
            if time.time() >= end_time:
                break
                
            # Search
            best_move_this_depth = None
            best_score_this_depth = -math.inf
            
            # Move Ordering
            ordered_moves = order_moves(moves, board)
            
            alpha = -math.inf
            beta = math.inf
            
            for move in ordered_moves:
                if time.time() >= end_time:
                    raise TimeLimitExceeded
                    
                clone = board.copy()
                make_move(clone, move)
                
                score = alpha_beta(
                    clone, 
                    current_depth - 1, 
                    alpha, 
                    beta, 
                    False, # Next is minimizing for us
                    clone.current_player, 
                    color, 
                    end_time,
                    learning_mode
                )
                
                if score > best_score_this_depth:
                    best_score_this_depth = score
                    best_move_this_depth = move
                
                alpha = max(alpha, score)
                if alpha >= beta:
                    break 
            
            if best_move_this_depth:
                best_move_so_far = best_move_this_depth
                
            current_depth += 1
            
    except TimeLimitExceeded:
        pass 
        
    return best_move_so_far
