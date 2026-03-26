from tkinter import font

import pygame
from interfaces.pygame.ui.debug_overlay import DebugOverlay

pygame.init()

class GameManager:
    def __init__(self, god_mode=False):
        self.state = None
        self.player = None
        self.enemies = []
        self.god_mode = god_mode
        self.debug_overlay = None

    def set_debug_font(self, font):
        self.debug_overlay = DebugOverlay(font)

    def change_state(self, new_state):
        self.state = new_state

    def update(self, events):
        if self.state:
            self.state.update(events)

    def draw(self, screen):
        if self.state:
            self.state.draw(screen)
        if self.god_mode and self.debug_overlay:
            self.debug_overlay.draw(screen, self)