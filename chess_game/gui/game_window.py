from typing import Optional, Set, Tuple, List
from pathlib import Path
import pygame
import random
from ..game_logic import Game
from ..ai_opponent import choose_ai_move, AI_SETTINGS
from ..utils import Color, Move, indices_to_square
from ..pieces import PieceType
from .chess_board_ui import BoardRenderer, BOARD_SIZE, SQUARE_SIZE
from .menu_handler import ButtonBar, Button
from .dialogs import PromotionDialog, MessageOverlay, WinningDialog


WINDOW_WIDTH = BOARD_SIZE + 260
WINDOW_HEIGHT = BOARD_SIZE + 80
PANEL_BG = (30, 30, 30)
TEXT_COLOR = (230, 230, 230)


class InteractionState:
    def __init__(self) -> None:
        self.selected: Optional[Tuple[int, int]] = None
        self.moves_from_selected: Set[Tuple[int, int]] = set()
        self.pending_promotion_moves: List[Move] = []
        self.hint_move: Optional[Move] = None
        self.awaiting_promotion = False


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
        self.board_renderer = BoardRenderer((40, 20))
        self.side_font = pygame.font.SysFont("arial", 18)
        self.title_font = pygame.font.SysFont("arial", 48, bold=True)
        self.small_font = pygame.font.SysFont("arial", 14)
        self.button_font = pygame.font.SysFont("arial", 16)
        self.interaction = InteractionState()
        self.message_overlay = MessageOverlay(
            pygame.Rect(0, WINDOW_HEIGHT - 40, WINDOW_WIDTH, 30),
        )
        # Assets are located in chess_game/gui/assets/pieces
        base_dir = Path(__file__).resolve().parent
        pieces_dir = base_dir / "assets" / "pieces"
        self.board_renderer.piece_images.load(pieces_dir)
        self.board_renderer.piece_images.set_mode_images()
        self.button_bar = ButtonBar(
            pygame.Rect(BOARD_SIZE + 40, WINDOW_HEIGHT - 60, 260, 50),
        )
        self.button_bar.add_button("New Game", self.new_game)
        self.button_bar.add_button("Undo", self.undo_move)
        self.button_bar.add_button("Hint", self.hint)
        self.button_bar.add_button("Settings", self.menu_settings)
        # Main Menu button moved to separate location
        
        self.btn_main_menu = Button(
            pygame.Rect(40, WINDOW_HEIGHT - 60, 120, 40),
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
        self.promotion_dialog: Optional[PromotionDialog] = None
        self.winning_dialog: Optional[WinningDialog] = None
        self.current_animation: Optional[MoveAnimation] = None
        self.pending_move: Optional[Tuple[Move, bool]] = None
        self.state = "menu"
        self.settings = {
            "theme": "Green",
            "sound_move": True,
            "sound_capture": True
        }
        self.menu_buttons: List[Button] = []
        self.difficulty_buttons: List[Button] = []
        self.settings_buttons: List[Button] = []
        self.color_buttons: List[Button] = []
        self.background_surface = self._create_background()
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

    def update_settings_buttons(self) -> None:
        self.settings_buttons = []
        center_x = WINDOW_WIDTH // 2
        start_y = WINDOW_HEIGHT // 2 - 140
        
        # Helper to create a row of radio buttons
        def add_row(y, options, current_val, callback_factory):
            total_w = sum(opt[1] for opt in options) + (len(options) - 1) * 10
            start_x = center_x - total_w // 2
            current_x = start_x
            
            for label, w, val in options:
                is_selected = (val == current_val)
                cb = callback_factory(val)
                rect = pygame.Rect(current_x, y, w, 40)
                self.settings_buttons.append(Button(rect, label, cb, selected=is_selected))
                current_x += w + 10

        # Piece Mode
        mode = self.board_renderer.piece_images.mode
        add_row(start_y, [("Logos", 100, "images"), ("Letters", 100, "letters")], mode, 
                lambda v: (lambda: self.set_piece_mode(v)))
        
        # Theme
        curr_theme = self.settings["theme"]
        themes = [("Classic", 80, "Classic"), ("Blue", 60, "Blue"), ("Green", 70, "Green"), ("B&W", 60, "B&W")]
        add_row(start_y + 60, themes, curr_theme, lambda v: (lambda: self.set_theme_mode(v)))
        
        # Sound
        snd = self.settings["sound_move"]
        add_row(start_y + 120, [("Sound On", 100, True), ("Sound Off", 100, False)], snd, 
                lambda v: (lambda: self.set_sound_mode(v)))

        # Back
        self.settings_buttons.append(Button(pygame.Rect(center_x - 100, start_y + 200, 200, 40), "Back", self.menu_back_to_main))

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
        self.new_game()
        self.state = "playing"

    def menu_settings(self) -> None:
        self.state = "settings"
        self.update_settings_buttons()

    def menu_back_to_main(self) -> None:
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
        if self.game.undo_last_move():
            self.interaction = InteractionState()
            self.message_overlay.show("Move undone", frames=120)
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

    def handle_board_click(self, pos: Tuple[int, int]) -> None:
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
        if self.interaction.selected is None:
            if piece is None or piece.color is not board.current_player:
                self.board_renderer.trigger_invalid_flash()
                return
            self.interaction.selected = (row, col)
            self.interaction.moves_from_selected = self.compute_moves_from(row, col)
            self.interaction.hint_move = None
            return
        if self.interaction.selected == (row, col):
            self.interaction.selected = None
            self.interaction.moves_from_selected.clear()
            return
        if piece is not None and piece.color is board.current_player:
            self.interaction.selected = (row, col)
            self.interaction.moves_from_selected = self.compute_moves_from(row, col)
            self.interaction.hint_move = None
            return
        targets = self.interaction.moves_from_selected
        if (row, col) not in targets:
            self.board_renderer.trigger_invalid_flash()
            return
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
        self.apply_move_and_maybe_ai(move)
        self.interaction.selected = None
        self.interaction.moves_from_selected.clear()

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

    def apply_move_and_maybe_ai(self, move: Move) -> None:
        if self.current_animation is not None:
            return
        self.current_animation = MoveAnimation(self.board_renderer, self.game, move)
        self.pending_move = (move, False)

    def maybe_start_ai_move(self) -> None:
        if not self.mode_human_vs_ai or self.game.result:
            return
        if self.game.board.current_player is not self.ai_color:
            return
        self.message_overlay.show("AI thinking...", frames=180)
        pygame.display.flip()
        pygame.event.pump()
        ai_move = choose_ai_move(
            self.game.board,
            self.ai_color,
            self.ai_depth,
            self.ai_randomness,
        )
        if ai_move is None:
            return
        self.current_animation = MoveAnimation(self.board_renderer, self.game, ai_move)
        self.pending_move = (ai_move, True)

    def draw_side_panel(self) -> None:
        panel_rect = pygame.Rect(BOARD_SIZE + 40, 20, WINDOW_WIDTH - BOARD_SIZE - 60, BOARD_SIZE - 40)
        pygame.draw.rect(self.screen, PANEL_BG, panel_rect)
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
        text = self.side_font.render("Captured White:", True, TEXT_COLOR)
        self.screen.blit(text, (panel_rect.x + 10, y))
        y += 22
        x = panel_rect.x + 10
        for piece in self.game.captured_white:
            image = self.board_renderer.piece_images.get(piece)
            if image is not None:
                small = pygame.transform.smoothscale(
                    image,
                    (SQUARE_SIZE // 3, SQUARE_SIZE // 3),
                )
                rect_img = small.get_rect(topleft=(x, y))
                self.screen.blit(small, rect_img)
                x += 20
        y += 35
        text = self.side_font.render("Captured Black:", True, TEXT_COLOR)
        self.screen.blit(text, (panel_rect.x + 10, y))
        y += 22
        x = panel_rect.x + 10
        for piece in self.game.captured_black:
            image = self.board_renderer.piece_images.get(piece)
            if image is not None:
                small = pygame.transform.smoothscale(
                    image,
                    (SQUARE_SIZE // 3, SQUARE_SIZE // 3),
                )
                rect_img = small.get_rect(topleft=(x, y))
                self.screen.blit(small, rect_img)
                x += 20
        y += 32
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
                elif self.state == "menu":
                    for b in self.menu_buttons:
                        b.handle_mouse_move(pos)
                elif self.state == "difficulty":
                    for b in self.difficulty_buttons:
                        b.handle_mouse_move(pos)
                elif self.state == "settings":
                    for b in self.settings_buttons:
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
                elif self.state == "color_selection":
                    for b in self.color_buttons:
                        b.handle_mouse_down(pos)

    def draw(self) -> None:
        if self.state in ["menu", "difficulty", "settings", "color_selection"]:
            self.screen.blit(self.background_surface, (0, 0))
        else:
            self.screen.fill((20, 20, 20))

        if self.state == "menu":
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
            rect = title.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 180))
            self.screen.blit(title, rect)
            pygame.draw.line(self.screen, (100, 100, 100), 
                             (WINDOW_WIDTH // 2 - 100, rect.bottom + 10), 
                             (WINDOW_WIDTH // 2 + 100, rect.bottom + 10), 2)
            for b in self.settings_buttons:
                b.draw(self.screen, self.button_font)
            self.message_overlay.draw(self.screen, self.small_font)
            pygame.display.flip()
            return
        if self.state == "color_selection":
            title = self.side_font.render("Choose Your Side", True, (255, 255, 255))
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
        self.board_renderer.draw_board(
            self.screen,
            self.game.board,
            self.interaction.selected,
            self.interaction.moves_from_selected,
            self.game.last_move,
            self.interaction.hint_move,
            hide_pieces,
            king_pos,
        )
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
            self.draw()
            if self.current_animation is not None and self.current_animation.is_done():
                if self.pending_move is not None:
                    move, is_ai = self.pending_move
                    self.game.apply_move(move)
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
