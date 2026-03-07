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

class SimplePopup:
    def __init__(self, rect: pygame.Rect, title: str, message: str) -> None:
        self.rect = rect
        self.title = title
        self.message = message
        self.buttons: List[Tuple[str, pygame.Rect, Callable[[], None]]] = []
        self.hover: List[bool] = []

    def add_button(self, label: str, callback: Callable[[], None]) -> None:
        y = self.rect.y + 120 + len(self.buttons) * 50
        btn_rect = pygame.Rect(self.rect.centerx - 120, y, 240, 40)
        self.buttons.append((label, btn_rect, callback))
        self.hover.append(False)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, small_font: pygame.font.Font) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surface.blit(overlay, (0, 0))
        pygame.draw.rect(surface, (50, 50, 50), self.rect, border_radius=12)
        pygame.draw.rect(surface, (255, 255, 255), self.rect, 2, border_radius=12)
        title_surf = font.render(self.title, True, (255, 255, 255))
        title_rect = title_surf.get_rect(center=(self.rect.centerx, self.rect.y + 40))
        surface.blit(title_surf, title_rect)
        msg = small_font.render(self.message, True, (220, 220, 220))
        msg_rect = msg.get_rect(center=(self.rect.centerx, self.rect.y + 80))
        surface.blit(msg, msg_rect)
        for i, (label, rect, _) in enumerate(self.buttons):
            color = (100, 160, 240) if self.hover[i] else (70, 130, 200)
            pygame.draw.rect(surface, color, rect, border_radius=8)
            pygame.draw.rect(surface, (255, 255, 255), rect, 1, border_radius=8)
            txt = font.render(label, True, (255, 255, 255))
            surface.blit(txt, txt.get_rect(center=rect.center))

    def handle_mouse_move(self, pos: Tuple[int, int]) -> None:
        for i, (_, rect, _) in enumerate(self.buttons):
            self.hover[i] = rect.collidepoint(pos)

    def handle_mouse_down(self, pos: Tuple[int, int]) -> bool:
        for _, rect, cb in self.buttons:
            if rect.collidepoint(pos):
                cb()
                return True
        return False

class TextPopup:
    def __init__(self, rect: pygame.Rect, title: str, text: str) -> None:
        self.rect = rect
        self.title = title
        self.text = text
        self.buttons: List[Tuple[str, pygame.Rect, Callable[[], None]]] = []
        self.hover: List[bool] = []
        self.scroll = 0

    def add_button(self, label: str, callback: Callable[[], None]) -> None:
        y = self.rect.bottom - 60
        w = 140
        spacing = 20
        i = len(self.buttons)
        start_x = self.rect.centerx - (w * 2 + spacing) // 2
        btn_rect = pygame.Rect(start_x + i * (w + spacing), y, w, 40)
        self.buttons.append((label, btn_rect, callback))
        self.hover.append(False)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, small_font: pygame.font.Font) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surface.blit(overlay, (0, 0))
        pygame.draw.rect(surface, (50, 50, 50), self.rect, border_radius=12)
        pygame.draw.rect(surface, (255, 255, 255), self.rect, 2, border_radius=12)
        title_surf = font.render(self.title, True, (255, 255, 255))
        title_rect = title_surf.get_rect(center=(self.rect.centerx, self.rect.y + 30))
        surface.blit(title_surf, title_rect)
        box = pygame.Rect(self.rect.x + 16, self.rect.y + 60, self.rect.width - 32, self.rect.height - 130)
        pygame.draw.rect(surface, (20, 20, 20), box, border_radius=8)
        pygame.draw.rect(surface, (200, 200, 200), box, 1, border_radius=8)
        clip = surface.subsurface(box).copy()
        clip.fill((20, 20, 20))
        y = -self.scroll
        for line in self.text.splitlines():
            line_surf = small_font.render(line, True, (240, 240, 240))
            clip.blit(line_surf, (8, y))
            y += line_surf.get_height() + 4
        surface.blit(clip, box.topleft)
        for i, (label, rect, _) in enumerate(self.buttons):
            color = (100, 160, 240) if self.hover[i] else (70, 130, 200)
            pygame.draw.rect(surface, color, rect, border_radius=8)
            pygame.draw.rect(surface, (255, 255, 255), rect, 1, border_radius=8)
            txt = font.render(label, True, (255, 255, 255))
            surface.blit(txt, txt.get_rect(center=rect.center))

    def handle_mouse_move(self, pos: Tuple[int, int]) -> None:
        for i, (_, rect, _) in enumerate(self.buttons):
            self.hover[i] = rect.collidepoint(pos)

    def handle_mouse_down(self, pos: Tuple[int, int]) -> bool:
        for _, rect, cb in self.buttons:
            if rect.collidepoint(pos):
                cb()
                return True
        return False

    def handle_wheel(self, delta: int) -> None:
        self.scroll = max(0, self.scroll - delta * 20)

