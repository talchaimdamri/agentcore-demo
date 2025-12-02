import base64
import json
import os
import sys
from code_int_mcp.client import CodeInterpreterClient

def get_file_list(client, session_id):
    print("Fetching file list...")
    # Find files in current dir and /tmp, excluding hidden ones
    cmd = "find . /tmp -maxdepth 2 -not -path '*/.*' -type f"
    result = client.execute_command(command=cmd, code_int_session_id=session_id)
    
    if not result.success:
        print(f"Error listing files: {result.error}")
        return []
    
    try:
        # result.output is a JSON string containing the execution result
        # We need to parse it to get the actual stdout
        data = json.loads(result.output)
        
        # The structure of 'result' in the event usually has 'stdout'
        if isinstance(data, dict) and 'stdout' in data:
            output_text = data['stdout']
        else:
            # Fallback if structure is different
            output_text = str(data)
            
        files = [f.strip() for f in output_text.split('\n') if f.strip()]
        return files
    except json.JSONDecodeError:
        # If it's not JSON, maybe it's the raw text
        return [f.strip() for f in result.output.split('\n') if f.strip()]
    except Exception as e:
        print(f"Error parsing file list: {e}")
        # Try to return raw lines as fallback
        return [f.strip() for f in result.output.split('\n') if f.strip()]

def download_file(client, session_id, remote_path):
    local_filename = os.path.basename(remote_path)
    print(f"Downloading {remote_path} to {local_filename}...")
    
    # Python code to read file and print base64
    code = f"""
import base64
import os
import sys

file_path = '{remote_path}'
if os.path.exists(file_path):
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
            b64_content = base64.b64encode(content).decode('utf-8')
            print(f"BASE64_START{{b64_content}}BASE64_END")
    except Exception as e:
        print(f"Error reading file: {{e}}")
else:
    print(f"File not found: {{file_path}}")
"""
    result = client.execute_code(code=code, code_int_session_id=session_id)
    
    if not result.success:
        print(f"Failed to execute download code: {result.error}")
        return

    # Extract base64
    output = result.output
    start_marker = "BASE64_START"
    end_marker = "BASE64_END"
    
    start_idx = output.find(start_marker)
    end_idx = output.find(end_marker)
    
    if start_idx != -1 and end_idx != -1:
        b64_data = output[start_idx + len(start_marker) : end_idx]
        try:
            file_content = base64.b64decode(b64_data)
            with open(local_filename, "wb") as f:
                f.write(file_content)
            print(f"✅ Successfully downloaded {local_filename} ({len(file_content)} bytes)")
        except Exception as e:
            print(f"❌ Error saving file: {e}")
    else:
        print("❌ Could not retrieve file content. Output was:")
        print(output)

def main():
    print("=== Code Interpreter File Downloader ===")
    
    # 1. Ask for Session ID
    if len(sys.argv) > 1:
        session_id = sys.argv[1]
        print(f"Using Session ID from argument: {session_id}")
    else:
        session_id = input("Enter Session ID: ").strip()
    
    if not session_id:
        print("Session ID is required.")
        return

    client = CodeInterpreterClient()
    
    # 2. List files
    files = get_file_list(client, session_id)
    
    if not files:
        print("No files found.")
        return

    print("\nAvailable files:")
    for i, f in enumerate(files):
        print(f"{i+1}. {f}")
    
    # 3. Ask for selection
    while True:
        selection = input("\nEnter file number to download (or 'q' to quit): ").strip()
        if selection.lower() == 'q':
            break
            
        try:
            idx = int(selection) - 1
            if 0 <= idx < len(files):
                target_file = files[idx]
                download_file(client, session_id, target_file)
            else:
                print("Invalid number.")
        except ValueError:
            print("Please enter a number.")

if __name__ == "__main__":
    main()
