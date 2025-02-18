#!/usr/bin/env python3
"""
9-verify-files.py

This script verifies that all expected JSON and audio files are present in the book folder.

Folder structure assumptions:
  - The top-level book folder (passed as --input_dir) contains the structure JSON file
    (e.g. "BOOKM_structure.json").
  - Within the book folder, there are language folders (e.g., "en-US", "es-ES", etc.).
    Each language folder is expected to contain two subfolders:
      • Content/  — containing chapter JSON files (in subfolders, e.g., by subbook and chapter)
      • Audio/    — containing audio files for the sentences, arranged in a parallel folder structure.
      
For each chapter JSON file found in the Content folder, the script loads the JSON and, for each sentence,
reads the "audioFile" field. It then computes the expected audio file path (by replacing the Content folder
with the Audio folder in the relative path) and checks that the file exists.

Output:
  - If any expected file (structure JSON, chapter JSON, or audio file) is missing, the script reports it.
  - If nothing is missing, the script prints "All expected files found."
  
Usage example:
    python 10-verify-files.py --input_dir "/path/to/The_Book_of_Mormon" [--verbose]
"""

import os
import re
import json
import argparse
import logging
from pathlib import Path
from jsonschema import validate, ValidationError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# --- JSON Schemas (as defined in previous steps) ---
structure_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Book Structure Schema",
    "type": "object",
    "properties": {
        "bookID": {"type": "string", "format": "uuid"},
        "bookTitle": {"type": "string"},
        "author": {"type": "string"},
        "languages": {
            "type": "array",
            "items": {"type": "string", "pattern": "^[a-z]{2}-[A-Z]{2}$"},
            "minItems": 1
        },
        "bookDescription": {"type": ["string", "null"]},
        "coverImageName": {"type": "string"},
        "bookCode": {"type": "string", "minLength": 1},
        "defaultPlaybackOrder": {
            "type": "array",
            "items": {"type": "string", "pattern": "^[a-z]{2}-[A-Z]{2}$"}
        },
        "subBooks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subBookID": {"type": "string", "format": "uuid"},
                    "subBookNumber": {"type": "integer", "minimum": 1},
                    "subBookTitle": {"type": "string"},
                    "chapters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "chapterID": {"type": "string", "format": "uuid"},
                                "chapterNumber": {"type": "integer", "minimum": 0},
                                "chapterTitle": {"type": "string"},
                                "totalParagraphs": {"type": "integer", "minimum": 0},
                                "totalSentences": {"type": "integer", "minimum": 0},
                                "contentReferences": {
                                    "type": "object",
                                    "patternProperties": {
                                        "^[a-z]{2}-[A-Z]{2}$": {"type": "string"}
                                    },
                                    "additionalProperties": False
                                }
                            },
                            "required": ["chapterID", "chapterNumber", "chapterTitle", "totalParagraphs", "totalSentences", "contentReferences"],
                            "additionalProperties": False
                        }
                    }
                },
                "required": ["subBookID", "subBookNumber", "subBookTitle", "chapters"],
                "additionalProperties": False
            }
        }
    },
    "required": ["bookID", "bookTitle", "author", "languages", "coverImageName", "bookCode", "defaultPlaybackOrder"],
    "oneOf": [
        {
            "required": ["subBooks"],
            "properties": {
                "subBooks": {"type": "array", "minItems": 1}
            }
        },
        {
            "required": ["chapters"],
            "properties": {
                "chapters": {"type": "array", "minItems": 1}
            }
        }
    ],
    "additionalProperties": False
}

chapter_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Chapter Schema",
    "type": "object",
    "properties": {
        "chapterID": {"type": "string", "format": "uuid"},
        "language": {"type": "string", "pattern": "^[a-z]{2}-[A-Z]{2}$"},
        "chapterNumber": {"type": "integer", "minimum": 0},
        "chapterTitle": {"type": "string"},
        "paragraphs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "paragraphID": {"type": "string", "format": "uuid"},
                    "paragraphIndex": {"type": "integer", "minimum": 1},
                    "sentences": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sentenceID": {"type": "string", "format": "uuid"},
                                "sentenceIndex": {"type": "integer", "minimum": 1},
                                "globalSentenceIndex": {"type": "integer", "minimum": 1},
                                "reference": {"type": "string"},
                                "text": {"type": "string"},
                                "audioFile": {"type": "string"}
                            },
                            "required": ["sentenceID", "sentenceIndex", "globalSentenceIndex", "reference", "text", "audioFile"],
                            "additionalProperties": False
                        }
                    }
                },
                "required": ["paragraphID", "paragraphIndex", "sentences"],
                "additionalProperties": False
            }
        }
    },
    "required": ["chapterID", "language", "chapterNumber", "chapterTitle", "paragraphs"],
    "additionalProperties": False
}

