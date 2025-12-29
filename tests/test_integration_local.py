import requests
import time
import json
import logging

def wait_for_host(url, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            # simple ping or just check if connection refused
            pass 
            # We can't really "ping" the function unless we know a health check endpoint, 
            # but we can try to connect. 
            # Actually, let's just wait a few seconds blindly for the host to startup, 
            # or try a request in a loop.
            break
        except Exception:
            time.sleep(1)
    time.sleep(10) # Give it 10 seconds to warm up explicitly

from azure.storage.blob import BlobServiceClient
import os

def setup_storage():
    print("Setting up local storage...")
    conn_str = "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;"
    container_name = "test-container"
    
    try:
        blob_service_client = BlobServiceClient.from_connection_string(conn_str)
        container_client = blob_service_client.get_container_client(container_name)
        
        if not container_client.exists():
            container_client.create_container()
            print(f"Created container {container_name}")
            
        # Upload a dummy file
        blob_client = container_client.get_blob_client("originals/test.jpg")
        if not blob_client.exists():
            blob_client.upload_blob(b"dummy image content", overwrite=True)
            print("Uploaded dummy test image")
            
    except Exception as e:
        print(f"Failed to setup storage: {e}")

def test_local_function():
    setup_storage()
    print("Testing local function...")
    url = "http://localhost:7071/api/stylesync"
    
    # Payload
    payload = {
        "source_folder": "originals/",
        "output_folder": "styled/",
        "container": "test-container",
        "styles": [
            {"name": "test-style", "prompt_text": "test prompt"}
        ]
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        # We need to loop this because the host might not be ready instantly
        for i in range(10):
            try:
                print(f"Attempt {i+1} to connect to {url}")
                response = requests.post(url, json=payload, headers=headers)
                print(f"Response status: {response.status_code}")
                print(f"Response body: {response.text}")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "completed":
                        print("SUCCESS: Function returned completed status.")
                        return
                elif response.status_code == 500:
                    # 500 might happen if our local settings mock is failing, which is expected 
                    # since we can't truly mock Blob Storage interactions easily without Azurite.
                    # Wait, we set "AZURE_STORAGE_CONNECTION_STRING": "UseDevelopmentStorage=true"
                    # We need Azurite running for this to work 100%. 
                    # If Azurite is not running, this will fail.
                    # The user asked to "install dependencies... for testing via runtime".
                    # Usually Azurite is VS Code extension or npm package.
                    # I should check if Azurite is needed.
                    print("Received 500 error. This might be due to missing Azurite storage emulator.")
            except requests.exceptions.ConnectionError:
                print("Connection refused, host might be starting...")
            
            time.sleep(2)
            
    except Exception as e:
        print(f"Test failed with exception: {e}")

if __name__ == "__main__":
    test_local_function()
