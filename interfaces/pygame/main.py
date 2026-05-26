import pygame
import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.game_rules.game_manager import GameManager
from core.game_rules.music_manager import MusicManager
from states.title import TitleState
from core.game_rules.constants import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, COLOR_BG, DEFAULT_FONT_SIZE, scale_font 

async def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    
    pygame.display.set_caption("Valor - 5e RPG Simulator")
    font = pygame.font.SysFont(None, scale_font(DEFAULT_FONT_SIZE))

    # Initialize Music and Game managers
    music_manager = MusicManager()
    game = GameManager(music_manager=music_manager)
    game.set_debug_font(font)

    # Start title music immediately
    music_manager.play_state_music('title')

    game.change_state(TitleState(game, font))

    while game.running:
        # For Pygbag/Web: limit framerate but allow yielding
        dt = clock.tick(FPS)
        
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT: 
                game.quit()
            
            # --- Handle Global Debug Toggle (F3) ---
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F3:
                    if game.debug_overlay:
                        game.debug_overlay.toggle()

        screen.fill((30,30,30))

        game.update(events, dt)
        game.draw(screen)

        pygame.display.flip()
        
        # VERY IMPORTANT for Pygbag/Web: Yield to the browser
        await asyncio.sleep(0)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    asyncio.run(main())
