#!/usr/bin/env python3
"""
7-translator.py

Stage 7: Translator (Batch Mode)

This script recursively scans an input directory for native content JSON files.
Native content JSON files are expected to have filenames ending with _{native_language}.json
(e.g., "BOOKM_S1_C1_en-US.json") located under a language-specific folder such as:
    /path/to/The_Book_of_Mormon/en-US/Content
For each such file, the script translates every sentence's text into one or more target languages
(using OpenAI's GPT-4 model). In each output file, the top-level "language" field is updated to
the target language, and each sentence's "text" field becomes a string in the target language.
Also, each sentence's "audioFile" field is updated so that the native language code is replaced by
the target language code.

The translated JSON files are output to a parallel folder structure under a new language folder.
For example, if the native file is:
    /path/to/The_Book_of_Mormon/en-US/Content/1-Default/Chapter1/BOOKM_S1_C1_en-US.json
and the target language is "es-ES", the output file will be:
    /path/to/The_Book_of_Mormon/es-ES/Content/1-Default/Chapter1/BOOKM_S1_C1_es-ES.json

Usage example:
    python 7-translator.py \
        --input_dir "/path/to/The_Book_of_Mormon/en-US/Content" \
        --output_dir "/path/to/The_Book_of_Mormon" \
        --native_language "en-US" \
        --target_languages "es-ES,fr-FR" \
        [--verbose]

Requirements:
  - Set the OPENAI_API_KEY environment variable with your OpenAI API key.
"""

import os
import re
import json
import argparse
import logging
from pathlib import Path
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def sanitize_filename(name):
    """
    Replace spaces and other problematic characters in the name to make it suitable for filenames.
    """
    return re.sub(r'[^A-Za-z0-9_]', '', name.replace(" ", "_"))