class InputPopup:
    def __init__(self, rect: pygame.Rect, title: str, prompt: str) -> None:
        self.rect = rect
        self.title = title
        self.prompt = prompt
        self.text = ""
        self.buttons: List[Tuple[str, pygame.Rect, Callable[[], None]]] = []
        self.hover: List[bool] = []

    def add_button(self, label: str, callback: Callable[[], None]) -> None:
        y = self.rect.bottom - 60
        w = 160
        spacing = 20
        count = len(self.buttons)
        start_x = self.rect.centerx - (w * 2 + spacing) // 2
        btn_rect = pygame.Rect(start_x + count * (w + spacing), y, w, 40)
        self.buttons.append((label, btn_rect, callback))
        self.hover.append(False)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, small_font: pygame.font.Font) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surface.blit(overlay, (0, 0))
        pygame.draw.rect(surface, (50, 50, 50), self.rect, border_radius=12)
        pygame.draw.rect(surface, (255, 255, 255), self.rect, 2, border_radius=12)
        title_surf = font.render(self.title, True, (255, 255, 255))
        title_rect = title_surf.get_rect(center=(self.rect.centerx, self.rect.y + 30))
        surface.blit(title_surf, title_rect)
        prompt_surf = small_font.render(self.prompt, True, (220, 220, 220))
        surface.blit(prompt_surf, (self.rect.x + 20, self.rect.y + 70))
        input_rect = pygame.Rect(self.rect.x + 20, self.rect.y + 100, self.rect.width - 40, 32)
        pygame.draw.rect(surface, (20, 20, 20), input_rect, border_radius=6)
        pygame.draw.rect(surface, (200, 200, 200), input_rect, 1, border_radius=6)
        display_text = self.text.replace("\r", " ").replace("\n", " ")
        text_surf = small_font.render(display_text, True, (255, 255, 255))
        inner_width = input_rect.width - 16
        text_w = text_surf.get_width()
        overflow = text_w - inner_width
        if overflow < 0:
            overflow = 0
        prev_clip = surface.get_clip()
        surface.set_clip(input_rect)
        surface.blit(text_surf, (input_rect.x + 8 - overflow, input_rect.y + 6))
        surface.set_clip(prev_clip)
        # Caret blink
        try:
            ticks = pygame.time.get_ticks()
        except Exception:
            ticks = 0
        if (ticks // 500) % 2 == 0:
            caret_x = input_rect.x + 8 + text_surf.get_width() - overflow + 2
            caret_y = input_rect.y + 6
            prev_clip = surface.get_clip()
            surface.set_clip(input_rect)
            pygame.draw.rect(surface, (255, 255, 255), pygame.Rect(caret_x, caret_y, 2, text_surf.get_height()))
            surface.set_clip(prev_clip)
        for i, (label, rect, _) in enumerate(self.buttons):
            color = (90, 160, 90) if self.hover[i] else (70, 130, 70)
            pygame.draw.rect(surface, color, rect, border_radius=8)
            pygame.draw.rect(surface, (255, 255, 255), rect, 1, border_radius=8)
            txt = font.render(label, True, (255, 255, 255))
            surface.blit(txt, txt.get_rect(center=rect.center))

    def handle_mouse_move(self, pos: Tuple[int, int]) -> None:
        for i, (_, rect, _) in enumerate(self.buttons):
            self.hover[i] = rect.collidepoint(pos)

    def handle_mouse_down(self, pos: Tuple[int, int]) -> bool:
        for _, rect, cb in self.buttons:
            if rect.collidepoint(pos):
                cb()
                return True
        return False

    def handle_key(self, event: pygame.event.Event) -> None:
        mods = getattr(event, "mod", pygame.key.get_mods())
        if (event.key == pygame.K_v and (mods & pygame.KMOD_CTRL)) or (event.key == pygame.K_INSERT and (mods & pygame.KMOD_SHIFT)):
            paste = ""
            try:
                import pygame.scrap as scrap
                scrap.init()
                data = scrap.get(scrap.SCRAP_TEXT)
                if data:
                    try:
                        paste = data.decode("utf-8", errors="ignore")
                    except Exception:
                        paste = ""
            except Exception:
                try:
                    import pyperclip
                    paste = pyperclip.paste()
                except Exception:
                    try:
                        import tkinter as tk
                        r = tk.Tk()
                        r.withdraw()
                        try:
                            paste = r.clipboard_get()
                        except Exception:
                            paste = ""
                        r.destroy()
                    except Exception:
                        try:
                            import ctypes
                            CF_UNICODETEXT = 13
                            user32 = ctypes.windll.user32
                            kernel32 = ctypes.windll.kernel32
                            if user32.OpenClipboard(0):
                                h = user32.GetClipboardData(CF_UNICODETEXT)
                                if h:
                                    p = kernel32.GlobalLock(h)
                                    if p:
                                        try:
                                            paste = ctypes.wstring_at(p)
                                        finally:
                                            kernel32.GlobalUnlock(h)
                                user32.CloseClipboard()
                        except Exception:
                            paste = ""
            if paste:
                self.text += paste
        elif event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
        elif event.key == pygame.K_RETURN:
            pass
        else:
            if event.unicode and len(event.unicode) == 1:
                self.text += event.unicode


class WinningDialog:
    def __init__(
        self,
        rect: pygame.Rect,
        title: str,
        on_restart: Callable[[], None],
        on_menu: Callable[[], None],
        on_save: Callable[[], None],
        on_export: Callable[[], None],
    ) -> None:
        self.rect = rect
        self.title = title
        self.on_restart = on_restart
        self.on_menu = on_menu
        self.on_save = on_save
        self.on_export = on_export
        
        w = 120
        h = 40
        spacing = 20
        total_w = 2 * w + spacing
        start_x = rect.centerx - total_w // 2
        y_top = self.rect.y + 90
        y_bottom = y_top + h + 10
        
        self.restart_rect = pygame.Rect(start_x, y_top, w, h)
        self.menu_rect = pygame.Rect(start_x + w + spacing, y_top, w, h)
        self.save_rect = pygame.Rect(start_x, y_bottom, w, h)
        self.export_rect = pygame.Rect(start_x + w + spacing, y_bottom, w, h)
        self.hover_restart = False
        self.hover_menu = False
        self.hover_save = False
        self.hover_export = False

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        
        pygame.draw.rect(surface, (50, 50, 50), self.rect, border_radius=12)
        pygame.draw.rect(surface, (255, 255, 255), self.rect, 2, border_radius=12)
        
        title_surf = font.render(self.title, True, (255, 255, 255))
        title_rect = title_surf.get_rect(center=(self.rect.centerx, self.rect.y + 40))
        surface.blit(title_surf, title_rect)
        
        restart_color = (66, 224, 133) if self.hover_restart else (46, 204, 113)
        menu_color = (251, 96, 80) if self.hover_menu else (231, 76, 60)
        save_color = (52, 152, 219) if self.hover_save else (41, 128, 185)
        export_color = (155, 89, 182) if self.hover_export else (142, 68, 173)
        
        self._draw_button(surface, font, self.restart_rect, "Restart", restart_color)
        self._draw_button(surface, font, self.menu_rect, "Main Menu", menu_color)
        self._draw_button(surface, font, self.save_rect, "Save", save_color)
        self._draw_button(surface, font, self.export_rect, "Export PGN", export_color)

    def _draw_button(self, surface, font, rect, text, color):
        pygame.draw.rect(surface, color, rect, border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255), rect, 1, border_radius=8)
        txt = font.render(text, True, (255, 255, 255))
        txt_rect = txt.get_rect(center=rect.center)
        surface.blit(txt, txt_rect)

    def handle_mouse_move(self, pos: Tuple[int, int]) -> None:
        self.hover_restart = self.restart_rect.collidepoint(pos)
        self.hover_menu = self.menu_rect.collidepoint(pos)
        self.hover_save = self.save_rect.collidepoint(pos)
        self.hover_export = self.export_rect.collidepoint(pos)

    def handle_mouse_down(self, pos: Tuple[int, int]) -> bool:
        if self.restart_rect.collidepoint(pos):
            self.on_restart()
            return True
        if self.menu_rect.collidepoint(pos):
            self.on_menu()
            return True
        if self.save_rect.collidepoint(pos):
            self.on_save()
            return True
        if self.export_rect.collidepoint(pos):
            self.on_export()
            return True
        return False
