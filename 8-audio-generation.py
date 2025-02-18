#!/usr/bin/env python3
"""
8-audio-generation.py

Stage 8: Audio Generation Stage

This script recursively scans the entire book folder for chapter JSON files in each language.
It expects the book folder to have subfolders for each language (e.g., "en-US", "es-ES", "fr-FR").
Within each language folder, the JSON files are stored under the "Content" folder (with a
subfolder structure such as {subbook}/{ChapterX}). For each chapter JSON file, the script will generate
audio files for every sentence using OpenAI’s text-to-speech API. The generated audio files are written
to a parallel folder structure under each language folder’s "Audio" folder, preserving the relative path.

Usage example:
    python 8-audio-generation.py \
        --input_dir "/path/to/The_Book_of_Mormon" \
        [--verbose]

Requirements:
  - The OPENAI_API_KEY environment variable must be set.
  - This script uses OpenAI's TTS API via the streaming interface.
"""

import os
import re
import json
import argparse
import logging
from pathlib import Path
import openai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def sanitize_filename(name):
    """
    Replace spaces and other problematic characters in the name to make it suitable for filenames.
    """
    return re.sub(r'[^A-Za-z0-9_]', '', name.replace(" ", "_"))

def generate_audio(sentence_text, language_code, output_path):
    """
    Generate text-to-speech audio for a given sentence and save it to the specified path.

    Parameters:
        sentence_text (str): The text to convert to speech.
        language_code (str): The language code (e.g., 'es-ES').
        output_path (Path): The path where the audio file will be saved.
    """
    try:
        if not openai.api_key:
            raise ValueError("OpenAI API key is not set. Please set the OPENAI_API_KEY environment variable.")
        
        # Use OpenAI's TTS API with the streaming interface.
        # (Adjust model and voice parameters as appropriate for your use case.)
        with openai.audio.speech.with_streaming_response.create(
            model="tts-1-hd",
            voice="alloy",
            input=sentence_text,
            response_format='aac'
        ) as response:
            response.stream_to_file(output_path)
        logger.info(f"Audio saved: {output_path}")
    except Exception as e:
        logger.error(f"Error generating audio for '{sentence_text}' in {language_code}: {e}")

def process_json_file(json_file: Path, content_base: Path, audio_base: Path):
    """
    Process a single chapter JSON file: for each sentence, generate its audio file.
    
    Parameters:
      json_file (Path): Path to the chapter JSON file.
      content_base (Path): The base "Content" folder (used to compute the relative path).
      audio_base (Path): The base folder where Audio files for this language should be stored.
    """
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            content = json.load(f)
    except Exception as e:
        logger.error(f"Error reading JSON file {json_file}: {e}")
        return

    language = content.get("language", "").strip()
    if not language:
        logger.error(f"No language specified in {json_file}. Skipping file.")
        return

    try:
        rel_path = json_file.relative_to(content_base)
    except Exception as e:
        logger.error(f"Error computing relative path for {json_file}: {e}")
        return

    # Construct the output audio folder: {audio_base}/{relative path's parent}
    output_audio_dir = audio_base / rel_path.parent
    output_audio_dir.mkdir(parents=True, exist_ok=True)

    for para in content.get("paragraphs", []):
        for sentence in para.get("sentences", []):
            sentence_text = sentence.get("text", "").strip()
            if not sentence_text:
                logger.warning(f"No text in sentence {sentence.get('sentenceID', 'UnknownID')}; skipping audio generation.")
                continue
            audio_filename = sentence.get("audioFile", "")
            if not audio_filename:
                logger.warning(f"No audio filename for sentence {sentence.get('sentenceID', 'UnknownID')}; skipping.")
                continue
            output_audio_path = output_audio_dir / audio_filename
            logger.info(f"Generating audio for sentence {sentence.get('sentenceID', 'UnknownID')} in {language}")
            generate_audio(sentence_text, language, output_audio_path)

def process_all_json_files(book_dir: Path):
    """
    Process all chapter JSON files for all languages under the given book folder.

    The expected folder structure is:
      {book_dir}/{language}/Content/...
    and the audio files will be output to:
      {book_dir}/{language}/Audio/...
    """
    # Iterate over each language folder within the book directory.
    for lang_folder in book_dir.iterdir():
        if not lang_folder.is_dir():
            continue
        # Check that this folder contains a Content folder.
        content_dir = lang_folder / "Content"
        if not content_dir.exists() or not content_dir.is_dir():
            logger.debug(f"Folder {lang_folder} does not contain a Content subfolder; skipping.")
            continue
        # Define the corresponding Audio base folder for this language.
        audio_base = lang_folder / "Audio"
        # Process all JSON files in the Content folder recursively.
        json_files = list(content_dir.rglob("*.json"))
        logger.info(f"Found {len(json_files)} JSON file(s) in {content_dir} for language {lang_folder.name}")
        for json_file in json_files:
            logger.info(f"Processing JSON file: {json_file}")
            process_json_file(json_file, content_dir, audio_base)

def main():
    parser = argparse.ArgumentParser(
        description="Generate audio files from chapter JSON files across all language folders."
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
    
    # Set the OpenAI API key.
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("The OPENAI_API_KEY environment variable is not set.")
        return
    openai.api_key = os.getenv("OPENAI_API_KEY")
    
    process_all_json_files(book_dir)

if __name__ == "__main__":
    main()
