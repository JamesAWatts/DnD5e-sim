import pygame
from ui.panel import Panel
from core.game_rules.constants import SCREEN_WIDTH, SCREEN_HEIGHT, scale_y

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
    def set_messages(self, messages, skip_typing=False):
        if isinstance(messages, str):
            messages = [messages]

        self.messages = messages
        self.current_message = self.messages.pop(0) if self.messages else ""
        self.visible_text = ""
        self.index = 0
        self.skip_typing = skip_typing
        self.is_typing = not skip_typing
        self.finished = False
        
        if skip_typing:
            self.index = len(self.current_message)
            self.visible_text = self.current_message

    def next_message(self):
        if self.messages:
            self.current_message = self.messages.pop(0)
            self.visible_text = ""
            self.index = 0
            if getattr(self, 'skip_typing', False):
                self.index = len(self.current_message)
                self.visible_text = self.current_message
                self.is_typing = False
            else:
                self.is_typing = True
        else:
            self.finished = True
            self.current_message = None # Explicitly None to clear 'busy' state
            self.is_typing = False

    # =========================
    # UPDATE
    # =========================
    def update(self):
        if not self.is_typing or not self.current_message:
            self.is_typing = False
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
        if not self.current_message: return # Safety

        if event.type == pygame.KEYDOWN:
            if event.key in [pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER]:
                if self.is_typing:
                    # Skip to full text
                    self.index = len(self.current_message)
                    self.visible_text = self.current_message
                    self.is_typing = False
                else:
                    self.next_message()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1: # Left click
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
        if not isinstance(text, str): text = str(text)

        # Support explicit newlines
        paragraphs = text.split("\n")
        all_lines = []

        for para in paragraphs:
            words = para.split(" ")
            current_line = ""

            for word in words:
                test_line = current_line + word + " "
                width, _ = self.font.size(test_line)

                if width <= max_width:
                    current_line = test_line
                else:
                    all_lines.append(current_line)
                    current_line = word + " "

            if current_line:
                all_lines.append(current_line)

        return all_lines

    # =========================
    # DRAW
    # =========================
    def draw(self, screen):
        # The Panel (the UI box itself) should ALWAYS be drawn 
        # to act as a consistent visual anchor.
        from core.game_rules.constants import COLOR_GOLD, COLOR_WHITE

        panel = Panel(
            400, # Center X
            450, # Near Bottom Y (600 - 150)
            760, # Width
            200 if getattr(self, 'skip_typing', False) else 140, # Expand for results
            border_color=COLOR_GOLD,
            border_width=3,
            centered=True,
            border_radius=20
        )

        rect = panel.draw(screen)

        # Only draw text/indicators if a message is actually active
        if self.current_message:
            max_width = rect.width - scale_y(40)
            lines = self.wrap_text(self.visible_text, max_width)
            line_height = self.font.get_height()

            from ui.panel import draw_text_outlined
            max_lines = 8 if getattr(self, 'skip_typing', False) else 3
            for i, line in enumerate(lines[:max_lines]): 
                text_x = rect.x + scale_y(20)
                text_y = rect.y + scale_y(15) + i * line_height
                draw_text_outlined(screen, line, self.font, COLOR_WHITE, text_x, text_y)

            # --- Continue indicator ---
            if not self.is_typing:
                prompt_x = rect.right - scale_y(40)
                prompt_y = rect.bottom - scale_y(30)
                draw_text_outlined(screen, ">>", self.font, COLOR_WHITE, prompt_x, prompt_y)