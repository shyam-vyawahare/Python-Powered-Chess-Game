from typing import Optional, Set, Tuple, List, Dict
from pathlib import Path
import pygame
import random
import threading
import queue
import os
import math
from ..game_logic import Game
from ..engine.lc0_engine import LC0Engine
from ..utils import Color, Move, indices_to_square, square_to_indices, PieceType
from ..pieces import Piece
from .chess_board_ui import BoardRenderer, BOARD_SIZE, SQUARE_SIZE
from .menu_handler import ButtonBar, Button
from .dialogs import PromotionDialog, MessageOverlay, WinningDialog


WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 720
PANEL_BG = (30, 30, 30)
TEXT_COLOR = (230, 230, 230)

# Turn States
TURN_PLAYER = "player"
TURN_AI = "ai"
TURN_LOCKED = "locked"

USEREVENT_AI_MOVE = pygame.USEREVENT + 1
USEREVENT_HINT_READY = pygame.USEREVENT + 2

class InteractionState:
    def __init__(self) -> None:
        self.selected: Optional[Tuple[int, int]] = None
        self.moves_from_selected: Set[Tuple[int, int]] = set()
        self.pending_promotion_moves: List[Move] = []
        self.hint_move: Optional[Move] = None
        self.awaiting_promotion = False
        self.dragging = False
        self.drag_start_pos: Optional[Tuple[int, int]] = None
        self.drag_offset: Tuple[int, int] = (0, 0)
        self.drag_piece: Optional[Piece] = None


class MoveAnimation:
    def __init__(
        self,
        renderer: BoardRenderer,
        board: Game,
        move: Move,
    ) -> None:
        self.renderer = renderer
        self.move = move
        self.start_time = pygame.time.get_ticks()
        self.duration = 250
        self.pieces: List[Tuple[pygame.Surface, Tuple[float, float], Tuple[float, float]]] = []
        self.captured_overlays: List[Tuple[pygame.Surface, Tuple[float, float]]] = []
        piece = board.board.get_piece(move.from_row, move.from_col)
        if piece is None:
            return
        rect_from = renderer.square_to_rect(move.from_row, move.from_col)
        rect_to = renderer.square_to_rect(move.to_row, move.to_col)
        image = renderer.piece_images.get(piece)
        if image is not None:
            self.pieces.append((image, rect_from.center, rect_to.center))
        captured = None
        if move.is_en_passant:
            direction = -1 if piece.color is Color.WHITE else 1
            captured_row = move.to_row + direction
            captured = board.board.get_piece(captured_row, move.to_col)
            if captured is not None:
                rect_cap = renderer.square_to_rect(captured_row, move.to_col)
                img_cap = renderer.piece_images.get(captured)
                if img_cap is not None:
                    self.captured_overlays.append((img_cap, rect_cap.center))
        else:
            captured = board.board.get_piece(move.to_row, move.to_col)
            if captured is not None:
                rect_cap = renderer.square_to_rect(move.to_row, move.to_col)
                img_cap = renderer.piece_images.get(captured)
                if img_cap is not None:
                    self.captured_overlays.append((img_cap, rect_cap.center))
        if move.is_castling and piece.kind is PieceType.KING:
            row = move.from_row
            if move.to_col == 6:
                rook_from_col = 7
                rook_to_col = 5
            else:
                rook_from_col = 0
                rook_to_col = 3
            rook = board.board.get_piece(row, rook_from_col)
            if rook is not None:
                rect_r_from = renderer.square_to_rect(row, rook_from_col)
                rect_r_to = renderer.square_to_rect(row, rook_to_col)
                img_rook = renderer.piece_images.get(rook)
                if img_rook is not None:
                    self.pieces.append((img_rook, rect_r_from.center, rect_r_to.center))

    def progress(self) -> float:
        elapsed = pygame.time.get_ticks() - self.start_time
        if elapsed <= 0:
            return 0.0
        if elapsed >= self.duration:
            return 1.0
        t = elapsed / self.duration
        return t * t * (3 - 2 * t)

    def is_done(self) -> bool:
        return self.progress() >= 1.0

