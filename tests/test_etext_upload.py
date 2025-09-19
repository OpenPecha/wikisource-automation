import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from wikisource.etext_upload import get_page_titles, log_upload_result, parse_text_file


class TestETextUpload(unittest.TestCase):
    def setUp(self):
        # Create a temporary file for testing parse_text_file
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_file_path = os.path.join(self.temp_dir.name, "test_text.txt")
        print(f"test_file_path: {self.test_file_path}")
        with open(self.test_file_path, "w", encoding="utf-8") as f:
            f.write(
                "Page no: 1\n"
                "This is page one text.\n"
                "More text for page one.\n"
                "Page no: 2\n"
                "This is (some) text for page two.\n"
                "More text (with parentheses) for page two."
            )

    def tearDown(self):
        # Clean up temporary directory
        self.temp_dir.cleanup()

    def test_parse_text_file(self):
        """Test parsing a text file into page-by-page dict"""
        result = parse_text_file(self.test_file_path)
        self.assertEqual(len(result), 2)
        self.assertIn("1", result)
        self.assertIn("2", result)
        self.assertEqual(result["1"], "This is page one text.\nMore text for page one.")
        # Parentheses should be removed
        self.assertEqual(
            result["2"], "This is  text for page two.\nMore text  for page two."
        )

    @patch("wikisource.etext_upload.json.load")
    @patch("wikisource.etext_upload.open")
    @patch("pathlib.Path.exists")
    def test_get_page_titles_from_cache(self, mock_exists, mock_open, mock_json_load):
        """Test loading page titles from cache"""
        # Mock cache file exists
        mock_exists.return_value = True

        # Mock the json data that would be loaded from cache
        mock_json_load.return_value = {"1": "Page:Test/1", "2": "Page:Test/2"}

        # Mock the site object
        mock_site = MagicMock()

        # Mock ProofreadPage class inside the function
        with patch("pywikibot.proofreadpage.ProofreadPage") as mock_proofreadpage:
            mock_page1 = MagicMock()
            mock_page2 = MagicMock()
            mock_proofreadpage.side_effect = [mock_page1, mock_page2]

            # Call the function
            result = get_page_titles("Index:Test", mock_site)

            # Verify we got the expected result
            self.assertEqual(len(result), 2)
            self.assertEqual(result["1"], mock_page1)
            self.assertEqual(result["2"], mock_page2)
            # Verify ProofreadPage was called with the right arguments
            mock_proofreadpage.assert_any_call(mock_site, "Page:Test/1")
            mock_proofreadpage.assert_any_call(mock_site, "Page:Test/2")

    @patch("wikisource.etext_upload.csv.writer")
    @patch("wikisource.etext_upload.os.path.isfile")
    @patch("wikisource.etext_upload.open")
    def test_log_upload_result(self, mock_open, mock_isfile, mock_csv_writer):
        """Test logging upload results to CSV"""
        # Mock file does not exist to test header creation
        mock_isfile.return_value = False

        # Mock the CSV writer
        mock_writer = MagicMock()
        mock_csv_writer.return_value = mock_writer

        # Call the function
        log_upload_result(
            "Index:Test", "1", "Page:Test/1", "success", None, "test_log.csv"
        )

        # Verify header was written
        mock_writer.writerow.assert_any_call(
            [
                "timestamp",
                "index_title",
                "page_number",
                "page_title",
                "status",
                "error_message",
            ]
        )

        # Verify data row was written
        mock_writer.writerow.assert_any_call(
            [
                unittest.mock.ANY,  # timestamp will vary
                "Index:Test",
                "1",
                "Page:Test/1",
                "success",
                "",
            ]
        )


if __name__ == "__main__":
    unittest.main()
