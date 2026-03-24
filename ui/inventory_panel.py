import pygame
from game.ui.panel import Panel
from constants import SCREEN_WIDTH, scale_x, scale_y

class InventoryPanel:
    def __init__(self, font):
        self.font = font
        self.items = []
        self.scroll_index = 0
        self.visible_count = 5

    def set_items(self, items):
        # Sort by gold value (descending)
        self.items = sorted(items, key=lambda x: x.get("value", 0), reverse=True)

        # Clamp scroll
        self.scroll_index = min(self.scroll_index, max(0, len(self.items) - self.visible_count))

    # =========================
    # INPUT
    # =========================
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:  # scroll up
                self.scroll_index = max(0, self.scroll_index - 1)
            elif event.button == 5:  # scroll down
                max_scroll = max(0, len(self.items) - self.visible_count)
                self.scroll_index = min(max_scroll, self.scroll_index + 1)

    # =========================
    # DRAW
    # =========================
    def draw(self, screen):
        panel = Panel(
            SCREEN_WIDTH - scale_x(260),
            scale_y(80),
            240,
            300
        )

        rect = panel.draw(screen)

        visible_items = self.items[self.scroll_index:self.scroll_index + self.visible_count]

        for i, item in enumerate(visible_items):
            text = f"{item['name']} (${item.get('value', 0)})"
            surf = self.font.render(text, True, (255, 255, 255))

            x = rect.x + scale_x(10)
            y = rect.y + scale_y(10) + i * scale_y(50)

            screen.blit(surf, (x, y))

        # --- Scroll indicators ---
        if self.scroll_index > 0:
            up = self.font.render("^", True, (255,255,255))
            screen.blit(up, (rect.right - 20, rect.y + 5))

        if self.scroll_index + self.visible_count < len(self.items):
            down = self.font.render("v", True, (255,255,255))
            screen.blit(down, (rect.right - 20, rect.bottom - 20))