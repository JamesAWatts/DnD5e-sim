import pygame
from game.ui.panel import Panel
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, scale_y

class DialogueBox:
    def __init__(self, font):
        self.font = font

        self.messages = []
        self.current_message = ""
        self.visible_text = ""

        self.index = 0
        self.speed = 2
        self.is_typing = False

        self.finished = False

    # =========================
    # MESSAGE CONTROL
    # =========================
    def set_messages(self, messages):
        if isinstance(messages, str):
            messages = [messages]

        self.messages = messages
        self.current_message = self.messages.pop(0) if self.messages else ""
        self.visible_text = ""
        self.index = 0
        self.is_typing = True
        self.finished = False

    def next_message(self):
        if self.messages:
            self.current_message = self.messages.pop(0)
            self.visible_text = ""
            self.index = 0
            self.is_typing = True
        else:
            self.finished = True
            self.current_message = ""

    # =========================
    # UPDATE
    # =========================
    def update(self):
        if not self.is_typing:
            return

        self.index += self.speed

        if self.index >= len(self.current_message):
            self.index = len(self.current_message)
            self.is_typing = False

        self.visible_text = self.current_message[:int(self.index)]

    # =========================
    # INPUT HANDLING
    # =========================
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                if self.is_typing:
                    # Skip to full text
                    self.index = len(self.current_message)
                    self.visible_text = self.current_message
                    self.is_typing = False
                else:
                    self.next_message()

    # =========================
    # TEXT WRAPPING
    # =========================
    def wrap_text(self, text, max_width):
        words = text.split(" ")
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + word + " "
            width, _ = self.font.size(test_line)

            if width <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word + " "

        if current_line:
            lines.append(current_line)

        return lines

    # =========================
    # DRAW
    # =========================
    def draw(self, screen):
        if not self.current_message:
            return

        from constants import COLOR_MIDNIGHT_BLUE, COLOR_GOLD, COLOR_WHITE
        panel = Panel(
            SCREEN_WIDTH // 2,
            SCREEN_HEIGHT - scale_y(160),
            760,
            140,
            bg_color=COLOR_MIDNIGHT_BLUE,
            border_color=COLOR_GOLD,
            border_width=3,
            centered=True,
            border_radius=20
        )

        rect = panel.draw(screen)

        max_width = rect.width - scale_y(40)
        lines = self.wrap_text(self.visible_text, max_width)

        line_height = self.font.get_height()

        from game.ui.panel import draw_text_outlined
        for i, line in enumerate(lines[:3]):  # limit to 3 lines
            text_x = rect.x + scale_y(20)
            text_y = rect.y + scale_y(20) + i * line_height

            draw_text_outlined(screen, line, self.font, COLOR_WHITE, text_x, text_y)

        # --- Continue indicator ---
        if not self.is_typing:
            prompt_x = rect.right - scale_y(40)
            prompt_y = rect.bottom - scale_y(30)
            draw_text_outlined(screen, ">>", self.font, COLOR_WHITE, prompt_x, prompt_y)