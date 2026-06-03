import pygame

class CombatDialogueManager:
    """
    Manages the narrative and dialogue queue for the combat state, 
    decoupling message flow from core combat logic.
    """
    def __init__(self, dialogue_box_instance):
        """
        Initializes the manager with an existing DialogueBox UI component.

        Args:
            dialogue_box_instance (DialogueBox): The UI component responsible for rendering text.
        """
        self.dialogue_box = dialogue_box_instance
        self.message_queue = []

    def queue_message(self, text):
        """
        Appends a string or a list of strings to the message queue.
        If the box is currently idle, immediately starts the first message.

        Args:
            text (str or list): The narrative text to be displayed.
        """
        if isinstance(text, list):
            self.message_queue.extend(text)
        else:
            self.message_queue.append(text)
            
        # Auto-start if idle
        if not self.dialogue_box.current_message and self.message_queue:
            self.start_next()

    def queue_action_start(self, actor_name, action_data, target_name):
        """Constructs and queues the starting announcement for an action."""
        msg = f"{actor_name} uses {action_data.get('name', 'Attack')} on {target_name}!"
        
        save_dc = action_data.get('save_dc') or action_data.get('dc')
        if save_dc:
            msg += f" (DC: {save_dc})"
            
        self.queue_message(msg)

    def queue_resolution_dialogue(self, results_list, target_orig):
        """Constructs and queues the narrative results of an action. Handles a list of results."""
        if not results_list: return
        
        # results_list is now expected to be a list of dictionaries (one per target)
        for result in results_list:
            target_name = result.get('target_name', 'Unknown')
            msg_parts = []
            
            # 1. Hit/Miss/Save
            if result.get('type') == 'save':
                if result.get('saved'):
                    msg_parts.append(f"{target_name} saved! ")
                else:
                    msg_parts.append(f"{target_name} failed the save! ")
            else:
                if result.get('hit'):
                    msg_parts.append(f"{target_name} was hit! ")
                else:
                    msg_parts.append(f"{target_name} evaded! ")
                    
            # 2. Damage
            damage = result.get('damage', 0)
            if damage > 0:
                if result.get('crit'):
                    msg_parts.append(f"Taking a CRITICAL {damage} damage! ")
                else:
                    msg_parts.append(f"Taking {damage} damage. ")
                    
            # 3. Effects
            for effect in result.get('effects', []):
                eff_name = effect.get('name', 'Effect')
                msg_parts.append(f"{eff_name} applied to {target_name}. ")
                
                dice = effect.get('dot_dice') or effect.get('hot_dice')
                if dice:
                    msg_parts.append(f"Target receives {dice} each turn. ")
                    
                duration = effect.get('duration')
                if duration:
                    msg_parts.append(f"Lasts for {duration} turns. ")
                    
            if msg_parts:
                self.queue_message("".join(msg_parts).strip())

    def update(self, dt):
        """
        Updates animation timers for the underlying dialogue box.

        Args:
            dt (float): Delta time since the last frame.
        """
        self.dialogue_box.update()

    def is_busy(self):
        """
        Checks if the manager is currently processing messages.

        Returns:
            bool: True if messages are queued or the dialogue box is active.
        """
        return len(self.message_queue) > 0 or bool(self.dialogue_box.current_message)

    def clear_queue(self):
        """Removes all pending messages from the queue and clears the current message."""     
        self.message_queue = []
        self.dialogue_box.current_message = None

    def start_next(self, skip_typing=False):
        """Immediately advances to the next message in the queue."""
        if self.message_queue:
            next_msg = self.message_queue.pop(0)
            self.dialogue_box.set_messages(next_msg, skip_typing=skip_typing)
        else:
            self.dialogue_box.current_message = None
            self.dialogue_box.is_typing = False

    def draw(self, screen):
        """
        Renders the dialogue box.
        """
        # We now call draw() unconditionally as it handles its own internal logic
        # for whether to show text or just the empty frame.
        self.dialogue_box.draw(screen)