def translate_text(text, target_language, client):
    """
    Translate text using OpenAI's GPT-4 model.

    Parameters:
        text (str): The text to translate.
        target_language (str): The language to translate the text into.
        client (OpenAI): An instance of the OpenAI client.

    Returns:
        str: The translated text, or an empty string if translation fails.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": f"You are a translator. Translate the following text to {target_language}."},
                {"role": "user", "content": text},
            ],
            temperature=0
        )
        translation = response.choices[0].message.content.strip()
        return translation
    except Exception as e:
        logger.error(f"Error during translation to {target_language}: {e}")
        return ""

def process_sentence(sentence, native_language_code, target_language, language_map, client):
    """
    Process a single sentence: extract the native text, translate it into the target language,
    and update the sentence so that its "text" field becomes a string (the translation).
    
    Also update the "audioFile" field by replacing the native language code with the target language code.
    
    Parameters:
        sentence (dict): A dictionary representing a sentence.
        native_language_code (str): The native language code (e.g., "en-US").
        target_language (str): The target language code (e.g., "es-ES").
        language_map (dict): Mapping from language codes to full language names.
        client (OpenAI): An instance of the OpenAI client.
    """
    text_field = sentence.get("text", "")
    if isinstance(text_field, dict):
        native_text = text_field.get(native_language_code, "").strip()
    else:
        native_text = text_field.strip()
    
    if not native_text:
        logger.warning(f"Sentence {sentence.get('sentenceID', 'UnknownID')} has no native text; skipping translation.")
        return
    
    target_language_name = language_map.get(target_language)
    if not target_language_name:
        logger.warning(f"Unsupported target language code '{target_language}'; skipping translation.")
        return
    
    translation = translate_text(native_text, target_language_name, client)
    if not translation:
        logger.warning(f"Translation failed for sentence {sentence.get('sentenceID')} in language '{target_language}'.")
        translation = ""
    else:
        logger.info(f"Added translation for sentence {sentence.get('sentenceID')} in language '{target_language}'.")
    
    # Replace the "text" field with the translation string.
    sentence["text"] = translation
    
    # Update the "audioFile" field by replacing the native language code with the target language code.
    audio_file = sentence.get("audioFile", "")
    updated_audio = re.sub(rf"_{re.escape(native_language_code)}\.aac$", f"_{target_language}.aac", audio_file)
    sentence["audioFile"] = updated_audio

def translate_content(content, native_language_code, target_language, language_map, client):
    """
    Traverse the chapter content JSON and translate each sentence into the target language.
    
    The content dictionary is updated in place so that each sentence's "text" field becomes
    a string in the target language.
    
    Parameters:
        content (dict): The content JSON dictionary (with a "paragraphs" array).
        native_language_code (str): The native language code.
        target_language (str): The target language code.
        language_map (dict): Mapping from language codes to full language names.
        client (OpenAI): An instance of the OpenAI client.
    """
    for para in content.get("paragraphs", []):
        for sentence in para.get("sentences", []):
            process_sentence(sentence, native_language_code, target_language, language_map, client)

def process_json_file(json_file, native_language_code, target_language_codes, language_map, client, input_base_dir, output_base_dir):
    """
    Process a single native content JSON file and produce translated versions.

    For each target language, the native JSON file is read, translated, and then written out
    to the corresponding target language folder while preserving the relative folder structure.
    
    The output filename is constructed by replacing the native language code in the filename with the target language code.
    """
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            native_content = json.load(f)
    except Exception as e:
        logger.error(f"Error reading JSON file {json_file}: {e}")
        return

    # Compute the relative path from the native base directory.
    try:
        rel_path = json_file.relative_to(input_base_dir)
    except Exception as e:
        logger.error(f"Error computing relative path for {json_file}: {e}")
        return

    for target_language in target_language_codes:
        # Deep copy native content for independent translation.
        translated_content = json.loads(json.dumps(native_content))
        # Update the top-level language field.
        translated_content["language"] = target_language
        # Translate the content.
        translate_content(translated_content, native_language_code, target_language, language_map, client)
        # Update the audioFile fields.
        for para in translated_content.get("paragraphs", []):
            for sentence in para.get("sentences", []):
                audio_file = sentence.get("audioFile", "")
                updated_audio = re.sub(rf"_{re.escape(native_language_code)}\.aac$", f"_{target_language}.aac", audio_file)
                sentence["audioFile"] = updated_audio
        # Construct the output filename.
        new_filename = re.sub(rf"_{re.escape(native_language_code)}\.json$", f"_{target_language}.json", json_file.name)
        if new_filename == json_file.name:
            new_filename = json_file.stem + f"_{target_language}.json"
        # Construct the full output path:
        # output_base_dir / {target_language} / Content / {relative folder path}
        output_path = output_base_dir / target_language / "Content" / rel_path.parent
        output_path.mkdir(parents=True, exist_ok=True)
        full_output_file = output_path / new_filename
        try:
            with open(full_output_file, "w", encoding="utf-8") as f_out:
                json.dump(translated_content, f_out, indent=4, ensure_ascii=False)
            logger.info(f"Saved translated JSON for language '{target_language}' to {full_output_file}")
        except Exception as e:
            logger.error(f"Error writing translated JSON file {full_output_file}: {e}")

def process_all_json_files(input_dir, native_language_code, target_language_codes, language_map, client, output_base_dir):
    """
    Recursively process all native content JSON files in the input directory.

    Native content JSON files are expected to have filenames ending with _{native_language}.json.
    For each file, new translated JSON files for each target language are produced and saved under
    output_base_dir in a folder structure:
        {output_base_dir}/{target_language}/Content/{relative_path_of_native_file}
    """
    native_pattern = re.compile(rf".*_{re.escape(native_language_code)}\.json$", re.IGNORECASE)
    json_files = [f for f in input_dir.rglob("*.json") if f.is_file() and native_pattern.match(f.name)]
    logger.info(f"Found {len(json_files)} native content JSON file(s) in {input_dir}")
    for json_file in json_files:
        logger.info(f"Processing native JSON file: {json_file}")
        process_json_file(json_file, native_language_code, target_language_codes, language_map, client, input_dir, output_base_dir)

def main():
    parser = argparse.ArgumentParser(
        description="Translate native content JSON files to target languages in batch mode and output them into language-specific folders."
    )
    parser.add_argument('--input_dir', type=str, required=True,
                        help='Base directory containing native content JSON files (e.g., "/path/to/The_Book_of_Mormon/en-US/Content").')
    parser.add_argument('--output_dir', type=str, required=True,
                        help='Top-level book folder where translated files will be saved in language-specific folders (e.g., "/path/to/The_Book_of_Mormon").')
    parser.add_argument('--native_language', type=str, required=True,
                        help='Native language code (e.g., "en-US").')
    parser.add_argument('--target_languages', type=str, required=True,
                        help='Comma-separated list of target language codes (e.g., "es-ES,fr-FR").')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging.')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    if not input_dir.exists() or not input_dir.is_dir():
        logger.error(f"Input directory '{input_dir}' does not exist or is not a directory.")
        return
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
    
    native_language_code = args.native_language.strip()
    target_language_codes = [lang.strip() for lang in args.target_languages.split(",") if lang.strip()]
    target_language_codes = [lang for lang in target_language_codes if lang != native_language_code]
    if not target_language_codes:
        logger.error("No target languages provided after excluding the native language.")
        return
    
    # Define a mapping from language codes to full language names.
    language_map = {
        "af-ZA": "Afrikaans",
        "ar-SA": "Arabic",
        "hy-AM": "Armenian",
        "az-AZ": "Azerbaijani",
        "be-BY": "Belarusian",
        "bs-BA": "Bosnian",
        "bg-BG": "Bulgarian",
        "ca-ES": "Catalan",
        "zh-CN": "Chinese",
        "hr-HR": "Croatian",
        "cs-CZ": "Czech",
        "da-DK": "Danish",
        "nl-NL": "Dutch",
        "en-US": "English",
        "et-EE": "Estonian",
        "fi-FI": "Finnish",
        "fr-FR": "French",
        "gl-ES": "Galician",
        "de-DE": "German",
        "el-GR": "Greek",
        "he-IL": "Hebrew",
        "hi-IN": "Hindi",
        "hu-HU": "Hungarian",
        "is-IS": "Icelandic",
        "id-ID": "Indonesian",
        "it-IT": "Italian",
        "ja-JP": "Japanese",
        "kn-IN": "Kannada",
        "kk-KZ": "Kazakh",
        "ko-KR": "Korean",
        "lv-LV": "Latvian",
        "lt-LT": "Lithuanian",
        "mk-MK": "Macedonian",
        "ms-MY": "Malay",
        "mr-IN": "Marathi",
        "mi-NZ": "Maori",
        "ne-NP": "Nepali",
        "nb-NO": "Norwegian",
        "fa-IR": "Persian",
        "pl-PL": "Polish",
        "pt-PT": "Portuguese",
        "ro-RO": "Romanian",
        "ru-RU": "Russian",
        "sr-RS": "Serbian",
        "sk-SK": "Slovak",
        "sl-SI": "Slovenian",
        "es-ES": "Spanish",
        "sw-KE": "Swahili",
        "sv-SE": "Swedish",
        "tl-PH": "Tagalog",
        "ta-IN": "Tamil",
        "th-TH": "Thai",
        "tr-TR": "Turkish",
        "uk-UA": "Ukrainian",
        "ur-PK": "Urdu",
        "vi-VN": "Vietnamese",
        "cy-GB": "Welsh",
        # Add additional mappings as needed.
    }
    
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("The OPENAI_API_KEY environment variable is not set.")
        return
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    process_all_json_files(input_dir, native_language_code, target_language_codes, language_map, client, output_dir)

if __name__ == "__main__":
    main()



# #!/usr/bin/env python3
# """
# 7-translator.py

