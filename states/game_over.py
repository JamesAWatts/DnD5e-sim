import pygame
from game.states.base_state import BaseState
from game.ui.menu import Menu
from game.ui.backgrounds import BackgroundManager

class GameOverState(BaseState):
    def __init__(self, game, font, retired=False):
        super().__init__(game, font)
        self.background = BackgroundManager.get_gameover_bg()

        self.menu = Menu(["Play Again", "Quit"], font, width=200)
        self.active_menu = self.menu

    def on_select(self, option):
        if option == "Play Again":
            from game.states.class_select import ClassSelectState
            self.game.change_state(ClassSelectState(self.game, self.font))
        elif option == "Quit":
            pygame.quit()
            exit()

    def draw(self, screen):
        super().draw(screen)

        from game.ui.panel import draw_text_outlined
        from constants import SCREEN_WIDTH
        title_text = "GAME OVER"
        tw, th = self.font.size(title_text)
        draw_text_outlined(screen, title_text, self.font, (255,0,0), (SCREEN_WIDTH // 2) - (tw // 2), 50)