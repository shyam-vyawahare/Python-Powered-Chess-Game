import sys
import os
import unittest
import queue
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# MOCK PYGAME BEFORE IMPORTING GAME_WINDOW
sys.modules['pygame'] = MagicMock()
sys.modules['pygame.locals'] = MagicMock()
import pygame

# Configure specific mocks
mock_surface = MagicMock()
mock_surface.blit = MagicMock()
mock_surface.get_width.return_value = 10
mock_surface.get_height.return_value = 10
mock_surface.get_rect.return_value = MagicMock(width=10, height=10)
mock_surface.copy.return_value = mock_surface
mock_surface.fill = MagicMock()
mock_surface.set_alpha = MagicMock()

pygame.display.set_mode.return_value = mock_surface
pygame.time.Clock.return_value = MagicMock()
pygame.image.load.return_value = mock_surface
pygame.font.SysFont.return_value = MagicMock()
pygame.font.SysFont.return_value.render.return_value = mock_surface
pygame.font.Font.return_value = MagicMock()
pygame.font.Font.return_value.render.return_value = mock_surface
pygame.mixer.Sound.return_value = MagicMock()

# Better Mock for Rect
def MockRect(*args, **kwargs):
    mock = MagicMock()
    mock.width = 100
    mock.height = 100
    mock.x = 0
    mock.y = 0
    mock.center = (50, 50)
    mock.centery = 50
    mock.right = 100
    mock.copy.return_value = mock
    mock.collidepoint.return_value = False
    return mock

pygame.Rect = MockRect
# pygame.Surface is already a Mock object from sys.modules['pygame'] = MagicMock()
# We just need to configure its return value when called.
pygame.Surface.return_value = mock_surface
pygame.draw = MagicMock()

# Now import GameWindow
from chess_game.gui.game_window import GameWindow, TURN_PLAYER, TURN_AI, TURN_LOCKED
from chess_game.game_logic import Color, Move

class TestGameWindowLogic(unittest.TestCase):
    def setUp(self):
        # Initialize GameWindow without running the loop
        self.window = GameWindow()
        # Ensure we are in a known state
        self.window.mode_human_vs_ai = True
        self.window.new_game()
        # Mock the AI Queue to be immediate for testing logic
        self.window.ai_move_queue = MagicMock()
        self.window.ai_move_queue.get_nowait.side_effect = queue.Empty

    def test_turn_state_initialization(self):
        """Test if turn states are initialized correctly."""
        print("\nTesting Turn State Initialization...")
        self.assertEqual(self.window.turn_state, TURN_PLAYER, "Initial state should be TURN_PLAYER")
        self.assertFalse(self.window.ai_move_scheduled, "AI move should not be scheduled initially")

    def test_player_move_triggers_ai_state(self):
        """Test if a player move transitions state to TURN_AI."""
        print("\nTesting Player Move -> AI State Transition...")
        
        # Simulate a player move (White Pawn e2 -> e4)
        # We need to manually simulate what apply_move_and_schedule_ai does
        # But we can call it directly if we mock the animation
        
        # Mock animation to be None or done immediately
        self.window.current_animation = None
        
        # Simulate making a move
        start = "e2"
        end = "e4"
        # We assume the move is valid for this test
        
        # In the actual code, apply_move_and_schedule_ai is called.
        # Let's call it.
        # Note: We need a valid Move object.
        # We can construct one or just mock the logic flow.
        
        # Let's directly test the state transition logic in update_game_logic
        # Scenario: Player has just moved. pending_move is set.
        
        # Manually set the state as if animation finished
        self.window.turn_state = TURN_PLAYER
        self.window.pending_move = (None, True) # (move, ai_needed=True)
        self.window.current_animation = MagicMock()
        self.window.current_animation.is_done.return_value = True
        self.window.current_animation.move = Move(6, 4, 4, 4) # e2->e4
        
        # Run update_game_logic
        with patch.object(self.window, 'trigger_ai_move') as mock_trigger:
            self.window.update_game_logic()
            
            # Check state
            self.assertEqual(self.window.turn_state, TURN_AI, "State should transition to TURN_AI after player move")
            # ai_move_scheduled is consumed immediately in the same frame
            self.assertFalse(self.window.ai_move_scheduled, "AI move flag should be consumed")
            # Verify AI was triggered
            mock_trigger.assert_called_once()

    def test_clock_pauses_during_ai(self):
        """Test that clock does not decrease when state is TURN_AI."""
        print("\nTesting Clock Pause Logic...")
        
        # Setup clock
        self.window.time_control = 60 # 1 min
        self.window.white_time = 60
        self.window.black_time = 60
        self.window.last_frame_time = 1000
        
        # Set state to TURN_AI
        self.window.turn_state = TURN_AI
        self.window.ai_thread = MagicMock()
        self.window.ai_thread.is_alive.return_value = True
        
        # Mock time.get_ticks to advance by 1 second
        pygame.time.get_ticks.return_value = 2000 # +1000ms
        
        # Run update_game_logic
        self.window.update_game_logic()
        
        # Check time (White moved, so Black's clock would run if not paused)
        # But wait, whose turn is it?
        # If White just moved, it's Black's turn (TURN_AI).
        self.window.game.board.current_player = Color.BLACK
        
        # Run update again to trigger clock logic
        self.window.update_game_logic()
        
        self.assertEqual(self.window.black_time, 60, "Black clock should be PAUSED during AI turn")

    def test_clock_runs_during_player_turn(self):
        """Test that clock runs when state is TURN_PLAYER."""
        print("\nTesting Clock Run Logic...")
        
        # Setup clock
        self.window.time_control = 60
        self.window.white_time = 60
        self.window.black_time = 60
        self.window.last_frame_time = 1000
        
        # Set state to TURN_PLAYER
        self.window.turn_state = TURN_PLAYER
        self.window.ai_thread = None
        self.window.current_animation = None
        self.window.game.board.current_player = Color.WHITE
        self.window.game.result = None
        
        # Mock time.get_ticks to advance by 1 second
        pygame.time.get_ticks.return_value = 2000 # +1000ms
        
        # Run update_game_logic
        self.window.update_game_logic()
        
        # Check time
        self.assertAlmostEqual(self.window.white_time, 59.0, delta=0.1, msg="White clock should decrease by 1s")

    def test_input_lock(self):
        """Test that input is ignored during TURN_AI."""
        print("\nTesting Input Lock...")
        
        self.window.turn_state = TURN_AI
        
        # Call handle_board_click
        result = self.window.handle_board_click(100, 100)
        
        # Should return early or do nothing
        # In current implementation, it checks turn_state.
        # We can't easily check return value if it's None, but we can check side effects.
        # e.g., selected_piece should remain None
        
        self.window.selected_piece = None
        self.window.handle_board_click(100, 100)
        self.assertIsNone(self.window.selected_piece, "Should not select piece during TURN_AI")

    def test_no_clock_mode(self):
        """Test behavior when time control is None (No Clock Mode)."""
        print("\nTesting No Clock Mode...")
        self.window.time_control = None
        self.window.white_time = 0
        self.window.black_time = 0
        
        # Advance time
        pygame.time.get_ticks.return_value = 2000
        self.window.last_frame_time = 1000
        
        self.window.update_game_logic()
        
        # Time should remain 0
        self.assertEqual(self.window.white_time, 0)
        self.assertEqual(self.window.black_time, 0)
        # Game should not end by time
        self.assertIsNone(self.window.game.result)

if __name__ == '__main__':
    unittest.main()