# Stage 7: Translator (Batch Mode)

# This script recursively scans an input directory for native content JSON files.
# Native content JSON files are expected to have filenames ending with _{native_language}.json
# (e.g., "BOOKM_S1_C1_en-US.json"). For each such file, the script translates every sentence's text
# into one or more target languages using OpenAI's GPT-4 model. In each output file, the sentence’s
# "text" field becomes a string containing only the translation in that target language, and the top-level
# "language" field is updated accordingly. Additionally, the "audioFile" field is updated so that its filename
# ends with the target language code.

# Translated JSON files are stored in the same folders as their native counterparts, with the filename
# modified by replacing the native language code with the target language code. For example, if the native file is
# "BOOKM_S1_C1_en-US.json" and a target language is "es-ES", the output file will be "BOOKM_S1_C1_es-ES.json".

# Usage example:
#     python 7-translator.py \
#         --input_dir "/path/to/content_jsons" \
#         --native_language "en-US" \
#         --target_languages "es-ES,fr-FR" \
#         [--verbose]

# Requirements:
#   - Set the OPENAI_API_KEY environment variable with your OpenAI API key.
# """

# import os
# import re
# import json
# import argparse
# import logging
# from pathlib import Path
# from openai import OpenAI

# # Configure logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
# logger = logging.getLogger(__name__)

