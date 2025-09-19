import tempfile
import unittest
from pathlib import Path

from src.wikisource.text_operations.text_splitter_txt.kagyur_splitter import (
    LineByLineProcessor,
)


class TestSimpleInputOutput(unittest.TestCase):
    """Simple input-output tests with real Kagyur text examples."""

    def setUp(self):
        """Set up test fixtures."""
        temp_dir = Path(tempfile.mkdtemp())
        self.processor = LineByLineProcessor(temp_dir, temp_dir)

    def test_process_line_examples(self):
        """Test process_line with real input examples and expected outputs."""
        test_cases = [
            # Basic text variant replacement
            ("སྦྱང་བ་{བཅྭ་,བཅོ་}བརྒྱད་པོ་དག", "སྦྱང་བ་བཅོ་བརྒྱད་པོ་དག", None, False),
            # Dotted marker removal
            ("[1a.1]ཐུན་མོང་མ་ཡིན་པ་གང་ཞེ་ན།", "ཐུན་མོང་མ་ཡིན་པ་གང་ཞེ་ན།", None, False),
            # Section token detection and removal
            (
                "{D1}དགེ་སློང་དག་སྔོན་བྱུང་བ་བཱ་རཱ་ཎ་སཱིའི་གྲོང་ཁྱེར་དུ།",
                "དགེ་སློང་དག་སྔོན་བྱུང་བ་བཱ་རཱ་ཎ་སཱིའི་གྲོང་ཁྱེར་དུ།",
                "D1",
                False,
            ),
            # Simple page marker detection
            (
                "[1a]རྒྱལ་པོ་ཚངས་སྦྱིན་ཞེས་བྱ་བ་རྒྱལ་སྲིད་བྱེད་དུ།",
                "[1a]རྒྱལ་པོ་ཚངས་སྦྱིན་ཞེས་བྱ་བ་རྒྱལ་སྲིད་བྱེད་དུ།",
                None,
                True,
            ),
            # Complex real example from Kagyur files
            (
                "[1b.4]{D1}{D1-1}༄༅༅། །རྒྱ་གར་སྐད་དུ། བི་ན་ཡ་བསྟུ། བོད་སྐད་དུ། འདུལ་བ་གཞི། བམ་པོ་དང་པོ།",
                "༄༅༅། །རྒྱ་གར་སྐད་དུ། བི་ན་ཡ་བསྟུ། བོད་སྐད་དུ། འདུལ་བ་གཞི། བམ་པོ་དང་པོ།",
                "D1",
                False,
            ),
            # Text with variants and page marker
            (
                "[2a]བྱང་ཆུབ་{བཅྭ་,བཅོ་}སེམས་དཔའ་དགའ་ལྡན་གྱི་གནས་ན་བཞུགས་པ་ན།",
                "[2a]བྱང་ཆུབ་བཅོ་སེམས་དཔའ་དགའ་ལྡན་གྱི་གནས་ན་བཞུགས་པ་ན།",
                None,
                True,
            ),
            # Multiple patterns in one line
            (
                "[3a.2]{D2}གཞན་{ཚོས་,ཚོང་}དུས་དང་། །བཞི་མདོ་དང་། སུམ་མདོ་རྣམས་སུ།",
                "གཞན་ཚོང་དུས་དང་། །བཞི་མདོ་དང་། སུམ་མདོ་རྣམས་སུ།",
                "D2",
                False,
            ),
            # Section with letter suffix
            (
                "{D1a}རྒྱལ་པོ་པད་མ་ཆེན་པོ་ལ་ལྷ་ཨང་གའི་རྒྱལ་པོས།",
                "རྒྱལ་པོ་པད་མ་ཆེན་པོ་ལ་ལྷ་ཨང་གའི་རྒྱལ་པོས།",
                "D1a",
                False,
            ),
            # Multiple text variants
            (
                "ཁང་{བཟངས་ཀྱི་,བཟང་གི་}གཞིར་གཏོགས་པ་ན་བློན་པོའི་{ཚོས་,ཚོང་}ཀྱིས།",
                "ཁང་བཟང་གི་གཞིར་གཏོགས་པ་ན་བློན་པོའི་ཚོང་ཀྱིས།",
                None,
                False,
            ),
            # Empty and whitespace cases
            ("", "", None, False),
            ("   ", "   ", None, False),
            # Only markers
            ("[1a.1][2b.3]", "", None, False),
            ("[1a][2b]", "[1a][2b]", None, True),
        ]

        for (
            input_text,
            expected_output,
            expected_section,
            expected_has_page,
        ) in test_cases:
            with self.subTest(input_text=input_text):
                processed, section, has_page = self.processor.process_line(input_text)
                self.assertEqual(
                    processed, expected_output, f"Output mismatch for: {input_text}"
                )
                self.assertEqual(
                    section, expected_section, f"Section mismatch for: {input_text}"
                )
                self.assertEqual(
                    has_page,
                    expected_has_page,
                    f"Page detection mismatch for: {input_text}",
                )

    def test_replace_page_markers_examples(self):
        """Test page marker replacement with real examples."""
        test_cases = [
            # Format: (input, start_counter, expected_output, expected_counter)
            ("[1a]", 1, "Page: 1", 2),
            (
                "[1a] ཐུན་མོང་མ་ཡིན་པ། [1b] དགེ་སློང་དག་སྔོན་བྱུང་བ།",
                1,
                "Page: 1 ཐུན་མོང་མ་ཡིན་པ། Page: 2 དགེ་སློང་དག་སྔོན་བྱུང་བ།",
                3,
            ),
            (
                "[2a]བྱང་ཆུབ་སེམས་དཔའ། [2b]དགའ་ལྡན་གྱི་གནས་ན། [3a]བཞུགས་པ་ན།",
                5,
                "Page: 5བྱང་ཆུབ་སེམས་དཔའ། Page: 6དགའ་ལྡན་གྱི་གནས་ན། Page: 7བཞུགས་པ་ན།",
                8,
            ),
            ("no page markers here", 1, "no page markers here", 1),
        ]

        for input_text, start_counter, expected_output, expected_counter in test_cases:
            with self.subTest(input_text=input_text):
                processed, new_counter = self.processor.replace_page_markers(
                    input_text, start_counter
                )
                self.assertEqual(
                    processed, expected_output, f"Output mismatch for: {input_text}"
                )
                self.assertEqual(
                    new_counter, expected_counter, f"Counter mismatch for: {input_text}"
                )

    def test_meaningful_line_examples(self):
        """Test meaningful line detection with real examples."""
        test_cases = [
            # Format: (input, expected_meaningful)
            ("༄༅༅། །རྒྱ་གར་སྐད་དུ། བི་ན་ཡ་བསྟུ།", True),
            ("དགེ་སློང་དག་སྔོན་བྱུང་བ་བཱ་རཱ་ཎ་སཱིའི་གྲོང་ཁྱེར་དུ།", True),
            ("རྒྱལ་པོ་ཚངས་སྦྱིན་ཞེས་བྱ་བ་རྒྱལ་སྲིད་བྱེད་དུ་འཇུག་སྟེ།", True),
            ("[1a]", False),
            ("[1a.1]", False),
            ("[2b.4]", False),
            ("", False),
            ("   ", False),
            ("\t\n", False),
            ("[1a] ཀ", True),
            ("[1a.1] ཁ", True),
            ("   [2b]   ", False),
        ]

        for input_text, expected_meaningful in test_cases:
            with self.subTest(input_text=input_text):
                result = self.processor.is_meaningful_line(input_text)
                self.assertEqual(
                    result,
                    expected_meaningful,
                    f"Meaningful detection failed for: '{input_text}'",
                )


if __name__ == "__main__":
    unittest.main()
