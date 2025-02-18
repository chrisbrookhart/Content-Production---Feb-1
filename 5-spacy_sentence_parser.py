#!/usr/bin/env python3
"""
5-spaCy-sentence-parser-all.py

Stage 4 (Revised): Batch Sentence Parsing & Content JSON Production

This script processes an entire folder hierarchy containing chapter text files.
It enforces a uniform folder structure by ensuring that even for books that do not
naturally have subbook folders, a default subbook folder ("1-Default") is created.
It also maintains a continuous global sentence counter throughout the entire book.

The output structure is as follows:
  {base_output_dir}/{language}/Content/{subbook_folder}/Chapter{chapter_number}/{filename}

For example:
  The_Book_of_Mormon/
  └── en-US/
      └── Content/
          ├── 1-Introduction_and_Witnesses/
          │   ├── Chapter1/
          │   │   └── BOOKM_S1_C1_en-US.json
          │   └── Chapter2/
          │       └── BOOKM_S1_C2_en-US.json
          └── ...

Usage example:
    python 5-spacy_sentence_parser.py \
        --input_dir "/path/to/chapter_texts" \
        --language "en-US" \
        --book_code "BOOKM" \
        --output_dir "/path/to/The_Book_of_Mormon" \
        [--verbose]
"""

import os
import re
import json
import uuid
import argparse
import logging
from pathlib import Path
import spacy

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def title_case(text):
    """
    Convert text to title case while preserving common lowercase words.
    """
    exceptions = {"of", "and", "the", "in", "on", "at", "to", "for", "with", "a", "an"}
    words = text.split()
    return " ".join([word.capitalize() if word.lower() not in exceptions or i == 0 else word.lower()
                     for i, word in enumerate(words)])

def sanitize_filename(name):
    """
    Remove or replace characters that are invalid in file or directory names.
    """
    return re.sub(r'[\\/*?:"<>|]', "", name)

def create_audio_filename(sequential_index, book_code, subbook_num, chapter_num, paragraph_num, sentence_num, language):
    """
    Create an audio filename following the naming convention that includes the subbook reference.
    
    Format:
      {global_index}_{book_code}_S{subbook_num}_C{chapter_num}_P{paragraph_num}_S{sentence_num}_{language}.aac
      
    Example:
      0000001_BOOKM_S1_C1_P1_S1_en-US.aac
    """
    return f"{sequential_index:07d}_{book_code}_S{subbook_num}_C{chapter_num}_P{paragraph_num}_S{sentence_num}_{language}.aac"

def parse_paragraphs(text):
    """
    Split text into paragraphs based on one or more blank lines.
    """
    paragraphs = re.split(r'\n\s*\n', text.strip())
    return [p.strip() for p in paragraphs if p.strip()]

def parse_sentences(line, nlp):
    """
    Use spaCy to segment a line into sentences.
    If spaCy returns no sentences, treat the entire line as one sentence.
    """
    doc = nlp(line)
    sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
    return sentences if sentences else [line.strip()]