# def sanitize_filename(name):
#     """
#     Replace spaces and other problematic characters in the name to make it suitable for filenames.
#     """
#     return re.sub(r'[^A-Za-z0-9_]', '', name.replace(" ", "_"))

# def translate_text(text, target_language, client):
#     """
#     Translate text using OpenAI's GPT-4 model.

#     Parameters:
#         text (str): The text to translate.
#         target_language (str): The language to translate the text into.
#         client (OpenAI): An instance of the OpenAI client.

#     Returns:
#         str: The translated text, or an empty string if translation fails.
#     """
#     try:
#         response = client.chat.completions.create(
#             model="gpt-4",
#             messages=[
#                 {"role": "system", "content": f"You are a translator. Translate the following text to {target_language}."},
#                 {"role": "user", "content": text},
#             ],
#             temperature=0
#         )
#         translation = response.choices[0].message.content.strip()
#         return translation
#     except Exception as e:
#         logger.error(f"Error during translation to {target_language}: {e}")
#         return ""

# def process_sentence(sentence, native_language_code, target_language, language_map, client):
#     """
#     Process a single sentence: extract the native text, translate it into the target language,
#     and update the sentence so that its "text" field becomes a string (the translation).
    
#     Also update the "audioFile" field by replacing the native language code with the target language code.
    
#     Parameters:
#         sentence (dict): A dictionary representing a sentence.
#         native_language_code (str): The native language code (e.g., "en-US").
#         target_language (str): The target language code (e.g., "es-ES").
#         language_map (dict): Mapping from language codes to full language names.
#         client (OpenAI): An instance of the OpenAI client.
#     """
#     # Check if "text" is a string or already a dict; if dict, extract native text.
#     text_field = sentence.get("text", "")
#     if isinstance(text_field, dict):
#         native_text = text_field.get(native_language_code, "").strip()
#     else:
#         native_text = text_field.strip()
    
#     if not native_text:
#         logger.warning(f"Sentence {sentence.get('sentenceID', 'UnknownID')} has no native text; skipping translation.")
#         return
    
#     # Translate the native text.
#     target_language_name = language_map.get(target_language)
#     if not target_language_name:
#         logger.warning(f"Unsupported target language code '{target_language}'; skipping.")
#         return
    
