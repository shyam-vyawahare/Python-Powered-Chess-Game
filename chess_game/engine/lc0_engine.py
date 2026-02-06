import subprocess
import os
import threading
import queue
import time
from typing import Optional

class LC0Engine:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.output_queue = queue.Queue()
        self.is_running = False
        self._reader_thread = None
        
        # Path Resolution
        # chess_game/engine/lc0_engine.py -> chess_game/engine
        ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
        # chess_game/engine -> chess_game
        CHESS_GAME_DIR = os.path.dirname(ENGINE_DIR)
        # chess_game -> ProjectRoot
        PROJECT_ROOT = os.path.dirname(CHESS_GAME_DIR)
        
        self.lc0_exe = os.path.join(PROJECT_ROOT, "engines", "lc0.exe")
        self.network_path = os.path.join(PROJECT_ROOT, "engines", "791556.pb.gz")
        
        if not os.path.exists(self.lc0_exe):
            raise FileNotFoundError(f"LC0 executable not found at: {self.lc0_exe}")
        if not os.path.exists(self.network_path):
            raise FileNotFoundError(f"LC0 network not found at: {self.network_path}")

        self._start_engine()

    def _start_engine(self):
        # Start LC0 with the weights file argument
        cmd = [self.lc0_exe, f"--weights={self.network_path}"]
        
        # Creation flag for Windows to not show console window
        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW
            
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
            creationflags=creationflags
        )
        self.is_running = True
        
        # Start reader thread
        self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self._reader_thread.start()
        
        # Initialize UCI
        self.send_command("uci")
        self._wait_for("uciok", timeout=5)

    def _read_output(self):
        """Reads stdout from the engine and puts lines into a queue."""
        while self.is_running and self.process:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                self.output_queue.put(line.strip())
            except Exception:
                break

    def send_command(self, command: str):
        """Sends a command to the engine."""
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(f"{command}\n")
                self.process.stdin.flush()
            except Exception as e:
                print(f"Error sending command to engine: {e}")

    def _wait_for(self, target_text: str, timeout: float = 2.0) -> bool:
        """Waits for specific text in the output."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Peek at queue or consume? We generally consume uci handshake
                # For simplicity in this synchronous init phase, we consume.
                line = self.output_queue.get(timeout=0.1)
                if target_text in line:
                    return True
            except queue.Empty:
                continue
        return False

    def new_game(self):
        """Ready the engine for a new game."""
        self.send_command("ucinewgame")
        self.send_command("isready")
        self._wait_for("readyok", timeout=2)

    def get_best_move(self, fen: str, movetime_ms: int = 100) -> Optional[str]:
        """
        Sends position and go command, waits for bestmove.
        This is a blocking call intended to be run in a thread.
        """
        # Clear queue of old messages
        with self.output_queue.mutex:
            self.output_queue.queue.clear()
            
        self.send_command(f"position fen {fen}")
        self.send_command(f"go movetime {movetime_ms}")
        
        # Wait for bestmove
        # We can wait slightly longer than movetime_ms because of overhead
        timeout = (movetime_ms / 1000.0) + 2.0 
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                line = self.output_queue.get(timeout=0.1)
                if line.startswith("bestmove"):
                    # Format: bestmove e2e4 [ponder ...]
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1]
            except queue.Empty:
                continue
                
        return None

    def quit(self):
        """Stops the engine process."""
        self.is_running = False
        if self.process:
            self.send_command("quit")
            try:
                self.process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
