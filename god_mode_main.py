import pygame
from game.game_manager import GameManager
from game.states.class_select import ClassSelectState
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, COLOR_BG, DEFAULT_FONT_SIZE, scale_font

pygame.init()

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("--- GOD MODE ---")

clock = pygame.time.Clock()
font = pygame.font.SysFont(None, scale_font(DEFAULT_FONT_SIZE))

# Pass god_mode=True
game = GameManager(god_mode=True)
game.change_state(ClassSelectState(game, font))
game.set_debug_font(font)

while True:
    events = pygame.event.get()

    for event in events:
        if event.type == pygame.QUIT:
            pygame.quit()
            exit()

    screen.fill(COLOR_BG)

    game.update(events)
    game.draw(screen)

    pygame.display.flip()
    clock.tick(FPS)