import csv
import io
import logging
import re
from pathlib import Path
from typing import Optional

import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_drive_file_id(url: str) -> Optional[str]:
    """
    Extract the file ID from a Google Drive URL.

    Args:
        url: URL containing the file ID

    Returns:
        str: Extracted file ID or None if not found
    """
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    return None


def get_wikisource_index_from_url(url: str) -> Optional[str]:
    """
    Extract the Wikisource index title from a URL.

    Args:
        url: URL containing the Wikisource index title

    Returns:
        str: Extracted index title or None if not found
    """
    m = re.search(r"/wiki/([^?#]+)", url)
    if m:
        return m.group(1)
    return None


def get_drive_file_name(drive_service, file_id: str) -> str:
    """
    Get the name of a file from Google Drive by file ID.

    Args:
        drive_service: Google Drive API service
        file_id: ID of the file

    Returns:
        str: Name of the file
    """
    file = drive_service.files().get(fileId=file_id, fields="name").execute()
    return file["name"]


def download_drive_file_with_name(
    drive_service, file_id: str, download_dir: str
) -> str:
    """
    Download a file from Google Drive by file ID and save it with its original name.

    Args:
        drive_service: Google Drive API service
        file_id: ID of the file to download
        download_dir: Directory to save the file

    Returns:
        str: Name of the downloaded file
    """
    file_name = get_drive_file_name(drive_service, file_id)
    dest_path = Path(download_dir) / file_name

    # Download the file from Drive using the API (works for most non-Google Docs files)
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.FileIO(dest_path, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    return file_name


def download_google_doc_with_name(
    drive_service, doc_url: str, download_dir: str
) -> str:
    """
    Download a Google Doc by URL and save it with its original name.

    Args:
        drive_service: Google Drive API service
        doc_url: URL of the Google Doc
        download_dir: Directory to save the file

    Returns:
        str: Name of the downloaded file
    """
    # Get file ID and real name
    match = re.match(
        r"https://docs.google.com/document/d/([a-zA-Z0-9_-]+)", doc_url
    )  # noqa
    if not match:
        raise ValueError("Not a Google Doc URL")
    file_id = match.group(1)
    file_name = get_drive_file_name(drive_service, file_id) + ".txt"  # exported as txt
    dest_path = Path(download_dir) / file_name

    # Download as plain text
    export_url = (
        f"https://docs.google.com/document/d/{file_id}/export?format=txt"  # noqa
    )
    response = requests.get(export_url)
    with open(dest_path, "wb") as f:
        f.write(response.content)
    return file_name


def download_links_and_make_csv(
    sheet_id: str, creds_path: str, range_rows: str, output_csv: str, download_dir: str
) -> None:
    """
    Downloads text files from Google Drive or Docs using URLs in a Google Sheet,
    extracts index titles from Wikisource links, and writes an Index-text CSV.
    The text filename is the original name from Drive/Docs, not a custom one.

    Args:
        sheet_id (str): Google Sheet ID.
        creds_path (str): Path to service account JSON credentials.
        range_rows (str): Sheet range (e.g. 'སྤྱོད་འཇུག་གི་ལས་གཞི།!G3:K8').
        output_csv (str): e.g. "src/wiki_utils/wikisource/data/work_list.csv"
        download_dir (str): e.g. "src/wiki_utils/wikisource/data/text"
    """
    creds = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )
    sheet_service = build("sheets", "v4", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)
    sheet = sheet_service.spreadsheets()

    result = sheet.get(
        spreadsheetId=sheet_id, ranges=[range_rows], includeGridData=True
    ).execute()
    rows = result["sheets"][0]["data"][0]["rowData"]

    output_rows = []
    Path(download_dir).mkdir(parents=True, exist_ok=True)

    for row in rows:
        try:
            wikidata_cell = row["values"][0]
            ws_link_cell = row["values"][4]
            wikidata_link = wikidata_cell.get("hyperlink")
            ws_link = ws_link_cell.get("hyperlink")

            if not wikidata_link or not ws_link:
                logger.warning(f"Missing Wikidata or Wikisource link in row: {row}")
                continue
            index_title = get_wikisource_index_from_url(ws_link)
            if not index_title:
                logger.warning(f"Invalid Wikisource link in row: {row}")
                continue

            if "drive.google.com" in wikidata_link:
                file_id = get_drive_file_id(wikidata_link)
                if file_id:
                    file_name = download_drive_file_with_name(
                        drive_service, file_id, download_dir
                    )
                else:
                    logger.warning(f"Could not extract file_id from: {wikidata_link}")
                    continue
            elif "docs.google.com/document" in wikidata_link:
                file_name = download_google_doc_with_name(
                    drive_service, wikidata_link, download_dir
                )
            else:
                logger.warning(f"Unknown file type: {wikidata_link}")
                continue

            output_rows.append([index_title, file_name])
        except Exception as e:
            logger.warning(f"Error processing row: {e}")

    # Write output CSV
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Index", "text"])
        writer.writerows(output_rows)
    print(f"\n\n✅ {len(output_rows)} files listed in '{output_csv}'.\n\n")