class GameWindow:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Python Chess")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.running = True
        self.game = Game()
        self.board_renderer = BoardRenderer((40, (WINDOW_HEIGHT - BOARD_SIZE) // 2))
        self.side_font = pygame.font.SysFont("arial", 18)
        self.title_font = pygame.font.SysFont("arial", 48, bold=True)
        self.small_font = pygame.font.SysFont("arial", 14)
        self.button_font = pygame.font.SysFont("arial", 16)
        self.interaction = InteractionState()
        self.message_overlay = MessageOverlay(
            pygame.Rect(0, WINDOW_HEIGHT - 40, WINDOW_WIDTH, 30),
        )
        
        # Asset Paths
        self.base_dir = Path(__file__).resolve().parent
        self.assets_dir = self.base_dir / "assets"
        self.pieces_dir = self.assets_dir / "pieces"
        self.bg_dir = self.assets_dir / "background"
        self.sounds_dir = self.assets_dir / "sounds"
        
        # Load Sounds
        try:
            pygame.mixer.init()
        except Exception:
            pass
            
        self.sounds: Dict[str, pygame.mixer.Sound] = {}
        if self.sounds_dir.exists():
            sound_files = {
                "move-self": "move-self.mp3",
                "move-check": "move-check.mp3",
                "capture": "capture.mp3",
                "castle": "castle.mp3",
                "promote": "promote.mp3"
            }
            for key, filename in sound_files.items():
                path = self.sounds_dir / filename
                if path.exists():
                    try:
                        self.sounds[key] = pygame.mixer.Sound(str(path))
                    except Exception:
                        pass

        # Load Logo
        self.logo_image = None
        logo_path = self.assets_dir / "Cheerss.png"
        if logo_path.exists():
            try:
                img = pygame.image.load(str(logo_path)).convert_alpha()
                w = img.get_width()
                h = img.get_height()
                target_w = 500
                target_h = int(h * (target_w / w))
                self.logo_image = pygame.transform.smoothscale(img, (target_w, target_h))
            except Exception:
                pass

        # Load Piece Sets
        self.available_piece_sets = []
        if self.pieces_dir.exists():
            for item in self.pieces_dir.iterdir():
                if item.is_dir() and item.name != "sounds":
                    self.available_piece_sets.append(item.name)
        if "classic" not in self.available_piece_sets:
            self.available_piece_sets.append("classic")
        self.current_piece_set = "classic"

        # Initialize Pieces
        self.board_renderer.piece_images.load(self.pieces_dir / self.current_piece_set)
        self.board_renderer.piece_images.set_mode_images()
        
        # Load Backgrounds
        self.available_backgrounds = []
        if self.bg_dir.exists():
            for item in self.bg_dir.iterdir():
                if item.suffix.lower() in ['.jpg', '.png', '.jpeg']:
                    self.available_backgrounds.append(item)
        
        self.background_surface = None
        classic_bg = None
        for bg in self.available_backgrounds:
            if "classic" in bg.name.lower():
                classic_bg = bg
                break
                
        if classic_bg:
             self.load_background(classic_bg)
        elif self.available_backgrounds:
             self.load_background(self.available_backgrounds[0])
        else:
             self.background_surface = self._create_background()

        # Button bar below board
        button_y = (WINDOW_HEIGHT + BOARD_SIZE) // 2 + 10
        self.button_bar = ButtonBar(
            pygame.Rect(40, button_y, 360, 40),
        )
        self.button_bar.add_button("New Game", self.new_game)
        self.button_bar.add_button("Undo", self.undo_move)
        self.button_bar.add_button("Hint", self.hint)
        self.button_bar.add_button("Settings", self.menu_settings)
        
        self.btn_main_menu = Button(
            pygame.Rect(WINDOW_WIDTH - 160, button_y, 120, 40),
            "Main Menu",
            self.return_to_menu
        )
        
        self.mode_human_vs_ai = True
        self.human_color = Color.WHITE
        self.ai_color = Color.BLACK
        self.ai_level_names = ["Easy", "Medium", "Hard"]
        self.ai_level_index = 1
        self.ai_depth = 3
        self.ai_randomness = 0.1
        self.ai_time_limit = 1.0
        self.ai_thread: Optional[threading.Thread] = None
        self.ai_move_queue: queue.Queue = queue.Queue()
        self.promotion_dialog: Optional[PromotionDialog] = None
        self.winning_dialog: Optional[WinningDialog] = None
        self.current_animation: Optional[MoveAnimation] = None
        self.pending_move: Optional[Tuple[Move, bool]] = None
        self.state = "menu"
        self.settings = {
            "theme": "Green",
            "sound_move": True,
            "sound_capture": True,
            "highlight_check": False
        }

        self.turn_state = TURN_PLAYER
        self.ai_move_scheduled = False

        # Time Control Settings
        self.time_control = None  # None means "No Clock"
        self.white_time = 0.0  # seconds
        self.black_time = 0.0
        self.increment_white = 0.0
        self.increment_black = 0.0
        self.last_frame_time = 0
        self.clock_buttons: List[Button] = []

        self.menu_buttons: List[Button] = []
        self.difficulty_buttons: List[Button] = []
        self.settings_tab = "Pieces"
        self.settings_tab_buttons: List[Button] = []
        self.settings_buttons: List[Button] = []
        self.color_buttons: List[Button] = []
        
        self.create_menus()
        self.create_settings_buttons()
        self.create_color_buttons()
        self.create_clock_buttons()
        
        # LC0 Engine
        self.engine: Optional[LC0Engine] = None
        self.ai_movetime = 100 # default Medium

    def ensure_engine(self):
        if self.engine is None:
            try:
                self.engine = LC0Engine()
            except Exception as e:
                print(f"Failed to initialize LC0: {e}")
                self.message_overlay.show("Error: LC0 Engine failed!", frames=200)

    def _create_background(self) -> pygame.Surface:
        surface = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        top_color = (40, 44, 52)
        bottom_color = (20, 20, 20)
        for y in range(WINDOW_HEIGHT):
            ratio = y / WINDOW_HEIGHT
            r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
            g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
            b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
            pygame.draw.line(surface, (r, g, b), (0, y), (WINDOW_WIDTH, y))
        return surface

    def create_menus(self) -> None:
        center_x = WINDOW_WIDTH // 2
        start_y = WINDOW_HEIGHT // 2 - 80
        w = 220
        h = 40
        labels = ["Single Player", "Two Players", "Settings", "Quit"]
        callbacks = [
            self.menu_single_player,
            self.menu_two_players,
            self.menu_settings,
            self.quit_game,
        ]
        self.menu_buttons = []
        for i, (label, cb) in enumerate(zip(labels, callbacks)):
            rect = pygame.Rect(center_x - w // 2, start_y + i * (h + 10), w, h)
            self.menu_buttons.append(
                Button(rect, label, cb),
            )
        diff_labels = ["Easy", "Medium", "Hard", "Back"]
        self.difficulty_buttons = []
        for i, label in enumerate(diff_labels):
            rect = pygame.Rect(center_x - w // 2, start_y + i * (h + 10), w, h)
            if label == "Back":
                cb = self.menu_back_to_main
            else:
                cb = lambda lvl=label: self.menu_start_single_with_level(lvl)
            self.difficulty_buttons.append(Button(rect, label, cb))

    def create_settings_buttons(self) -> None:
        pass

    def load_background(self, path: Path) -> None:
        try:
            img = pygame.image.load(str(path)).convert()
            self.background_surface = pygame.transform.smoothscale(img, (WINDOW_WIDTH, WINDOW_HEIGHT))
            self.current_bg_path = path
        except Exception:
            pass

    def play_sound(self, sound_name: str) -> None:
        if not self.settings["sound_move"]:
            return
        if sound_name in self.sounds:
            try:
                self.sounds[sound_name].play()
            except Exception:
                pass
                
    def set_piece_set_name(self, name: str) -> None:
        self.current_piece_set = name
        self.board_renderer.piece_images.images.clear()
        self.board_renderer.piece_images.load(self.pieces_dir / name)
        self.update_settings_buttons()

    def update_settings_buttons(self) -> None:
        self.settings_buttons = []
        self.settings_tab_buttons = []
        
        tab_width = 150
        tab_height = 40
        start_x = 40
        start_y = 100
        
        tabs = ["Pieces", "Board", "Background", "Game"]
        for i, tab in enumerate(tabs):
            rect = pygame.Rect(start_x, start_y + i * (tab_height + 10), tab_width, tab_height)
            selected = (self.settings_tab == tab)
            self.settings_tab_buttons.append(Button(rect, tab, lambda t=tab: self.set_settings_tab(t), selected=selected))
            
        self.settings_buttons.append(Button(pygame.Rect(40, WINDOW_HEIGHT - 80, 150, 40), "Back", self.menu_back_to_main))
            
        content_x = 220
        content_y = 100
        
        if self.settings_tab == "Pieces":
            mode = self.board_renderer.piece_images.mode
            letter_icon = pygame.Surface((32, 32), pygame.SRCALPHA)
            k_font = pygame.font.SysFont("serif", 28, bold=True)
            k_text = k_font.render("K", True, (255, 255, 255))
            if k_text:
                letter_icon.blit(k_text, k_text.get_rect(center=(16, 16)))
                
            btn_h = 50
            self.settings_buttons.append(Button(
                pygame.Rect(content_x, content_y, 200, btn_h), 
                "Letters", 
                lambda: self.set_piece_mode("letters"), 
                selected=(mode=="letters"),
                icon=letter_icon
            ))
            
            current_y = content_y + btn_h + 10
            
            for set_name in self.available_piece_sets:
                icon = None
                try:
                    icon_path = self.pieces_dir / set_name / "white_knight.png"
                    if icon_path.exists():
                        icon = pygame.image.load(str(icon_path)).convert_alpha()
                        icon = pygame.transform.smoothscale(icon, (32, 32))
                except:
                    pass
                
                is_selected = (mode == "images" and self.current_piece_set == set_name)
                
                self.settings_buttons.append(Button(
                    pygame.Rect(content_x, current_y, 200, btn_h),
                    set_name.replace("-", " ").title(),
                    lambda n=set_name: [self.set_piece_set_name(n), self.set_piece_mode("images")],
                    selected=is_selected,
                    icon=icon
                ))
                current_y += btn_h + 10
                
        elif self.settings_tab == "Board":
            themes = list(self.board_renderer.themes.keys())
            curr_theme = self.settings["theme"]
            if curr_theme == "Classic": curr_theme = "Brown"
            
            btn_w = 200
            btn_h = 40
            spacing = 10
            
            for i, name in enumerate(themes):
                x = content_x
                y = content_y + i * (btn_h + spacing)
                rect = pygame.Rect(x, y, btn_w, btn_h)
                self.settings_buttons.append(Button(rect, name, lambda n=name: self.set_theme_mode(n), selected=(curr_theme==name)))

        elif self.settings_tab == "Background":
            btn_w = 200
            btn_h = 40
            for i, bg_path in enumerate(self.available_backgrounds):
                name = bg_path.stem.replace("_", " ").title()
                is_selected = (hasattr(self, 'current_bg_path') and self.current_bg_path == bg_path)
                rect = pygame.Rect(content_x, content_y + i * (btn_h + 10), btn_w, btn_h)
                self.settings_buttons.append(Button(rect, name, lambda p=bg_path: self.load_background(p), selected=is_selected))
                
        elif self.settings_tab == "Game":
            snd = self.settings["sound_move"]
            self.settings_buttons.append(Button(pygame.Rect(content_x, content_y, 140, 40), "Sound: " + ("On" if snd else "Off"), 
                self.toggle_sound))
            chk = self.settings["highlight_check"]
            self.settings_buttons.append(Button(pygame.Rect(content_x, content_y + 60, 200, 40), "Show Check: " + ("Yes" if chk else "No"), 
                lambda: self.set_highlight_check(not chk)))

    def set_settings_tab(self, tab: str) -> None:
        self.settings_tab = tab
        self.update_settings_buttons()

    def set_highlight_check(self, enabled: bool) -> None:
        self.settings["highlight_check"] = enabled
        self.update_settings_buttons()

    def set_piece_mode(self, mode: str) -> None:
        if mode == "images":
            self.board_renderer.piece_images.set_mode_images()
        else:
            self.board_renderer.piece_images.set_mode_letters()
        self.update_settings_buttons()

    def set_theme_mode(self, theme: str) -> None:
        self.settings["theme"] = theme
        self.board_renderer.set_theme(theme)
        self.update_settings_buttons()

    def set_sound_mode(self, enabled: bool) -> None:
        self.settings["sound_move"] = enabled
        self.settings["sound_capture"] = enabled
        self.update_settings_buttons()

    def create_color_buttons(self) -> None:
        center_x = WINDOW_WIDTH // 2
        start_y = WINDOW_HEIGHT // 2 - 40
        w = 220
        h = 40
        labels = ["Play as White", "Play as Black", "Random", "Back"]
        callbacks = [
            lambda: self.set_human_color(Color.WHITE),
            lambda: self.set_human_color(Color.BLACK),
            lambda: self.set_human_color(None),
            self.menu_back_to_difficulty
        ]
        self.color_buttons = [Button(pygame.Rect(center_x - w//2, start_y + i*(h+10), w, h), labels[i], callbacks[i]) for i in range(4)]

    def create_clock_buttons(self) -> None:
        center_x = WINDOW_WIDTH // 2
        start_y = WINDOW_HEIGHT // 2 - 200
        
        self.clock_buttons = []
        
        # Helper to add section
        def add_section(title, options, y_pos):
            btn_w = 100
            btn_h = 40
            spacing_x = 10
            total_w = len(options) * btn_w + (len(options) - 1) * spacing_x
            start_x = center_x - total_w // 2
            
            for i, (label, time_min, inc_sec) in enumerate(options):
                x = start_x + i * (btn_w + spacing_x)
                rect = pygame.Rect(x, y_pos, btn_w, btn_h)
                
                def set_tc(m=time_min, s=inc_sec):
                    self.set_time_control(m, s)
                    
                self.clock_buttons.append(Button(rect, label, set_tc))
            
            return y_pos + btn_h + 40

        # Bullet
        y = start_y + 40
        y = add_section("Bullet", [("1 min", 1, 0), ("1 | 1", 1, 1), ("2 | 1", 2, 1)], y)
        
        # Blitz
        y = add_section("Blitz", [("3 min", 3, 0), ("3 | 2", 3, 2), ("5 min", 5, 0)], y)
        
        # Rapid
        y = add_section("Rapid", [("10 min", 10, 0), ("15 | 10", 15, 10), ("30 min", 30, 0)], y)
        
        # Casual
        rect = pygame.Rect(center_x - 75, y, 150, 40)
        self.clock_buttons.append(Button(rect, "No Clock", lambda: self.set_time_control(None, 0)))
        
        # Back
        self.clock_buttons.append(Button(pygame.Rect(40, WINDOW_HEIGHT - 80, 100, 40), "Back", self.menu_back_from_clock))

    def set_time_control(self, minutes: Optional[int], increment: int) -> None:
        if minutes is None:
            self.time_control = None
        else:
            self.time_control = (minutes * 60, increment)
        
        self.new_game()
        self.state = "playing"
        
        # If AI is White, schedule it immediately
        if self.mode_human_vs_ai and self.game.board.current_player == self.ai_color:
            self.turn_state = TURN_AI
            self.ai_move_scheduled = True
        else:
            self.turn_state = TURN_PLAYER

    def menu_back_from_clock(self) -> None:
        if self.mode_human_vs_ai:
            self.state = "color_selection"
        else:
            self.state = "menu"

    def apply_ai_settings(self) -> None:
        level = self.ai_level_names[self.ai_level_index]
        # Easy -> 50ms, Medium -> 100ms, Hard -> 200ms
        if level == "Easy":
            self.ai_movetime = 50
        elif level == "Hard":
            self.ai_movetime = 200
        else: # Medium
            self.ai_movetime = 100
            
    def new_game(self) -> None:
        self.game = Game()
        self.board_renderer.invalid_flash_frames = 0
        self.interaction = InteractionState()
        self.current_animation = None
        self.pending_move = None
        self.message_overlay.show("New game started", frames=120)
        
        if self.time_control:
            self.white_time = float(self.time_control[0])
            self.black_time = float(self.time_control[0])
            self.increment_white = self.time_control[1]
            self.increment_black = self.time_control[1]
        else:
            self.white_time = 0.0
            self.black_time = 0.0
            self.increment_white = 0.0
            self.increment_black = 0.0
        self.last_frame_time = pygame.time.get_ticks()

    def menu_single_player(self) -> None:
        self.state = "difficulty"

    def menu_two_players(self) -> None:
        self.mode_human_vs_ai = False
        self.board_renderer.orientation = Color.WHITE
        self.state = "clock_selection"

    def menu_settings(self) -> None:
        self.last_state = self.state
        self.state = "settings"
        self.update_settings_buttons()

    def menu_back_to_main(self) -> None:
        if hasattr(self, 'last_state') and self.last_state == "playing":
            self.state = "playing"
            self.update_settings_buttons()
        else:
            self.state = "menu"
        
    def menu_back_to_difficulty(self) -> None:
        self.state = "difficulty"

    def menu_start_single_with_level(self, level_label: str) -> None:
        if level_label in self.ai_level_names:
            self.ai_level_index = self.ai_level_names.index(level_label)
        self.apply_ai_settings()
        self.state = "color_selection"
        
    def set_human_color(self, color: Optional[Color]) -> None:
        self.mode_human_vs_ai = True
        if color is None:
            self.human_color = random.choice([Color.WHITE, Color.BLACK])
        else:
            self.human_color = color
        self.ai_color = self.human_color.opposite
        self.board_renderer.orientation = self.human_color
        self.state = "clock_selection"

    def toggle_piece_display_mode(self) -> None:
        images_mode = self.board_renderer.piece_images.mode == "images"
        if images_mode:
            self.board_renderer.piece_images.set_mode_letters()
            self.message_overlay.show("Piece style: Letters", frames=60)
        else:
            self.board_renderer.piece_images.set_mode_images()
            self.message_overlay.show("Piece style: Images", frames=60)
        if self.state == "settings":
            self.update_settings_buttons()

    def cycle_theme(self) -> None:
        themes = list(self.board_renderer.themes.keys())
        current = self.settings["theme"]
        try:
            idx = themes.index(current)
            next_idx = (idx + 1) % len(themes)
        except ValueError:
            next_idx = 0
        new_theme = themes[next_idx]
        self.settings["theme"] = new_theme
        self.board_renderer.set_theme(new_theme)
        if self.state == "settings":
            self.update_settings_buttons()
            
    def toggle_sound(self) -> None:
        self.settings["sound_move"] = not self.settings["sound_move"]
        self.settings["sound_capture"] = self.settings["sound_move"]
        if self.state == "settings":
            self.update_settings_buttons()

    def restart_game(self) -> None:
        self.new_game()
        self.state = "playing"
        self.winning_dialog = None
        
        # If AI is White, schedule it immediately
        if self.mode_human_vs_ai and self.game.board.current_player == self.ai_color:
            self.turn_state = TURN_AI
            self.ai_move_scheduled = True
        else:
            self.turn_state = TURN_PLAYER

    def return_to_menu(self) -> None:
        self.new_game()
        self.state = "menu"
        self.winning_dialog = None

    def quit_game(self) -> None:
        self.running = False

    def undo_move(self) -> None:
        if self.ai_thread is not None and self.ai_thread.is_alive():
            self.message_overlay.show("Cannot undo while AI is thinking", frames=120)
            return
        if self.current_animation is not None:
            return
            
        undo_count = 1
        if self.mode_human_vs_ai and self.game.board.current_player == self.human_color:
             if len(self.game.history) >= 2:
                 undo_count = 2
        
        success = False
        for _ in range(undo_count):
            if self.game.undo_last_move():
                success = True
            else:
                break
        
        if success:
            self.interaction = InteractionState()
            self.message_overlay.show("Move undone", frames=120)
            while not self.ai_move_queue.empty():
                try:
                    self.ai_move_queue.get_nowait()
                except queue.Empty:
                    pass
        else:
            self.message_overlay.show("No moves to undo", frames=120)

    def hint(self) -> None:
        if self.game.result:
            return
            
        self.ensure_engine()
        if not self.engine:
            self.message_overlay.show("Engine not available", frames=120)
            return

        self.message_overlay.show("Thinking...", frames=60)
        
        fen = self.game.board.to_fen()
        # User requested 50ms for hints
        movetime = 50 
        
        threading.Thread(
            target=self.run_lc0_hint,
            args=(fen, movetime),
            daemon=True
        ).start()

    def resign(self) -> None:
        if self.game.result:
            return
        winner = self.game.board.current_player.opposite
        name = "White" if winner is Color.WHITE else "Black"
        self.game.result = f"{name} wins by resignation"

    def move_text(self, move: Move) -> str:
        start = indices_to_square(move.from_row, move.from_col)
        end = indices_to_square(move.to_row, move.to_col)
        return start + " " + end

    def compute_moves_from(self, row: int, col: int) -> Set[Tuple[int, int]]:
        result: Set[Tuple[int, int]] = set()
        for move in self.game.get_legal_moves():
            if move.from_row == row and move.from_col == col:
                result.add((move.to_row, move.to_col))
        return result

    def handle_board_click(self, pos: Tuple[int, int], animate: bool = True) -> None:
        if self.game.result:
            return
        if self.current_animation is not None:
            return
        
        # STRICT TURN STATE CHECK
        if self.mode_human_vs_ai:
            if self.turn_state != TURN_PLAYER:
                return
            if self.game.board.current_player != self.human_color:
                return

        square = self.board_renderer.pixel_to_square(*pos)
        if square is None:
            self.interaction.selected = None
            self.interaction.moves_from_selected.clear()
            return
        row, col = square
        board = self.game.board
        piece = board.get_piece(row, col)
        if self.interaction.awaiting_promotion:
            return
        
        if piece is not None and piece.color is board.current_player:
            self.interaction.selected = (row, col)
            self.interaction.moves_from_selected = self.compute_moves_from(row, col)
            self.interaction.hint_move = None
            return

        if self.interaction.selected is not None:
            targets = self.interaction.moves_from_selected
            if (row, col) in targets:
                moves = [
                    m
                    for m in self.game.get_legal_moves()
                    if m.from_row == self.interaction.selected[0]
                    and m.from_col == self.interaction.selected[1]
                    and m.to_row == row
                    and m.to_col == col
                ]
                if not moves:
                    self.board_renderer.trigger_invalid_flash()
                    return
                promotion_moves = [m for m in moves if m.promotion is not None]
                if promotion_moves:
                    self.interaction.pending_promotion_moves = promotion_moves
                    self.interaction.awaiting_promotion = True
                    rect = pygame.Rect(
                        80,
                        WINDOW_HEIGHT // 2 - 30,
                        WINDOW_WIDTH - 160,
                        60,
                    )
                    dialog = PromotionDialog(
                        rect, 
                        self.handle_promotion_choice,
                        self.board_renderer.piece_images,
                        self.game.board.current_player
                    )
                    dialog.layout()
                    self.promotion_dialog = dialog
                    return
                move = moves[0]
                self.apply_move_and_schedule_ai(move, animate=animate)
                self.interaction.selected = None
                self.interaction.moves_from_selected.clear()
                return
            
            self.interaction.selected = None
            self.interaction.moves_from_selected.clear()
            return
        pass

    def handle_promotion_choice(self, choice: str) -> None:
        moves = [
            m
            for m in self.interaction.pending_promotion_moves
            if m.promotion is not None and m.promotion.value == choice
        ]
        if not moves:
            self.interaction.awaiting_promotion = False
            self.promotion_dialog = None
            self.interaction.pending_promotion_moves = []
            return
        move = moves[0]
        self.apply_move_and_schedule_ai(move)
        self.interaction.awaiting_promotion = False
        self.promotion_dialog = None
        self.interaction.pending_promotion_moves = []
        self.interaction.selected = None
        self.interaction.moves_from_selected.clear()

    def apply_move_with_sound(self, move: Move) -> None:
        is_capture = False
        target_piece = self.game.board.get_piece(move.to_row, move.to_col)
        if target_piece is not None:
            is_capture = True
        elif move.is_en_passant:
            is_capture = True
            
        self.game.apply_move(move)
        
        # Clock Update - Apply Increment
        if self.time_control is not None:
            # The move is done, so current_player is the NEXT player.
            # The player who just moved is opposite.
            just_moved = self.game.board.current_player.opposite
            if just_moved == Color.WHITE:
                self.white_time += self.increment_white
            else:
                self.black_time += self.increment_black
        
        is_check = self.game.is_in_check()
        
        if is_check:
            self.play_sound("move-check")
        elif is_capture:
            self.play_sound("capture")
        elif move.is_castling:
            self.play_sound("castle")
        elif move.promotion is not None:
            self.play_sound("promote")
        else:
            self.play_sound("move-self")

    def apply_move_and_schedule_ai(self, move: Move, animate: bool = True) -> None:
        if self.current_animation is not None:
            return
        if animate:
            self.current_animation = MoveAnimation(self.board_renderer, self.game, move)
            # Pending move: (move, is_ai_response_needed)
            # If Human vs AI, and we just moved (Human), then YES, AI response needed.
            # If AI just moved, then NO, AI response NOT needed (return control to player).
            is_ai_needed = self.mode_human_vs_ai and not self.game.result and (self.game.board.current_player != self.ai_color)
            self.pending_move = (move, is_ai_needed)
            self.turn_state = TURN_LOCKED # Lock input during animation
        else:
            self.apply_move_with_sound(move)
            self.pending_move = None
            self.current_animation = None
            
            is_ai_needed = self.mode_human_vs_ai and not self.game.result and (self.game.board.current_player != self.ai_color)
            if is_ai_needed:
                # Transition to AI Turn
                self.turn_state = TURN_AI
                self.ai_move_scheduled = True
            else:
                self.turn_state = TURN_PLAYER

    def run_lc0_hint(self, fen: str, movetime: int) -> None:
        try:
            if not self.engine:
                return
            best_move_str = self.engine.get_best_move(fen, movetime)
            if best_move_str:
                move = self._parse_engine_move(best_move_str)
                if move:
                    pygame.event.post(pygame.event.Event(USEREVENT_HINT_READY, move=move))
        except Exception as e:
            print(f"LC0 Hint Error: {e}")

    def run_lc0_search(self, fen: str, movetime: int) -> None:
        try:
            # Check for engine
            if not self.engine:
                print("LC0 Engine not initialized")
                return

            best_move_str = self.engine.get_best_move(fen, movetime)
            if best_move_str:
                move = self._parse_engine_move(best_move_str)
                if move:
                    pygame.event.post(pygame.event.Event(USEREVENT_AI_MOVE, move=move))
                else:
                    print(f"Failed to parse move: {best_move_str}")
            else:
                print("Engine returned no move")
        except Exception as e:
            print(f"LC0 Error: {e}")

    def _parse_engine_move(self, move_str: str) -> Optional[Move]:
        if not move_str or len(move_str) < 4:
            return None
        
        from_sq = move_str[:2]
        to_sq = move_str[2:4]
        promotion_char = move_str[4] if len(move_str) > 4 else None
        
        from_idx = square_to_indices(from_sq)
        to_idx = square_to_indices(to_sq)
        
        if not from_idx or not to_idx:
            return None
            
        from_r, from_c = from_idx
        to_r, to_c = to_idx
        
        piece = self.game.board.get_piece(from_r, from_c)
        if piece is None:
            return None
            
        # Promotion
        promotion = None
        if promotion_char:
            if promotion_char == 'q': promotion = PieceType.QUEEN
            elif promotion_char == 'r': promotion = PieceType.ROOK
            elif promotion_char == 'b': promotion = PieceType.BISHOP
            elif promotion_char == 'n': promotion = PieceType.KNIGHT
            
        # Capture
        target_piece = self.game.board.get_piece(to_r, to_c)
        is_capture = target_piece is not None
        
        # En Passant
        is_en_passant = False
        if piece.kind == PieceType.PAWN and abs(to_c - from_c) == 1 and not is_capture:
            # Diagonal move to empty square
            is_en_passant = True
            is_capture = True
            
        # Castling
        is_castling = False
        if piece.kind == PieceType.KING and abs(to_c - from_c) > 1:
            is_castling = True
            
        return Move(from_r, from_c, to_r, to_c, promotion, is_castling, is_en_passant)

    def trigger_ai_move(self) -> None:
        if not self.mode_human_vs_ai or self.game.result:
            return
        if self.game.board.current_player != self.ai_color:
            return
        
        self.ensure_engine()
        if not self.engine:
            return
            
        # Don't show overlay if move is instant (0.1s), it just flickers.
        # self.message_overlay.show("AI thinking...", frames=180)
        
        fen = self.game.board.to_fen()
        movetime = self.ai_movetime
        
        self.ai_thread = threading.Thread(
            target=self.run_lc0_search,
            args=(fen, movetime)
        )
        self.ai_thread.daemon = True
        self.ai_thread.start()

    def update_game_logic(self) -> None:
        # 1. Handle Animation Completion
        if self.current_animation is not None:
            if self.current_animation.is_done():
                move = self.current_animation.move
                self.current_animation = None
                
                # Apply the move permanently
                self.apply_move_with_sound(move)
                
                # Check pending state for AI trigger
                if self.pending_move:
                    _, ai_needed = self.pending_move
                    self.pending_move = None
                    if ai_needed:
                        self.turn_state = TURN_AI
                        self.ai_move_scheduled = True
                    else:
                        self.turn_state = TURN_PLAYER
        
        # 2. Handle AI Scheduling (One Shot)
        if self.turn_state == TURN_AI and self.ai_move_scheduled:
            self.ai_move_scheduled = False
            self.trigger_ai_move()
            
        # 3. Handle AI Completion (Now via USEREVENT)
        # if self.turn_state == TURN_AI: ... handled in handle_events
                
        # 4. Handle Clock
        current_time = pygame.time.get_ticks()
        dt = (current_time - self.last_frame_time) / 1000.0
        self.last_frame_time = current_time
        
        if self.time_control is not None and not self.game.result:
            # Rule: Pause clocks during AI computation and Animations
            is_thinking = (self.turn_state == TURN_AI and self.ai_thread is not None and self.ai_thread.is_alive())
            is_animating = (self.current_animation is not None)
            
            if not is_thinking and not is_animating:
                if self.game.board.current_player == Color.WHITE:
                    self.white_time -= dt
                    if self.white_time <= 0:
                        self.white_time = 0
                        self.game.result = "Black wins on time"
                        self.winning_dialog = WinningDialog(
                            pygame.Rect(WINDOW_WIDTH//2 - 150, WINDOW_HEIGHT//2 - 100, 300, 200),
                            "Black wins on time!",
                            self.restart_game,
                            self.return_to_menu
                        )
                else:
                    self.black_time -= dt
                    if self.black_time <= 0:
                        self.black_time = 0
                        self.game.result = "White wins on time"
                        self.winning_dialog = WinningDialog(
                            pygame.Rect(WINDOW_WIDTH//2 - 150, WINDOW_HEIGHT//2 - 100, 300, 200),
                            "White wins on time!",
                            self.restart_game,
                            self.return_to_menu
                        )

    def draw_side_panel(self) -> None:
        board_y = (WINDOW_HEIGHT - BOARD_SIZE) // 2
        panel_x = BOARD_SIZE + 80
        panel_width = WINDOW_WIDTH - panel_x - 40
        panel_rect = pygame.Rect(panel_x, board_y, panel_width, BOARD_SIZE)
        
        s = pygame.Surface((panel_rect.width, panel_rect.height))
        s.set_alpha(200)
        s.fill((0, 0, 0))
        self.screen.blit(s, (panel_rect.x, panel_rect.y))
        
        y = panel_rect.y + 10
        
        # 1. Game Info Title
        text = self.side_font.render("Game Info", True, TEXT_COLOR)
        self.screen.blit(text, (panel_rect.x + 10, y))
        y += 30
        
        # 2. Clocks (New UI)
        if self.time_control is not None:
            def format_time(t):
                if t < 0: t = 0
                m = int(t // 60)
                s = int(t % 60)
                # ms = int((t - int(t)) * 10)
                return f"{m:02d}:{s:02d}"
            
            w_time_str = format_time(self.white_time)
            b_time_str = format_time(self.black_time)
            
            # Colors
            w_active = self.game.board.current_player == Color.WHITE
            b_active = self.game.board.current_player == Color.BLACK
            
            w_bg_color = (60, 60, 60) if w_active else (30, 30, 30)
            b_bg_color = (60, 60, 60) if b_active else (30, 30, 30)
            
            w_border = (0, 255, 0) if w_active else (100, 100, 100)
            b_border = (0, 255, 0) if b_active else (100, 100, 100)
            
            w_text_color = (255, 50, 50) if self.white_time < 10 else (255, 255, 255)
            b_text_color = (255, 50, 50) if self.black_time < 10 else (255, 255, 255)
            
            # Draw White Clock
            clock_h = 40
            pygame.draw.rect(self.screen, w_bg_color, (panel_rect.x + 10, y, 120, clock_h))
            pygame.draw.rect(self.screen, w_border, (panel_rect.x + 10, y, 120, clock_h), 2)
            lbl = self.side_font.render(f"White: {w_time_str}", True, w_text_color)
            self.screen.blit(lbl, (panel_rect.x + 20, y + 10))
            
            y += clock_h + 10
            
            # Draw Black Clock
            pygame.draw.rect(self.screen, b_bg_color, (panel_rect.x + 10, y, 120, clock_h))
            pygame.draw.rect(self.screen, b_border, (panel_rect.x + 10, y, 120, clock_h), 2)
            lbl = self.side_font.render(f"Black: {b_time_str}", True, b_text_color)
            self.screen.blit(lbl, (panel_rect.x + 20, y + 10))
            
            y += clock_h + 20
        
        # 3. Turn Indicator
        turn_str = "White" if self.game.board.current_player is Color.WHITE else "Black"
        text = self.side_font.render("Turn: " + turn_str, True, TEXT_COLOR)
        self.screen.blit(text, (panel_rect.x + 10, y))
        y += 24
        
        # 4. Status
        status = "Active"
        if self.game.result:
            status = self.game.result
        elif self.game.is_checkmate():
            status = "Checkmate"
        elif self.game.is_stalemate():
            status = "Stalemate"
        elif self.game.is_in_check():
            status = "Check"
            
        status_surf = self.side_font.render(f"Status: {status}", True, TEXT_COLOR)
        self.screen.blit(status_surf, (panel_rect.x + 10, y))
        y += 30
        
        # 5. Captured Pieces
        def draw_captured(label, pieces, start_y):
            lbl = self.side_font.render(label, True, TEXT_COLOR)
            self.screen.blit(lbl, (panel_rect.x + 10, start_y))
            start_y += 22
            
            if not pieces:
                return start_y + 35
            
            icon_size = SQUARE_SIZE // 3
            available_width = panel_rect.width - 20
            count = len(pieces)
            step = 20
            
            required_width = (count - 1) * step + icon_size
            if required_width > available_width and count > 1:
                step = (available_width - icon_size) / (count - 1)
            
            start_x = panel_rect.x + 10
            for i, piece in enumerate(pieces):
                image = self.board_renderer.piece_images.get(piece)
                if image is not None:
                    small = pygame.transform.smoothscale(
                        image,
                        (icon_size, icon_size),
                    )
                    rect_img = small.get_rect(topleft=(int(start_x + i * step), start_y))
                    self.screen.blit(small, rect_img)
            return start_y + 35

        y = draw_captured("Captured White:", self.game.captured_white, y)
        y = draw_captured("Captured Black:", self.game.captured_black, y)
        
        y += 10
        
        # 6. Move Log
        text = self.side_font.render("Moves:", True, TEXT_COLOR)
        self.screen.blit(text, (panel_rect.x + 10, y))
        y += 22
        
        formatted_lines = []
        for i in range(0, len(self.game.move_log), 2):
            move_num = i // 2 + 1
            white_move = self.game.move_log[i]
            if i + 1 < len(self.game.move_log):
                black_move = self.game.move_log[i+1]
                formatted_lines.append(f"{move_num}. {white_move} {black_move}")
            else:
                formatted_lines.append(f"{move_num}. {white_move}")
                
        max_lines = 8 # Reduced lines to fit clock
        start_idx = max(0, len(formatted_lines) - max_lines)
        display_lines = formatted_lines[start_idx:]
        
        for line in display_lines:
            glyph = self.small_font.render(line, True, TEXT_COLOR)
            self.screen.blit(glyph, (panel_rect.x + 10, y))
            y += 18

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            if event.type == USEREVENT_AI_MOVE:
                if self.turn_state == TURN_AI:
                    self.apply_move_and_schedule_ai(event.move, animate=True)
            
            if event.type == USEREVENT_HINT_READY:
                move = event.move
                self.interaction.hint_move = move
                self.message_overlay.show("Suggested move " + self.move_text(move), frames=180)

            if self.winning_dialog is not None:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.winning_dialog.handle_mouse_down(event.pos)
                elif event.type == pygame.MOUSEMOTION:
                    self.winning_dialog.handle_mouse_move(event.pos)
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == "playing":
                        self.return_to_menu()
            elif event.type == pygame.MOUSEMOTION:
                pos = event.pos
                if self.state == "playing":
                    self.board_renderer.update_hover(pos)
                    self.button_bar.handle_mouse_move(pos)
                    self.btn_main_menu.handle_mouse_move(pos)
                    if self.interaction.dragging and self.interaction.selected:
                        pass
                elif self.state == "menu":
                    for b in self.menu_buttons:
                        b.handle_mouse_move(pos)
                elif self.state == "difficulty":
                    for b in self.difficulty_buttons:
                        b.handle_mouse_move(pos)
                elif self.state == "settings":
                    for b in self.settings_buttons:
                        b.handle_mouse_move(pos)
                    for b in self.settings_tab_buttons:
                        b.handle_mouse_move(pos)
                elif self.state == "color_selection":
                    for b in self.color_buttons:
                        b.handle_mouse_move(pos)
                elif self.state == "clock_selection":
                    for b in self.clock_buttons:
                        b.handle_mouse_move(pos)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if self.state == "playing":
                    if self.promotion_dialog is not None and self.interaction.awaiting_promotion:
                        if self.promotion_dialog.handle_mouse_down(pos):
                            continue
                    if self.board_renderer.board_rect().collidepoint(pos):
                        self.handle_board_click(pos)
                        if self.interaction.selected:
                            sq = self.board_renderer.pixel_to_square(*pos)
                            if sq == self.interaction.selected:
                                self.interaction.dragging = True
                                self.interaction.drag_start_pos = pos
                                r, c = sq
                                self.interaction.drag_piece = self.game.board.get_piece(r, c)
                    else:
                        self.button_bar.handle_mouse_down(pos)
                        self.btn_main_menu.handle_mouse_down(pos)
                elif self.state == "menu":
                    for b in self.menu_buttons:
                        b.handle_mouse_down(pos)
                elif self.state == "difficulty":
                    for b in self.difficulty_buttons:
                        b.handle_mouse_down(pos)
                elif self.state == "settings":
                    for b in self.settings_buttons:
                        b.handle_mouse_down(pos)
                    for b in self.settings_tab_buttons:
                        b.handle_mouse_down(pos)
                elif self.state == "color_selection":
                    for b in self.color_buttons:
                        b.handle_mouse_down(pos)
                elif self.state == "clock_selection":
                    for b in self.clock_buttons:
                        b.handle_mouse_down(pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.state == "playing" and self.interaction.dragging:
                    pos = event.pos
                    self.interaction.dragging = False
                    self.interaction.drag_piece = None
                    
                    square = self.board_renderer.pixel_to_square(*pos)
                    if square and self.interaction.selected:
                        r, c = square
                        if (r, c) == self.interaction.selected:
                            continue
                        
                        self.handle_board_click(pos, animate=False)

    def draw(self) -> None:
        if self.state in ["menu", "difficulty", "settings", "color_selection", "clock_selection"]:
            self.screen.blit(self.background_surface, (0, 0))
        else:
            self.screen.fill((20, 20, 20))

        if self.state == "menu":
            if self.logo_image:
                rect = self.logo_image.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 150))
                self.screen.blit(self.logo_image, rect)
            else:
                title = self.title_font.render("Chess Game", True, (255, 255, 255))
                rect = title.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 150))
                self.screen.blit(title, rect)
                
            for b in self.menu_buttons:
                b.draw(self.screen, self.button_font)
            self.message_overlay.draw(self.screen, self.small_font)
            pygame.display.flip()
            return
        if self.state == "difficulty":
            title = self.title_font.render("Select Difficulty", True, (255, 255, 255))
            rect = title.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 150))
            self.screen.blit(title, rect)
            for b in self.difficulty_buttons:
                b.draw(self.screen, self.button_font)
            self.message_overlay.draw(self.screen, self.small_font)
            pygame.display.flip()
            return
        if self.state == "settings":
            title = self.title_font.render("Settings", True, (255, 255, 255))
            self.screen.blit(title, (40, 30))
            
            for b in self.settings_tab_buttons:
                b.draw(self.screen, self.button_font)
            for b in self.settings_buttons:
                b.draw(self.screen, self.button_font)
                
            if self.settings_tab in ["Pieces", "Board"]:
                preview_rect = pygame.Rect(450, 100, 400, 400)
                pygame.draw.rect(self.screen, (40, 40, 40), preview_rect)
                pygame.draw.rect(self.screen, (100, 100, 100), preview_rect, 2)
                
                theme_name = self.settings["theme"]
                if theme_name == "Classic": theme_name = "Brown"
                light, dark = self.board_renderer.themes.get(theme_name, ((240, 217, 181), (181, 136, 99)))
                
                sq_size = 100
                for r in range(4):
                    for c in range(4):
                        color = light if (r + c) % 2 == 0 else dark
                        pygame.draw.rect(self.screen, color, 
                                         (preview_rect.x + c * sq_size, preview_rect.y + r * sq_size, sq_size, sq_size))
                
                def draw_preview_piece(row, col, piece_type, color):
                    p = Piece(color, piece_type)
                    img = self.board_renderer.piece_images.get(p)
                    if img:
                        img_rect = img.get_rect(center=(preview_rect.x + col * sq_size + sq_size//2, 
                                                        preview_rect.y + row * sq_size + sq_size//2))
                        self.screen.blit(img, img_rect)
                
                draw_preview_piece(0, 0, PieceType.PAWN, Color.WHITE)
                draw_preview_piece(0, 1, PieceType.KNIGHT, Color.BLACK)
                draw_preview_piece(1, 0, PieceType.BISHOP, Color.BLACK)
                draw_preview_piece(1, 1, PieceType.ROOK, Color.WHITE)
                draw_preview_piece(2, 2, PieceType.QUEEN, Color.WHITE)
                draw_preview_piece(2, 3, PieceType.KING, Color.BLACK)
                draw_preview_piece(3, 2, PieceType.PAWN, Color.BLACK)
                draw_preview_piece(3, 3, PieceType.KNIGHT, Color.WHITE)

            self.message_overlay.draw(self.screen, self.small_font)
            pygame.display.flip()
            return
        if self.state == "color_selection":
            title = self.title_font.render("Choose Your Side", True, (255, 255, 255))
            rect = title.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 100))
            self.screen.blit(title, rect)
            for b in self.color_buttons:
                b.draw(self.screen, self.button_font)
            self.message_overlay.draw(self.screen, self.small_font)
            pygame.display.flip()
            return
        if self.state == "clock_selection":
            title = self.title_font.render("Select Time Control", True, (255, 255, 255))
            rect = title.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 250))
            self.screen.blit(title, rect)
            for b in self.clock_buttons:
                b.draw(self.screen, self.button_font)
            self.message_overlay.draw(self.screen, self.small_font)
            pygame.display.flip()
            return

        king_pos = None
        if self.game.is_in_check():
            for row in range(8):
                for col in range(8):
                    piece = self.game.board.get_piece(row, col)
                    if piece is not None and piece.color is self.game.board.current_player and piece.kind is PieceType.KING:
                        king_pos = (row, col)
                        break
                if king_pos is not None:
                    break
        hide_pieces: Set[Tuple[int, int]] = set()
        if self.current_animation is not None:
            move = self.current_animation.move
            hide_pieces.add((move.from_row, move.from_col))
            hide_pieces.add((move.to_row, move.to_col))
        
        if self.interaction.dragging and self.interaction.selected:
            hide_pieces.add(self.interaction.selected)

        self.board_renderer.draw_board(
            self.screen,
            self.game.board,
            self.interaction.selected,
            self.interaction.moves_from_selected,
            self.game.last_move,
            self.interaction.hint_move,
            hide_pieces,
            king_pos,
            highlight_check=self.settings["highlight_check"]
        )
        
        if self.interaction.dragging and self.interaction.drag_piece:
            image = self.board_renderer.piece_images.get(self.interaction.drag_piece)
            if image:
                mouse_pos = pygame.mouse.get_pos()
                rect = image.get_rect(center=mouse_pos)
                self.screen.blit(image, rect)

        self.draw_side_panel()
        self.button_bar.draw(self.screen, self.button_font)
        self.btn_main_menu.draw(self.screen, self.button_font)
        if self.promotion_dialog is not None and self.interaction.awaiting_promotion:
            self.promotion_dialog.draw(self.screen, self.side_font)
        self.message_overlay.draw(self.screen, self.small_font)
        if self.current_animation is not None:
            t = self.current_animation.progress()
            for image, start_pos, end_pos in self.current_animation.pieces:
                x = start_pos[0] + (end_pos[0] - start_pos[0]) * t
                y = start_pos[1] + (end_pos[1] - start_pos[1]) * t
                rect = image.get_rect(center=(int(x), int(y)))
                self.screen.blit(image, rect)
            for image, pos in self.current_animation.captured_overlays:
                alpha_t = 1.0 - t
                temp = image.copy()
                temp.set_alpha(int(255 * alpha_t))
                rect = temp.get_rect(center=(int(pos[0]), int(pos[1])))
                self.screen.blit(temp, rect)
        
        if self.game.result and self.winning_dialog is None:
            if self.mode_human_vs_ai:
                try:
                    LEARNING_SYSTEM.record_game(self.game.history, self.game.result, self.ai_color)
                except Exception as e:
                    print(f"Learning Error: {e}")

            self.winning_dialog = WinningDialog(
                pygame.Rect(WINDOW_WIDTH // 2 - 150, WINDOW_HEIGHT // 2 - 100, 300, 200),
                self.game.result,
                self.restart_game,
                self.return_to_menu
            )
            
        if self.winning_dialog is not None:
            self.winning_dialog.draw(self.screen, self.button_font)

        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            self.handle_events()
            
            if self.state == "playing":
                self.update_game_logic()
            
            self.draw()
            self.clock.tick(60)
        pygame.quit()


def run() -> None:
    window = GameWindow()
    window.run()
