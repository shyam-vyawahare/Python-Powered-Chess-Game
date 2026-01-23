from typing import List, Tuple, Optional, Callable
import pygame


class Button:
    def __init__(
        self,
        rect: pygame.Rect,
        label: str,
        callback: Callable[[], None],
        selected: bool = False,
        icon: Optional[pygame.Surface] = None,
    ) -> None:
        self.rect = rect
        self.label = label
        self.callback = callback
        self.hover = False
        self.selected = selected
        self.icon = icon

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if self.selected:
            color = (46, 204, 113)  # Green for selected
            text_color = (255, 255, 255)
            border_color = (255, 255, 255)
        elif self.hover:
            color = (90, 90, 90)
            text_color = (255, 255, 255)
            border_color = (180, 180, 180)
        else:
            color = (60, 60, 60)
            text_color = (220, 220, 220)
            border_color = (100, 100, 100)

        # Shadow
        shadow_rect = self.rect.copy()
        shadow_rect.y += 3
        pygame.draw.rect(surface, (20, 20, 20), shadow_rect, border_radius=8)

        # Main Body
        pygame.draw.rect(surface, color, self.rect, border_radius=8)
        
        # Border
        pygame.draw.rect(surface, border_color, self.rect, 2 if self.selected else 1, border_radius=8)

        if self.icon:
            # Draw icon on left or center if no label
            icon_rect = self.icon.get_rect(midleft=(self.rect.x + 12, self.rect.centery))
            surface.blit(self.icon, icon_rect)
            # Draw label to right of icon
            if self.label:
                text = font.render(self.label, True, text_color)
                # Center text in remaining space
                remaining_w = self.rect.width - (icon_rect.right - self.rect.x)
                center_x = icon_rect.right + remaining_w // 2
                text_rect = text.get_rect(center=(center_x, self.rect.centery))
                surface.blit(text, text_rect)
        else:
            text = font.render(self.label, True, text_color)
            rect = text.get_rect(center=self.rect.center)
            surface.blit(text, rect)
            
        # Hover glow effect (subtle)
        if self.hover and not self.selected:
             glow = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
             pygame.draw.rect(glow, (255, 255, 255, 30), glow.get_rect(), border_radius=8)
             surface.blit(glow, self.rect)

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

