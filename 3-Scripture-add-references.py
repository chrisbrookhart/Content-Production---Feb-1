import re

def wrap_number_patterns_with_newline(input_file_path, output_file_path):
    """
    Opens a text file, finds all instances of 'number:colon:number space',
    and moves them to their own line before the text in the format:
    '<!-- REF: number:colon:number -->'.

    :param input_file_path: Path to the input text file
    :param output_file_path: Path to the output text file
    """
    # Define the regex pattern to match the specified pattern
    pattern = r'\b(\d+:\d+) '  # Captures the number:colon:number pattern

    # Define the replacement format to place the reference on its own line
    replacement = r'<!-- REF: \1 -->\n'

    try:
        # Open the input file and read its content
        with open(input_file_path, 'r') as file:
            content = file.readlines()

        # Process each line, inserting references on their own line
        updated_content = []
        for line in content:
            # Replace the pattern and add the reference line if a match is found
            updated_line = re.sub(pattern, replacement, line)
            if updated_line != line:  # A match was found and replaced
                match = re.search(pattern, line)
                if match:
                    updated_content.append(f'<!-- REF: {match.group(1)} -->\n')
            # Add the original (now cleaned) line
            updated_content.append(re.sub(pattern, '', line))

        # Write the updated content to the output file
        with open(output_file_path, 'w') as file:
            file.writelines(updated_content)

        print(f"Processing complete. Updated file saved to '{output_file_path}'.")
    
    except FileNotFoundError:
        print(f"Error: The file at '{input_file_path}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

# Placeholder for file paths
# input_file_path = 'path/to/your/input_file.txt'  # Replace with your input file path
# output_file_path = 'path/to/your/output_file.txt'  # Replace with your desired output file path

input_file_path = '/Users/chrisbrookhart/Library/Mobile Documents/com~apple~CloudDocs/Developer/My iOS Apps/EchoBooks Content/Book_of_Mormon/The_Book_of_Mormon_with_headers.txt'  # Replace with your input file path
output_file_path = '/Users/chrisbrookhart/Library/Mobile Documents/com~apple~CloudDocs/Developer/My iOS Apps/EchoBooks Content/Book_of_Mormon/The_Book_of_Mormon3_with_refs.txt'  # Replace with your desired output file path

# Call the function
wrap_number_patterns_with_newline(input_file_path, output_file_path)