def validate_json_file(json_file: Path, schema: dict) -> bool:
    """
    Validate a JSON file against the given schema.
    
    Parameters:
      json_file (Path): Path to the JSON file.
      schema (dict): The JSON schema to validate against.
    
    Returns:
      bool: True if valid, False otherwise.
    """
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        validate(instance=data, schema=schema)
        logger.info(f"Validation successful for {json_file}")
        return True
    except Exception as e:
        logger.error(f"Validation error in {json_file}: {e}")
        return False

def verify_files(book_dir: Path):
    """
    Verify that all expected JSON and audio files are present in the book folder.

    Checks:
      1. That a structure JSON file exists in the top-level book folder (any file with "structure" in its name).
      2. For each language folder (e.g., "en-US", "es-ES", etc.):
         - That both "Content" and "Audio" subfolders exist.
         - Recursively, for each chapter JSON file in Content:
              • That the chapter JSON file exists.
              • For each sentence in the JSON, that the audio file (as specified in the "audioFile" field)
                exists in the corresponding location under the Audio folder.
    Reports missing files. If nothing is missing, prints "All expected files found."
    """
    missing_files = []

    # Check for structure JSON in the top-level folder.
    structure_files = list(book_dir.glob("*structure*.json"))
    if not structure_files:
        missing_files.append("Structure JSON file (e.g., 'structure.json' or '*structure*.json') is missing in the top-level folder.")

    # Process each language folder.
    for lang_folder in book_dir.iterdir():
        if not lang_folder.is_dir():
            continue
        if not re.match(r'^[a-z]{2}-[A-Z]{2}$', lang_folder.name):
            continue

        content_dir = lang_folder / "Content"
        audio_dir = lang_folder / "Audio"

        if not content_dir.exists() or not content_dir.is_dir():
            missing_files.append(f"Content folder is missing in language folder '{lang_folder.name}'.")
            continue
        if not audio_dir.exists() or not audio_dir.is_dir():
            missing_files.append(f"Audio folder is missing in language folder '{lang_folder.name}'.")
            continue

        # Recursively check chapter JSON files in Content.
        chapter_files = list(content_dir.rglob("*.json"))
        for chap_file in chapter_files:
            if not chap_file.exists():
                missing_files.append(f"Chapter JSON file missing: {chap_file}")
            else:
                # Load chapter JSON and check audio files for each sentence.
                try:
                    with open(chap_file, "r", encoding="utf-8") as f:
                        chapter = json.load(f)
                except Exception as e:
                    missing_files.append(f"Error reading JSON file {chap_file}: {e}")
                    continue

                # Determine the relative path of the chapter file with respect to the Content folder.
                try:
                    rel_path = chap_file.relative_to(content_dir)
                except Exception as e:
                    missing_files.append(f"Error computing relative path for {chap_file}: {e}")
                    continue

                # The corresponding audio folder for this chapter should be under Audio with the same relative folder.
                expected_audio_dir = audio_dir / rel_path.parent
                for para in chapter.get("paragraphs", []):
                    for sentence in para.get("sentences", []):
                        audio_filename = sentence.get("audioFile", "")
                        if not audio_filename:
                            missing_files.append(f"Missing 'audioFile' field in sentence {sentence.get('sentenceID', 'UnknownID')} in {chap_file}")
                            continue
                        expected_audio_file = expected_audio_dir / audio_filename
                        if not expected_audio_file.exists():
                            missing_files.append(f"Missing audio file: {expected_audio_file}")
    
    if missing_files:
        logger.error("Missing files detected:")
        for file in missing_files:
            logger.error(file)
    else:
        logger.info("All expected files found.")

def main():
    parser = argparse.ArgumentParser(
        description="Verify that all expected structure, chapter JSON, and audio files are present in the book folder."
    )
    parser.add_argument('--input_dir', type=str, required=True,
                        help='Top-level book folder (e.g., "/path/to/The_Book_of_Mormon").')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging.')
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    book_dir = Path(args.input_dir)
    if not book_dir.exists() or not book_dir.is_dir():
        logger.error(f"Input directory '{book_dir}' does not exist or is not a directory.")
        return

    verify_files(book_dir)

if __name__ == "__main__":
    main()
