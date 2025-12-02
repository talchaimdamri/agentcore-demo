import base64
import json
from code_int_mcp.client import CodeInterpreterClient

def download_presentation():
    # Replace with your actual Code Interpreter session ID
    session_id = "<your-session-id>"
    file_path = "/tmp/your-file.pptx"  # Path to file in Code Interpreter session
    output_filename = "downloaded-file.pptx"
    
    client = CodeInterpreterClient()
    
    print(f"Connecting to session {session_id}...")
    
    # Python code to run in the Code Interpreter
    code = f"""
import base64
try:
    with open('{file_path}', 'rb') as f:
        content = f.read()
        b64_content = base64.b64encode(content).decode('utf-8')
        print(f"BASE64_START{{b64_content}}BASE64_END")
except Exception as e:
    print(f"Error: {{e}}")
"""
    
    print(f"Requesting file {file_path}...")
    result = client.execute_code(code=code, code_int_session_id=session_id)
    
    if not result.success:
        print(f"Failed to execute code: {result.error}")
        return
        
    output = result.output
    
    # Extract base64 content
    try:
        # The output might be a JSON string of the stream events, we need to parse it or find our marker
        # The client.py implementation of _invoke_code_interpreter does:
        # output = json.dumps(event["result"], indent=2)
        # So 'output' is a JSON string.
        
        # Let's try to find our markers directly in the string, it's robust enough
        start_marker = "BASE64_START"
        end_marker = "BASE64_END"
        
        start_idx = output.find(start_marker)
        end_idx = output.find(end_marker)
        
        if start_idx != -1 and end_idx != -1:
            b64_data = output[start_idx + len(start_marker) : end_idx]
            
            # Decode and save
            file_content = base64.b64decode(b64_data)
            with open(output_filename, "wb") as f:
                f.write(file_content)
            
            print(f"Successfully downloaded {output_filename} ({len(file_content)} bytes)")
        else:
            print("Could not find base64 data in output.")
            print("Output was:", output)
            
    except Exception as e:
        print(f"Error processing output: {e}")
        print("Output was:", output)

if __name__ == "__main__":
    download_presentation()
