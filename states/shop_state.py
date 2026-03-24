from game.states.base_state import BaseState
from game.ui.menu import Menu
from game.ui.backgrounds import BackgroundManager

class ShopState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        self.background = BackgroundManager.get_shop_bg()

        self.inventory = game.player.get("inventory_ref", {})
        self.mode = "MAIN"

        self.main_menu = Menu(["Buy", "Sell", "Back"], font, width=200)
        self.buy_menu = Menu(["Potion (10g)", "Back"], font, width=200)
        self.sell_menu = None

        self.active_menu = self.main_menu

    def on_select(self, option):
        if self.mode == "MAIN":
            if option == "Buy":
                self.mode = "BUY"
                self.active_menu = self.buy_menu

            elif option == "Sell":
                self.refresh_sell_list()
                self.mode = "SELL"
                self.active_menu = self.sell_menu

            elif option == "Back":
                from game.states.hub import HubState
                self.game.change_state(HubState(self.game, self.font))

        elif self.mode == "BUY":
            if option == "Back":
                self.mode = "MAIN"
                self.active_menu = self.main_menu
            else:
                self.buy_item(option)

        elif self.mode == "SELL":
            if option == "Back":
                self.mode = "MAIN"
                self.active_menu = self.main_menu
            else:
                self.sell_item(option)

    def draw(self, screen):
        super().draw(screen)

        from game.ui.panel import draw_text_outlined
        from constants import SCREEN_WIDTH
        title_text = "Shop"
        tw, th = self.font.size(title_text)
        draw_text_outlined(screen, title_text, self.font, (255,255,255), (SCREEN_WIDTH // 2) - (tw // 2), 50)