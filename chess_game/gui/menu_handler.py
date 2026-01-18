from typing import List, Tuple, Optional, Callable
import pygame


class Button:
    def __init__(
        self,
        rect: pygame.Rect,
        label: str,
        callback: Callable[[], None],
    ) -> None:
        self.rect = rect
        self.label = label
        self.callback = callback
        self.hover = False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        base_color = (70, 70, 70)
        hover_color = (100, 100, 100)
        color = hover_color if self.hover else base_color
        pygame.draw.rect(surface, color, self.rect, border_radius=4)
        text = font.render(self.label, True, (230, 230, 230))
        rect = text.get_rect(center=self.rect.center)
        surface.blit(text, rect)

    def handle_mouse_move(self, pos: Tuple[int, int]) -> None:
        self.hover = self.rect.collidepoint(pos)

    def handle_mouse_down(self, pos: Tuple[int, int]) -> None:
        if self.rect.collidepoint(pos):
            self.callback()


class ButtonBar:
    def __init__(self, rect: pygame.Rect) -> None:
        self.rect = rect
        self.buttons: List[Button] = []

    def add_button(self, label: str, callback: Callable[[], None]) -> None:
        count = len(self.buttons)
        width = max(100, self.rect.width // max(4, count + 1))
        margin = 10
        x = self.rect.x + margin + count * (width + margin)
        y = self.rect.y + margin
        button_rect = pygame.Rect(x, y, width, self.rect.height - 2 * margin)
        self.buttons.append(Button(button_rect, label, callback))

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        for button in self.buttons:
            button.draw(surface, font)

    def handle_mouse_move(self, pos: Tuple[int, int]) -> None:
        for button in self.buttons:
            button.handle_mouse_move(pos)

    def handle_mouse_down(self, pos: Tuple[int, int]) -> None:
        for button in self.buttons:
            button.handle_mouse_down(pos)

