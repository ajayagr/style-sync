import msal
import sys
import logging
import time

# Use the "Microsoft Graph PowerShell" public client ID as a default for testing/scripts
# Is widely known and allows Device Code Flow for public use.
# Alternatively, user can provide their own.
DEFAULT_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e" 
AUTHORITY_URL = "https://login.microsoftonline.com/common"
SCOPES = ["Files.ReadWrite.All", "User.Read"]

def get_onedrive_token(client_id=None):
    """
    Authenticates using MSAL Device Code Flow.
    Returns the access token or None on failure.
    """
    cid = client_id or DEFAULT_CLIENT_ID
    app = msal.PublicClientApplication(cid, authority=AUTHORITY_URL)

    # 1. Attempt silent acquisition (cache) - simplified here, 
    # normally we'd need a token cache persistence.
    # For now, just do fresh login or checking accounts if in memory (won't persist across runs without serialization).
    # Since this is a CLI run, we likely always need to auth unless we save cache to disk.
    
    # Let's initiate device flow
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        print(f"Failed to create device flow. Error: {flow.get('error')}")
        return None

    print("\n" + "="*60)
    print("OneDrive Authentication Required")
    print(flow["message"])
    print("="*60 + "\n")
    
    result = app.acquire_token_by_device_flow(flow)
    
    if "access_token" in result:
        print("\nAuthentication Successful!")
        return result["access_token"]
    else:
        print(f"\nAuthentication Failed: {result.get('error')}")
        print(result.get("error_description"))
        return None
