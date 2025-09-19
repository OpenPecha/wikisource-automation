import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
]


class GoogleSheetsUpdater:
    """Updates Google Sheets with Google Docs URLs from text_id mapping"""

    def __init__(self, credentials_path: str, token_path: str = "token.json"):
        """
        Initialize the Google Sheets updater

        Args:
            credentials_path: Path to OAuth client JSON
            token_path: Path to cached OAuth token file
        """
        self.credentials_path = credentials_path
        self.token_path = token_path

        # Configure as needed.
        # self.GOOGLE_SHEET_ID = "1f4fu_IKT22o5U8cmplwQsAc0CU4CRg_Nj5eprw-CDdY"
        self.GOOGLE_SHEET_ID = "1vtQ_aCDN1Y9jbwmJEE48aIgPauRvheFgYF6X1xKieMo"
        self.SHEET_NAME = "སྡེ་དགེ་བསྟན་འགྱུར་ཡར་འཇུག"

        # Create output directory for logs and missing IDs
        self.output_dir = "google_sheets_update_output"
        os.makedirs(self.output_dir, exist_ok=True)

        self.setup_logging()
        self.setup_google_services()
        self.missing_text_ids: List[str] = []

    def setup_logging(self) -> None:
        """Setup logging configuration"""
        log_file_path = os.path.join(self.output_dir, "google_sheets_update.log")

        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

        # File handler
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setFormatter(formatter)

        # Console handler
        console_formatter = logging.Formatter(
            "🔍 %(asctime)s | %(levelname)s\n📝 %(message)s"
        )
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)

        # Configure logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.propagate = False

        self.logger.info(f"📁 Log file created at: {log_file_path}")

    def setup_google_services(self) -> None:
        """Initialize Google Sheets API service via OAuth"""
        creds = None

        # Reuse token if present
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        # If no valid creds, run OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        self.sheets_service = build(
            "sheets", "v4", credentials=creds, cache_discovery=False
        )
        self.logger.info("🚀 Google Sheets API service initialized successfully")

    def load_url_mapping(
        self,
        mapping_file: str = "google_docs_upload_output/text_id_to_url_mapping.json",
    ) -> Dict[str, str]:
        """Load text_id to URL mapping from JSON file"""
        if not os.path.exists(mapping_file):
            self.logger.error(f"❌ Mapping file not found: {mapping_file}")
            return {}

        try:
            with open(mapping_file) as f:
                mapping = json.load(f)
            self.logger.info(
                f"📖 Loaded {len(mapping)} URL mappings from {mapping_file}"
            )
            return mapping
        except Exception as e:
            self.logger.error(f"❌ Failed to load mapping file: {e}")
            return {}

    def read_sheet_range(
        self, start_row: int, end_row: int
    ) -> Tuple[List[str], List[str]]:
        """
        Read text_ids from column J and existing URLs from column K for specified row range

        Returns:
            Tuple of (text_ids_list, existing_urls_list)
        """
        try:
            # Read data from columns J (text_id), K (hyperlinked URLs), and L (direct URLs)
            range_name = f"{self.SHEET_NAME}!J{start_row}:L{end_row}"

            result = (
                self.sheets_service.spreadsheets()
                .values()
                .get(spreadsheetId=self.GOOGLE_SHEET_ID, range=range_name)
                .execute()
            )

            values = result.get("values", [])
            text_ids = []
            existing_urls = []

            for row in values:
                # Column J (index 0) contains text_id
                text_id = row[0] if len(row) > 0 else ""
                text_ids.append(text_id)

                # Check both Column K (index 1) and Column L (index 2) for existing URLs
                existing_url_k = row[1] if len(row) > 1 else ""
                existing_url_l = row[2] if len(row) > 2 else ""
                # If either column has content, consider it as existing
                existing_url = existing_url_k or existing_url_l
                existing_urls.append(existing_url)

            self.logger.info(f"📊 Read {len(text_ids)} rows from range {range_name}")
            return text_ids, existing_urls

        except HttpError as e:
            self.logger.error(f"❌ Failed to read sheet range: {e}")
            return [], []

    def update_sheet_urls(
        self, start_row: int, urls_to_update: List[Tuple[int, str, str]]
    ) -> None:
        """
        Update Google Sheet with hyperlinked text IDs in column K and direct URLs in column L

        Args:
            start_row: Starting row number
            urls_to_update: List of (row_offset, url, text_id) tuples
        """
        if not urls_to_update:
            self.logger.info("No URLs to update")
            return

        try:
            # Prepare batch update data for both columns K and L
            data = []
            for row_offset, url, text_id in urls_to_update:
                actual_row = start_row + row_offset

                # Column K: Hyperlink formula =HYPERLINK("url", "display_text")
                hyperlink_formula = f'=HYPERLINK("{url}", "{text_id}")'
                data.append(
                    {
                        "range": f"{self.SHEET_NAME}!K{actual_row}",
                        "values": [[hyperlink_formula]],
                    }
                )

                # Column L: Direct URL
                data.append(
                    {"range": f"{self.SHEET_NAME}!L{actual_row}", "values": [[url]]}
                )

            # Batch update with USER_ENTERED to process formulas in column K
            body = {"valueInputOption": "USER_ENTERED", "data": data}

            result = (
                self.sheets_service.spreadsheets()
                .values()
                .batchUpdate(spreadsheetId=self.GOOGLE_SHEET_ID, body=body)
                .execute()
            )

            updated_cells = result.get("totalUpdatedCells", 0)
            self.logger.info(
                f"✅ Successfully updated {updated_cells} cells (both column K with hyperlinked text IDs and column L with direct URLs)"
            )

        except HttpError as e:
            if "protected cell" in str(e).lower():
                self.logger.warning(
                    f"⚠️  Some cells are protected and couldn't be updated. Contact sheet owner to remove protection."
                )
                self.logger.info(f"✅ Partial update completed for non-protected cells")
            else:
                self.logger.error(f"❌ Failed to update sheet: {e}")

    def save_missing_text_ids(self) -> None:
        """Save missing text_ids to a JSON file"""
        if not self.missing_text_ids:
            self.logger.info("No missing text_ids to save")
            return

        missing_file = os.path.join(self.output_dir, "missing_text_ids.json")
        try:
            with open(missing_file, "w") as f:
                json.dump(self.missing_text_ids, f, indent=2)
            self.logger.info(
                f"📄 Missing text_ids saved to {missing_file} ({len(self.missing_text_ids)} entries)"
            )
        except Exception as e:
            self.logger.error(f"❌ Failed to save missing text_ids: {e}")

    def update_sheet_range(
        self,
        start_row: int,
        end_row: int,
        mapping_file: str = "google_docs_upload_output/text_id_to_url_mapping.json",
    ) -> None:
        """
        Update Google Sheet with URLs for specified row range

        Args:
            start_row: Starting row number (1-based)
            end_row: Ending row number (1-based)
            mapping_file: Path to the text_id to URL mapping JSON file
        """
        self.logger.info(
            f"🚀 Starting Google Sheets update for rows {start_row} to {end_row}"
        )

        # Load URL mapping
        url_mapping = self.load_url_mapping(mapping_file)
        if not url_mapping:
            self.logger.error("❌ No URL mapping available. Cannot proceed.")
            return

        # Read current sheet data
        text_ids, existing_urls = self.read_sheet_range(start_row, end_row)

        if not text_ids:
            self.logger.error("❌ No data found in specified range")
            return

        # Process each row
        urls_to_update = []
        skipped_existing = 0
        missing_count = 0

        for i, (text_id, existing_url) in enumerate(zip(text_ids, existing_urls)):
            if not text_id.strip():
                continue  # Skip empty text_ids

            # Skip if column K already has a URL
            if existing_url.strip():
                skipped_existing += 1
                self.logger.info(
                    f"⏭️  Row {start_row + i}: Skipping {text_id} - already has URL"
                )
                continue

            # Check if text_id exists in our mapping
            if text_id in url_mapping:
                url = url_mapping[text_id]
                urls_to_update.append(
                    (i, url, text_id)
                )  # Include text_id for hyperlink display
                self.logger.info(f"✅ Row {start_row + i}: {text_id} → URL found")
            else:
                self.missing_text_ids.append(text_id)
                missing_count += 1
                self.logger.warning(
                    f"⚠️  Row {start_row + i}: {text_id} → URL not found in mapping"
                )

        # Update the sheet
        self.update_sheet_urls(start_row, urls_to_update)

        # Save missing text_ids
        self.save_missing_text_ids()

        self.logger.info("✅ Google Sheets update completed!")
        self.logger.info(f"📈 Summary:")
        self.logger.info(f"   Total rows processed: {len(text_ids)}")
        self.logger.info(f"   URLs updated: {len(urls_to_update)}")
        self.logger.info(f"   Skipped (already had URLs): {skipped_existing}")
        self.logger.info(f"   Missing from mapping: {missing_count}")


