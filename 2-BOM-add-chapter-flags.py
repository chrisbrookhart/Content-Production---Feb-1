# NOTE: THIS CODE WAS DESIGNED TO LOOK FOR PATTERNS IN THE BOOK OF MORMON.
# IT ADDS CHAPTER FLAGS TO THE TEXT FILE ABOVE LINES WHERE IT FINDS THE WORD CHAPTER

import os
import re

def add_chapter_flags(input_path, output_path):
    if not os.path.isfile(input_path):
        print(f"Error: The input file '{input_path}' does not exist.")
        return
    
    try:
        with open(input_path, 'r') as file:
            # Read all lines from the file
            lines = file.readlines()
        
        updated_lines = []
        for i, line in enumerate(lines):
            # Check if the line contains the word "Chapter" and a chapter number
            match = re.search(r'\bChapter\s+(\d+)', line, re.IGNORECASE)
            if match:
                # Extract the chapter number
                chapter_number = match.group(1)
                # Insert the comment flag before the current line
                updated_lines.append(f"<!-- CHAPTER: {chapter_number} -->\n")
            # Add the current line to the updated list
            updated_lines.append(line)
        
        # Write the updated content to the output file
        with open(output_path, 'w') as output_file:
            output_file.writelines(updated_lines)
        
        print(f"File successfully processed. Output saved to: {output_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage:
# input_path = "/path/to/your/input.txt"
# output_path = "/path/to/your/output.txt"

input_path = '/Users/chrisbrookhart/Library/Mobile Documents/com~apple~CloudDocs/Developer/My iOS Apps/EchoBooks Content/Book_of_Mormon/The_Book_of_Mormon_no_nl.txt'
output_path = '/Users/chrisbrookhart/Library/Mobile Documents/com~apple~CloudDocs/Developer/My iOS Apps/EchoBooks Content/Book_of_Mormon/The_Book_of_Mormon_with_chapter_flags.txt'

add_chapter_flags(input_path, output_path)
