import pygame
import os
import random
from core.game_rules.path_utils import get_resource_path

class MusicManager:
    def __init__(self):
        # 1. Get the dynamic path to assets/bgm
        self.music_dir = get_resource_path(os.path.join('assets', 'bgm'))
        
        self.current_track = None
        self.last_combat_index = -1
        self.last_boss_index = -1
        
        # Settings
        self.volume = 0.5
        self.is_muted = False
        
        # Position Tracking (for WASM Resume)
        self.current_track_start_offset = 0.0 # The 'start' time passed to play()
        self.last_captured_pos = 0.0          # The absolute position when stopped
        
        # Fading Logic
        self.fade_state = 'IDLE' # 'IDLE', 'FADING_OUT', 'FADING_IN'
        self.fade_timer = 0.0
        self.FADE_DURATION = 0.75 # Seconds per phase (total 1.5s transition)
        self.target_track = None
        self.target_loops = -1
        self._track_lists = {}

        # 3. Set an initial volume
        pygame.mixer.music.set_volume(self.volume)
        print(f"MusicManager: Mixer initialized. Music Dir: {self.music_dir}")

    def update(self, dt_ms):
        """Processes music volume fades (Disabled for Wasm optimization)."""
        pass

    def stop_and_capture(self):
        """Captures the current playback position and performs a hard stop."""
        if self.current_track and pygame.mixer.music.get_busy():
            # music.get_pos() returns ms since play() was called
            relative_pos = pygame.mixer.music.get_pos() / 1000.0
            self.last_captured_pos = self.current_track_start_offset + relative_pos
            print(f"MusicManager: Captured position {self.last_captured_pos:.2f}s")
        else:
            self.last_captured_pos = 0.0
            
        pygame.mixer.music.stop()

    def fade_out(self, duration=None):
        """Initiates a volume fade out of the current music."""
        if duration: self.FADE_DURATION = duration
        if self.current_track and pygame.mixer.music.get_busy():
            self.fade_state = 'IDLE' 

    def set_volume(self, value):
        """Sets the target volume (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, value))
        if not self.is_muted:
            pygame.mixer.music.set_volume(self.volume)

    def toggle_mute(self):
        """Toggles between muted and unmuted."""
        self.is_muted = not self.is_muted
        if self.is_muted:
            pygame.mixer.music.set_volume(0.0)
        else:
            pygame.mixer.music.set_volume(self.volume)
        return self.is_muted

    def play_state_music(self, state_name, is_boss=False):
        """
        Immediately transitions to the music defined for the state (Hard cut for Wasm).
        """
        new_path = None
        s_name = state_name.lower()

        # Explicit Silence
        if 'autosave' in s_name:
            return

        # 0. Inheritance Passthrough
        # Settings, Inventory, and Save ALWAYS inherit the current track.
        is_menu = any(x in s_name for x in ['settings', 'inventory', 'save'])
        if is_menu and self.current_track:
            new_path = self.current_track
        
        # 1. Map states to their music files/folders (if not inherited)
        if new_path is None:
            if 'title' in s_name:
                new_path = os.path.join(self.music_dir, 'title', 'theme - into the throne v3.ogg')
            elif any(x in s_name for x in ['hub', 'shop', 'tavern', 'bestiary']):
                new_path = os.path.join(self.music_dir, 'hub', 'scene - prepare for tomorrow.ogg')
            elif any(x in s_name for x in ['level_up', 'levelup', 'victory']):
                new_path = os.path.join(self.music_dir, 'level_up', 'jingle - win.ogg')
            elif 'combat' in s_name:
                # SPECIAL CASE: If we are in Combat and just came FROM Settings, 
                # we don't want a new random track. We want the one we were just playing.
                if self.current_track and 'combat' in self.current_track.lower():
                     new_path = self.current_track
                else:
                    if is_boss:
                        new_path = self._get_random_track('boss')
                    else:
                        new_path = self._get_random_track('combat')

        # 2. Check if we actually have music for this state
        if new_path is None or not os.path.exists(new_path):
            return

        # 3. Resume vs New Play
        loops = 0 if any(x in s_name for x in ['level_up', 'levelup', 'victory']) else -1
        
        if new_path == self.current_track:
            # Same track: Resume at captured position
            self._execute_play(new_path, loops, start_time=self.last_captured_pos)
        else:
            # Different track: Start from beginning
            self.last_captured_pos = 0.0
            self._execute_play(new_path, loops, start_time=0.0)

        pygame.mixer.music.set_volume(self.volume)
        self.fade_state = 'IDLE'

    def _execute_play(self, path, loops, start_time=0.0):
        """Immediate track execution (stops current)."""
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(path)
            # Pygame music.play() 'start' is in seconds for OGG
            pygame.mixer.music.play(loops, start=start_time)
            self.current_track = path
            self.current_track_start_offset = start_time
            print(f"MusicManager: Playing {os.path.basename(path)} at {start_time:.2f}s")
        except Exception as e:
            print(f"MusicManager Error: Could not play {path}: {e}")

    def _get_random_track(self, folder_name):
        """Picks a random track from the specified bgm subfolder, using caching."""
        folder_path = os.path.join(self.music_dir, folder_name)
        
        if folder_path not in self._track_lists:
            if not os.path.exists(folder_path):
                self._track_lists[folder_path] = []
                return None
            tracks = [f for f in os.listdir(folder_path) if f.endswith('.ogg')]
            self._track_lists[folder_path] = tracks
        
        tracks = self._track_lists[folder_path]
        if not tracks: return None
        if len(tracks) == 1: return os.path.join(folder_path, tracks[0])

        # Avoid repeat
        last_idx_attr = f"last_{folder_name}_index"
        last_idx = getattr(self, last_idx_attr, -1)
        
        new_index = last_idx
        while new_index == last_idx:
            new_index = random.randint(0, len(tracks) - 1)
        
        setattr(self, last_idx_attr, new_index)
        return os.path.join(folder_path, tracks[new_index])
