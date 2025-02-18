#!/usr/bin/env python3
"""
assemble_structure_json.py

Stage 5: Structure JSON Assembly

This script scans the output folder produced by the chapter extraction stage and
produces a unified structure JSON file for the book.

The unified structure JSON contains:
  - Book metadata (bookID, bookTitle, author, languages, bookDescription, coverImageName, bookCode, defaultPlaybackOrder)
  - A table of contents organized as follows:
      • Every book is assumed to have subbooks. The "subBooks" array is built.
          Each subBook includes:
              - subBookID (generated UUID)
              - subBookNumber (extracted from the folder name)
              - subBookTitle (the remainder of the folder name)
              - chapters: a list of chapter metadata objects.
                Each chapter object includes:
                  - chapterID (generated UUID)
                  - chapterNumber (inferred from the chapter JSON filename)
                  - chapterTitle (extracted from the first line of the chapter file)
                  - totalParagraphs (computed by counting paragraphs in the chapter JSON)
                  - totalSentences (computed by summing the sentences in all paragraphs)
                  - contentReferences: a dictionary mapping each language code to the expected filename
                    for that chapter’s content JSON file. Filenames are generated as:
                      {book_code}_S{subbook_number}_C{chapter_number}_{language}.json

The program accepts an output directory parameter (--output_dir) where the unified structure JSON file will be saved.
The actual filename is determined by convention using the book code (e.g., "BOOKM_structure.json").


Usage Notes for assemble_structure_json.py:

- The input directory (--input_dir) should point to the native language’s Content folder.
  For example, if your book folder is "The_Book_ofMormon" and your native language is "en-US",
  the input directory should be:
      /path/to/The_Book_ofMormon/en-US/Content
  This folder should contain subfolders for each subbook (or "1-Default" if the book is flat), 
  with each subbook folder containing chapter folders (e.g., "Chapter1", "Chapter2", etc.) 
  that hold the chapter JSON files.

- The output directory (--output_dir) should be the location where you want the unified 
  structure JSON to be saved. Typically, you could choose the top-level book folder. For example:
      /path/to/The_Book_ofMormon
  The script will then write the structure JSON file (e.g., "BOOKM_structure.json") into that folder.

Usage example:
    python 6-assemble_structure_json.py \
        --book_title "The Book of Mormon" \
        --author "Translated by Joseph Smith" \
        --languages "en-US,es-ES,fr-FR" \
        --book_code "BOOKM" \
        --cover_image_name "TheBookOfMormon.png" \
        --book_description "A record of the Nephites and Lamanites." \
        --default_playback_order "en-US,es-ES,fr-FR" \
        --input_dir "/path/to/The_Book_ofMormon/en-US/Content" \
        --output_dir "/path/to/The_Book_ofMormon" \
        [--verbose]
"""

import re
import json
import uuid
import argparse
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def sanitize_filename(name):
    """Remove or replace characters that are invalid in file or directory names."""
    return re.sub(r'[\\/*?:"<>|]', "", name)

