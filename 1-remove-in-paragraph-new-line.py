import os

def remove_inline_newlines(input_path, output_path):
    if not os.path.isfile(input_path):
        print(f"Error: The input file '{input_path}' does not exist.")
        return
    
    try:
        with open(input_path, 'r') as file:
            # Read the entire file content
            content = file.read()
        
        # Replace single newlines within paragraphs with a space
        cleaned_content = []
        for paragraph in content.split('\n\n'):
            # Replace single newlines in paragraphs with a space
            paragraph = paragraph.replace('\n', ' ')
            cleaned_content.append(paragraph)
        
        # Join the paragraphs back with double newlines to preserve paragraph breaks
        result = '\n\n'.join(cleaned_content)
        
        # Write the cleaned content to the output file
        with open(output_path, 'w') as output_file:
            output_file.write(result)
        
        print(f"File successfully processed. Output saved to: {output_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage:
input_path = '/Users/chrisbrookhart/Library/Mobile Documents/com~apple~CloudDocs/Developer/My iOS Apps/EchoBooks Content/Sherlock_Holmes/SherlockHolmes.txt'
output_path = '/Users/chrisbrookhart/Library/Mobile Documents/com~apple~CloudDocs/Developer/My iOS Apps/EchoBooks Content/Sherlock_Holmes/SherlockHolmes-nl.txt'

remove_inline_newlines(input_path, output_path)