def process_chapter_file(chapter_file: Path, nlp, language: str, book_code: str, subbook_num: int, global_counter: dict) -> dict:
    """
    Process a single chapter text file and return a content JSON dictionary.
    
    The chapter file is assumed to have:
      - The first line as the chapter title.
      - The remainder as the chapter content.
    
    The function extracts paragraphs and sentences, assigns local and global sentence indices
    using the passed mutable global counter, and generates an audio filename for each sentence.
    
    Reference Handling:
      - Before any reference marker is encountered, sentences have an empty reference.
      - Once a reference marker is encountered (a line like <!-- REF: ... -->),
        that reference is applied to all subsequent sentences until a new marker is found.
      - When the chapter is complete, the reference does not carry over.
    
    Parameters:
      - chapter_file: Path to the chapter text file.
      - nlp: Loaded spaCy model.
      - language: Target language code (e.g., "en-US").
      - book_code: Book code for generating audio filenames.
      - subbook_num: The subbook number (extracted from the folder name or defaulted to 1).
      - global_counter: A mutable dictionary holding the global sentence index.
      
    Returns:
      dict: Chapter content structured according to the unified JSON schema.
    """
    logger.info(f"Processing chapter file: {chapter_file}")
    try:
        with open(chapter_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        logger.error(f"Error reading file {chapter_file}: {e}")
        return None

    if not lines:
        logger.warning(f"Chapter file '{chapter_file}' is empty.")
        return None

    chapter_title = lines[0].strip()
    formatted_title = title_case(chapter_title)
    logger.info(f"Extracted chapter title: {formatted_title}")
    
    content = ''.join(lines[1:]).strip()
    paragraphs_text = parse_paragraphs(content)
    logger.info(f"Found {len(paragraphs_text)} paragraphs in chapter '{formatted_title}'")
    
    chapter_num_match = re.search(r'chapter(\d+)\.txt$', chapter_file.name, re.IGNORECASE)
    chapter_number = int(chapter_num_match.group(1)) if chapter_num_match else 0
    
    chapter_id = str(uuid.uuid4())
    chapter_dict = {
        "chapterID": chapter_id,
        "language": language,
        "chapterNumber": chapter_number,
        "chapterTitle": formatted_title,
        "paragraphs": []
    }
    
    # Initialize reference to empty for each chapter.
    current_reference = ""
    for para_index, para_text in enumerate(paragraphs_text, start=1):
        paragraph_id = str(uuid.uuid4())
        paragraph_dict = {
            "paragraphID": paragraph_id,
            "paragraphIndex": para_index,
            "sentences": []
        }
        para_lines = para_text.splitlines()
        # Do not clear current_reference after processing a sentence;
        # once set, it persists until a new marker is encountered.
        for line in para_lines:
            line = line.strip()
            if not line:
                continue
            # Check for a reference marker.
            ref_match = re.match(r'<!--\s*REF:\s*(.+?)\s*-->', line, re.IGNORECASE)
            if ref_match:
                current_reference = ref_match.group(1).strip()
                logger.debug(f"Found reference marker: {current_reference}")
                # Do not clear current_reference; let it persist.
                continue
            sentence_texts = parse_sentences(line, nlp)
            for local_idx, sent in enumerate(sentence_texts, start=1):
                sentence_id = str(uuid.uuid4())
                audio_filename = create_audio_filename(
                    sequential_index=global_counter["value"],
                    book_code=book_code,
                    subbook_num=subbook_num,
                    chapter_num=chapter_number,
                    paragraph_num=para_index,
                    sentence_num=local_idx,
                    language=language
                )
                sentence_text = sent.strip()
                sentence_dict = {
                    "sentenceID": sentence_id,
                    "sentenceIndex": local_idx,
                    "globalSentenceIndex": global_counter["value"],
                    "reference": current_reference,  # Use the current reference (may be empty initially)
                    "text": sentence_text,
                    "audioFile": audio_filename
                }
                paragraph_dict["sentences"].append(sentence_dict)
                logger.debug(f"Added sentence {local_idx} (global {global_counter['value']}) in paragraph {para_index}")
                global_counter["value"] += 1
        # When the paragraph is finished, the current_reference remains active (it will carry over to subsequent paragraphs in the chapter).
        paragraph_dict["sentences"] and chapter_dict["paragraphs"].append(paragraph_dict)
        logger.info(f"Added paragraph {para_index} with {len(paragraph_dict['sentences'])} sentences")
    # At the end of the chapter, reset the current reference so it does not carry over.
    current_reference = ""
    logger.info(f"Finished processing chapter '{formatted_title}' with {len(chapter_dict['paragraphs'])} paragraphs")
    return chapter_dict

def get_subbook_info(chapter_file: Path, base_input_dir: Path):
    """
    Determine the subbook folder name and number from the chapter file's relative path.
    
    If the chapter file is inside a folder whose name starts with a numeric prefix (e.g., "1-Introduction and Witnesses"),
    that folder name and number are returned; otherwise, return a default ("1-Default", 1).
    """
    try:
        rel_path = chapter_file.relative_to(base_input_dir)
        parts = rel_path.parts
        if len(parts) > 1:
            subbook_folder = parts[0]
            match = re.match(r'^(\d+)-(.+)$', subbook_folder)
            if match:
                subbook_num = int(match.group(1))
                return subbook_folder, subbook_num
    except Exception as e:
        logger.debug(f"Could not determine subbook info for {chapter_file}: {e}")
    return "1-Default", 1

def process_all_chapter_files(base_input_dir: Path, nlp, language: str, book_code: str, base_output_dir: Path):
    """
    Recursively process all chapter text files under the base input directory and output the chapter JSON files
    into a hierarchical folder structure.
    
    Output structure:
      {base_output_dir}/{language}/Content/{subbook_folder}/Chapter{chapter_number}/{filename}
    
    For flat books (with no subbook folders in the input), a default subbook folder ("1-Default") is used.
    A mutable global counter is maintained so that the global sentence index is continuous.
    """
    global_counter = {"value": 1}
    
    subbook_folders = [d for d in base_input_dir.iterdir() if d.is_dir() and re.match(r'^\d+-', d.name)]
    use_default_subbook = False
    if not subbook_folders:
        logger.info("No subbook folders detected in input directory; using default subbook.")
        use_default_subbook = True
    
    chapter_files = sorted(base_input_dir.rglob("chapter*.txt"))
    logger.info(f"Found {len(chapter_files)} chapter file(s) under {base_input_dir}")
    
    for chapter_file in chapter_files:
        if use_default_subbook:
            subbook_folder = "1-Default"
            subbook_num = 1
        else:
            subbook_folder, subbook_num = get_subbook_info(chapter_file, base_input_dir)
        
        chapter_num_match = re.search(r'chapter(\d+)\.txt$', chapter_file.name, re.IGNORECASE)
        chapter_number = int(chapter_num_match.group(1)) if chapter_num_match else 0
        
        # Construct output folder:
        # {base_output_dir}/{language}/Content/{subbook_folder}/Chapter{chapter_number}
        output_subdir = base_output_dir / language / "Content" / subbook_folder / f"Chapter{chapter_number}"
        output_subdir.mkdir(parents=True, exist_ok=True)
        
        chapter_data = process_chapter_file(chapter_file, nlp, language, book_code, subbook_num, global_counter)
        if not chapter_data:
            continue
        
        # Construct output filename: {book_code}_S{subbook_num}_C{chapter_number}_{language}.json
        output_filename = f"{book_code}_S{subbook_num}_C{chapter_number}_{language}.json"
        output_file_path = output_subdir / output_filename
        
        try:
            with open(output_file_path, "w", encoding="utf-8") as json_file:
                json.dump(chapter_data, json_file, indent=4, ensure_ascii=False)
            logger.info(f"Saved content JSON for {chapter_file} as {output_file_path}")
        except Exception as e:
            logger.error(f"Error writing JSON file {output_file_path}: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Process all chapter text files to produce content JSONs in a hierarchical folder structure."
    )
    parser.add_argument('--input_dir', type=str, required=True,
                        help='Base directory containing chapter text files (and subbook folders, if any).')
    parser.add_argument('--language', type=str, required=True,
                        help='Target language code for the output JSON files (e.g., "en-US").')
    parser.add_argument('--book_code', type=str, required=True,
                        help='Book code used for naming the output files (e.g., "BOOKM").')
    parser.add_argument('--output_dir', type=str, required=True,
                        help='Base directory where the output folder structure will be created (i.e., the book-level folder).')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging.')
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    base_input_dir = Path(args.input_dir)
    base_output_dir = Path(args.output_dir)
    
    if not base_input_dir.exists() or not base_input_dir.is_dir():
        logger.error(f"Input directory '{base_input_dir}' does not exist or is not a directory.")
        return
    
    try:
        nlp = spacy.load("en_core_web_sm")
        logger.debug("Loaded spaCy model 'en_core_web_sm'")
    except Exception as e:
        logger.error(f"Error loading spaCy model: {e}")
        return
    
    process_all_chapter_files(base_input_dir, nlp, args.language, args.book_code, base_output_dir)

if __name__ == "__main__":
    main()


  





# #!/usr/bin/env python3
# """
# 5-spaCy-sentence-parser-all.py

# Stage 4 (Revised): Batch Sentence Parsing & Content JSON Production

# This script processes an entire folder hierarchy containing chapter text files.
# It enforces a uniform folder structure by ensuring that even for books that do not
# naturally have subbook folders, a default subbook folder ("1-Default") is created.
# It also maintains a continuous global sentence counter throughout the entire book.

# For each chapter text file (e.g., "chapter1.txt"), the script uses spaCy to:
#   - Split the content into paragraphs and sentences.
#   - Assign each sentence a local sentence index (within its paragraph) and a global sentence index (across the entire book).
#   - Generate an audio filename that includes the subbook number using the naming convention:
#       {global_index}_{book_code}_S{subbook_num}_C{chapter_num}_P{paragraph_num}_S{sentence_num}_{language}.aac
#   - Attach any reference markers (lines like <!-- REF: 1:1 -->) to the following sentence.

# The output is a content JSON file for each chapter (for a specific language). The output JSON
# file is named using the naming convention:
#     {book_code}_S{subbook_num}_C{chapter_num}_{language}.json
# and is placed in an output folder that mirrors the input folder structure.

# Usage example:
#     python 5-spaCy-sentence-parser-all.py \
#         --input_dir "/path/to/chapters" \
#         --language "en-US" \
#         --book_code "BOOKM" \
#         --output_dir "/path/to/output_jsons" \
#         [--verbose]
# """

# import os
# import re
# import json
# import uuid
# import argparse
# import logging
# from pathlib import Path
# import spacy

# # Configure logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
# logger = logging.getLogger(__name__)

# def title_case(text):
#     """
#     Convert text to title case while preserving common lowercase words.
#     """
#     exceptions = {"of", "and", "the", "in", "on", "at", "to", "for", "with", "a", "an"}
#     words = text.split()
#     return " ".join(
#         [word.capitalize() if word.lower() not in exceptions or i == 0 else word.lower()
#          for i, word in enumerate(words)]
#     )

# def sanitize_filename(name):
#     """
#     Remove or replace characters that are invalid in file or directory names.
#     """
#     return re.sub(r'[\\/*?:"<>|]', "", name)

# def create_audio_filename(sequential_index, book_code, subbook_num, chapter_num, paragraph_num, sentence_num, language):
#     """
#     Create an audio filename following the naming convention that includes the subbook reference.
    
#     Format:
#       {global_index}_{book_code}_S{subbook_num}_C{chapter_num}_P{paragraph_num}_S{sentence_num}_{language}.aac
      
#     Example:
#       0000001_BOOKM_S1_C1_P1_S1_en-US.aac
#     """
#     return f"{sequential_index:07d}_{book_code}_S{subbook_num}_C{chapter_num}_P{paragraph_num}_S{sentence_num}_{language}.aac"

# def parse_paragraphs(text):
#     """
#     Split text into paragraphs based on one or more blank lines.
#     """
#     paragraphs = re.split(r'\n\s*\n', text.strip())
#     return [p.strip() for p in paragraphs if p.strip()]

# def parse_sentences(line, nlp):
#     """
#     Use spaCy to segment a line into sentences.
#     If spaCy returns no sentences, treat the entire line as one sentence.
#     """
#     doc = nlp(line)
#     sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
#     return sentences if sentences else [line.strip()]

# def process_chapter_file(chapter_file: Path, nlp, language: str, book_code: str, subbook_num: int, global_counter: dict) -> dict:
#     """
#     Process a single chapter text file and return a content JSON dictionary.
    
#     The chapter file is assumed to have:
#       - The first line as the chapter title.
#       - The remainder as the chapter content.
    
#     The function extracts paragraphs and sentences, assigns local and global sentence indices
#     using the passed mutable global counter, and generates an audio filename for each sentence.
    
#     Parameters:
#       - chapter_file: Path to the chapter text file.
#       - nlp: Loaded spaCy model.
#       - language: Target language code (e.g., "en-US").
#       - book_code: Book code for generating audio filenames.
#       - subbook_num: The subbook number (from the folder name or defaulted to 1).
#       - global_counter: A mutable dictionary holding the global sentence index.
      
#     Returns:
#       dict: Chapter content structured according to the unified JSON schema.
#     """
#     logger.info(f"Processing chapter file: {chapter_file}")
#     with open(chapter_file, "r", encoding="utf-8") as f:
#         lines = f.readlines()
    
#     if not lines:
#         logger.warning(f"Chapter file '{chapter_file}' is empty.")
#         return None

#     chapter_title = lines[0].strip()
#     formatted_title = title_case(chapter_title)
#     logger.info(f"Extracted chapter title: {formatted_title}")
    
#     content = ''.join(lines[1:]).strip()
#     paragraphs_text = parse_paragraphs(content)
#     logger.info(f"Found {len(paragraphs_text)} paragraphs in chapter '{formatted_title}'")
    
#     # Infer chapter number from filename, e.g. "chapter1.txt"
#     chapter_num_match = re.search(r'chapter(\d+)\.txt$', chapter_file.name, re.IGNORECASE)
#     chapter_number = int(chapter_num_match.group(1)) if chapter_num_match else 0
    
#     chapter_id = str(uuid.uuid4())
#     chapter_dict = {
#         "chapterID": chapter_id,
#         "language": language,
#         "chapterNumber": chapter_number,
#         "chapterTitle": formatted_title,
#         "paragraphs": []
#     }
    
#     # Process paragraphs and sentences without resetting the global counter.
#     for para_index, para_text in enumerate(paragraphs_text, start=1):
#         paragraph_id = str(uuid.uuid4())
#         paragraph_dict = {
#             "paragraphID": paragraph_id,
#             "paragraphIndex": para_index,
#             "sentences": []
#         }
#         para_lines = para_text.splitlines()
#         current_reference = ""
#         for line in para_lines:
#             line = line.strip()
#             if not line:
#                 continue
#             ref_match = re.match(r'<!--\s*REF:\s*(.+?)\s*-->', line, re.IGNORECASE)
#             if ref_match:
#                 current_reference = ref_match.group(1).strip()
#                 logger.debug(f"Found reference: {current_reference}")
#                 continue
#             sentence_texts = parse_sentences(line, nlp)
#             for local_idx, sent in enumerate(sentence_texts, start=1):
#                 sentence_id = str(uuid.uuid4())
#                 audio_filename = create_audio_filename(
#                     sequential_index=global_counter["value"],
#                     book_code=book_code,
#                     subbook_num=subbook_num,
#                     chapter_num=chapter_number,
#                     paragraph_num=para_index,
#                     sentence_num=local_idx,
#                     language=language
#                 )
#                 sentence_dict = {
#                     "sentenceID": sentence_id,
#                     "sentenceIndex": local_idx,
#                     "globalSentenceIndex": global_counter["value"],
#                     "reference": current_reference,
#                     "text": sent,
#                     "audioFile": audio_filename
#                 }
#                 paragraph_dict["sentences"].append(sentence_dict)
#                 logger.debug(f"Added sentence {local_idx} (global {global_counter['value']}) in paragraph {para_index}")
#                 global_counter["value"] += 1
#                 current_reference = ""
#         if paragraph_dict["sentences"]:
#             chapter_dict["paragraphs"].append(paragraph_dict)
#             logger.info(f"Added paragraph {para_index} with {len(paragraph_dict['sentences'])} sentences")
#         else:
#             logger.info(f"Skipping empty paragraph {para_index}")
    
#     logger.info(f"Finished processing chapter '{formatted_title}' with {len(chapter_dict['paragraphs'])} paragraphs")
#     return chapter_dict

# def get_subbook_number(chapter_file: Path, base_input_dir: Path) -> int:
#     """
#     Determine the subbook number for a chapter file based on its relative location.
#     If the chapter file is inside a subdirectory whose name starts with a numeric prefix,
#     that number is returned; otherwise, return 1.
#     """
#     try:
#         rel_parent = chapter_file.relative_to(base_input_dir).parent
#         if rel_parent != Path('.'):
#             subbook_dir_name = rel_parent.parts[0]
#             match = re.match(r'^(\d+)-', subbook_dir_name)
#             if match:
#                 return int(match.group(1))
#     except Exception as e:
#         logger.debug(f"Could not determine subbook number for {chapter_file}: {e}")
#     return 1

# def process_all_chapter_files(base_input_dir: Path, nlp, language: str, book_code: str, base_output_dir: Path):
#     """
#     Recursively process all chapter text files under the base input directory to produce content JSONs.
    
#     The folder structure is preserved in the output. For each chapter text file found, a content JSON file is produced.
#     If the input directory does not contain any subbook folders, a default subbook folder ("1-Default") is created in the output.
    
#     The output filename is constructed using the complete naming convention:
#       {book_code}_S{subbook_num}_C{chapter_number}_{language}.json
      
#     A mutable global counter is maintained so that the global sentence index is continuous throughout the entire book.
#     """
#     global_counter = {"value": 1}
    
#     # Determine if the input directory has any subbook folders.
#     subbook_folders = [d for d in base_input_dir.iterdir() if d.is_dir() and re.match(r'^\d+-', d.name)]
#     use_default_subbook = False
#     if not subbook_folders:
#         logger.info("No subbook folders detected in input directory; using default subbook.")
#         use_default_subbook = True
#         # Create a default subbook folder in the output directory.
#         default_subbook_folder = base_output_dir / "1-Default"
#         default_subbook_folder.mkdir(parents=True, exist_ok=True)
    
#     # Recursively find all chapter text files.
#     chapter_files = sorted(base_input_dir.rglob("chapter*.txt"))
#     logger.info(f"Found {len(chapter_files)} chapter file(s) under {base_input_dir}")
    
#     for chapter_file in chapter_files:
#         subbook_num = get_subbook_number(chapter_file, base_input_dir)
#         if use_default_subbook:
#             output_subdir = default_subbook_folder
#             subbook_num = 1
#         else:
#             try:
#                 rel_path = chapter_file.relative_to(base_input_dir)
#                 output_subdir = base_output_dir / rel_path.parent
#             except ValueError:
#                 output_subdir = base_output_dir
        
#         output_subdir.mkdir(parents=True, exist_ok=True)
        
#         chapter_data = process_chapter_file(chapter_file, nlp, language, book_code, subbook_num, global_counter)
#         if not chapter_data:
#             continue
        
#         # Construct the output filename using the full naming convention.
#         # For example: "BOOKM_S1_C{chapter_number}_{language}.json"
#         base_filename = f"{book_code}_S{subbook_num}_C{chapter_data['chapterNumber']}_{language}.json"
#         output_file_path = output_subdir / base_filename
        
#         with open(output_file_path, "w", encoding="utf-8") as json_file:
#             json.dump(chapter_data, json_file, indent=4, ensure_ascii=False)
#         logger.info(f"Saved content JSON for {chapter_file} as {output_file_path}")

# def main():
#     parser = argparse.ArgumentParser(
#         description="Process all chapter text files in a folder hierarchy to produce content JSONs for a specified language."
#     )
#     parser.add_argument('--input_dir', type=str, required=True,
#                         help='Base directory containing chapter text files (and subbook folders, if any).')
#     parser.add_argument('--language', type=str, required=True,
#                         help='Target language code (e.g., en-US) for the content JSON files.')
#     parser.add_argument('--book_code', type=str, required=True,
#                         help='Book code used for generating audio file names (e.g., BOOKM).')
#     parser.add_argument('--output_dir', type=str, required=True,
#                         help='Base directory where the content JSON files will be written (preserving folder structure).')
#     parser.add_argument('--verbose', action='store_true', help='Enable verbose logging.')
#     args = parser.parse_args()
    
#     if args.verbose:
#         logger.setLevel(logging.DEBUG)
    
#     base_input_dir = Path(args.input_dir)
#     base_output_dir = Path(args.output_dir)
    
#     if not base_input_dir.exists() or not base_input_dir.is_dir():
#         logger.error(f"Input directory '{base_input_dir}' does not exist or is not a directory.")
#         return
    
#     try:
#         nlp = spacy.load("en_core_web_sm")
#         logger.debug("Loaded spaCy model 'en_core_web_sm'")
#     except Exception as e:
#         logger.error(f"Error loading spaCy model: {e}")
#         return
    
#     process_all_chapter_files(base_input_dir, nlp, args.language, args.book_code, base_output_dir)
    
# if __name__ == "__main__":
#     main()
