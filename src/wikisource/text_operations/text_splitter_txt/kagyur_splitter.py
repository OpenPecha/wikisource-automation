import re
from pathlib import Path
from typing import List, Optional, Tuple

# Section starters like {D1}, {D1a}, {D4}, {D5}, etc.
SECTION_TOKEN_RE = re.compile(r"\{D(\d+)([a-z])?\}")
# Tokens like {D1-1}, {D4-3} to strip entirely
SECTION_DASH_TOKEN_RE = re.compile(r"\{D\d+-\d+\}")
# Page markers to remove: [1a.1], [2b.4] (any letter then .digits)
BRACKET_WITH_DOT_RE = re.compile(r"\[\d+[a-z]\.\d+\]")
# Page markers to replace with Page: N (no dot)
BRACKET_PAGE_RE = re.compile(r"\[\d+[a-z]\]")
# Text variants like {བཅྭ་,བཅོ་} - take the right side (after comma)
TEXT_VARIANT_RE = re.compile(r"\{([^,}]+),([^}]+)\}")


class LineByLineProcessor:
    def __init__(self, input_dir: Path, output_dir: Path, content_threshold: int = 50):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.content_threshold = (
            content_threshold  # Minimum meaningful lines to trigger split
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process_line(self, line: str) -> Tuple[str, Optional[str], bool]:
        """
        Process a single line and return:
        - processed_line: the cleaned line
        - section_token: if a section token is found (e.g., "D1", "D1a")
        - has_page_marker: if line contains a page marker
        """
        # Handle text variants like {བཅྭ་,བཅོ་} - take the right side (after comma)
        line = TEXT_VARIANT_RE.sub(r"\2", line)

        # Remove dotted page markers entirely
        line = BRACKET_WITH_DOT_RE.sub("", line)

        # Remove section dash tokens
        line = SECTION_DASH_TOKEN_RE.sub("", line)

        # Check for section tokens
        section_match = SECTION_TOKEN_RE.search(line)
        section_token = None
        if section_match:
            sect_num = section_match.group(1)
            sect_letter = section_match.group(2) or ""
            section_token = f"D{sect_num}{sect_letter}"
            # Remove the section token from the line
            line = SECTION_TOKEN_RE.sub("", line)

        # Check if line has page markers
        has_page_marker = bool(BRACKET_PAGE_RE.search(line))

        return line, section_token, has_page_marker

    def is_meaningful_line(self, line: str) -> bool:
        """
        Check if a line contains meaningful content (not just page markers or empty)
        """
        # Remove page markers and whitespace to check for actual content
        cleaned = BRACKET_PAGE_RE.sub("", line).strip()
        cleaned = BRACKET_WITH_DOT_RE.sub("", cleaned).strip()

        # Line is meaningful if it has non-whitespace content after cleaning
        return len(cleaned) > 0

    def count_meaningful_lines_before_section(
        self, lines: List[str]
    ) -> Tuple[int, int]:
        """
        Count meaningful lines before the first section token.
        Returns (meaningful_count, first_section_line_index)
        """
        meaningful_count = 0
        first_section_line = -1

        for i, line in enumerate(lines):
            # Check if this line has a section token
            if SECTION_TOKEN_RE.search(line):
                first_section_line = i
                break

            # Count meaningful lines
            if self.is_meaningful_line(line):
                meaningful_count += 1

        return meaningful_count, first_section_line

    def replace_page_markers(self, line: str, page_counter: int) -> Tuple[str, int]:
        """
        Replace page markers with Page: N and return updated line and new counter
        """

        def repl(match):
            nonlocal page_counter
            result = f"Page: {page_counter}"
            page_counter += 1
            return result

        processed_line = BRACKET_PAGE_RE.sub(repl, line)
        return processed_line, page_counter

    def process_file(self, input_file: Path) -> List[Path]:
        """
        Process a single input file line by line
        """
        content = input_file.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Check if we should split before the first section token
        (
            meaningful_count,
            first_section_line,
        ) = self.count_meaningful_lines_before_section(lines)
        should_split_before_first = (
            meaningful_count >= self.content_threshold and first_section_line > 0
        )

        output_files: List[Path] = []
        current_lines: List[str] = []
        current_section = "UNKNOWN"
        page_counter = 1
        last_page_marker_line: Optional[str] = None
        section_counter = 0

        for line in lines:
            processed_line, section_token, has_page_marker = self.process_line(line)

            # If we find a section token
            if section_token:
                if section_counter == 0:
                    if should_split_before_first:
                        # Split before first section token - create base file first
                        # Remove the last page marker from current file if it exists
                        if last_page_marker_line is not None and current_lines:
                            # Find and remove the last page marker line
                            for i in range(len(current_lines) - 1, -1, -1):
                                if BRACKET_PAGE_RE.search(current_lines[i]):
                                    last_page_marker_line = current_lines.pop(i)
                                    break

                        # Write base file (content before first section)
                        output_file = self.write_section_file(
                            input_file, "BASE", current_lines
                        )
                        output_files.append(output_file)

                        # Start new file for this section
                        current_section = section_token
                        current_lines = []
                        page_counter = 1

                        if last_page_marker_line is not None:
                            processed_marker_line = BRACKET_PAGE_RE.sub(
                                "Page: 1", last_page_marker_line
                            )
                            current_lines.append(processed_marker_line)
                            page_counter = 2
                            last_page_marker_line = None

                        section_counter += 1
                    else:
                        current_section = section_token
                        section_counter += 1
                else:
                    if last_page_marker_line is not None and current_lines:
                        # Find and remove the last page marker line
                        for i in range(len(current_lines) - 1, -1, -1):
                            if BRACKET_PAGE_RE.search(current_lines[i]):
                                last_page_marker_line = current_lines.pop(i)
                                break

                    output_file = self.write_section_file(
                        input_file, current_section, current_lines
                    )
                    output_files.append(output_file)

                    current_section = section_token
                    current_lines = []
                    page_counter = 1
                    section_counter = 0

                    if last_page_marker_line is not None:
                        processed_marker_line = BRACKET_PAGE_RE.sub(
                            "Page: 1", last_page_marker_line
                        )
                        current_lines.append(processed_marker_line)
                        page_counter = 2
                        last_page_marker_line = None

                    section_counter += 1

            if has_page_marker:
                processed_line, page_counter = self.replace_page_markers(
                    processed_line, page_counter
                )
                # Keep track of last page marker for potential moving only if section_counter > 0
                if section_counter > 0:
                    last_page_marker_line = line

            current_lines.append(processed_line)

        if current_lines:
            output_file = self.write_section_file(
                input_file, current_section, current_lines
            )
            output_files.append(output_file)

        return output_files

    def write_section_file(
        self, input_file: Path, section: str, lines: List[str]
    ) -> Path:
        """
        Write a section to an output file
        """
        if section == "UNKNOWN":
            output_name = f"{input_file.stem}.txt"
        elif section == "BASE":
            output_name = f"{input_file.stem}.txt"
        else:
            output_name = f"{input_file.stem}_{section}.txt"

        output_path = self.output_dir / output_name
        content = "\n".join(lines)
        output_path.write_text(content, encoding="utf-8")
        return output_path

    def process_all_files(self) -> None:
        """
        Process all txt files in the input directory
        """
        txt_files = sorted(f for f in self.input_dir.glob("*.txt") if f.is_file())

        if not txt_files:
            print(f"No .txt files found in {self.input_dir}")
            return

        total_outputs = 0
        print(f"Found {len(txt_files)} input files.")

        for txt_file in txt_files:
            output_files = self.process_file(txt_file)
            total_outputs += len(output_files)
            print(f"- {txt_file.name} -> {len(output_files)} section file(s)")

        print(
            f"\nDone. Wrote {total_outputs} output file(s) to: {self.output_dir.resolve()}"
        )


def main():
    script_dir = Path(__file__).parent.parent.parent
    input_dir = script_dir / "data_text_operations" / "kagyur_text"
    output_dir = script_dir / "data_text_operations" / "kagyur_output"

    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Input dir not found or not a directory: {input_dir}")

    processor = LineByLineProcessor(input_dir, output_dir)
    processor.process_all_files()


if __name__ == "__main__":
    main()
