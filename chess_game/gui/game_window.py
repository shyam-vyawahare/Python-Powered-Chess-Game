from typing import Optional, Set, Tuple, List
from pathlib import Path
import pygame
from ..game_logic import Game
from ..ai_opponent import choose_ai_move, AI_SETTINGS
from ..utils import Color, Move, indices_to_square
from ..pieces import PieceType
from .chess_board_ui import BoardRenderer, BOARD_SIZE, SQUARE_SIZE
from .menu_handler import ButtonBar
from .dialogs import PromotionDialog, MessageOverlay


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

class Button:
    def __init__(self, rect, text, callback):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.callback = callback
        self.hovered = False

    def handle_mouse_move(self, pos):
        self.hovered = self.rect.collidepoint(pos)

    def handle_mouse_down(self, pos):
        if self.rect.collidepoint(pos):
            self.callback()

    def draw(self, screen, font):
        color = (100, 160, 220) if self.hovered else (70, 130, 180)

        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        pygame.draw.rect(screen, (255, 255, 255), self.rect, 2, border_radius=8)

        text_surf = font.render(self.text, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)



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
        self.small_font = pygame.font.SysFont("arial", 14)
        self.button_font = pygame.font.SysFont("arial", 16)
        self.interaction = InteractionState()
        self.message_overlay = MessageOverlay(
            pygame.Rect(0, WINDOW_HEIGHT - 40, WINDOW_WIDTH, 30),
        )
        base_dir = Path(__file__).resolve().parent.parent.parent
        pieces_dir = base_dir / "assets" / "pieces"
        self.board_renderer.piece_images.load(pieces_dir)
        self.board_renderer.piece_images.set_mode_images()
        self.button_bar = ButtonBar(
            pygame.Rect(BOARD_SIZE + 40, WINDOW_HEIGHT - 60, 260, 50),
        )
        self.button_bar.add_button("New Game", self.new_game)
        self.button_bar.add_button("Undo", self.undo_move)
        self.button_bar.add_button("Hint", self.hint)
        self.button_bar.add_button("Settings", self.toggle_piece_display_mode)
        self.button_bar.add_button("Menu", self.return_to_menu)
        self.mode_human_vs_ai = True
        self.human_color = Color.WHITE
        self.ai_color = Color.BLACK
        self.ai_level_names = ["Easy", "Medium", "Hard"]
        self.ai_level_index = 1
        self.ai_depth = 3
        self.ai_randomness = 0.1
        self.promotion_dialog: Optional[PromotionDialog] = None
        self.current_animation: Optional[MoveAnimation] = None
        self.pending_move: Optional[Tuple[Move, bool]] = None
        self.state = "menu"
        self.menu_buttons: List = []
        self.difficulty_buttons: List = []
        self.create_menus()

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
        self.toggle_piece_display_mode()

    def menu_back_to_main(self) -> None:
        self.state = "menu"

    def menu_start_single_with_level(self, level_label: str) -> None:
        if level_label in self.ai_level_names:
            self.ai_level_index = self.ai_level_names.index(level_label)
        self.apply_ai_settings()
        self.mode_human_vs_ai = True
        self.human_color = Color.WHITE
        self.ai_color = Color.BLACK
        self.new_game()
        self.state = "playing"

    def toggle_piece_display_mode(self) -> None:
        images_mode = self.board_renderer.piece_images.mode == "images"
        if images_mode:
            self.board_renderer.piece_images.set_mode_letters()
            self.message_overlay.show("Piece style: Letters", frames=180)
        else:
            self.board_renderer.piece_images.set_mode_images()
            self.message_overlay.show("Piece style: Images", frames=180)

    def return_to_menu(self) -> None:
        self.new_game()
        self.state = "menu"

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
        for label in [
            "Game Info",
            "Turn: " + turn,
            "Status: " + status,
        ]:
            text = self.side_font.render(label, True, TEXT_COLOR)
            self.screen.blit(text, (panel_rect.x + 10, y))
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
                    (SQUARE_SIZE // 2, SQUARE_SIZE // 2),
                )
                rect_img = small.get_rect(topleft=(x, y))
                self.screen.blit(small, rect_img)
                x += rect_img.width + 4
        y += 28
        text = self.side_font.render("Captured Black:", True, TEXT_COLOR)
        self.screen.blit(text, (panel_rect.x + 10, y))
        y += 22
        x = panel_rect.x + 10
        for piece in self.game.captured_black:
            image = self.board_renderer.piece_images.get(piece)
            if image is not None:
                small = pygame.transform.smoothscale(
                    image,
                    (SQUARE_SIZE // 2, SQUARE_SIZE // 2),
                )
                rect_img = small.get_rect(topleft=(x, y))
                self.screen.blit(small, rect_img)
                x += rect_img.width + 4
        y += 32
        text = self.side_font.render("Moves:", True, TEXT_COLOR)
        self.screen.blit(text, (panel_rect.x + 10, y))
        y += 22
        max_lines = 12
        recent_moves = self.game.move_log[-max_lines:]
        for idx, entry in enumerate(recent_moves, start=max(1, len(self.game.move_log) - len(recent_moves) + 1)):
            line = f"{idx}: {entry}"
            glyph = self.small_font.render(line, True, TEXT_COLOR)
            self.screen.blit(glyph, (panel_rect.x + 10, y))
            y += 18

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == "playing":
                        self.return_to_menu()
            elif event.type == pygame.MOUSEMOTION:
                pos = event.pos
                if self.state == "playing":
                    self.board_renderer.update_hover(pos)
                    self.button_bar.handle_mouse_move(pos)
                elif self.state == "menu":
                    for b in self.menu_buttons:
                        b.handle_mouse_move(pos)
                elif self.state == "difficulty":
                    for b in self.difficulty_buttons:
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
                elif self.state == "menu":
                    for b in self.menu_buttons:
                        b.handle_mouse_down(pos)
                elif self.state == "difficulty":
                    for b in self.difficulty_buttons:
                        b.handle_mouse_down(pos)

    def draw(self) -> None:
        self.screen.fill((20, 20, 20))
        if self.state == "menu":
            title = self.side_font.render("Chess Game", True, (255, 255, 255))
            rect = title.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 130))
            self.screen.blit(title, rect)
            for b in self.menu_buttons:
                b.draw(self.screen, self.button_font)
            self.message_overlay.draw(self.screen, self.small_font)
            pygame.display.flip()
            return
        if self.state == "difficulty":
            title = self.side_font.render("Select Difficulty", True, (255, 255, 255))
            rect = title.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 130))
            self.screen.blit(title, rect)
            for b in self.difficulty_buttons:
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
        if self.promotion_dialog is not None and self.interaction.awaiting_promotion:
            self.promotion_dialog.draw(self.screen, self.side_font)
        self.message_overlay.draw(self.screen, self.small_font)
        if self.current_animation is not None:
            t = self.current_animation.progress()
            for image, start_pos, end_pos in self.current_animation.pieces:
                x = start_pos[0] + (end_pos[0] - start_pos[0]) * t
                y = start_pos[1] + (end_pos[1] - start_pos[1]) * t
                shadow_radius = BOARD_SIZE // 16
                pygame.draw.circle(self.screen, (0, 0, 0), (int(x) + 2, int(y) + 2), shadow_radius)
                rect = image.get_rect(center=(int(x), int(y)))
                self.screen.blit(image, rect)
            for image, pos in self.current_animation.captured_overlays:
                alpha_t = 1.0 - t
                temp = image.copy()
                temp.set_alpha(int(255 * alpha_t))
                rect = temp.get_rect(center=(int(pos[0]), int(pos[1])))
                self.screen.blit(temp, rect)
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
