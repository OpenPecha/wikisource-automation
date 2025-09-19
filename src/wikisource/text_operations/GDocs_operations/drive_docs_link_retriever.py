import json
import logging
import os
from typing import Dict, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Required scopes for Drive and Documents access (shared with upload_to_google_docs.py)
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]


class DriveDocumentLinker:
    """
    Simple approach: Get filenames and webViewLinks from Google Drive in one API call.
    """

    def __init__(
        self,
        credentials_path: str,
        tengyur_folder_id: str,
        token_path: str = "token.json",
    ):
        """
        Initialize the Drive document linker

        Args:
            credentials_path: Path to OAuth client JSON
            tengyur_folder_id: Google Drive folder ID containing the documents
            token_path: Path to cached OAuth token file
        """
        self.credentials_path = credentials_path
        self.tengyur_folder_id = tengyur_folder_id
        self.token_path = token_path

        # Create output directory for logs and generated files
        self.output_dir = "drive_linker_output"
        os.makedirs(self.output_dir, exist_ok=True)

        self.setup_logging()
        self.setup_google_services()

    def setup_logging(self) -> None:
        """Setup logging configuration with clean formatting"""
        log_file_path = os.path.join(self.output_dir, "drive_document_links.log")

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
        """Initialize Google Drive API service via OAuth user credentials."""
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
                creds = flow.run_local_server(port=0)
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        self.drive_service = build(
            "drive", "v3", credentials=creds, cache_discovery=False
        )
        self.logger.info("🚀 Google Drive API service initialized successfully")

    def get_all_document_links(self) -> Dict[str, str]:
        """
        Get all document filenames and their corresponding webViewLinks from the Tengyur folder

        Returns:
            Dictionary mapping filename -> webViewLink
        """
        self.logger.info(
            f"📂 Starting document retrieval from Tengyur folder\n   Folder ID: {self.tengyur_folder_id}"
        )

        try:
            # Single API call to get both filenames and webViewLinks, excluding trashed files
            query = f"parents in '{self.tengyur_folder_id}' and mimeType='application/vnd.google-apps.document' and trashed=false"

            self.logger.info(
                f"🔍 Executing Drive API query:\n   Query: {query}\n   Fields: files(id,name,webViewLink)"
            )

            # Handle pagination to get ALL documents
            filename_to_link = {}
            page_token = None
            total_files = 0

            while True:
                results = (
                    self.drive_service.files()
                    .list(
                        q=query,
                        fields="nextPageToken, files(id,name,webViewLink)",
                        supportsAllDrives=True,
                        pageSize=1000,
                        pageToken=page_token,
                    )
                    .execute()
                )

                files = results.get("files", [])
                total_files += len(files)

                # Build filename -> edit link mapping (convert webViewLink to edit link)
                for file in files:
                    filename = file["name"]
                    doc_id = file["id"]
                    # Create edit link instead of webViewLink
                    edit_link = f"https://docs.google.com/document/d/{doc_id}/edit"
                    filename_to_link[filename] = edit_link

                # Check if there are more pages
                page_token = results.get("nextPageToken")
                if not page_token:
                    break

                self.logger.info(
                    f"📄 Retrieved {total_files} documents so far, fetching next page..."
                )

            self.logger.info(f"📊 Total documents retrieved: {total_files}")

            self.logger.info(
                f"✅ Successfully retrieved {len(filename_to_link)} document links from Google Drive"
            )

            # If no Google Docs found, check if folder has ANY files for debugging
            if not filename_to_link:
                self.logger.info(
                    "🔍 No Google Docs found. Checking for ANY files in the folder..."
                )
                fallback_query = f"parents in '{self.tengyur_folder_id}'"
                fallback_results = (
                    self.drive_service.files()
                    .list(
                        q=fallback_query,
                        fields="files(id,name,mimeType)",
                        supportsAllDrives=True,
                        pageSize=10,
                    )
                    .execute()
                )

                all_files = fallback_results.get("files", [])
                self.logger.info(f"📊 Total files in folder: {len(all_files)}")

                if all_files:
                    self.logger.info("📋 Sample files (any type):")
                    for file in all_files[:5]:
                        self.logger.info(
                            f"   • {file['name']} (Type: {file['mimeType']})"
                        )

            # Log sample of what we found
            if filename_to_link:
                sample_files = list(filename_to_link.keys())[:5]
                self.logger.info(
                    f"📋 Sample Google Docs found:\n   {chr(10).join([f'   • {file}' for file in sample_files])}"
                )

            return filename_to_link

        except HttpError as e:
            self.logger.error(
                f"❌ DRIVE API ERROR: Failed to fetch documents\n   Error details: {e}\n   Folder ID: {self.tengyur_folder_id}"
            )
            return {}

    def display_results(self, filename_to_link: Dict[str, str]) -> None:
        """
        Display the results in a readable format
        """
        print("\n" + "=" * 60)
        print("📄 DOCUMENT LINKS RETRIEVED")
        print("=" * 60)
        print(f"Total documents found: {len(filename_to_link)}")
        print("\n📋 Document List:")
        print("-" * 60)

        for filename, link in sorted(filename_to_link.items()):
            print(f"📄 {filename}")
            print(f"🔗 {link}")
            print("-" * 60)

    def save_to_json(
        self,
        filename_to_link: Dict[str, str],
        output_file: str = "text_id_to_url_mapping.json",
    ) -> None:
        """
        Save the filename -> link mapping to a JSON file in the format expected by update_google_sheets.py
        """
        try:
            # Save to drive_linker_output directory (separate from upload output)
            output_dir = "drive_linker_output"
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, output_file)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(filename_to_link, f, indent=2, ensure_ascii=False)
            self.logger.info(
                f"💾 Successfully saved {len(filename_to_link)} document links\n   Output file: {output_file}"
            )
            print(f"\n💾 Results saved to: {output_file}")
        except Exception as e:
            self.logger.error(
                f"❌ FILE SAVE ERROR: Failed to save document links to JSON\n   Target file: {output_file}\n   Error details: {e}"
            )
            print(f"\n❌ Failed to save to {output_file}: {e}")


