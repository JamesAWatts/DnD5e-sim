import os
from game.states.base_state import BaseState
from game.ui.menu import Menu
from game.ui.backgrounds import BackgroundManager
from players.leveler import load_player_classes, add_class_level
from constants import COLOR_BG, COLOR_LIGHT_GRAY, SCREEN_WIDTH

class LevelUpState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)

        # Use manager to pick random background
        self.background = BackgroundManager.get_levelup_bg()

        self.class_names = list(load_player_classes().keys())
        # 25% transparent means 75% opacity, alpha = 255 * 0.75 = 191
        self.menu = Menu(self.class_names, font, bg_color=COLOR_BG, border_color=COLOR_LIGHT_GRAY, alpha=191, width=300)

        self.active_menu = self.menu

    def on_select(self, option):
        add_class_level(self.game.player, option)

        from game.states.hub import HubState
        self.game.change_state(HubState(self.game, self.font))

    def draw(self, screen):
        super().draw(screen)

        from game.ui.panel import draw_text_outlined
        title_text = "Level Up!"
        tw, th = self.font.size(title_text)
        draw_text_outlined(screen, title_text, self.font, (255, 255, 0), (SCREEN_WIDTH // 2) - (tw // 2), 50)