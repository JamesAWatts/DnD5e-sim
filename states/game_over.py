import pygame
import random
from states.base_state import BaseState
from ui.menu import Menu
from ui.dialogue_box import DialogueBox
from graphics.backgrounds import BackgroundManager

from ui.panel import Panel, draw_text_outlined
from core.game_rules.constants import scale_y, scale_x, COLOR_GOLD, COLOR_WHITE, SCREEN_WIDTH, SCREEN_HEIGHT

class GameOverState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        self.background = BackgroundManager.get_gameover_bg()

        self.menu = Menu(["Play Again", "Quit"], self.fonts['medium'], width=200)
        self.active_menu = self.menu
        self.dialogue = DialogueBox(self.fonts['large'])
        self.message_queue = []
        
        # ======================
        # 💀 DEATH MESSAGES
        # ======================
        self.death_messages = [
            "You have fallen in battle.",
            "Your journey ends here.",
            "The dungeon claims another soul.",
        ]

        # ======================
        # 📢 BUILD MESSAGE QUEUE
        # ======================
        msg = random.choice(self.death_messages)
        self.queue_message("GAME OVER")
        self.queue_message(msg)

        self.start_next_message()

        # Wasm Optimization: Static Caching
        self.cached_header = None
        self._render_header_cache()

    def _render_header_cache(self):
        header_text = "GAME OVER"
        tw, th = self.fonts['xlarge'].size(header_text)
        self.cached_header = pygame.Surface((tw + 10, th + 10), pygame.SRCALPHA)
        draw_text_outlined(self.cached_header, header_text, self.fonts['xlarge'], (255, 50, 50), 5, 5)
    
    def queue_message(self, text):
        self.message_queue.append(text)

    def start_next_message(self):
        if self.message_queue:
            self.dialogue.set_messages([self.message_queue.pop(0)])

    def on_select(self, option):
        if option == "Play Again":
            from states.title import TitleState
            self.game.reset_game()
            self.game.change_state(TitleState(self.game, self.fonts))
        elif option == "Quit":
            self.game.quit()

    def update(self, events, dt):
        # Dialogue handling (same as combat)
        if self.dialogue.current_message:
            self.dialogue.update()
            for event in events:
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    was_typing = self.dialogue.is_typing
                    self.dialogue.handle_event(event)

                    if not was_typing and not self.dialogue.current_message:
                        if self.message_queue:
                            self.dialogue.set_messages([self.message_queue.pop(0)])
            return

        # After dialogue → allow menu
        super().update(events, dt)

    def draw(self, screen):
        self.draw_background(screen)

        # 1. Draw Header (Cached)
        if self.cached_header:
            screen.blit(self.cached_header, (SCREEN_WIDTH // 2 - self.cached_header.get_width() // 2, 100))

        # 2. If dialogue still playing → show it
        if self.dialogue.current_message:
            self.dialogue.draw(screen)
        else:
            # Draw Menu
            if self.active_menu:
                # Menu.draw handles centering and clamping based on its internal raw_pos/width
                # raw_center_x=400 is the horizontal center of 800x600
                self.active_menu.draw(screen, 400, SCREEN_HEIGHT / scale_y(1) - 150)