def get_config() -> Optional[Dict[str, str]]:
    """Configuration settings"""
    config = {
        "credentials_path": "../../../../oauth-credentials.json",
        "tengyur_folder_id": "1Ae6rQadtfxfwKICLC87szcJAUjqQI7PR",  # Your Tengyur folder ID
        "token_path": "token.json",
    }

    # Validate credentials file
    if not os.path.exists(config["credentials_path"]):
        print(f"❌ Error: Credentials file not found: {config['credentials_path']}")
        return None

    return config


def main() -> None:
    """Main function"""
    try:
        # Get configuration
        config = get_config()
        if not config:
            return

        print("=" * 60)
        print("📄 GOOGLE DRIVE DOCUMENT LINKER 📄")
        print("=" * 60)
        print(f"\n📋 CONFIGURATION:")
        print(f"   Tengyur Folder: {config['tengyur_folder_id']}")
        print(f"   Credentials: {config['credentials_path']}")
        print(f"   Output Directory: drive_linker_output/")
        print("\n🚀 Fetching document links...")

        # Initialize linker
        linker = DriveDocumentLinker(
            config["credentials_path"],
            config["tengyur_folder_id"],
            config["token_path"],
        )

        # Get all document links
        filename_to_link = linker.get_all_document_links()

        if not filename_to_link:
            print("\n❌ No documents found in the folder")
            return

        # Save to default JSON file
        linker.save_to_json(filename_to_link)

        print(f"\n📁 All files saved in: {linker.output_dir}/")
        print(f"\n✅ Successfully retrieved {len(filename_to_link)} document links!")

    except KeyboardInterrupt:
        print("\n\n⏹️ Process interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
