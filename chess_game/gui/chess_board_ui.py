from typing import Dict, Optional, Tuple, List, Set
from pathlib import Path
import pygame
from ..pieces import Piece
from ..utils import Color, Move
from ..board import Board


BOARD_SIZE = 560
SQUARE_SIZE = BOARD_SIZE // 8
LIGHT_SQUARE = (240, 217, 181)
DARK_SQUARE = (181, 136, 99)
HIGHLIGHT_MOVE = (186, 202, 68)
HIGHLIGHT_SELECTED = (246, 246, 105)
HIGHLIGHT_LAST_MOVE = (205, 210, 106)
HIGHLIGHT_INVALID = (220, 50, 50)
LABEL_COLOR = (200, 200, 200)


class PieceImages:
    def __init__(self) -> None:
        self.images: Dict[str, pygame.Surface] = {}
        self.letters: Dict[str, pygame.Surface] = {}
        self.fallback_font: Optional[pygame.font.Font] = None
        self.mode: str = "images"

    def load(self, base_path: Path) -> None:
        variants = {
            "white_king": ("white_king.png", "K"),
            "white_queen": ("white_queen.png", "Q"),
            "white_rook": ("white_rook.png", "R"),
            "white_bishop": ("white_bishop.png", "B"),
            "white_knight": ("white_knight.png", "N"),
            "white_pawn": ("white_pawn.png", "P"),
            "black_king": ("black_king.png", "k"),
            "black_queen": ("black_queen.png", "q"),
            "black_rook": ("black_rook.png", "r"),
            "black_bishop": ("black_bishop.png", "b"),
            "black_knight": ("black_knight.png", "n"),
            "black_pawn": ("black_pawn.png", "p"),
        }
        try:
            self.fallback_font = pygame.font.SysFont("arial", 40)
        except Exception:
            self.fallback_font = None
        for key, (filename, symbol) in variants.items():
            path = base_path / filename
            text_surface: Optional[pygame.Surface] = None
            if self.fallback_font is not None:
                text_surface = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
                color = (0, 0, 0) if symbol.islower() else (255, 255, 255)
                text = self.fallback_font.render(symbol.upper(), True, color)
                rect = text.get_rect(center=(SQUARE_SIZE // 2, SQUARE_SIZE // 2))
                text_surface.blit(text, rect)
                self.letters[key] = text_surface
            if path.is_file():
                try:
                    image = pygame.image.load(str(path)).convert_alpha()
                    image = pygame.transform.smoothscale(
                        image,
                        (SQUARE_SIZE - 10, SQUARE_SIZE - 10),
                    )
                    self.images[key] = image
                    continue
                except Exception:
                    pass
            if text_surface is not None and key not in self.letters:
                self.letters[key] = text_surface

    def set_mode_images(self) -> None:
        self.mode = "images"

    def set_mode_letters(self) -> None:
        self.mode = "letters"

    def key_for_piece(self, piece: Piece) -> str:
        color = "white" if piece.color is Color.WHITE else "black"
        kind = piece.kind.name.lower()
        return f"{color}_{kind}"

    def get(self, piece: Piece) -> Optional[pygame.Surface]:
        key = self.key_for_piece(piece)
        if self.mode == "letters":
            surface = self.letters.get(key)
            if surface is not None:
                return surface
        img = self.images.get(key)
        if img is not None and self.mode == "images":
            return img
        return self.letters.get(key, img)


class BoardRenderer:
    def __init__(self, top_left: Tuple[int, int]) -> None:
        self.offset_x, self.offset_y = top_left
        self.piece_images = PieceImages()
        self.hover_square: Optional[Tuple[int, int]] = None
        self.invalid_flash_frames = 0
        self.orientation: Color = Color.WHITE
        
        # Theme support
        self.themes = {
            "Brown": ((240, 217, 181), (181, 136, 99)),
            "Blue": ((232, 235, 239), (125, 135, 150)),
            "Green": ((238, 238, 210), (118, 150, 86)),
            "B&W": ((240, 240, 240), (50, 50, 50)),
        }
        self.light_square_color = self.themes["Green"][0]
        self.dark_square_color = self.themes["Green"][1]

    def set_theme(self, theme_name: str) -> None:
        if theme_name in self.themes:
            self.light_square_color, self.dark_square_color = self.themes[theme_name]

    def board_rect(self) -> pygame.Rect:
        return pygame.Rect(self.offset_x, self.offset_y, BOARD_SIZE, BOARD_SIZE)

    def pixel_to_square(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        x_rel = x - self.offset_x
        y_rel = y - self.offset_y
        if x_rel < 0 or y_rel < 0 or x_rel >= BOARD_SIZE or y_rel >= BOARD_SIZE:
            return None
        col = x_rel // SQUARE_SIZE
        row = y_rel // SQUARE_SIZE
        if self.orientation == Color.BLACK:
            col = 7 - col
            row = 7 - row
        return int(row), int(col)

    def square_to_rect(self, row: int, col: int) -> pygame.Rect:
        if self.orientation == Color.BLACK:
            draw_col = 7 - col
            draw_row = 7 - row
        else:
            draw_col = col
            draw_row = row
        x = self.offset_x + draw_col * SQUARE_SIZE
        y = self.offset_y + draw_row * SQUARE_SIZE
        return pygame.Rect(x, y, SQUARE_SIZE, SQUARE_SIZE)

    def update_hover(self, mouse_pos: Tuple[int, int]) -> None:
        self.hover_square = self.pixel_to_square(*mouse_pos)

    def trigger_invalid_flash(self) -> None:
        self.invalid_flash_frames = 10

    def draw_board(
        self,
        surface: pygame.Surface,
        board: Board,
        selected: Optional[Tuple[int, int]],
        moves_from_selected: Set[Tuple[int, int]],
        last_move: Optional[Move],
        hint_move: Optional[Move],
        hide_pieces: Set[Tuple[int, int]],
        king_in_check: Optional[Tuple[int, int]],
        highlight_check: bool = False,
    ) -> None:
        # Flash removed as per request
        if self.invalid_flash_frames > 0:
            self.invalid_flash_frames -= 1
        for row in range(8):
            for col in range(8):
                rect = self.square_to_rect(row, col)
                if (row + col) % 2 == 0:
                    color = self.light_square_color
                else:
                    color = self.dark_square_color
                pygame.draw.rect(surface, color, rect)
        if last_move is not None:
            for r, c in [
                (last_move.from_row, last_move.from_col),
                (last_move.to_row, last_move.to_col),
            ]:
                rect = self.square_to_rect(r, c)
                pygame.draw.rect(surface, HIGHLIGHT_LAST_MOVE, rect, 0)
        if hint_move is not None:
            rect = self.square_to_rect(hint_move.to_row, hint_move.to_col)
            pygame.draw.rect(surface, HIGHLIGHT_MOVE, rect, 0)
        if selected is not None:
            rect = self.square_to_rect(*selected)
            pygame.draw.rect(surface, HIGHLIGHT_SELECTED, rect, 0)
        for row, col in moves_from_selected:
            rect = self.square_to_rect(row, col)
            center_x, center_y = rect.center
            radius = SQUARE_SIZE // 8
            pygame.draw.circle(surface, HIGHLIGHT_MOVE, (center_x, center_y), radius)
        for row in range(8):
            for col in range(8):
                if (row, col) in hide_pieces:
                    continue
                piece = board.get_piece(row, col)
                if piece is None:
                    continue
                rect = self.square_to_rect(row, col)
                image = self.piece_images.get(piece)
                if image is not None:
                    center = rect.center
                    img_rect = image.get_rect(center=center)
                    surface.blit(image, img_rect)
        if king_in_check is not None and highlight_check:
            rect = self.square_to_rect(king_in_check[0], king_in_check[1])
            pygame.draw.rect(surface, (200, 50, 50), rect, 3)
        self.draw_labels(surface)

    def draw_labels(self, surface: pygame.Surface) -> None:
        font = pygame.font.SysFont("arial", 14)
        files = "abcdefgh"
        if self.orientation == Color.BLACK:
            files = files[::-1]
            ranks = [str(i+1) for i in range(8)]
        else:
            ranks = [str(8-i) for i in range(8)]

        for col in range(8):
            label = font.render(files[col], True, LABEL_COLOR)
            x = self.offset_x + col * SQUARE_SIZE + SQUARE_SIZE // 2
            y = self.offset_y + BOARD_SIZE + 4
            rect = label.get_rect(center=(x, y))
            surface.blit(label, rect)
        for row in range(8):
            label = font.render(ranks[row], True, LABEL_COLOR)
            x = self.offset_x - 10
            y = self.offset_y + row * SQUARE_SIZE + SQUARE_SIZE // 2
            rect = label.get_rect(center=(x, y))
            surface.blit(label, rect)
