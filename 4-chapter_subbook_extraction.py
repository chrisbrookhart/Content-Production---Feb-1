#!/usr/bin/env python3
"""
chapter_subbook_extraction.py

This program processes a cleaned, tagged book text file and extracts chapters,
optionally organizing them into subbooks. It detects special markers in the text:

    <!-- SUBBOOK: SubBook Title -->
    <!-- CHAPTER: Chapter Title -->

For each chapter found, the program creates a text file with the following format:
  - The first line is the chapter title (converted to title case).
  - A blank line.
  - The chapter content.

If subbook markers are present, the program creates subdirectories (with a numerical
prefix and sanitized subbook title) and saves the chapter files there. If no subbook
tags are detected, all chapter files are saved in the output directory.

Usage example:
    python 4-chapter_subbook_extraction.py \
        --book_title "Example Book Title" \
        --book_text "/path/to/cleaned_book.txt" \
        --output_dir "/path/to/output_directory" \
        [--verbose]
"""

import os
import re
import argparse
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def title_case(text):
    """
    Convert a string to title case while preserving common words in lowercase.
    
    Example:
        "the golden bird" -> "The Golden Bird"
    """
    exceptions = {"of", "and", "the", "in", "on", "at", "to", "for", "with", "a", "an"}
    words = text.split()
    return " ".join(
        [word.capitalize() if word.lower() not in exceptions or i == 0 else word.lower()
         for i, word in enumerate(words)]
    )

def sanitize_filename(name):
    """
    Remove or replace characters that are invalid in file or directory names.
    """
    return re.sub(r'[\\/*?:"<>|]', "", name)

def get_chapter_number(chapter_dir):
    """
    Determine the next chapter number by counting existing chapter files in the directory.
    
    Returns:
        int: Next chapter number (1-based index).
    """
    existing_chapters = list(chapter_dir.glob("chapter*.txt"))
    return len(existing_chapters) + 1

def extract_chapters(book_text, output_dir):
    """
    Extract chapters (and subbooks, if present) from the book text.

    The program scans for:
      - Subbook markers: <!-- SUBBOOK: SubBook Title -->
      - Chapter markers:  <!-- CHAPTER: Chapter Title -->
      
    If a subbook marker is encountered, a new subbook folder is created (inside the output directory)
    and subsequent chapters are written there. If no subbook markers are found, chapters are saved directly
    to the output directory.

    Parameters:
        book_text (str): The complete cleaned book text.
        output_dir (Path): Directory where chapter files will be saved.
    
    Returns:
        bool: True if at least one subbook tag was detected; False otherwise.
    """
    # Ensure the output directory exists.
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Split the text into lines.
    lines = book_text.splitlines()
    
    current_subbook = None
    current_subbook_index = 0
    current_chapter = None
    chapter_lines = []
    subbook_detected = False
    
    # The directory where the current chapter file will be written.
    current_output_dir = output_dir

    def write_current_chapter(subbook_dir, chapter_title, chapter_lines):
        """
        Write the accumulated chapter content to a file in the given subbook directory.
        The file is named 'chapterX.txt' where X is the next chapter number.
        """
        if not chapter_title or not chapter_lines:
            return
        chapter_number = get_chapter_number(subbook_dir)
        filename = f"chapter{chapter_number}.txt"
        file_path = subbook_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            # Write the chapter title (title-cased), a blank line, then the content.
            f.write(title_case(chapter_title) + "\n\n")
            f.write("\n".join(chapter_lines).strip() + "\n")
        logger.info(f"Saved Chapter: '{chapter_title}' as {file_path}")

    # Process each line in the text.
    for line in lines:
        stripped_line = line.strip()
        
        # Check for a subbook tag.
        subbook_match = re.match(r'<!--\s*SUBBOOK:\s*(.+?)\s*-->', stripped_line, re.IGNORECASE)
        if subbook_match:
            # If a chapter is in progress, finish it.
            if current_chapter is not None and chapter_lines:
                write_current_chapter(current_output_dir, current_chapter, chapter_lines)
                chapter_lines = []
                current_chapter = None
            
            # Record the subbook.
            subbook_title = subbook_match.group(1).strip()
            current_subbook = subbook_title
            current_subbook_index += 1
            subbook_detected = True
            # Create a subdirectory for this subbook.
            subbook_dir_name = f"{current_subbook_index}-{sanitize_filename(subbook_title)}"
            current_output_dir = output_dir / subbook_dir_name
            current_output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Detected SubBook: '{subbook_title}'. Created directory: '{current_output_dir}'")
            continue
        
        # Check for a chapter tag.
        chapter_match = re.match(r'<!--\s*CHAPTER:\s*(.+?)\s*-->', stripped_line, re.IGNORECASE)
        if chapter_match:
            # If there's an ongoing chapter, write it out.
            if current_chapter is not None and chapter_lines:
                write_current_chapter(current_output_dir, current_chapter, chapter_lines)
                chapter_lines = []
            # Start a new chapter.
            current_chapter = chapter_match.group(1).strip()
            logger.info(f"Detected Chapter: '{current_chapter}'")
            continue
        
        # Otherwise, if we're within a chapter, add the line to the current chapter content.
        if current_chapter is not None:
            chapter_lines.append(line)
    
    # Write any remaining chapter.
    if current_chapter is not None and chapter_lines:
        write_current_chapter(current_output_dir, current_chapter, chapter_lines)
    
    return subbook_detected

def main():
    parser = argparse.ArgumentParser(
        description="Extract chapters (and subbooks) from a cleaned, tagged book text file."
    )
    parser.add_argument('--book_title', type=str, required=True, help='Title of the book.')
    parser.add_argument('--book_text', type=str, required=True, help='Path to the cleaned book text file.')
    parser.add_argument('--output_dir', type=str, required=True, help='Directory where chapter files will be saved.')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging.')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    book_text_path = Path(args.book_text)
    if not book_text_path.is_file():
        logger.error(f"Book text file does not exist: {book_text_path}")
        return
    
    output_dir = Path(args.output_dir)
    
    # Read the entire book text.
    with open(book_text_path, "r", encoding="utf-8") as f:
        book_text = f.read()
    
    # Extract chapters (and subbooks) from the text.
    subbook_found = extract_chapters(book_text, output_dir)
    if not subbook_found:
        logger.info("No subbook tags detected; chapters have been saved directly in the output directory.")
    else:
        logger.info("Subbook structure detected; chapters have been organized into subbook folders.")

if __name__ == "__main__":
    main()
