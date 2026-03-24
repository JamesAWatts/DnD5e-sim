import pygame
from constants import scale_x, scale_y

class DebugOverlay:
    def __init__(self, font):
        self.font = font
        self.padding = scale_x(10)
        self.line_height = font.get_height() + scale_y(2)

    def draw(self, screen, game):
        state = game.state

        lines = []

        # --- State info ---
        lines.append(f"State: {state.__class__.__name__}")

        # --- Player info ---
        if hasattr(game, "player") and game.player:
            hp = game.player.get("current_hp", "?")
            max_hp = game.player.get("max_hp", "?")
            lines.append(f"Player HP: {hp}/{max_hp}")

        # --- Combat-specific info ---
        if state.__class__.__name__ == "CombatState":
            lines.append(f"Phase: {getattr(state, 'phase', '?')}")
            lines.append(f"Menu: {getattr(state, 'menu_state', '?')}")

            if hasattr(state, "enemies"):
                for i, enemy in enumerate(state.enemies):
                    ehp = enemy.get("current_hp", "?")
                    max_ehp = enemy.get("max_hp", "?")
                    lines.append(f"Enemy {i}: {enemy['name']} {ehp}/{max_ehp}")

        # --- Dialogue ---
        if hasattr(state, "dialogue"):
            lines.append(f"Dialogue Active: {bool(state.dialogue.current_message)}")
            lines.append(f"Typing: {state.dialogue.is_typing}")

        # --- Controls ---
        lines.append("---- DEBUG ----")
        lines.append("ENTER: advance dialogue")
        lines.append("ESC: quit (if implemented)")

        # --- Draw background ---
        width = scale_x(300)
        height = self.padding * 2 + len(lines) * self.line_height

        bg_rect = pygame.Rect(
            self.padding,
            self.padding,
            width,
            height
        )

        pygame.draw.rect(screen, (0, 0, 0), bg_rect)
        pygame.draw.rect(screen, (0, 255, 0), bg_rect, 1)

        # --- Draw text ---
        for i, line in enumerate(lines):
            text_surface = self.font.render(line, True, (0, 255, 0))
            x = bg_rect.x + self.padding
            y = bg_rect.y + self.padding + i * self.line_height
            screen.blit(text_surface, (x, y))