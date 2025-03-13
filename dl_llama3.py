import requests
import time
import json
import argparse
import sys

def download_model(model_name, show_progress=True):
    print(f"Attempting to download model: {model_name}")
    
    try:
        # The pull endpoint downloads a model
        response = requests.post(
            'http://localhost:11434/api/pull',
            json={'name': model_name},
            stream=True  # Important for streaming the download progress
        )
        
        # Process the streaming response to show download progress
        if response.status_code == 200:
            print(f"Download of {model_name} started...")
            
            for line in response.iter_lines():
                if line:
                    try:
                        progress = json.loads(line)
                        
                        # Display different types of progress information
                        if 'status' in progress:
                            print(f"Status: {progress['status']}")
                        
                        if 'digest' in progress:
                            print(f"Model digest: {progress['digest']}")
                            
                        if 'completed' in progress and 'total' in progress:
                            if progress['total'] > 0:  # Avoid division by zero
                                percent = (progress['completed'] / progress['total']) * 100
                                
                                # Create a progress bar if showing progress
                                if show_progress:
                                    bar_length = 50
                                    filled_length = int(bar_length * progress['completed'] // progress['total'])
                                    bar = '█' * filled_length + '░' * (bar_length - filled_length)
                                    
                                    # Calculate download speed
                                    if 'download_speed' in progress:
                                        speed = format_size(progress['download_speed']) + "/s"
                                    else:
                                        speed = "N/A"
                                    
                                    # Format sizes for display
                                    completed = format_size(progress['completed'])
                                    total = format_size(progress['total'])
                                    
                                    # Clear line and print progress
                                    sys.stdout.write(f"\r|{bar}| {percent:.1f}% ({completed}/{total}) Speed: {speed}")
                                    sys.stdout.flush()
                                else:
                                    print(f"Progress: {percent:.2f}% ({progress['completed']}/{progress['total']})")
                    except json.JSONDecodeError:
                        print(f"Progress update: {line}")
            
            print("\nDownload of {model_name} complete!")
            return True
        else:
            print(f"Failed to start download: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to Ollama. Make sure Ollama is running at http://localhost:11434")
        return False
    except Exception as e:
        print(f"Error during download: {str(e)}")
        return False

def format_size(size_bytes):
    """Format size in bytes to human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024 or unit == 'TB':
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024

def check_model_exists(model_name):
    """Check if model already exists in Ollama"""
    try:
        response = requests.get('http://localhost:11434/api/tags')
        if response.status_code == 200:
            models = response.json().get('models', [])
            for model in models:
                if model.get('name') == model_name:
                    return True
        return False
    except:
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download Llama 3 70B model for Ollama")
    parser.add_argument("--model", default="llama3:70b", help="Model name to download (default: llama3:70b)")
    args = parser.parse_args()
    
    model = args.model
    
    # Check if Ollama is running
    try:
        requests.get('http://localhost:11434/api/version')
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to Ollama. Make sure Ollama is running at http://localhost:11434")
        sys.exit(1)
    
    # Check if model already exists
    if check_model_exists(model):
        print(f"Model {model} is already downloaded.")
        user_input = input("Do you want to download it again? (y/n): ")
        if user_input.lower() != 'y':
            print("Download canceled.")
            sys.exit(0)
    
    print(f"Starting download of {model}...")
    success = download_model(model)
    
    if success:
        print(f"\nModel {model} has been successfully downloaded.")
        print("You can now update your agent.py to use this model by changing:")
        print('call_llm(messages, model="llama3:70b", timeout=300)')
        print("\nNote: This model requires more VRAM than llama2:13b. Make sure your system has adequate resources.")
    else:
        print(f"\nFailed to download {model}. Please check your connection and try again.")