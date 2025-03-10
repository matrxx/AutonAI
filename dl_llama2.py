import requests
import time
import json

def download_model(model_name):
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
                        if 'status' in progress:
                            print(f"Status: {progress['status']}")
                        if 'completed' in progress and 'total' in progress:
                            percent = (progress['completed'] / progress['total']) * 100
                            print(f"Progress: {percent:.2f}% ({progress['completed']}/{progress['total']})")
                    except:
                        print(f"Progress update: {line}")
            
            print(f"Download of {model_name} complete!")
            return True
        else:
            print(f"Failed to start download: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"Error during download: {str(e)}")
        return False

if __name__ == "__main__":
    model = "llama2:13b"
    print(f"Starting download of {model}...")
    download_model(model)
    print("If download was successful, you can now use this model with your agent")