"""
NOTE: SAVES THE OUTPUT TO THE EXISTING FILE.

Example usage:
python A-add_subbook_flags.py book.txt subbooks.txt

book.txt → The full text of the book.
subbooks.txt → A list of subbook titles (one per line).
"""


import sys

def load_subbooks(subbooks_path):
    """Load subbook titles from the provided file."""
    with open(subbooks_path, 'r', encoding='utf-8') as file:
        return [line.strip() for line in file if line.strip()]

def add_flags_to_book(book_path, subbooks_path):
    """Adds subbook flags to the book text where subbook titles appear."""
    subbooks = load_subbooks(subbooks_path)
    
    with open(book_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    found_counts = {title: 0 for title in subbooks}
    modified_lines = []
    
    for line in lines:
        stripped_line = line.strip()
        
        if stripped_line in subbooks:
            found_counts[stripped_line] += 1
            modified_lines.append(f"<!-- SUBBOOK: {stripped_line} -->\n")

        modified_lines.append(line)
    
    # Check for errors
    not_found = [title for title, count in found_counts.items() if count == 0]
    multiple_found = [title for title, count in found_counts.items() if count > 1]

    if not_found:
        print(f"Error: The following subbooks were NOT found in the book file:\n{not_found}")
        return

    if multiple_found:
        print(f"Error: The following subbooks were found MORE THAN ONCE in the book file:\n{multiple_found}")
        return

    # Write the modified content back to the same file
    with open(book_path, 'w', encoding='utf-8') as file:
        file.writelines(modified_lines)
    
    print(f"Subbook flags successfully added to {book_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python A-add_subbook_flags.py <book_path> <subbooks_path>")
    else:
        book_path = sys.argv[1]
        subbooks_path = sys.argv[2]
        add_flags_to_book(book_path, subbooks_path)