#     translation = translate_text(native_text, target_language_name, client)
#     if not translation:
#         logger.warning(f"Translation failed for sentence {sentence.get('sentenceID')} in language '{target_language}'.")
#         translation = ""
#     else:
#         logger.info(f"Added translation for sentence {sentence.get('sentenceID')} in language '{target_language}'.")
    
#     # Replace the sentence "text" field with the translation.
#     sentence["text"] = translation
#     # Update the audioFile field: replace _{native_language}.aac with _{target_language}.aac.
#     audio_file = sentence.get("audioFile", "")
#     updated_audio = re.sub(rf"_{re.escape(native_language_code)}\.aac$", f"_{target_language}.aac", audio_file)
#     sentence["audioFile"] = updated_audio

# def translate_content(content, native_language_code, target_language, language_map, client):
#     """
#     Traverse the chapter content JSON and translate every sentence into the target language.
    
#     The content dictionary is updated in place so that each sentence's "text" field becomes
#     a string in the target language.
    
#     Parameters:
#         content (dict): The content JSON dictionary (with a "paragraphs" array).
#         native_language_code (str): The native language code.
#         target_language (str): The target language code.
#         language_map (dict): Mapping from language codes to full language names.
#         client (OpenAI): An instance of the OpenAI client.
#     """
#     for para in content.get("paragraphs", []):
#         for sentence in para.get("sentences", []):
#             process_sentence(sentence, native_language_code, target_language, language_map, client)

# def process_json_file(json_file, native_language_code, target_language_codes, language_map, client):
#     """
#     Process a single native content JSON file and produce translated versions.
    
#     For each target language, the native JSON file is read, translated, and a new JSON file is
#     written to the same folder with the filename modified by replacing the native language code
#     with the target language code.
#     """
#     try:
#         with open(json_file, "r", encoding="utf-8") as f:
#             native_content = json.load(f)
#     except Exception as e:
#         logger.error(f"Error reading JSON file {json_file}: {e}")
#         return

#     # For each target language, create a translated copy.
#     for target_language in target_language_codes:
#         # Make a deep copy of the native content.
#         translated_content = json.loads(json.dumps(native_content))
#         # Update the top-level language field to the target language.
#         translated_content["language"] = target_language
#         # Translate each sentence in the content.
#         translate_content(translated_content, native_language_code, target_language, language_map, client)
#         # Construct the output filename by replacing the native language code with the target language code.
#         new_filename = re.sub(rf"_{re.escape(native_language_code)}\.json$", f"_{target_language}.json", json_file.name)
#         if new_filename == json_file.name:
#             new_filename = json_file.stem + f"_{target_language}.json"
#         output_path = json_file.parent / new_filename
#         try:
#             with open(output_path, "w", encoding="utf-8") as f_out:
#                 json.dump(translated_content, f_out, indent=4, ensure_ascii=False)
#             logger.info(f"Saved translated JSON for language '{target_language}' to {output_path}")
#         except Exception as e:
#             logger.error(f"Error writing translated JSON file {output_path}: {e}")

# def process_all_json_files(input_dir, native_language_code, target_language_codes, language_map, client):
#     """
#     Recursively process all native content JSON files in the input directory.

#     Native content JSON files are expected to have filenames ending with _{native_language}.json.
#     For each file, new translated JSON files for each target language are produced and saved in the same folder.
#     """
#     native_pattern = re.compile(rf".*_{re.escape(native_language_code)}\.json$", re.IGNORECASE)
#     json_files = [f for f in input_dir.rglob("*.json") if f.is_file() and native_pattern.match(f.name)]
#     logger.info(f"Found {len(json_files)} native content JSON file(s) in {input_dir}")
#     for json_file in json_files:
#         logger.info(f"Processing native JSON file: {json_file}")
#         process_json_file(json_file, native_language_code, target_language_codes, language_map, client)