def extract_chapter_metadata(chapter_file: Path, book_code: str) -> dict:
    """
    Extract chapter metadata from a chapter JSON file.
    Assumes that the chapter JSON file (produced by the sentence parser stage) contains a "chapterTitle" field
    and a "paragraphs" array.
    
    It infers the chapter number from the filename using the new naming convention:
      {book_code}_S{subbook_num}_C{chapter_number}_{language}.json
    
    Returns a dictionary with:
      - chapterID: a new UUID,
      - chapterNumber: inferred from the filename (defaulting to 0 if not found),
      - chapterTitle: the title (converted to title case),
      - totalParagraphs: number of paragraphs (length of the "paragraphs" array),
      - totalSentences: computed by summing the lengths of the "sentences" arrays in each paragraph,
      - contentReferences: an empty dictionary to be filled later.
    """
    try:
        with open(chapter_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        chapter_title = data.get("chapterTitle", "").strip()
        formatted_title = chapter_title.title()
        paragraphs = data.get("paragraphs", [])
        total_paragraphs = len(paragraphs)
        total_sentences = sum(len(para.get("sentences", [])) for para in paragraphs)
        # Use the new naming convention to extract the chapter number.
        # Expected pattern: {book_code}_S\d+_C(\d+)_.*\.json$
        pattern = re.compile(rf"^{re.escape(book_code)}_S\d+_C(\d+)_.*\.json$", re.IGNORECASE)
        match = pattern.search(chapter_file.name)
        chapter_number = int(match.group(1)) if match else 0
        
        return {
            "chapterID": str(uuid.uuid4()),
            "chapterNumber": chapter_number,
            "chapterTitle": formatted_title,
            "totalParagraphs": total_paragraphs,
            "totalSentences": total_sentences,
            "contentReferences": {}  # To be populated for each language.
        }
    except Exception as e:
        logger.error(f"Error processing chapter file {chapter_file}: {e}")
        return None

def assemble_subbook(subbook_dir: Path, languages: list, book_code: str) -> dict:
    """
    Assemble metadata for a subbook by scanning a subdirectory containing chapter JSON files.
    
    Expects that the subbook folder name starts with a numeric prefix followed by a dash (e.g., "1-Introduction").
    
    Returns a dictionary with:
      - subBookID: generated UUID,
      - subBookNumber: extracted numeric prefix,
      - subBookTitle: the remainder of the folder name,
      - chapters: a list of chapter metadata dictionaries.
      
    The contentReferences for each chapter are built using the naming convention:
      {book_code}_S{subbook_number}_C{chapter_number}_{language}.json
    """
    subbook_name = subbook_dir.name
    match = re.match(r'^(\d+)-(.+)$', subbook_name)
    if match:
        subbook_number = int(match.group(1))
        subbook_title = match.group(2).strip()
    else:
        subbook_number = 1
        subbook_title = "Default"
    
    subbook = {
        "subBookID": str(uuid.uuid4()),
        "subBookNumber": subbook_number,
        "subBookTitle": subbook_title,
        "chapters": []
    }
    
    # Search recursively for chapter JSON files in the subbook folder.
    # Use a pattern that matches our new naming convention.
    pattern = re.compile(rf"^{re.escape(book_code)}_S\d+_C\d+_.*\.json$", re.IGNORECASE)
    chapter_files = sorted([f for f in subbook_dir.rglob("*") if f.is_file() and pattern.match(f.name)])
    for chapter_file in chapter_files:
        chapter_meta = extract_chapter_metadata(chapter_file, book_code)
        if chapter_meta:
            for lang in languages:
                chapter_meta["contentReferences"][lang] = f"{book_code}_S{subbook_number}_C{chapter_meta['chapterNumber']}_{lang}.json"
            subbook["chapters"].append(chapter_meta)
    subbook["chapters"].sort(key=lambda c: c["chapterNumber"])
    return subbook

def assemble_flat_chapters(input_dir: Path, languages: list, book_code: str) -> list:
    """
    Assemble metadata for a non-hierarchical book (i.e., no subbook folders) by scanning chapter JSON files.
    
    Returns a list of chapter metadata dictionaries. For a flat book, we assume a default subbook number of 1.
    The contentReferences for each chapter are built using the naming convention:
      {book_code}_S1_C{chapter_number}_{language}.json
    """
    chapters = []
    pattern = re.compile(rf"^{re.escape(book_code)}_S\d+_C\d+_.*\.json$", re.IGNORECASE)
    chapter_files = sorted([f for f in input_dir.glob("*") if f.is_file() and pattern.match(f.name)])
    for chapter_file in chapter_files:
        chapter_meta = extract_chapter_metadata(chapter_file, book_code)
        if chapter_meta:
            for lang in languages:
                chapter_meta["contentReferences"][lang] = f"{book_code}_S1_C{chapter_meta['chapterNumber']}_{lang}.json"
            chapters.append(chapter_meta)
    chapters.sort(key=lambda c: c["chapterNumber"])
    return chapters

def assemble_structure_json(book_metadata: dict, input_dir: Path, languages: list, book_code: str) -> dict:
    """
    Assemble the unified structure JSON for the book.

    Parameters:
      - book_metadata: dictionary containing book-level metadata (title, author, description, cover image, book code, default playback order).
      - input_dir: folder containing chapter JSON files and subbook folders.
      - languages: list of language codes available for the book.
      - book_code: the book code, used for constructing contentReferences filenames.

    Returns:
      dict: The unified structure JSON.
    """
    structure = {
        "bookID": str(uuid.uuid4()),
        "bookTitle": book_metadata.get("bookTitle", ""),
        "author": book_metadata.get("author", ""),
        "languages": languages,
        "bookDescription": book_metadata.get("bookDescription", ""),
        "coverImageName": book_metadata.get("coverImageName", ""),
        "bookCode": book_metadata.get("bookCode", ""),
        "defaultPlaybackOrder": book_metadata.get("defaultPlaybackOrder", languages)
    }
    
    # Look for subbook folders (names starting with a numeric prefix).
    subbook_dirs = [d for d in input_dir.iterdir() if d.is_dir() and re.match(r'^\d+-', d.name)]
    if subbook_dirs:
        subbooks = []
        subbook_dirs = sorted(subbook_dirs, key=lambda d: int(re.match(r'^(\d+)-', d.name).group(1)))
        for subbook_dir in subbook_dirs:
            subbook = assemble_subbook(subbook_dir, languages, book_code)
            subbooks.append(subbook)
        structure["subBooks"] = subbooks
    else:
        # If no subbook folders are detected, assume a default subbook folder.
        chapters = assemble_flat_chapters(input_dir, languages, book_code)
        structure["subBooks"] = [{
            "subBookID": str(uuid.uuid4()),
            "subBookNumber": 1,
            "subBookTitle": "Default",
            "chapters": chapters
        }]
    
    return structure

def main():
    parser = argparse.ArgumentParser(
        description="Assemble a unified structure JSON for a book by scanning the chapter JSON files folder."
    )
    parser.add_argument('--book_title', type=str, required=True, help='Title of the book.')
    parser.add_argument('--author', type=str, required=True, help='Author of the book.')
    parser.add_argument('--languages', type=str, required=True,
                        help='Comma-separated list of language codes (e.g., "en-US,es-ES,fr-FR").')
    parser.add_argument('--book_code', type=str, required=True, help='Unique book code (e.g., "BOOKM").')
    parser.add_argument('--cover_image_name', type=str, required=True, help='Cover image filename (e.g., "cover.png").')
    parser.add_argument('--book_description', type=str, default="", help='Description of the book.')
    parser.add_argument('--default_playback_order', type=str, default="",
                        help='Comma-separated list of language codes for default playback order. If not provided, uses the languages list.')
    parser.add_argument('--input_dir', type=str, required=True,
                        help='Path to the folder containing chapter JSON files (and subbook folders, if any).')
    parser.add_argument('--output_dir', type=str, required=True,
                        help='Directory where the unified structure JSON file will be saved.')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging.')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]
    if args.default_playback_order:
        default_playback_order = [lang.strip() for lang in args.default_playback_order.split(",") if lang.strip()]
    else:
        default_playback_order = languages
    
    book_metadata = {
        "bookTitle": args.book_title,
        "author": args.author,
        "bookDescription": args.book_description,
        "coverImageName": args.cover_image_name,
        "bookCode": args.book_code,
        "defaultPlaybackOrder": default_playback_order
    }
    
    input_dir = Path(args.input_dir)
    if not input_dir.exists() or not input_dir.is_dir():
        logger.error(f"Input directory '{input_dir}' does not exist or is not a directory.")
        return
    
    structure = assemble_structure_json(book_metadata, input_dir, languages, args.book_code)
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_filename = f"{args.book_code}_structure.json"
    output_file_path = output_dir / output_filename
    
    try:
        with open(output_file_path, "w", encoding="utf-8") as out_file:
            json.dump(structure, out_file, indent=4, ensure_ascii=False)
        logger.info(f"Unified structure JSON successfully saved to '{output_file_path}'.")
    except Exception as e:
        logger.error(f"Error writing structure JSON: {e}")

if __name__ == "__main__":
    main()
