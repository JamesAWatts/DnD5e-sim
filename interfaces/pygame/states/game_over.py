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

        self.menu = Menu(["Play Again", "Quit"], font, width=200)
        self.active_menu = self.menu
        self.dialogue = DialogueBox(self.font)
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
    
    def queue_message(self, text):
        self.message_queue.append(text)

    def start_next_message(self):
        if self.message_queue:
            self.dialogue.set_messages([self.message_queue.pop(0)])

    def on_select(self, option):
        if option == "Play Again":
            from states.title import TitleState
            self.game.reset_game()
            self.game.change_state(TitleState(self.game, self.font))
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

        # If dialogue still playing → show it
        if self.dialogue.current_message:
            self.dialogue.draw(screen)
        else:
            # Draw Menu
            if self.active_menu:
                # Center the menu horizontally at the bottom
                menu_width = self.active_menu.get_raw_width()
                # Position so the menu is centered: center_x should be such that
                # center_x - menu_width//2 gives us the left edge we want
                # We want the menu centered in the 800px base width
                center_x = 400  # This centers a menu in the middle of 800px
                # But if the menu is wider than available space, we need to adjust
                if menu_width > 790:  # Leave 5px margin on each side
                    center_x = menu_width // 2 + 5
                self.active_menu.draw(screen, center_x, SCREEN_HEIGHT - scale_y(150))
