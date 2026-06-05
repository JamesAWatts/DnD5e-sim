# pygbag: name=Valor, width=1280, height=720
import pygame
import asyncio

pygame.mixer.pre_init(44100, -16, 2, 1024)
pygame.init()
pygame.mixer.set_num_channels(32)

import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.game_rules.game_manager import GameManager
from core.game_rules.music_manager import MusicManager
from states.title import TitleState
from core.game_rules.constants import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS, COLOR_BG, FONT_PATH, scale_font,
    FONT_SIZE_SMALL, FONT_SIZE_MEDIUM, FONT_SIZE_LARGE, FONT_SIZE_XLARGE, FONT_SIZE_TITLE
)
from core.game_rules.path_utils import get_resource_path

async def main():
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    
    pygame.display.set_caption("Valor - Alpha Demo - A.1.2")
    
    # Load all font sizes
    fonts = {
        'small': pygame.font.Font(get_resource_path(FONT_PATH), scale_font(FONT_SIZE_SMALL)),
        'medium': pygame.font.Font(get_resource_path(FONT_PATH), scale_font(FONT_SIZE_MEDIUM)),
        'large': pygame.font.Font(get_resource_path(FONT_PATH), scale_font(FONT_SIZE_LARGE)),
        'xlarge': pygame.font.Font(get_resource_path(FONT_PATH), scale_font(FONT_SIZE_XLARGE)),
        'title': pygame.font.Font(get_resource_path(FONT_PATH), scale_font(FONT_SIZE_TITLE))
    }

    # Initialize Music and Game managers
    music_manager = MusicManager()
    game = GameManager(music_manager=music_manager)
    game.set_debug_font(fonts['small'])

    # Start title music immediately
    music_manager.play_state_music('title')

    game.change_state(TitleState(game, fonts))

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
