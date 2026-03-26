import pygame
import random
from interfaces.pygame.states.base_state import BaseState
from interfaces.pygame.ui.menu import Menu
from interfaces.pygame.ui.dialogue_box import DialogueBox
from interfaces.pygame.ui.backgrounds import BackgroundManager

class GameOverState(BaseState):
    def __init__(self, game, font, retired=False):
        super().__init__(game, font)
        self.background = BackgroundManager.get_gameover_bg()

        self.retired = retired
        self.menu = Menu(["Play Again", "Quit"], font, width=200)
        self.active_menu = self.menu
        self.dialogue = DialogueBox(self.font)
        self.message_queue = []

        # ======================
        # 🧓 RETIREMENT MESSAGES
        # ======================
        self.retirement_messages = [
            "You retire to a quiet farm. The goats respect you.",
            "You open a tavern. The drinks are terrible, but the stories are great.",
            "You become a legend... mostly exaggerated.",
            "You retire rich! Unfortunately, inflation exists.",
            "You vanish into the wilderness. Probably fine.",
            "You write a memoir. No one believes it.",
            "You settle down... for about a week.",
        ]

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
        if self.retired:
            msg = random.choice(self.retirement_messages)
            messages = [f"{self.game.player.get('name', 'Hero')} retires...", msg]
        else:
            msg = random.choice(self.death_messages)
            messages = ["GAME OVER", msg]

        if self.retired:
            msg = random.choice(self.retirement_messages)
            self.queue_message(f"{self.game.player.get('name', 'Hero')} retires...")
            self.queue_message(msg)
        else:
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
            from interfaces.pygame.states.class_select import ClassSelectState
            self.game.change_state(ClassSelectState(self.game, self.font))
        elif option == "Quit":
            pygame.quit()
            exit()

    def update(self, events):
        # Dialogue handling (same as combat)
        if self.dialogue.current_message:
            self.dialogue.update()

            for event in events:
                if event.type == pygame.KEYDOWN:
                    was_typing = self.dialogue.is_typing
                    self.dialogue.handle_event(event)

                    if not was_typing and not self.dialogue.current_message:
                        if self.message_queue:
                            self.start_next_message()

            return

        # After dialogue → allow menu
        super().update(events)

    def draw(self, screen):
        super().draw(screen)

        # If dialogue still playing → show it
        if self.dialogue.current_message:
            self.dialogue.draw(screen)
