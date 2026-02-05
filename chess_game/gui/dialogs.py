from typing import Optional, Callable, List, Tuple, Any
import pygame
from chess_game.pieces import Piece, PieceType
from chess_game.utils import Color


class PromotionDialog:
    def __init__(
        self,
        rect: pygame.Rect,
        on_choice: Callable[[str], None],
        piece_images: Any,
        color: Color
    ) -> None:
        self.rect = rect
        self.on_choice = on_choice
        self.piece_images = piece_images
        self.color = color
        self.options = ["Q", "R", "B", "N"]
        self.option_pieces = {
            "Q": Piece(color, PieceType.QUEEN),
            "R": Piece(color, PieceType.ROOK),
            "B": Piece(color, PieceType.BISHOP),
            "N": Piece(color, PieceType.KNIGHT)
        }
        self.option_rects: List[pygame.Rect] = []

    def layout(self) -> None:
        self.option_rects.clear()
        width = self.rect.width // len(self.options)
        for i, _ in enumerate(self.options):
            x = self.rect.x + i * width
            self.option_rects.append(pygame.Rect(x, self.rect.y, width, self.rect.height))

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        pygame.draw.rect(surface, (40, 40, 40), self.rect, border_radius=6)
        pygame.draw.rect(surface, (200, 200, 200), self.rect, 2, border_radius=6)
        
        for option, rect in zip(self.options, self.option_rects):
            piece = self.option_pieces[option]
            img = self.piece_images.get(piece)
            
            if img:
                # Scale if necessary (images are usually sized for board squares)
                # Rect height is 60. Square size is likely bigger (75).
                # piece_images.get returns a surface sized for the board.
                # We might need to scale it down to fit the dialog button.
                
                # Check image size
                if img.get_height() > rect.height - 10:
                    scale = (rect.height - 10) / img.get_height()
                    new_size = (int(img.get_width() * scale), int(img.get_height() * scale))
                    img = pygame.transform.smoothscale(img, new_size)
                    
                img_rect = img.get_rect(center=rect.center)
                surface.blit(img, img_rect)
            else:
                text = font.render(option, True, (230, 230, 230))
                t_rect = text.get_rect(center=rect.center)
                surface.blit(text, t_rect)

    def handle_mouse_down(self, pos) -> bool:
        for option, rect in zip(self.options, self.option_rects):
            if rect.collidepoint(pos):
                self.on_choice(option)
                return True
        return False


class MessageOverlay:
    def __init__(self, rect: pygame.Rect) -> None:
        self.rect = rect
        self.text = ""
        self.frames_remaining = 0

    def show(self, text: str, frames: int = 180) -> None:
        self.text = text
        self.frames_remaining = frames

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if self.frames_remaining <= 0 or not self.text:
            return
        self.frames_remaining -= 1
        # Create a surface with alpha channel for transparency
        s = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        s.fill((0, 0, 0, 150))
        surface.blit(s, self.rect)
        
        text = font.render(self.text, True, (255, 255, 255))
        rect = text.get_rect(center=self.rect.center)
        surface.blit(text, rect)


class WinningDialog:
    def __init__(
        self,
        rect: pygame.Rect,
        title: str,
        on_restart: Callable[[], None],
        on_menu: Callable[[], None]
    ) -> None:
        self.rect = rect
        self.title = title
        self.on_restart = on_restart
        self.on_menu = on_menu
        
        # Calculate button rects
        w = 120
        h = 40
        spacing = 20
        total_w = 2 * w + spacing
        start_x = rect.centerx - total_w // 2
        y = rect.centery + 10
        
        self.restart_rect = pygame.Rect(start_x, y, w, h)
        self.menu_rect = pygame.Rect(start_x + w + spacing, y, w, h)
        self.hover_restart = False
        self.hover_menu = False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        # Overlay background (full screen dim)
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        
        # Dialog box
        pygame.draw.rect(surface, (50, 50, 50), self.rect, border_radius=12)
        pygame.draw.rect(surface, (255, 255, 255), self.rect, 2, border_radius=12)
        
        # Title
        title_surf = font.render(self.title, True, (255, 255, 255))
        title_rect = title_surf.get_rect(center=(self.rect.centerx, self.rect.y + 40))
        surface.blit(title_surf, title_rect)
        
        # Buttons
        restart_color = (66, 224, 133) if self.hover_restart else (46, 204, 113)
        menu_color = (251, 96, 80) if self.hover_menu else (231, 76, 60)
        
        self._draw_button(surface, font, self.restart_rect, "Restart", restart_color)
        self._draw_button(surface, font, self.menu_rect, "Main Menu", menu_color)

    def _draw_button(self, surface, font, rect, text, color):
        pygame.draw.rect(surface, color, rect, border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255), rect, 1, border_radius=8)
        txt = font.render(text, True, (255, 255, 255))
        txt_rect = txt.get_rect(center=rect.center)
        surface.blit(txt, txt_rect)

    def handle_mouse_move(self, pos: Tuple[int, int]) -> None:
        self.hover_restart = self.restart_rect.collidepoint(pos)
        self.hover_menu = self.menu_rect.collidepoint(pos)

    def handle_mouse_down(self, pos: Tuple[int, int]) -> bool:
        if self.restart_rect.collidepoint(pos):
            self.on_restart()
            return True
        if self.menu_rect.collidepoint(pos):
            self.on_menu()
            return True
        return False
