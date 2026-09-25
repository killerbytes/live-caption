import unittest
import sys
import os

# Ensure the workspace is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import CaptionManager

class TestCaptionManager(unittest.TestCase):
    def test_info_message(self):
        manager = CaptionManager(max_lines=4, line_width=20)
        self.assertEqual(manager.handle_message("info", "Hello Info"), "Hello Info")
        self.assertEqual(manager.finalized_lines, [])
        self.assertEqual(manager.current_partial, "")

    def test_partial_message(self):
        manager = CaptionManager(max_lines=4, line_width=20)
        # 1. Start with empty
        self.assertEqual(manager.handle_message("partial", "hello world"), "hello world")
        
        # 2. Add final, then partial
        manager.handle_message("final", "sentence one")
        # sentence one is 12 chars, fits in 1 line
        self.assertEqual(manager.handle_message("partial", "hello"), "sentence one\nhello")

    def test_fifo_clearing_exactly_four_lines(self):
        # Line width 20, max_lines 4
        manager = CaptionManager(max_lines=4, line_width=20)
        
        # Add 4 lines of finalized text
        manager.handle_message("final", "line one")
        manager.handle_message("final", "line two")
        manager.handle_message("final", "line three")
        manager.handle_message("final", "line four")
        
        expected = "line one\nline two\nline three\nline four"
        self.assertEqual(manager.get_display_text(), expected)
        
        # Add 5th line - this should trigger FIFO clearing of first 2 lines
        manager.handle_message("final", "line five")
        
        # Lines 1-2 ("line one", "line two") cleared.
        # Lines 3-4 ("line three", "line four") move to 1-2.
        # Line 5 ("line five") is appended.
        expected = "line three\nline four\nline five"
        self.assertEqual(manager.get_display_text(), expected)
        
        # Add 6th line
        manager.handle_message("final", "line six")
        # Fits in 4 lines, no clearing
        expected = "line three\nline four\nline five\nline six"
        self.assertEqual(manager.get_display_text(), expected)

        # Add 7th line - should trigger FIFO clearing of first 2 lines again
        manager.handle_message("final", "line seven")
        # Lines 1-2 ("line three", "line four") cleared.
        # Lines 3-4 ("line five", "line six") move to 1-2.
        # Lines 7 is appended.
        expected = "line five\nline six\nline seven"
        self.assertEqual(manager.get_display_text(), expected)

    def test_long_message_wrapping_and_clearing(self):
        manager = CaptionManager(max_lines=4, line_width=10)
        # "1234567890 1234567890" will wrap to:
        # ["1234567890", "1234567890"] (2 lines)
        manager.handle_message("final", "1234567890 1234567890")
        self.assertEqual(manager.finalized_lines, ["1234567890", "1234567890"])
        
        # Add 3 more lines -> total 5 lines
        # "aaaaa bbbbb ccccc" will wrap to ["aaaaa", "bbbbb", "ccccc"] (3 lines)
        manager.handle_message("final", "aaaaa bbbbb ccccc")
        # finalized_lines would temporarily be: ["1234567890", "1234567890", "aaaaa", "bbbbb", "ccccc"] (5 lines)
        # After shift of 2: ["aaaaa", "bbbbb", "ccccc"] (3 lines)
        self.assertEqual(manager.finalized_lines, ["aaaaa", "bbbbb", "ccccc"])

if __name__ == "__main__":
    unittest.main()
