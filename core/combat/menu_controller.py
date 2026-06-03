import pygame
from enum import Enum, auto

class MenuState(Enum):
    SELECTING_ACTION = auto()
    SELECTING_TARGET = auto()

class CombatMenuController:
    """
    A decoupled input controller for turn-based combat menus and targeting.
    Pure state-machine: No rendering, no resolution math.
    """
    def __init__(self, actions=None, grid_bounds=(3, 4)):
        # Menu Data
        self.actions = actions or ["ATTACK", "DEFEND", "SKILL", "ITEM"]
        self.action_index = 0
        
        # Grid Data (Columns, Rows)
        self.grid_cols, self.grid_rows = grid_bounds
        self.cursor_grid_x = 0
        self.cursor_grid_y = 0
        
        # State Management
        self.state = MenuState.SELECTING_ACTION
        self.selected_action = None

    def process_input(self, events):
        """
        Main entry point for processing the Pygame event queue.
        Returns a payload dict if a turn is finalized, otherwise None.
        """
        for event in events:
            if self.state == MenuState.SELECTING_ACTION:
                result = self._handle_action_selection(event)
                if result: return result
            
            elif self.state == MenuState.SELECTING_TARGET:
                result = self._handle_target_selection(event)
                if result: return result
        
        return None

    def _handle_action_selection(self, event):
        """Logic for navigating the base action menu."""
        if event.type == pygame.KEYDOWN:
            if event.key in [pygame.K_UP, pygame.K_w, pygame.K_LEFT, pygame.K_a]:
                self.action_index = (self.action_index - 1) % len(self.actions)
            elif event.key in [pygame.K_DOWN, pygame.K_s, pygame.K_RIGHT, pygame.K_d]:
                self.action_index = (self.action_index + 1) % len(self.actions)
            elif event.key in [pygame.K_RETURN, pygame.K_SPACE]:
                return self._confirm_action(self.actions[self.action_index])

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1: # Left Click
                # Note: In a decoupled controller, we assume some external system 
                # might have updated action_index via hover or we just confirm the current one.
                return self._confirm_action(self.actions[self.action_index])

        return None

    def _handle_target_selection(self, event):
        """Logic for navigating the combat tile grid (Keyboard navigation removed, handled externally)."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._cancel_targeting()
                return None
            
            elif event.key in [pygame.K_RETURN, pygame.K_SPACE]:
                return self._finalize_turn()

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1: # Left Click
                return self._finalize_turn()
            elif event.button == 3: # Right Click
                self._cancel_targeting()

        return None

    def _confirm_action(self, action):
        """Transition from action selection to targeting."""
        self.selected_action = action
        self.state = MenuState.SELECTING_TARGET
        return None

    def _cancel_targeting(self):
        """Back out of targeting and return to action selection."""
        self.state = MenuState.SELECTING_ACTION
        self.selected_action = None

    def _finalize_turn(self):
        """Construct and return the final action payload."""
        payload = {
            "action": self.selected_action,
            "target_grid": (self.cursor_grid_x, self.cursor_grid_y)
        }
        # Reset state for next time
        self.state = MenuState.SELECTING_ACTION
        self.selected_action = None
        return payload

    def set_hover_index(self, index):
        """External hook to sync mouse hover with menu index."""
        if 0 <= index < len(self.actions):
            self.action_index = index

    def set_hover_grid(self, x, y):
        """External hook to sync mouse hover with grid coordinates."""
        if 0 <= x < self.grid_cols and 0 <= y < self.grid_rows:
            self.cursor_grid_x = x
            self.cursor_grid_y = y
