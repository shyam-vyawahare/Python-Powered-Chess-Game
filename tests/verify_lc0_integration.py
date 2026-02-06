import sys
import os
import time

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from chess_game.engine.lc0_engine import LC0Engine

def test_lc0():
    print("Initializing LC0 Engine...")
    try:
        engine = LC0Engine()
    except Exception as e:
        print(f"Failed to init engine: {e}")
        return

    print("Engine initialized.")
    
    fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    print(f"Requesting move for start pos (100ms)...")
    
    start = time.time()
    move = engine.get_best_move(fen, 100)
    end = time.time()
    
    print(f"Best move: {move}")
    print(f"Time taken: {end - start:.4f}s")
    
    if move:
        print("SUCCESS: Engine returned a move.")
    else:
        print("FAILURE: Engine returned None.")

    print("Quitting engine...")
    engine.quit()
    print("Done.")

if __name__ == "__main__":
    test_lc0()
