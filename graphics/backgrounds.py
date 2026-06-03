import pygame
import random
import os
from core.game_rules.constants import SCREEN_WIDTH, SCREEN_HEIGHT
from core.game_rules.path_utils import get_resource_path

# Use get_resource_path to find the assets/backgrounds folder dynamically
ASSETS_DIR = get_resource_path(os.path.join("assets", "backgrounds"))

class BackgroundManager:
    """
    Centralized manager for loading, scaling, and caching background images.
    """
    _cache = {}
    _file_lists = {} # Cache for os.listdir results
    
    def __init__(self):
        self.bg = BackgroundManager.get_combat_bg()

    @staticmethod
    def _get_files(directory):
        """Helper to get and cache file lists from a directory."""
        if directory in BackgroundManager._file_lists:
            return BackgroundManager._file_lists[directory]
            
        if not os.path.exists(directory):
            print(f"DEBUG: Directory {directory} does not exist.")
            return []
            
        files = [f for f in os.listdir(directory) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        BackgroundManager._file_lists[directory] = files
        return files

    @staticmethod
    def pick_random(directory):
        """Returns a random image path from the cached file lists."""
        files = BackgroundManager._get_files(directory)
        if not files:
            return None
        return os.path.join(directory, random.choice(files))

    def draw(self, screen):
        if self.bg:
            screen.blit(self.bg, (0, 0))
    
    @staticmethod
    def load_bg(path):
        """Loads and scales a background image, using a cache for performance."""
        if not path:
            return None
        
        # Normalize path for cache key
        norm_path = os.path.normpath(path)
        
        if norm_path in BackgroundManager._cache:
            return BackgroundManager._cache[norm_path]

        try:
            # print(f"DEBUG: BackgroundManager loading {norm_path}")
            bg = pygame.image.load(norm_path).convert()
            scaled_bg = pygame.transform.scale(bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
            BackgroundManager._cache[norm_path] = scaled_bg
            return scaled_bg
        except Exception as e:
            print(f"DEBUG: BackgroundManager Error {norm_path}: {e}")
            return None

    @staticmethod
    def get_hub_bg(player_profile):
        path = player_profile.get("hub_background")
        if not path:
            directory = os.path.join(ASSETS_DIR, "hub")
            path = BackgroundManager.pick_random(directory)
            player_profile["hub_background"] = path
        return BackgroundManager.load_bg(path)
    
    @staticmethod
    def refresh_hub_bg(player_profile):
        path = BackgroundManager.pick_random(os.path.join(ASSETS_DIR, "hub"))
        player_profile["hub_background"] = path
        return BackgroundManager.load_bg(path)


    @staticmethod
    def get_combat_bg():
        return BackgroundManager.load_bg(
            BackgroundManager.pick_random(os.path.join(ASSETS_DIR, "combat"))
        )


    @staticmethod
    def get_levelup_bg():
        return BackgroundManager.load_bg(
            BackgroundManager.pick_random(os.path.join(ASSETS_DIR, "level_up"))
        )


    @staticmethod
    def get_rest_bg():
        return BackgroundManager.load_bg(
            BackgroundManager.pick_random(os.path.join(ASSETS_DIR, "rest"))
        )


    @staticmethod
    def get_shop_bg():
        return BackgroundManager.load_bg(
            os.path.join(ASSETS_DIR, "shop.png")
        )


    @staticmethod
    def get_gameover_bg():
        return BackgroundManager.load_bg(
            os.path.join(ASSETS_DIR, "game_over.png")
        )

    @staticmethod
    def get_title_bg():
        return BackgroundManager.load_bg(
            os.path.join(ASSETS_DIR, "title.png")
        )

    @staticmethod
    def get_bestiary_bg():
        return BackgroundManager.load_bg(
            os.path.join(ASSETS_DIR, "book", "book.png")
        )
