import json
import os
from typing import Dict, List, Optional, Any, Tuple
from .utils import Color, Move
from .pieces import piece_values, PieceType
from .game_logic import GameSnapshot  # Ensure this import works

LEARNING_FILE = "chess_learning.json"

class ChessLearningSystem:
    def __init__(self, filepath: str = LEARNING_FILE):
        self.filepath = filepath
        self.data: Dict[str, Any] = {
            "openings": {},         # Sequence -> {wins, draws, losses}
            "blunders": {},         # FEN hash -> {move_str -> count}
            "tactics": {},          # FEN hash -> {move_str -> count} (Successful tactics)
            "player_stats": {       # General stats about human player
                "games_played": 0,
                "win_rate": 0.0,
                "style": "unknown"  # aggressive, passive, balanced
            }
        }
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    loaded = json.load(f)
                    # Merge loaded data with default structure to ensure all keys exist
                    for k, v in loaded.items():
                        if k in self.data:
                            self.data[k] = v
            except Exception as e:
                print(f"Error loading learning data: {e}")

    def save(self):
        try:
            with open(self.filepath, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error saving learning data: {e}")

    def record_game(self, history: List[GameSnapshot], result: str, ai_color: Color):
        """
        Learn from the completed game.
        """
        is_draw = "Draw" in result
        
        # Determine AI result
        ai_won = False
        if not is_draw:
            if ai_color == Color.WHITE and "White wins" in result:
                ai_won = True
            elif ai_color == Color.BLACK and "Black wins" in result:
                ai_won = True
        
        # Update Player Stats
        self.data["player_stats"]["games_played"] += 1
        if not ai_won and not is_draw:
             # Human won
             pass # Logic to update win rate could be added
        
        # 1. Opening Learning (First 20 plies)
        if not history:
            return

        final_snapshot = history[-1]
        move_log = final_snapshot.move_log
        
        opening_depth = min(len(move_log), 20)
        current_seq = []
        
        # Only learn openings if AI won or drew
        if ai_won or is_draw:
            for i in range(opening_depth):
                move_str = move_log[i]
                current_seq.append(move_str)
                seq_key = " ".join(current_seq)
                
                if seq_key not in self.data["openings"]:
                    self.data["openings"][seq_key] = {"w": 0, "d": 0, "l": 0}
                
                stats = self.data["openings"][seq_key]
                if is_draw:
                    stats["d"] += 1
                elif ai_won:
                    stats["w"] += 1

        # 2. Blunder & Tactic Detection
        # We look for moves where evaluation changed significantly after opponent's reply
        from .game_logic import material_balance
        
        for i in range(len(history) - 2):
            snapshot = history[i]
            # Check if it was AI's turn to move
            if snapshot.board.current_player == ai_color:
                # AI made a move. history[i+1] is the state after AI move.
                # history[i+2] is the state after Opponent's reply.
                
                move = history[i+1].last_move
                if not move: continue

                before_material = material_balance(snapshot.board, ai_color)
                after_reply_material = material_balance(history[i+2].board, ai_color)
                
                diff = after_reply_material - before_material
                
                board_key = snapshot.board.board_key()

                # Blunder Detection: Lost significant material
                if diff <= -200: # Slightly more sensitive than 250
                    self._record_blunder(board_key, move)
                
                # Tactic Detection: Gained significant material (and held it)
                # We want to ensure the gain persists.
                # But here we only look 2 plies ahead (AI move, Opponent Reply).
                # If after reply we are up material compared to start, we did something good.
                if diff >= 200:
                     self._record_tactic(board_key, move)
                    
        self.save()

    def _record_blunder(self, board_key: str, move: Move):
        move_str = self._move_to_str(move)
        if board_key not in self.data["blunders"]:
            self.data["blunders"][board_key] = {}
        
        if move_str not in self.data["blunders"][board_key]:
            self.data["blunders"][board_key][move_str] = 0
        
        self.data["blunders"][board_key][move_str] += 1

    def _record_tactic(self, board_key: str, move: Move):
        move_str = self._move_to_str(move)
        if "tactics" not in self.data:
            self.data["tactics"] = {}
            
        if board_key not in self.data["tactics"]:
            self.data["tactics"][board_key] = {}
            
        if move_str not in self.data["tactics"][board_key]:
            self.data["tactics"][board_key][move_str] = 0
            
        self.data["tactics"][board_key][move_str] += 1

    def get_opening_move(self, move_history: List[str]) -> Optional[str]:
        """Suggest a move based on history."""
        # Current sequence
        seq_key = " ".join(move_history)
        
        # Look for continuations in our data
        # We need keys that start with seq_key + " " + next_move
        # This is a bit inefficient to search all keys. 
        # A tree structure would be better, but for lightweight JSON, we iterate or restructure.
        # Optimization: We only have 'openings' dictionary.
        # Let's just look for direct children if we can.
        
        candidates = []
        
        # If no history, look for single moves
        prefix = seq_key + " " if seq_key else ""
        
        for k, stats in self.data["openings"].items():
            if k.startswith(prefix):
                # Check if it is a direct child (one more move)
                remainder = k[len(prefix):]
                if " " not in remainder: # It's exactly one move more
                    # Evaluate success rate
                    total = stats["w"] + stats["d"] + stats["l"]
                    if total > 0:
                        # Simple score: Win=1, Draw=0.5
                        score = (stats["w"] * 1.0 + stats["d"] * 0.5) / total
                        if score > 0.4: # Only suggest if not terrible
                            candidates.append((remainder, score, total))
        
        if not candidates:
            return None
            
        # Sort by score then popularity
        candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return candidates[0][0]

    def get_blunder_penalty(self, board_key: str, move: Move) -> int:
        """Return penalty score if move is a known blunder."""
        if board_key in self.data["blunders"]:
            move_str = self._move_to_str(move)
            count = self.data["blunders"][board_key].get(move_str, 0)
            if count > 0:
                return count * 100 # Heavy penalty per occurrence
        return 0

    def get_tactical_bonus(self, board_key: str, move: Move) -> int:
        """Return bonus score if move is a known successful tactic."""
        if "tactics" in self.data and board_key in self.data["tactics"]:
            move_str = self._move_to_str(move)
            count = self.data["tactics"][board_key].get(move_str, 0)
            if count > 0:
                return count * 50 # Bonus per occurrence
        return 0

    def _move_to_str(self, move: Move) -> str:
        return f"{move.from_row},{move.from_col},{move.to_row},{move.to_col},{move.promotion}"
