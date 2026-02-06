import subprocess
import os
import threading
import queue
import time
import random
from typing import Optional, Dict, List

class LC0Engine:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.output_queue = queue.Queue()
        self.is_running = False
        self.is_searching = False
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

    def restart(self):
        """Restarts the engine process."""
        self.quit()
        time.sleep(0.2)
        self._start_engine()

    def _validate_fen(self, fen: str) -> bool:
        """Basic FEN validation."""
        parts = fen.split()
        if len(parts) < 2: return False
        ranks = parts[0].split('/')
        if len(ranks) != 8: return False
        if parts[1] not in ['w', 'b']: return False
        return True

    def get_best_move(self, fen: str, limits: Optional[Dict] = None) -> Optional[str]:
        """
        Sends position and go command, waits for bestmove.
        Supported limits: 'movetime', 'nodes', 'multipv'
        If 'multipv' > 1, it will pick a random move from the top N candidates (simulated 'noise').
        """
        if self.is_searching:
            print("Engine busy: Search already in progress")
            return None
            
        if not self._validate_fen(fen):
            print(f"Invalid FEN: {fen}")
            return None

        self.is_searching = True
        
        # Default limits
        if isinstance(limits, int):
            limits = {'movetime': limits}
        limits = limits or {}
        movetime = limits.get('movetime', 1000)
        nodes = limits.get('nodes', None)
        multipv = limits.get('multipv', 1)
        
        candidates = {}  # Map multipv_id -> move
        
        try:
            # Clear queue
            with self.output_queue.mutex:
                self.output_queue.queue.clear()
                
            # Configure MultiPV if needed
            if multipv > 1:
                self.send_command(f"setoption name MultiPV value {multipv}")
            else:
                self.send_command("setoption name MultiPV value 1")
            
            # Build go command
            cmd = "go"
            if nodes:
                cmd += f" nodes {nodes}"
            else:
                cmd += f" movetime {movetime}"
                
            self.send_command(f"position fen {fen}")
            self.send_command(cmd)
            
            # Timeout safety
            # If using nodes, we still need a fallback timeout.
            # 12000 nodes is fast (usually <2s), but on slow CPU could be 10s.
            # We set a generous timeout to prevent hanging.
            safety_timeout = 30.0
            if 'movetime' in limits:
                # If movetime is strict, use it + buffer
                safety_timeout = (limits['movetime'] / 1000.0) + 2.0
            
            start_time = time.time()
            
            while time.time() - start_time < safety_timeout:
                try:
                    line = self.output_queue.get(timeout=0.1)
                    
                    # Collect MultiPV candidates
                    # Format: info depth X ... multipv N ... pv e2e4 ...
                    if multipv > 1 and "pv" in line and "info" in line:
                         parts = line.split()
                         try:
                             # Extract MultiPV ID
                             mpv_id = 1
                             if "multipv" in parts:
                                 mpv_idx = parts.index("multipv")
                                 if mpv_idx + 1 < len(parts):
                                     mpv_id = int(parts[mpv_idx + 1])
                             
                             # Extract Move
                             pv_index = parts.index("pv")
                             if pv_index + 1 < len(parts):
                                 m = parts[pv_index + 1]
                                 candidates[mpv_id] = m
                         except (ValueError, IndexError):
                             pass

                    if line.startswith("bestmove"):
                        parts = line.split()
                        best_move = parts[1] if len(parts) >= 2 else None
                        
                        if multipv > 1 and candidates:
                             # Pick random from the latest Top N candidates
                             # We have candidates[1] (best), candidates[2] (2nd best), etc.
                             # If we asked for MultiPV 3, we should have keys 1, 2, 3.
                             # But maybe only 1 and 2 if 3 is bad.
                             available_moves = list(candidates.values())
                             if available_moves:
                                 # User said: "Easy -> pick from top 3"
                                 # Our AI_LEVELS sets multipv=3 for Easy.
                                 # So we just pick randomly from whatever we have.
                                 return random.choice(available_moves)
                        
                        return best_move
                        
                except queue.Empty:
                    continue
            
            print("Engine timeout.")
            return None
            
        finally:
            self.is_searching = False

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
