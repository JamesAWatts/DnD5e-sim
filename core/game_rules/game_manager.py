import pygame
from ui.debug_overlay import DebugOverlay
from graphics.transition_manager import TransitionManager

pygame.init()

class GameManager:
    def __init__(self, god_mode=False, music_manager=None):
        self.state = None
        self.pending_state = None
        self.party = [] # List of player dicts
        self.enemies = []
        self.god_mode = god_mode
        self.debug_overlay = None
        self.music_manager = music_manager
        self.transition_mgr = TransitionManager()
        self.capture_for_flash = False
        self.running = True # Control flag for the main loop
        
        self.party_member_name = None # Used during hiring process
        self.battle_counter = 0
        self.consecutive_combats = 0
        self.bestiary_rp = {}
        self.inventory = {
            'gold': 0,
            'weapon': {},
            'armor': {},
            'shield': {},
            'trinket': {},
            'consumable': {},
            'junk': {},
            'key_items': {}
        }

    def reset_game(self):
        """Resets all session-specific data for a clean start."""
        self.party = []
        self.enemies = []
        self.party_member_name = None
        self.battle_counter = 0
        self.consecutive_combats = 0
        self.bestiary_rp = {}
        self.inventory = {
            'gold': 0,
            'weapon': {},
            'armor': {},
            'shield': {},
            'trinket': {},
            'consumable': {},
            'junk': {},
            'key_items': {}
        }

    @property
    def player(self):
        """Returns the first player in the party for backward compatibility."""
        return self.party[0] if self.party else None

    @player.setter
    def player(self, value):
        """Sets the first player in the party."""
        if not self.party:
            self.party.append(value)
        else:
            self.party[0] = value

    def set_debug_font(self, font):
        # The new DebugOverlay initializes its own font based on size, 
        # but we can pass a size or just use the default.
        self.debug_overlay = DebugOverlay()

    def change_state(self, new_state, transition_type='fade'):
        # --- 1. LEVEL UP INTERCEPT ---
        # Check if any party member needs to level up before changing to a non-special state.
        # This allows us to "pause" the flow to handle character progression.
        from core.players.leveler import needs_level_up
        state_name = type(new_state).__name__
        
        # We don't intercept if we're already going to LevelUp, Title, or ClassSelect
        if state_name not in ["LevelUpState", "TitleState", "ClassSelectState"]:
            levelup_p = next((p for p in self.party if needs_level_up(p)), None)
            if levelup_p:
                from states.level_up import LevelUpState
                # Grab fonts from current state if possible
                fonts = getattr(self.state, 'fonts', None)
                if fonts:
                    print(f"[GAME] Intercepting {state_name} -> LevelUpState for {levelup_p.get('name')}")
                    new_state = LevelUpState(self, fonts, player=levelup_p)
                    # Re-check transition type or use default fade
                    transition_type = 'fade'

        # If we already have a state, use a transition
        if self.state and self.transition_mgr:
            self.pending_state = new_state
            self.pending_transition_type = transition_type
            
            # Start audio fade out early to avoid pops/glitches during transition
            if self.music_manager:
                self.music_manager.fade_out()

            # Check if this is a combat transition with a leader
            is_combat = type(new_state).__name__ == "CombatState"
            is_leader = any(e.get('is_leader') for e in self.enemies) if is_combat else False
            
            if is_leader:
                self.capture_for_flash = True # Signal draw() to capture screen and start flash
            else:
                self.transition_mgr.start_transition(is_closing=True, callback=self._on_close_finished, transition_type=transition_type)
        else:
            self._apply_state_change(new_state)

    def _on_close_finished(self):
        if self.pending_state:
            self._apply_state_change(self.pending_state)
            self.pending_state = None
            t_type = getattr(self, 'pending_transition_type', 'fade')
            self.transition_mgr.start_transition(is_closing=False, transition_type=t_type)

    def _apply_state_change(self, new_state):
        # Capture previous state name before switching
        if self.state:
            previous_name = type(self.state).__name__
            # Normalize names for consistency
            if "CombatState" in previous_name: previous_name = "COMBAT_STATE"
            elif "LevelUpState" in previous_name: previous_name = "LEVEL_UP_STATE"
            elif "HubState" in previous_name: previous_name = "HUB_STATE"
            elif "AutoSaveNoticeState" in previous_name: previous_name = "AUTOSAVE_NOTICE"
            self.previous_state_name = previous_name
        else:
            self.previous_state_name = None

        self.state = new_state
        # Automatically update music when state changes
        if self.music_manager and new_state:
            state_class_name = type(new_state).__name__
            state_key = state_class_name.replace('State', '').lower()
            
            # Detect boss fight
            is_boss = any(e.get('is_leader') for e in self.enemies) if 'combat' in state_key else False
            
            self.music_manager.play_state_music(state_key, is_boss=is_boss)

    def update(self, events, dt=16):
        if self.transition_mgr:
            self.transition_mgr.update(dt)

        if self.music_manager:
            self.music_manager.update(dt)
            
        # Only update state if not flashing or if we want background logic to continue
        if self.state and self.transition_mgr.phase != 'LEADER_FLASH':
            self.state.update(events, dt)

    def get_total_party_level(self):
        """Calculates the combined level of all party members."""
        return sum(p.get('level', 1) for p in self.party)

    def calculate_encounter_level(self):
        """Calculates the encounter budget based on party size and total level."""
        import math
        party_size = len(self.party)
        total_level = self.get_total_party_level()
        
        if party_size > 1:
            return math.ceil((total_level / 2) + (party_size - 1))
        return total_level

    def get_unlocked_hub_features(self):
        """Returns a list of feature names unlocked based on party progression."""
        total_level = self.get_total_party_level()
        features = ["Fight", "Tavern", "Shop", "Inventory"]
        
        # Progression logic: Bestiary unlocks at total level 21
        if total_level >= 21:
            features.insert(1, "Bestiary")
            
        if self.god_mode:
            features += ["Level Up", "Invincible"]
            
        return features

    def quit(self):
        """Signals the main loop to terminate gracefully."""
        self.running = False

    def draw(self, screen):
        if self.capture_for_flash:
            self.capture_for_flash = False
            # Draw one last frame of current state to capture it
            if self.state: self.state.draw(screen)
            self.transition_mgr.trigger_leader_flash(screen, callback=lambda: self.transition_mgr.start_transition(is_closing=True, callback=self._on_close_finished))
            return # Don't draw again this frame

        if self.state:
            self.state.draw(screen)

        if self.transition_mgr:
            self.transition_mgr.draw(screen)

        if self.debug_overlay:
            # Clear transient data each frame
            self.debug_overlay.clear_frame_data()
            self.debug_overlay.draw(screen, self)