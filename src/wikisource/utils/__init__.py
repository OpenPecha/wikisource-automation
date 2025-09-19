"""
Utility functions for wikisource automation.
"""
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Union


def write_json(data: Union[dict, list], output_path: Union[str, Path]) -> None:
    """
    Write data to a JSON file with proper encoding.

    Args:
        data: Dictionary or list to write to JSON
        output_path: Path where to save the JSON file
    """
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(file_path: Union[str, Path]) -> Union[dict, list]:
    """
    Read data from a JSON file.

    Args:
        file_path: Path to the JSON file

    Returns:
        Parsed JSON data
    """
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    return data


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing or replacing invalid characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for filesystem
    """
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    # Remove leading/trailing spaces and dots
    filename = filename.strip(" .")
    # Limit length
    if len(filename) > 255:
        filename = filename[:255]
    return filename


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists, create it if it doesn't.

    Args:
        path: Directory path

    Returns:
        Path object of the directory
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_url(url: str) -> bool:
    """
    Validate if a string is a valid URL.

    Args:
        url: URL string to validate

    Returns:
        True if valid URL, False otherwise
    """
    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+"  # domain...
        r"(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # host...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return bool(url_pattern.match(url))


def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace and unwanted characters.

    Args:
        text: Text to clean

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text)
    # Remove leading/trailing whitespace
    text = text.strip()
    return text


def format_wikisource_page_title(title: str) -> str:
    """
    Format a title for Wikisource page naming conventions.

    Args:
        title: Original title

    Returns:
        Formatted title suitable for Wikisource
    """
    # Replace spaces with underscores (Wikisource convention)
    title = title.replace(" ", "_")
    # Remove invalid characters for page titles
    title = re.sub(r"[#<>\[\]|{}]", "", title)
    return title


def get_file_extension(filename: str) -> str:
    """
    Get file extension from filename.

    Args:
        filename: Name of the file

    Returns:
        File extension (without dot)
    """
    return Path(filename).suffix.lstrip(".")


def is_text_file(filename: str) -> bool:
    """
    Check if a file is a text file based on its extension.

    Args:
        filename: Name of the file

    Returns:
        True if it's a text file, False otherwise
    """
    text_extensions = {"txt", "md", "rst", "csv", "json", "xml", "html"}
    extension = get_file_extension(filename).lower()
    return extension in text_extensions
