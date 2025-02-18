#!/usr/bin/env python3
"""
final_json_validation.py

This script validates the JSON files produced by the content pipeline.
It validates both the book's structure JSON and all chapter JSON files.

Usage example:
    python final_json_validation.py --input_dir "/path/to/The_Book_of_Mormon" [--verbose]

Directory assumptions:
  - The top-level book folder (provided as --input_dir) contains the structure JSON,
    e.g. "structure.json" or "*structure*.json" (such as "BOOKM_structure.json").
  - Within the book folder, there are language folders (e.g., "en-US", "es-ES", etc.).
    Inside each language folder, a "Content" folder holds the chapter JSON files.
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

# --- JSON Schemas ---
# Schema for the unified structure JSON
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

# Schema for chapter JSON files
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

def validate_all_json_files(book_dir: Path):
    """
    Recursively search the book folder for the structure JSON and chapter JSON files,
    and validate them against their respective schemas.
    
    Assumptions:
      - The structure JSON is located in the top-level book folder and is named with "structure" in its filename.
      - Chapter JSON files are located under {book_dir}/{language}/Content/
    """
    # Look for structure JSON files (match any filename containing "structure" case-insensitively)
    structure_candidates = list(book_dir.glob("*structure*.json"))
    if not structure_candidates:
        logger.error(f"No structure JSON file found in {book_dir}")
    else:
        for struct_file in structure_candidates:
            logger.info(f"Validating structure JSON: {struct_file}")
            validate_json_file(struct_file, structure_schema)
    
    # Now, find chapter JSON files under language folders.
    # We assume language folders are named like "en-US", "es-ES", etc.
    for lang_dir in book_dir.iterdir():
        if not lang_dir.is_dir():
            continue
        if not re.match(r'^[a-z]{2}-[A-Z]{2}$', lang_dir.name):
            continue
        content_dir = lang_dir / "Content"
        if not content_dir.exists() or not content_dir.is_dir():
            logger.debug(f"No Content folder in {lang_dir}; skipping.")
            continue
        chapter_files = list(content_dir.rglob("*.json"))
        logger.info(f"Found {len(chapter_files)} chapter JSON file(s) in {content_dir}")
        for chapter_file in chapter_files:
            logger.info(f"Validating chapter JSON: {chapter_file}")
            validate_json_file(chapter_file, chapter_schema)

def main():
    parser = argparse.ArgumentParser(
        description="Validate the book structure JSON and all chapter JSON files in the book folder."
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
    
    validate_all_json_files(book_dir)

if __name__ == "__main__":
    main()
