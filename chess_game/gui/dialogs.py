from typing import Optional, Callable, List
import pygame


class PromotionDialog:
    def __init__(
        self,
        rect: pygame.Rect,
        on_choice: Callable[[str], None],
    ) -> None:
        self.rect = rect
        self.on_choice = on_choice
        self.options = ["Q", "R", "B", "N"]
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
        pygame.draw.rect(surface, (0, 0, 0, 150), self.rect)
        text = font.render(self.text, True, (255, 255, 255))
        rect = text.get_rect(center=self.rect.center)
        surface.blit(text, rect)

