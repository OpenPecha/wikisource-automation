import csv
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import pywikibot

from wikisource.helper_function import download_links_and_make_csv
from wikisource.utils.logger import get_logger

# Initialize the logger
logger = get_logger(__name__)


SITE_CODE = "mul"
FAMILY = "wikisource"


def login_to_wikisource() -> pywikibot.Site:
    """
    Logs in to Wikisource using Pywikibot.
    Returns:
    - site: Pywikibot Site object for Wikisource.
    """
    site = pywikibot.Site(SITE_CODE, FAMILY)
    site.login()
    return site


# --- Helper Functions ---
def parse_text_file(text_file_path: str) -> Dict[str, str]:
    """
    Parse the text file into a dict: {page_number: text}
    Assumes format:
        Page no: N\n<text>\n...\nPage no: M\n<text>\n...
    """
    page_texts = {}
    current_page = None
    current_lines: List[str] = []
    with open(text_file_path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            if line.strip().startswith("Page no:"):
                # Save previous page
                if current_page is not None:
                    page_texts[str(current_page)] = "\n".join(current_lines).strip()
                # Start new page
                try:
                    current_page = line.split(":", 1)[1].strip()
                except IndexError:
                    current_page = None
                current_lines = []
            else:
                # Remove text within parentheses
                line = re.sub(r"\([^)]*\)", "", line)
                current_lines.append(line)
        # Save last page
        if current_page is not None:
            page_texts[str(current_page)] = "\n".join(current_lines).strip()
    return page_texts


# def parse_text_file(text_file_path: str) -> Dict[str, str]:
#     """
#     Parse the text file into a dict: {page_number: text}
#     Assumes format:
#         <number> <text>
#         <text continued>
#         <number> <text>
#         ...
#     """
#     page_texts = {}
#     current_page = None
#     current_lines: list[str] = []
#     # Use [0-9]+ instead of \d+ to match only ASCII numbers
#     page_num_re = re.compile(r"^\s*([0-9]+)\s+(.*)")
#     with open(text_file_path, encoding="utf-8-sig") as f:
#         for line in f:
#             line = line.rstrip("\n")
#             # Check if the line starts with a number and a space
#             match = page_num_re.match(line)
#             if match:
#                 # Save the previous page's content
#                 if current_page is not None:
#                     page_texts[str(current_page)] = "\n".join(current_lines).strip()
#                 # Start a new page
#                 current_page = match.group(1)
#                 line_text = match.group(2)
#                 current_lines = [line_text]
#             else:
#                 # This is just a content line; add it to the current page's lines
#                 current_lines.append(line)
#         # Save the last page
#         if current_page is not None:
#             page_texts[str(current_page)] = "\n".join(current_lines).strip()

#     # save in json to understand.
#     text_file_path_obj = Path(text_file_path)
#     base_name = text_file_path_obj.stem
#     json_file_name = base_name + ".json"
#     data_dir = Path(__file__).parent / "data"
#     target_folder = data_dir / "json_Saver"
#     target_folder.mkdir(parents=True, exist_ok=True)
#     json_file_path = target_folder / json_file_name
#     with open(json_file_path, "w", encoding="utf-8") as jf:
#         json.dump(page_texts, jf, ensure_ascii=False, indent=2)

#     return page_texts


def get_page_titles(
    index_title: str, site: pywikibot.Site
) -> Dict[str, "pywikibot.proofreadpage.ProofreadPage"]:
    """
    Returns a dict of {page_number: ProofreadPage object}.
    Caches the mapping {page_number: page_title} in a local file for faster reuse.
    """
    # Set cache_dir at the project root level (alongside data folder)
    project_root = Path(__file__).parent.parent.parent
    cache_dir = project_root / "cache"
    # Create cache directory if it doesn't exist
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Use SHA256 hash of index_title for unique, safe filename
    index_hash = hashlib.sha256(index_title.encode("utf-8")).hexdigest()
    cache_file = cache_dir / f"Page_{index_hash}.json"

    # Try to load from cache
    if cache_file.exists():
        try:
            with open(cache_file, encoding="utf-8") as f:
                mapping = json.load(f)
            from pywikibot.proofreadpage import ProofreadPage

            page_dict = {k: ProofreadPage(site, v) for k, v in mapping.items()}
            return page_dict
        except (json.JSONDecodeError, OSError):
            logger.warning(
                f"\n\nCache file {cache_file} is invalid or empty. Deleting and refetching.\n\n"
            )
            cache_file.unlink()

    # Otherwise, fetch from Wikisource and cache
    index = pywikibot.Page(site, index_title)
    if not index.exists():
        logger.error(f"\n\nIndex page '{index_title}' does not exist.\n\n")
        return {}
    from pywikibot.proofreadpage import IndexPage

    idx = IndexPage(index)
    page_dict = {}
    mapping = {}
    for p in idx.page_gen():
        if p._num is not None:
            page_dict[str(p._num)] = p
            mapping[str(p._num)] = p.title()
    # Save mapping to cache
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    return page_dict


def log_upload_result(
    index_title: str,
    page_no: str,
    page_title: str,
    status: str,
    error_message: Optional[str] = None,
    log_path: str = "upload_log.csv",
) -> None:
    """Log upload result to a CSV file"""
    # Save log file at project root level
    project_root = Path(__file__).parent.parent.parent
    csv_file_path = project_root / log_path
    file_exists = csv_file_path.exists()

    with open(csv_file_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(
                [
                    "timestamp",
                    "index_title",
                    "page_number",
                    "page_title",
                    "status",
                    "error_message",
                ]
            )
        writer.writerow(
            [
                datetime.now().isoformat(),
                index_title,
                page_no,
                page_title,
                status,
                error_message or "",
            ]
        )


def upload_texts(site: pywikibot.Site, index_title: str, text_file_path: str) -> None:
    page_texts = parse_text_file(text_file_path)
    page_objs = get_page_titles(index_title, site)
    for page_no, text in page_texts.items():
        if page_no not in page_objs:
            logger.warning(f"\n\nPage number {page_no} not found in index.\n\n")
            log_upload_result(
                index_title, page_no, "", "failure", "Page number not found in index"
            )
            continue
        page = page_objs[page_no]
        logger.info(f"Uploading text to {page.title()}...")
        try:
            # ---- NEW: Clean and style the text ----
            # Remove HTML tags (if any exist in your OCR/text)
            clean_text = re.sub(r"<[^>]+>", "", text).strip()
            # Apply margin styling
            styled_content = (
                '<div style="margin-left: 3em; margin-right: 3em;">'
                f"{clean_text if clean_text else '&nbsp;'}"
                "</div>"
                "<noinclude></noinclude>"
            )
            # Wrap text in correct ProofreadPage format
            quality_tag = (
                '<noinclude><pagequality level="3" user="Ganga4364" /></noinclude>'
            )
            formatted_text = f"{quality_tag}\n{styled_content}\n<noinclude></noinclude>"
            page.text = formatted_text
            page.proofread_page_quality = 3  # 3 = Proofread
            page.save(summary="Bot: Adding OCR/provided text and marking as proofread.")
            logger.info(f"\n\nSuccess: {page.title()}\n\n")
            log_upload_result(index_title, page_no, page.title(), "success")
        except Exception as e:
            logger.error(f"\n\nError uploading {page.title()}: {e}\n\n")
            log_upload_result(index_title, page_no, page.title(), "failure", str(e))


def batch_upload_from_csv(
    csv_file_path: str,
    data_dir: str,
    site: Optional[pywikibot.Site] = None,
) -> None:
    """Upload texts for all entries in a CSV file"""
    if site is None:
        site = login_to_wikisource()

    df = pd.read_csv(csv_file_path)
    for i, row in df.iterrows():
        index_title = row["Index"]
        text = row["text"]
        text_file_path = os.path.join(data_dir, text)
        logger.info(f"\n\nProcessing: {index_title} with {text_file_path}\n\n")
        if not isinstance(index_title, str) or not isinstance(text_file_path, str):
            logger.warning(f"\nSkipping row {i} due to missing data.\n")
            continue
        upload_texts(site, index_title, text_file_path)


if __name__ == "__main__":
    """
    This script uploads texts from a CSV file to Wikisource.
    Note -
    * Uncomment the download_links_and_make_csv() line to download
    links and make CSV after running this script comment it out.
    * Before executing download_links_and_make_csv(), you can comment out the batch_upload_from_csv() line.
    You can verify the work_list.csv and text directory. Then execute batch_upload_from_csv() to upload texts.
    * You can do in continuation as well but recommended is always check first
    if the work_list.csv and text directory are correct.
    """
    BASE_DIR = Path(__file__).parent.parent.parent
    sheet_id = "1vtQ_aCDN1Y9jbwmJEE48aIgPauRvheFgYF6X1xKieMo"
    creds_path = BASE_DIR / "service-account-credentials.json"
    range_rows = "སྤྱོད་འཇུག་གི་ལས་གཞི།!G3:K8"
    output_csv = BASE_DIR / "data" / "work_list.csv"
    download_dir = BASE_DIR / "data" / "text"

    download_links_and_make_csv(
        sheet_id, creds_path, range_rows, output_csv, download_dir
    )

    csv_file_path = str(output_csv)
    data_dir_path = str(download_dir)
    # batch_upload_from_csv(csv_file_path, data_dir_path)
    logger.info("\n\n✅✅✅ Done.\n\n")
