import logging
import json
from unittest.mock import MagicMock, patch
import azure.functions as func
import sys
import os

# Add path to function code
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'StyleSyncFunction')))
import __init__ as my_func

def run_test():
    print("Starting Test...")
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('azure').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

    # Mock Request
    req_body = {
        "source_folder": "originals/",
        "output_folder": "styled/",
        "container": "test-container",
        "styles": [
            {"name": "test-style", "prompt_text": "test prompt"}
        ]
    }
    req = func.HttpRequest(
        method='POST',
        body=json.dumps(req_body).encode('utf-8'),
        url='/api/StyleSyncFunction',
        headers={'Content-Type': 'application/json'}
    )

    # Mock Environment
    with patch.dict(os.environ, {
        'AZURE_STORAGE_CONNECTION_STRING': 'DefaultEndpointsProtocol=https;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;',
        'AZURE_API_KEY': 'test-key',
        'AZURE_ENDPOINT_URL': 'http://test-api.com/generate'
    }):
        # Mock Blob Service - Patching the IMPORTED class in the module
        with patch.object(my_func, 'BlobServiceClient') as mock_blob_service:
            # Setup mocks
            mock_client_instance = mock_blob_service.from_connection_string.return_value
            mock_container_client = mock_client_instance.get_container_client.return_value
            mock_container_client.exists.return_value = True
            
            # Mock blobs
            mock_blob = MagicMock()
            mock_blob.name = "originals/test.jpg"
            mock_container_client.list_blobs.return_value = [mock_blob]
            
            mock_blob_client = mock_container_client.get_blob_client.return_value
            mock_blob_client.download_blob.return_value.readall.return_value = b"fake_image_data"
            mock_blob_client.exists.return_value = False

            # Mock Requests
            with patch('requests.post') as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.content = b"styled_image_data"

                # Run Function
                try:
                    resp = my_func.main(req)
                    print(f"Function returned status: {resp.status_code}")
                    resp_body = json.loads(resp.get_body())
                    # print("Response Body:", json.dumps(resp_body, indent=2))
                    
                    if resp.status_code == 200 and "styled/test-style/test.jpg" in resp_body['processed']:
                        print("SUCCESS: Test passed!")
                    else:
                        print("FAILURE: Validation failed.")
                except Exception as e:
                    print(f"FAILURE: Exception during execution: {e}")
                    import traceback
                    traceback.print_exc()

if __name__ == '__main__':
    run_test()
