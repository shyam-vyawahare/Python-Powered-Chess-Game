Python Chess Game
==================

Overview
--------

This is a console-based chess game implemented in Python. It supports:
- Full chess rules, including castling, en passant, and pawn promotion
- Two-player mode (human vs human)
- Single-player mode (human vs computer) with multiple difficulty levels
- Check, checkmate, stalemate detection
- Optional draws by agreement, threefold repetition, and fifty-move rule
- Move history display and basic undo functionality

Project Structure
-----------------

- `chess_game/`
  - `main.py` – entry point and game loop
  - `board.py` – board representation and ASCII display
  - `pieces.py` – piece definitions and values
  - `game_logic.py` – move generation, validation, and game state
  - `ai_opponent.py` – computer opponent using minimax with alpha-beta pruning
  - `utils.py` – helper types and coordinate utilities
- `RUN.bat` – Windows launcher
- `SETUP.bat` – Windows one-time setup for dependencies
- `run.sh` – Linux/macOS launcher
- `requirements.txt` – Python dependencies (currently none)

Requirements
------------

- Python 3.7 or newer
- A terminal capable of displaying Unicode chess symbols

Running on Windows
------------------

Double-click `RUN.bat` in the project root or run:

    RUN.bat

The script:
- Verifies that Python is installed and at least version 3.7
- Installs dependencies from `requirements.txt` if present
- Launches the chess game

Running on Linux/macOS
----------------------

Make the launcher executable (once):

    chmod +x run.sh

Then run:

    ./run.sh

The script:
- Verifies that `python3` is installed and at least version 3.7
- Installs dependencies from `requirements.txt` if present
- Launches the chess game

Game Controls
-------------

- Enter moves as:
  - `e2 e4`
  - `e2-e4`
  - `e2e4`
- Commands during the game:
  - `resign` – resign the game
  - `draw` – offer or accept a draw
  - `undo` – undo the last move (if available)
  - `history` – show move history
  - `moves e2` – list legal moves for the piece on `e2`
  - `quit` or `exit` – terminate the game

Pawn Promotion
--------------

When a pawn reaches the last rank, you can promote it to:

- Queen (`Q`)
- Rook (`R`)
- Bishop (`B`)
- Knight (`N`)

In human games, the program will prompt you to choose a promotion piece where applicable. The AI promotes pawns automatically based on its evaluation.

"# Python-Powered-Chess-Game" 
