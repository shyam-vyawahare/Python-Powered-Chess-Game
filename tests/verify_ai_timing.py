import sys
import os
import time
import random
import unittest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from chess_game.ai_opponent import choose_ai_move, AI_SETTINGS
from chess_game.game_logic import Board, Color

class TestAITiming(unittest.TestCase):
    def setUp(self):
        self.board = Board()
        # Set up a board state where moves are possible
        self.board.setup_initial()

    def test_easy_mode_timing(self):
        """Verify Easy mode respects the 30ms time cap."""
        settings = AI_SETTINGS["Easy"]
        time_limit = settings["time_limit"]
        print(f"\nTesting Easy Mode (Limit: {time_limit}s)...")
        
        start = time.time()
        move = choose_ai_move(self.board, Color.BLACK, settings["depth"], settings["randomness"], time_limit)
        duration = time.time() - start
        
        print(f"Easy Mode took: {duration:.4f}s")
        self.assertLess(duration, time_limit + 0.05, "AI exceeded Easy time limit significantly") # Allow small overhead
        self.assertIsNotNone(move, "AI returned None in Easy mode")

    def test_medium_mode_timing(self):
        """Verify Medium mode respects the 80ms time cap."""
        settings = AI_SETTINGS["Medium"]
        time_limit = settings["time_limit"]
        print(f"\nTesting Medium Mode (Limit: {time_limit}s)...")
        
        start = time.time()
        move = choose_ai_move(self.board, Color.BLACK, settings["depth"], settings["randomness"], time_limit)
        duration = time.time() - start
        
        print(f"Medium Mode took: {duration:.4f}s")
        self.assertLess(duration, time_limit + 0.05, "AI exceeded Medium time limit significantly")
        self.assertIsNotNone(move, "AI returned None in Medium mode")

    def test_hard_mode_timing(self):
        """Verify Hard mode respects the 150ms time cap."""
        settings = AI_SETTINGS["Hard"]
        time_limit = settings["time_limit"]
        print(f"\nTesting Hard Mode (Limit: {time_limit}s)...")
        
        start = time.time()
        move = choose_ai_move(self.board, Color.BLACK, settings["depth"], settings["randomness"], time_limit)
        duration = time.time() - start
        
        print(f"Hard Mode took: {duration:.4f}s")
        self.assertLess(duration, time_limit + 0.05, "AI exceeded Hard time limit significantly")
        self.assertIsNotNone(move, "AI returned None in Hard mode")

if __name__ == '__main__':
    unittest.main()
