"""
NOTE: SAVES THE OUTPUT TO THE EXISTING FILE.

Example usage:
python B-add_chapter_flags.py book.txt chapters.txt

book.txt → The full text of the book.
chapters.txt → A list of chapter titles (one per line).
"""

import sys

def load_chapters(chapters_path):
    """Load chapter titles from the provided file."""
    with open(chapters_path, 'r', encoding='utf-8') as file:
        return [line.strip() for line in file if line.strip()]

def add_flags_to_book(book_path, chapters_path):
    """Adds chapter flags to the book text where chapter titles appear."""
    chapters = load_chapters(chapters_path)
    
    with open(book_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    found_counts = {title: 0 for title in chapters}
    modified_lines = []
    
    for line in lines:
        stripped_line = line.strip()
        
        if stripped_line in chapters:
            found_counts[stripped_line] += 1
            modified_lines.append(f"<!-- CHAPTER: {stripped_line} -->\n")

        modified_lines.append(line)
    
    # Check for errors
    not_found = [title for title, count in found_counts.items() if count == 0]
    multiple_found = [title for title, count in found_counts.items() if count > 1]

    if not_found:
        print(f"Error: The following chapters were NOT found in the book file:\n{not_found}")
        return

    if multiple_found:
        print(f"Error: The following chapters were found MORE THAN ONCE in the book file:\n{multiple_found}")
        return

    # Write the modified content back to the same file
    with open(book_path, 'w', encoding='utf-8') as file:
        file.writelines(modified_lines)
    
    print(f"Chapter flags successfully added to {book_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python B-add_chapter_flags.py <book_path> <chapters_path>")
    else:
        book_path = sys.argv[1]
        chapters_path = sys.argv[2]
        add_flags_to_book(book_path, chapters_path)
