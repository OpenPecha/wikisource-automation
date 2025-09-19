import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

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


class GoogleDocsUploader:
    """Handles uploading text files to Google Docs with resume capability"""

    def __init__(
        self,
        credentials_path: str,
        progress_file: str = "upload_progress.json",
        token_path: str = "token.json",
    ):
        """
        Initialize the uploader

        Args:
            credentials_path: Path to OAuth client JSON (oauth_client.json)
            progress_file: Path to progress tracking file
            token_path: Path to cached OAuth token file
        """
        self.credentials_path = credentials_path
        self.token_path = token_path

        # Create output directory for logs and progress files
        self.output_dir = "google_docs_upload_output"
        os.makedirs(self.output_dir, exist_ok=True)

        # Ensure progress file is in output directory
        if not os.path.dirname(progress_file):
            self.progress_file = os.path.join(self.output_dir, progress_file)
        else:
            self.progress_file = progress_file

        self.setup_logging()
        self.setup_google_services()
        self.tengyur_folder_id: Optional[str] = None
        self.progress_data = self.load_progress()

        # Dictionary to store text_id -> document_id mapping during execution
        self.doc_id_mapping: Dict[str, str] = {}

    def setup_logging(self) -> None:
        """Setup logging configuration with clean formatting"""
        log_file_path = os.path.join(self.output_dir, "google_docs_upload.log")

        # Create clean formatter without excessive separators
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

        # File handler
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setFormatter(formatter)

        # Console handler with clean format
        console_formatter = logging.Formatter(
            "🔍 %(asctime)s | %(levelname)s\n📝 %(message)s"
        )
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)

        # Configure logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # Clear any existing handlers
        self.logger.handlers.clear()

        # Add our custom handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        # Prevent propagation to root logger
        self.logger.propagate = False

        self.logger.info(f"📁 Log file created at: {log_file_path}")

    def setup_google_services(self) -> None:
        """Initialize Google API services via OAuth user credentials."""
        creds = None
        # Reuse token if present
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        # If no valid creds, run OAuth flow once
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                # If you have a browser: use local server flow
                creds = flow.run_local_server(port=0)
                # If headless server, use:
                # creds = flow.run_console()
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        # cache_discovery=False silences the oauth2client file_cache notice
        self.docs_service = build(
            "docs", "v1", credentials=creds, cache_discovery=False
        )
        self.drive_service = build(
            "drive", "v3", credentials=creds, cache_discovery=False
        )
        self.logger.info("🚀 Google API services (OAuth) initialized successfully")

    def load_progress(self) -> Dict:
        """Load progress from file"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file) as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Could not load progress file: {e}")

        return {
            "completed": [],
            "failed": [],
            "last_processed": None,
            "tengyur_folder_id": None,
        }

    def save_progress(self) -> None:
        """Save current progress to file"""
        try:
            with open(self.progress_file, "w") as f:
                json.dump(self.progress_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save progress: {e}")

    def _write_mapping_to_json(self) -> None:
        """Write the URL mapping to JSON file at the end of execution, merging with existing mappings"""
        if not self.doc_id_mapping:
            self.logger.info("No document mappings to save")
            return

        # Create URL mapping from document IDs
        new_url_mapping = {}
        for text_id, doc_id in self.doc_id_mapping.items():
            new_url_mapping[
                text_id
            ] = f"https://docs.google.com/document/d/{doc_id}/edit"

        # Load existing mapping file if it exists
        url_mapping_file = os.path.join(self.output_dir, "text_id_to_url_mapping.json")
        existing_mapping = {}

        if os.path.exists(url_mapping_file):
            try:
                with open(url_mapping_file) as f:
                    existing_mapping = json.load(f)
                self.logger.info(
                    f"📖 Loaded {len(existing_mapping)} existing mappings from {url_mapping_file}"
                )
            except Exception as e:
                self.logger.warning(f"Could not load existing mapping file: {e}")

        # Merge existing and new mappings
        combined_mapping = existing_mapping.copy()
        combined_mapping.update(new_url_mapping)

        # Save combined URL mapping
        try:
            with open(url_mapping_file, "w") as f:
                json.dump(combined_mapping, f, indent=2)
            self.logger.info(f"🔗 URL mapping saved to {url_mapping_file}")
            self.logger.info(
                f"   📊 Total entries: {len(combined_mapping)} (added {len(new_url_mapping)} new)"
            )
        except Exception as e:
            self.logger.error(f"Failed to save URL mapping: {e}")

    def get_tengyur_folder(self) -> str:
        """Use the existing Tengyur folder in Google Drive (works for My Drive or Shared Drives)."""
        self.tengyur_folder_id = "1Ae6rQadtfxfwKICLC87szcJAUjqQI7PR"  # your folder ID
        try:
            folder_info = (
                self.drive_service.files()
                .get(
                    fileId=self.tengyur_folder_id,
                    fields="id,name,driveId",
                    supportsAllDrives=True,
                )
                .execute()
            )
            self.is_shared_drive = "driveId" in folder_info
            where = "Shared Drive" if self.is_shared_drive else "My Drive"
            self.logger.info(
                f"📂 Using existing Tengyur folder\n   Name: {folder_info['name']}\n   ID: {self.tengyur_folder_id}\n   Location: {where}"
            )
            self.progress_data["tengyur_folder_id"] = self.tengyur_folder_id
            self.save_progress()
            return self.tengyur_folder_id
        except HttpError as e:
            self.logger.error(
                f"Failed to access Tengyur folder {self.tengyur_folder_id}: {e}"
            )
            raise

    def clean_text_content(self, content: str) -> str:
        """Remove trailing ༄ character from text content if present at the end"""
        if content.endswith("༄"):
            cleaned_content = content.rstrip("༄").rstrip()
            self.logger.info("🧹 Removed trailing ༄ character from text content")
            return cleaned_content
        return content

    def read_text_file(self, text_id: str) -> Optional[str]:
        """Read content from text file"""
        text_file_path = Path(f"../../../../data_text_operations/text/{text_id}")

        # Look for text files in the directory
        if not text_file_path.exists():
            self.logger.warning(f"Directory not found: {text_file_path}")
            return None

        # Find .txt files in the directory
        txt_files = list(text_file_path.glob("*.txt"))

        if not txt_files:
            self.logger.warning(f"No .txt files found in {text_file_path}")
            return None

        # Use the first .txt file found
        txt_file = txt_files[0]

        try:
            with open(txt_file, encoding="utf-8") as f:
                content = f.read()

            # Clean the content by removing trailing ༄ character
            content = self.clean_text_content(content)

            self.logger.info(f"📖 Read {len(content)} characters from {txt_file}")
            return content

        except Exception as e:
            self.logger.error(f"Failed to read {txt_file}: {e}")
            return None

    def create_google_doc(self, text_id: str, content: str) -> Optional[str]:
        """Create a Google Doc with the given content directly inside the Tengyur folder."""
        try:
            # Create the Doc IN the target folder
            file_metadata = {
                "name": text_id,
                "mimeType": "application/vnd.google-apps.document",
                "parents": [self.tengyur_folder_id],
            }
            doc = (
                self.drive_service.files()
                .create(body=file_metadata, fields="id", supportsAllDrives=True)
                .execute()
            )
            doc_id = doc.get("id")

            # Insert content
            requests = [{"insertText": {"location": {"index": 1}, "text": content}}]
            self.docs_service.documents().batchUpdate(
                documentId=doc_id, body={"requests": requests}
            ).execute()

            self.logger.info(
                f"🎉 Successfully created Google Doc\n   Text ID: {text_id}\n   Doc ID: {doc_id}"
            )
            return doc_id

        except HttpError as e:
            self.logger.error(f"Failed to create Google Doc for {text_id}: {e}")
            return None

    def process_text_file(self, text_id: str) -> bool:
        """Process a single text file"""
        # Skip if already completed
        if text_id in self.progress_data["completed"]:
            self.logger.info(f"Skipping {text_id} - already completed")
            return True

        # Start processing log
        self.logger.info(f"📄 Processing {text_id}...")

        # Read text content
        content = self.read_text_file(text_id)
        if not content:
            self.progress_data["failed"].append(text_id)
            self.save_progress()
            return False

        # Create Google Doc
        doc_id = self.create_google_doc(text_id, content)
        if not doc_id:
            self.progress_data["failed"].append(text_id)
            self.save_progress()
            self.logger.error(f"❌ Failed to create Google Doc for {text_id}")
            # Add separator line after failed processing
            print("\n" + "-" * 80 + "\n")
            return False

        # Store document ID in mapping dictionary
        self.doc_id_mapping[text_id] = doc_id

        # Mark as completed
        self.progress_data["completed"].append(text_id)
        self.progress_data["last_processed"] = text_id
        self.save_progress()

        self.logger.info(f"✅ Successfully completed {text_id}")
        # Add separator line after completing each text file
        print("\n" + "-" * 80 + "\n")
        return True

    def get_text_ids_in_range(
        self, start_id: Optional[str] = None, end_id: Optional[str] = None
    ) -> List[str]:
        """Get list of text IDs in specified range"""
        # Read all text IDs from text_list.txt
        text_list_path = Path("../../../../data_text_operations/text_list.txt")

        if not text_list_path.exists():
            self.logger.error("text_list.txt not found")
            return []

        with open(text_list_path, encoding="utf-8") as f:
            all_text_ids = [line.strip() for line in f if line.strip()]

        # Filter by range if specified
        if start_id or end_id:
            try:
                start_idx = all_text_ids.index(start_id) if start_id else 0
                end_idx = (
                    all_text_ids.index(end_id) + 1 if end_id else len(all_text_ids)
                )
                filtered_ids = all_text_ids[start_idx:end_idx]
                self.logger.info(
                    f"Processing range: {start_id or 'start'} to {end_id or 'end'} ({len(filtered_ids)} files)"
                )
                return filtered_ids
            except ValueError as e:
                self.logger.error(f"Invalid range specified: {e}")
                return []

        return all_text_ids

    def upload_batch(
        self,
        start_id: Optional[str] = None,
        end_id: Optional[str] = None,
        delay: float = 1.0,
    ) -> None:
        """Upload batch of text files to Google Docs"""
        self.logger.info("🚀 Starting Google Docs upload process...")

        # Setup Tengyur folder
        self.get_tengyur_folder()

        # Get text IDs to process
        text_ids = self.get_text_ids_in_range(start_id, end_id)

        if not text_ids:
            self.logger.error("No text IDs to process")
            return

        total_files = len(text_ids)
        completed_count = len(
            [tid for tid in text_ids if tid in self.progress_data["completed"]]
        )

        self.logger.info(
            f"📊 Upload Statistics\n   Total files to process: {total_files}\n   Already completed: {completed_count}\n   Remaining: {total_files - completed_count}"
        )

        # Process each text file
        for i, text_id in enumerate(text_ids, 1):
            try:
                success = self.process_text_file(text_id)

                if success:
                    self.logger.info(
                        f"🚀 Overall Progress: {i}/{total_files} files completed"
                    )
                else:
                    self.logger.error(
                        f"⚠️  Overall Progress: {i}/{total_files} files processed (last failed)"
                    )

                # Rate limiting delay
                if delay > 0:
                    time.sleep(delay)

            except KeyboardInterrupt:
                self.logger.info("Upload interrupted by user")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error processing {text_id}: {e}")
                self.progress_data["failed"].append(text_id)
                self.save_progress()

        # Final summary
        final_completed = len(
            [tid for tid in text_ids if tid in self.progress_data["completed"]]
        )
        final_failed = len(
            [tid for tid in text_ids if tid in self.progress_data["failed"]]
        )

        self.logger.info("✅ Upload batch completed!")
        self.logger.info(
            f"📈 Final Results\n   Successfully uploaded: {final_completed}\n   Failed: {final_failed}"
        )

        # Write document ID mapping to JSON file at the end
        self._write_mapping_to_json()

        if self.progress_data["failed"]:
            self.logger.info(
                f"❌ Failed files:\n   {chr(10).join([f'   • {file}' for file in self.progress_data['failed']])}"
            )


def get_upload_config() -> Optional[Dict[str, Any]]:
    """Configuration settings - modify these as needed"""
    config = {
        "credentials_path": "../../../../oauth-credentials.json",
        "start_id": "D3999",  # Change this to start from different text ID
        "end_id": "D4464",  # the end range u want.
        "delay": 1.0,
        "progress_file": "upload_progress_OAuth.json",
    }

    if not os.path.exists(str(config["credentials_path"])):
        print(f"❌ Error: Credentials file not found: {config['credentials_path']}")
        return None

    print("=" * 60)
    print("🔥 GOOGLE DOCS UPLOAD TOOL FOR TIBETAN TEXTS 🔥")
    print("=" * 60)
    print("\n📋 UPLOAD CONFIGURATION:")
    print(f"   Credentials: {config['credentials_path']}")
    print(f"   Start ID: {config['start_id'] if config['start_id'] else 'Beginning'}")
    print(f"   End ID: {config['end_id'] if config['end_id'] else 'End'}")
    print(f"   Delay: {config['delay']} seconds")
    print(f"   Progress file: {config['progress_file']}")
    print("\n🚀 Starting upload...")

    return config


def main() -> None:
    """Main function."""
    try:
        config = get_upload_config()
        if not config:
            return

        print("\n🔄 Initializing upload...")
        uploader = GoogleDocsUploader(
            config["credentials_path"], config["progress_file"]
        )
        uploader.upload_batch(config["start_id"], config["end_id"], config["delay"])

    except KeyboardInterrupt:
        print("\n\n⏹️ Upload interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return


if __name__ == "__main__":
    main()