# def main():
#     parser = argparse.ArgumentParser(
#         description="Translate native content JSON files to target languages in batch mode."
#     )
#     parser.add_argument('--input_dir', type=str, required=True,
#                         help='Base directory containing native content JSON files (with subbook folders, if any).')
#     parser.add_argument('--native_language', type=str, required=True,
#                         help='Native language code (e.g., "en-US").')
#     parser.add_argument('--target_languages', type=str, required=True,
#                         help='Comma-separated list of target language codes (e.g., "es-ES,fr-FR,de-DE").')
#     parser.add_argument('--verbose', action='store_true', help='Enable verbose logging.')
    
#     args = parser.parse_args()
    
#     if args.verbose:
#         logger.setLevel(logging.DEBUG)
    
#     input_dir = Path(args.input_dir)
#     if not input_dir.exists() or not input_dir.is_dir():
#         logger.error(f"Input directory '{input_dir}' does not exist or is not a directory.")
#         return
    
#     native_language_code = args.native_language.strip()
#     target_language_codes = [lang.strip() for lang in args.target_languages.split(",") if lang.strip()]
#     # Exclude native language if present.
#     target_language_codes = [lang for lang in target_language_codes if lang != native_language_code]
#     if not target_language_codes:
#         logger.error("No target languages provided after excluding the native language.")
#         return
    
#     # Define a mapping from language codes to full language names.
#     language_map = {
#         "af-ZA": "Afrikaans",
#         "ar-SA": "Arabic",
#         "hy-AM": "Armenian",
#         "az-AZ": "Azerbaijani",
#         "be-BY": "Belarusian",
#         "bs-BA": "Bosnian",
#         "bg-BG": "Bulgarian",
#         "ca-ES": "Catalan",
#         "zh-CN": "Chinese",
#         "hr-HR": "Croatian",
#         "cs-CZ": "Czech",
#         "da-DK": "Danish",
#         "nl-NL": "Dutch",
#         "en-US": "English",
#         "et-EE": "Estonian",
#         "fi-FI": "Finnish",
#         "fr-FR": "French",
#         "gl-ES": "Galician",
#         "de-DE": "German",
#         "el-GR": "Greek",
#         "he-IL": "Hebrew",
#         "hi-IN": "Hindi",
#         "hu-HU": "Hungarian",
#         "is-IS": "Icelandic",
#         "id-ID": "Indonesian",
#         "it-IT": "Italian",
#         "ja-JP": "Japanese",
#         "kn-IN": "Kannada",
#         "kk-KZ": "Kazakh",
#         "ko-KR": "Korean",
#         "lv-LV": "Latvian",
#         "lt-LT": "Lithuanian",
#         "mk-MK": "Macedonian",
#         "ms-MY": "Malay",
#         "mr-IN": "Marathi",
#         "mi-NZ": "Maori",
#         "ne-NP": "Nepali",
#         "nb-NO": "Norwegian",
#         "fa-IR": "Persian",
#         "pl-PL": "Polish",
#         "pt-PT": "Portuguese",
#         "ro-RO": "Romanian",
#         "ru-RU": "Russian",
#         "sr-RS": "Serbian",
#         "sk-SK": "Slovak",
#         "sl-SI": "Slovenian",
#         "es-ES": "Spanish",
#         "sw-KE": "Swahili",
#         "sv-SE": "Swedish",
#         "tl-PH": "Tagalog",
#         "ta-IN": "Tamil",
#         "th-TH": "Thai",
#         "tr-TR": "Turkish",
#         "uk-UA": "Ukrainian",
#         "ur-PK": "Urdu",
#         "vi-VN": "Vietnamese",
#         "cy-GB": "Welsh",
#         # Add additional mappings as needed.
#     }
    
#     if not os.getenv("OPENAI_API_KEY"):
#         logger.error("The OPENAI_API_KEY environment variable is not set.")
#         return
    
#     client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
#     process_all_json_files(input_dir, native_language_code, target_language_codes, language_map, client)

# if __name__ == "__main__":
#     main()
