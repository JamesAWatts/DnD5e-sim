from game.states.base_state import BaseState
from game.ui.menu import Menu
from game.ui.backgrounds import BackgroundManager

class InventoryState(BaseState):
    def __init__(self, game, font):
        super().__init__(game, font)
        self.background = BackgroundManager.get_hub_bg(game.player)

        self.inventory = game.player.get("inventory_ref", {})
        self.category_menu = Menu(["Weapon", "Armor", "Consumable", "Back"], font)

        self.item_menu = None
        self.mode = "CATEGORIES"

        self.active_menu = self.category_menu

    def on_select(self, option):
        if self.mode == "CATEGORIES":
            if option == "Back":
                from game.states.hub import HubState
                self.game.change_state(HubState(self.game, self.font))
            else:
                items = self.inventory.get(option.lower(), [])
                self.item_menu = Menu(items + ["Back"], self.font)
                self.active_menu = self.item_menu
                self.mode = "ITEMS"

        elif self.mode == "ITEMS":
            if option == "Back":
                self.active_menu = self.category_menu
                self.mode = "CATEGORIES"
            else:
                self.handle_item_action(option)

    def draw(self, screen):
        super().draw(screen)

        from game.ui.panel import draw_text_outlined
        from constants import SCREEN_WIDTH
        title_text = "Inventory"
        tw, th = self.font.size(title_text)
        draw_text_outlined(screen, title_text, self.font, (255, 255, 255), (SCREEN_WIDTH // 2) - (tw // 2), 50)