def get_update_config() -> Optional[Dict[str, Any]]:
    """Configuration settings - modify these as needed"""
    config = {
        "credentials_path": "../../../../oauth-credentials.json",
        "start_row": 2106,
        "end_row": 2386,
        "mapping_file": "google_docs_upload_output/text_id_to_url_mapping.json",
    }

    if not os.path.exists(str(config["credentials_path"])):
        print(f"❌ Error: Credentials file not found: {config['credentials_path']}")
        return None

    print("=" * 60)
    print("🔥 GOOGLE SHEETS URL UPDATER 🔥")
    print("=" * 60)
    print("\n📋 UPDATE CONFIGURATION:")
    print(f"   Credentials: {config['credentials_path']}")
    print(f"   Row range: {config['start_row']} to {config['end_row']}")
    print(f"   Mapping file: {config['mapping_file']}")
    print("\n🚀 Starting update...")

    return config


def main() -> None:
    """Main function"""
    try:
        config = get_update_config()
        if not config:
            return

        print("\n🔄 Initializing sheets updater...")
        updater = GoogleSheetsUpdater(config["credentials_path"])

        updater.update_sheet_range(
            start_row=config["start_row"],
            end_row=config["end_row"],
            mapping_file=config["mapping_file"],
        )

    except KeyboardInterrupt:
        print("\n\n⏹️ Update interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
