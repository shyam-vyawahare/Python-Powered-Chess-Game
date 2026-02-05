from typing import Optional, Set, Tuple, List, Dict
from pathlib import Path
import pygame
import random
import threading
import queue
import os
from ..game_logic import Game
from ..ai_opponent import choose_ai_move, AI_SETTINGS
from ..utils import Color, Move, indices_to_square
from ..pieces import PieceType, Piece
from .chess_board_ui import BoardRenderer, BOARD_SIZE, SQUARE_SIZE
from .menu_handler import ButtonBar, Button
from .dialogs import PromotionDialog, MessageOverlay, WinningDialog


WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 720
PANEL_BG = (30, 30, 30)
TEXT_COLOR = (230, 230, 230)


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
        # Initialize mixer explicitly
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
                # Scale proportionally to reasonable width (e.g. 500px)
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
        
        # Load Initial Background (Prefer Classic)
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
        self.menu_buttons: List[Button] = []
        self.difficulty_buttons: List[Button] = []
        self.settings_tab = "Pieces"
        self.settings_tab_buttons: List[Button] = []
        self.settings_buttons: List[Button] = []
        self.color_buttons: List[Button] = []
        # self.background_surface is initialized above
        self.create_menus()
        self.create_settings_buttons()
        self.create_color_buttons()

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
        center_x = WINDOW_WIDTH // 2
        start_y = WINDOW_HEIGHT // 2 - 80
        w = 260
        h = 40
        # Will be updated in draw or update loop based on current settings, but initialized here
        # Actually, let's just create the rects and callbacks, and text will be dynamic or buttons updated
        # Simpler: Recreate buttons when entering settings or updating them.
        pass

    def load_background(self, path: Path) -> None:
        try:
            img = pygame.image.load(str(path)).convert()
            self.background_surface = pygame.transform.smoothscale(img, (WINDOW_WIDTH, WINDOW_HEIGHT))
            self.current_bg_path = path # Store current for UI highlighting if needed
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
        # If we were in letter mode, we stay in letter mode, but images are updated in background
        # If we were in image mode, we see new images immediately
        self.update_settings_buttons()

    def update_settings_buttons(self) -> None:
        self.settings_buttons = []
        self.settings_tab_buttons = []
        
        # Layout
        tab_width = 150
        tab_height = 40
        start_x = 40
        start_y = 100
        
        # Tabs
        tabs = ["Pieces", "Board", "Background", "Game"]
        for i, tab in enumerate(tabs):
            rect = pygame.Rect(start_x, start_y + i * (tab_height + 10), tab_width, tab_height)
            selected = (self.settings_tab == tab)
            self.settings_tab_buttons.append(Button(rect, tab, lambda t=tab: self.set_settings_tab(t), selected=selected))
            
        # Back button
        self.settings_buttons.append(Button(pygame.Rect(40, WINDOW_HEIGHT - 80, 150, 40), "Back", self.menu_back_to_main))
            
        # Content
        content_x = 220
        content_y = 100
        
        if self.settings_tab == "Pieces":
            # Piece Style
            mode = self.board_renderer.piece_images.mode
            
            # 1. Letters Option
            # Letters: "K" Surface
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
            
            # 2. Image Sets
            current_y = content_y + btn_h + 10
            
            for set_name in self.available_piece_sets:
                # Load a sample icon for this set (e.g. White Knight)
                # We need to construct the path manually to get the icon without reloading the whole set into the renderer just for the button
                # Actually, simpler: just use the name. Or try to load one image.
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
            # Themes
            themes = list(self.board_renderer.themes.keys())
            curr_theme = self.settings["theme"]
            if curr_theme == "Classic": curr_theme = "Brown"
            
            # Use a list layout to avoid overlapping with preview
            btn_w = 200
            btn_h = 40
            spacing = 10
            
            for i, name in enumerate(themes):
                # Single column
                x = content_x
                y = content_y + i * (btn_h + spacing)
                
                # Check bounds - if too many themes, might need scrolling or 2 columns with smaller width
                # But for now, we have about 9 themes. 9 * 50 = 450px.
                # content_y is 100. 100 + 450 = 550. WINDOW_HEIGHT is 720. Fits.
                
                rect = pygame.Rect(x, y, btn_w, btn_h)
                self.settings_buttons.append(Button(rect, name, lambda n=name: self.set_theme_mode(n), selected=(curr_theme==name)))

        elif self.settings_tab == "Background":
            # Backgrounds list
            btn_w = 200
            btn_h = 40
            
            # Option to generate default if list is empty?
            # We already loaded available backgrounds in init
            
            for i, bg_path in enumerate(self.available_backgrounds):
                name = bg_path.stem.replace("_", " ").title()
                is_selected = (hasattr(self, 'current_bg_path') and self.current_bg_path == bg_path)
                
                # Thumbnail?
                # Generating thumbnails for every frame might be expensive. 
                # Ideally, cache them. For now, let's just list names. The preview on the right shows the big image.
                
                rect = pygame.Rect(content_x, content_y + i * (btn_h + 10), btn_w, btn_h)
                self.settings_buttons.append(Button(rect, name, lambda p=bg_path: self.load_background(p), selected=is_selected))
                
        elif self.settings_tab == "Game":
            # Sound
            snd = self.settings["sound_move"]
            self.settings_buttons.append(Button(pygame.Rect(content_x, content_y, 140, 40), "Sound: " + ("On" if snd else "Off"), 
                self.toggle_sound))
            
            # Check Highlight
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

    def apply_ai_settings(self) -> None:
        level = self.ai_level_names[self.ai_level_index]
        settings = AI_SETTINGS.get(level, AI_SETTINGS["Medium"])
        self.ai_depth = settings["depth"]
        self.ai_randomness = settings["randomness"]

    def new_game(self) -> None:
        self.game = Game()
        self.interaction = InteractionState()
        self.current_animation = None
        self.pending_move = None
        self.message_overlay.show("New game started", frames=120)

    def menu_single_player(self) -> None:
        self.state = "difficulty"

    def menu_two_players(self) -> None:
        self.mode_human_vs_ai = False
        self.board_renderer.orientation = Color.WHITE
        self.new_game()
        self.state = "playing"

    def menu_settings(self) -> None:
        self.last_state = self.state
        self.state = "settings"
        self.update_settings_buttons()

    def menu_back_to_main(self) -> None:
        if hasattr(self, 'last_state') and self.last_state == "playing":
            self.state = "playing"
            self.update_settings_buttons() # Cleanup if needed
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
        self.new_game()
        self.state = "playing"
        # If AI is white, trigger first move
        self.maybe_start_ai_move()

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
        self.maybe_start_ai_move()

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
            
        # Single Player Logic: Undo both AI and Human move if it is Human's turn
        undo_count = 1
        if self.mode_human_vs_ai and self.game.board.current_player == self.human_color:
             # It is human's turn, so AI must have moved last.
             # We want to undo AI's move AND Human's previous move to let Human retry.
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
            
            # Clear any pending AI moves in queue to prevent ghost moves
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
        color = self.game.board.current_player
        move = choose_ai_move(
            self.game.board,
            color,
            max(1, self.ai_depth - 1),
            0.0,
        )
        if move is None:
            self.message_overlay.show("No legal moves", frames=120)
            return
        self.interaction.hint_move = move
        self.message_overlay.show("Suggested move " + self.move_text(move), frames=180)

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
        
        # Logic update for Drag & Drop and Deselect
        # If we clicked (MOUSEBUTTONDOWN), we might be starting a drag or selecting.
        
        # 1. If we click on our own piece, select it (and start drag logic elsewhere)
        if piece is not None and piece.color is board.current_player:
            self.interaction.selected = (row, col)
            self.interaction.moves_from_selected = self.compute_moves_from(row, col)
            self.interaction.hint_move = None
            return

        # 2. If we have a selection, try to move to the clicked square
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
                    dialog = PromotionDialog(rect, self.handle_promotion_choice)
                    dialog.layout()
                    self.promotion_dialog = dialog
                    return
                move = moves[0]
                self.apply_move_and_maybe_ai(move, animate=animate)
                self.interaction.selected = None
                self.interaction.moves_from_selected.clear()
                return
            
            # 3. If clicking empty square or enemy piece that is NOT a valid move target -> Deselect
            # (If it was own piece, it was handled in #1)
            self.interaction.selected = None
            self.interaction.moves_from_selected.clear()
            return

        # 4. If no selection and clicked empty/enemy -> Invalid flash (or just ignore)
        # User requested: "Invalid actions should ... simply not allow the move ... No visual punishment"
        # So we just ignore.
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
        self.apply_move_and_maybe_ai(move)
        self.interaction.awaiting_promotion = False
        self.promotion_dialog = None
        self.interaction.pending_promotion_moves = []
        self.interaction.selected = None
        self.interaction.moves_from_selected.clear()

    def apply_move_with_sound(self, move: Move) -> None:
        # Determine sound triggers
        is_capture = False
        target_piece = self.game.board.get_piece(move.to_row, move.to_col)
        if target_piece is not None:
            is_capture = True
        elif move.is_en_passant:
            is_capture = True
            
        self.game.apply_move(move)
        
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

    def apply_move_and_maybe_ai(self, move: Move, animate: bool = True) -> None:
        if self.current_animation is not None:
            return
        if animate:
            self.current_animation = MoveAnimation(self.board_renderer, self.game, move)
            self.pending_move = (move, False)
        else:
            self.apply_move_with_sound(move)
            self.pending_move = None
            self.current_animation = None
            self.maybe_start_ai_move()

    def run_ai_search(self, board_copy: Game, color: Color, depth: int, randomness: float) -> None:
        try:
            ai_move = choose_ai_move(board_copy.board, color, depth, randomness)
            self.ai_move_queue.put(ai_move)
        except Exception as e:
            print(f"AI Error: {e}")
            self.ai_move_queue.put(None)

    def maybe_start_ai_move(self) -> None:
        if not self.mode_human_vs_ai or self.game.result:
            return
        if self.game.board.current_player is not self.ai_color:
            return
        self.message_overlay.show("AI thinking...", frames=180)
        
        # Start AI in a separate thread
        board_copy = Game()
        board_copy.board = self.game.board.copy() # Deep copy of the board state
        # We need to ensure Game state (history, repetition) is also copied if AI uses it,
        # but choose_ai_move currently only takes 'board' (ChessBoard).
        # So passing board_copy.board should be sufficient if choose_ai_move is isolated.
        
        self.ai_thread = threading.Thread(
            target=self.run_ai_search,
            args=(board_copy, self.ai_color, self.ai_depth, self.ai_randomness)
        )
        self.ai_thread.daemon = True
        self.ai_thread.start()

    def draw_side_panel(self) -> None:
        # Align panel with the board
        board_y = (WINDOW_HEIGHT - BOARD_SIZE) // 2
        panel_x = BOARD_SIZE + 80
        panel_width = WINDOW_WIDTH - panel_x - 40
        panel_rect = pygame.Rect(panel_x, board_y, panel_width, BOARD_SIZE)
        
        # Transparent background for panel
        s = pygame.Surface((panel_rect.width, panel_rect.height))
        s.set_alpha(200)
        s.fill((0, 0, 0))
        self.screen.blit(s, (panel_rect.x, panel_rect.y))
        
        turn = "White" if self.game.board.current_player is Color.WHITE else "Black"
        status = "Active"
        if self.game.result:
            status = self.game.result
        else:
            if self.game.is_checkmate():
                status = "Checkmate"
            elif self.game.is_stalemate():
                status = "Stalemate"
            elif self.game.is_in_check():
                status = "Check"
        y = panel_rect.y + 10
        
        # Game Info
        text = self.side_font.render("Game Info", True, TEXT_COLOR)
        self.screen.blit(text, (panel_rect.x + 10, y))
        y += 24
        
        # Turn
        text = self.side_font.render("Turn: " + turn, True, TEXT_COLOR)
        self.screen.blit(text, (panel_rect.x + 10, y))
        y += 24
        
        # Status (Wrapped)
        status_prefix = "Status: "
        full_status = status_prefix + status
        
        words = full_status.split(' ')
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            w, h = self.side_font.size(test_line)
            if w < panel_rect.width - 20:
                current_line.append(word)
            else:
                if current_line:
                    line_surf = self.side_font.render(' '.join(current_line), True, TEXT_COLOR)
                    self.screen.blit(line_surf, (panel_rect.x + 10, y))
                    y += 24
                current_line = [word]
        if current_line:
            line_surf = self.side_font.render(' '.join(current_line), True, TEXT_COLOR)
            self.screen.blit(line_surf, (panel_rect.x + 10, y))
            y += 24
            
        y += 10
        
        # Captured pieces helper
        def draw_captured(label, pieces, start_y):
            lbl = self.side_font.render(label, True, TEXT_COLOR)
            self.screen.blit(lbl, (panel_rect.x + 10, start_y))
            start_y += 22
            
            if not pieces:
                return start_y + 35
            
            icon_size = SQUARE_SIZE // 3
            available_width = panel_rect.width - 20
            count = len(pieces)
            step = 20 # default spacing
            
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
        text = self.side_font.render("Moves:", True, TEXT_COLOR)
        self.screen.blit(text, (panel_rect.x + 10, y))
        y += 22
        
        # Format moves into "1. e4 e5" style
        formatted_lines = []
        for i in range(0, len(self.game.move_log), 2):
            move_num = i // 2 + 1
            white_move = self.game.move_log[i]
            if i + 1 < len(self.game.move_log):
                black_move = self.game.move_log[i+1]
                formatted_lines.append(f"{move_num}. {white_move} {black_move}")
            else:
                formatted_lines.append(f"{move_num}. {white_move}")
                
        max_lines = 12
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
                    # Dragging logic
                    if self.interaction.dragging and self.interaction.selected:
                        pass # Just trigger redraw
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
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if self.state == "playing":
                    if self.promotion_dialog is not None and self.interaction.awaiting_promotion:
                        if self.promotion_dialog.handle_mouse_down(pos):
                            continue
                    if self.board_renderer.board_rect().collidepoint(pos):
                        self.handle_board_click(pos)
                        # Start Drag
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
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.state == "playing" and self.interaction.dragging:
                    pos = event.pos
                    self.interaction.dragging = False
                    self.interaction.drag_piece = None
                    
                    # Try to complete move
                    square = self.board_renderer.pixel_to_square(*pos)
                    if square and self.interaction.selected:
                        r, c = square
                        # If released on same square, do nothing (keep selected)
                        if (r, c) == self.interaction.selected:
                            continue
                        
                        # Try to move
                        self.handle_board_click(pos, animate=False)

    def draw(self) -> None:
        if self.state in ["menu", "difficulty", "settings", "color_selection"]:
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
                
            # Preview Area
            if self.settings_tab in ["Pieces", "Board"]:
                preview_rect = pygame.Rect(450, 100, 400, 400)
                pygame.draw.rect(self.screen, (40, 40, 40), preview_rect)
                pygame.draw.rect(self.screen, (100, 100, 100), preview_rect, 2)
                
                # Get theme colors
                theme_name = self.settings["theme"]
                if theme_name == "Classic": theme_name = "Brown"
                light, dark = self.board_renderer.themes.get(theme_name, ((240, 217, 181), (181, 136, 99)))
                
                # Draw 4x4 grid
                sq_size = 100
                for r in range(4):
                    for c in range(4):
                        color = light if (r + c) % 2 == 0 else dark
                        pygame.draw.rect(self.screen, color, 
                                         (preview_rect.x + c * sq_size, preview_rect.y + r * sq_size, sq_size, sq_size))
                
                # Draw sample pieces
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
        
        # Draw dragged piece
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
            
            # Check for AI move result
            if not self.ai_move_queue.empty():
                ai_move = self.ai_move_queue.get()
                if ai_move:
                    self.current_animation = MoveAnimation(self.board_renderer, self.game, ai_move)
                    self.pending_move = (ai_move, True)
                self.ai_thread = None
            
            self.draw()
            if self.current_animation is not None and self.current_animation.is_done():
                if self.pending_move is not None:
                    move, is_ai = self.pending_move
                    self.apply_move_with_sound(move)
                    self.pending_move = None
                    self.current_animation = None
                    if not is_ai:
                        self.maybe_start_ai_move()
                else:
                    self.current_animation = None
            self.clock.tick(60)
        pygame.quit()


def run() -> None:
    window = GameWindow()
    window.run()
