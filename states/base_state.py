import pygame

class BaseState:
    def __init__(self, game, font):
        self.game = game
        self.font = font
        self.active_menu = None
        self.background = None

    def update(self, events):
        if not self.active_menu:
            return

        mouse_pos = pygame.mouse.get_pos()
        mouse_click = any(event.type == pygame.MOUSEBUTTONDOWN for event in events)

        # Mouse input
        selection = self.active_menu.handle_mouse(mouse_pos, mouse_click)
        if selection is not None:
            self.active_menu.selected = selection
            option = self.active_menu.options[selection]
            self.on_select(option)

        # Keyboard input
        for event in events:
            result = self.active_menu.handle_event(event)
            if result:
                self.on_select(result)

    def on_select(self, option):
        raise NotImplementedError

    def draw_background(self, screen):
        """Renders the background image if it exists."""
        if self.background:
            screen.blit(self.background, (0, 0))

    def draw(self, screen):
        """
        Default draw: renders background, then centers active menu.
        States can override this or call draw_background() specifically.
        """
        self.draw_background(screen)

        if self.active_menu:
            width, height = screen.get_size()
            self.active_menu.draw(screen, width // 2, height // 3)