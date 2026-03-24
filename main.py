import pygame
from game.game_manager import GameManager
from game.states.class_select import ClassSelectState
from constants import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, COLOR_BG, DEFAULT_FONT_SIZE, scale_font 

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
clock = pygame.time.Clock()
clock.tick(FPS)
screen.fill(COLOR_BG)
pygame.display.set_caption("5e RPG Simulator")
font = pygame.font.SysFont(None, scale_font(DEFAULT_FONT_SIZE))

game = GameManager()
game.change_state(ClassSelectState(game, font))

while True:
    events = pygame.event.get()

    for event in events:
        if event.type == pygame.QUIT: 
            pygame.quit()
            exit()

    screen.fill((30,30,30))

    game.update(events)
    game.draw(screen)

    pygame.display.flip()
    clock.tick(60)