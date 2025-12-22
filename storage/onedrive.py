import requests
import os
from typing import Iterator
from .base import StorageProvider, FileItem

class OneDriveStorageProvider(StorageProvider):
    GRAPH_API = "https://graph.microsoft.com/v1.0"
    
    def __init__(self, access_token: str):
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    def _clean_path(self, path: str) -> str:
        # Graph API returns paths like "/drive/root:/Folder/File"
        # We need to strip the prefix "/drive/root:" when constructing our own URLs
        # which are based on /me/drive/root:/...
        if path.startswith("/drive/root:"):
            return path[len("/drive/root:"):]
        return path.strip("/")

    def _get_drive_item(self, path: str):
        clean_path = self._clean_path(path)
        # Handle root specially
        if not clean_path or clean_path == "/":
            url = f"{self.GRAPH_API}/me/drive/root"
        else:
            url = f"{self.GRAPH_API}/me/drive/root:/{clean_path}"
        
        response = requests.get(url, headers=self.headers)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def list_files(self, path: str) -> Iterator[FileItem]:
        clean_path = self._clean_path(path)
        if not clean_path or clean_path == "/":
            url = f"{self.GRAPH_API}/me/drive/root/children"
        else:
            url = f"{self.GRAPH_API}/me/drive/root:/{clean_path}:/children"

        while url:
            # ... (rest of loop logic is fine, but update the yield)
            response = requests.get(url, headers=self.headers)
            if response.status_code == 404:
                return 
            response.raise_for_status()
            data = response.json()
            
            for item in data.get("value", []):
                is_dir = "folder" in item
                # Capture the full API path for robust referencing, but clean it later
                full_api_path = item.get("parentReference", {}).get("path", "") + "/" + item["name"]
                yield FileItem(
                    name=item["name"],
                    is_dir=is_dir,
                    size=item.get("size") if not is_dir else None,
                    path=full_api_path 
                )
            
            url = data.get("@odata.nextLink")

    def read_file(self, path: str) -> bytes:
        clean_path = self._clean_path(path)
        url = f"{self.GRAPH_API}/me/drive/root:/{clean_path}:/content"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.content

    def write_file(self, path: str, data: bytes) -> None:
        clean_path = self._clean_path(path)
        url = f"{self.GRAPH_API}/me/drive/root:/{clean_path}:/content"
        
        response = requests.put(url, headers=self.headers, data=data)
        response.raise_for_status()

    def delete_file(self, path: str) -> None:
        # Need item ID or can use path
        clean_path = path.strip("/")
        url = f"{self.GRAPH_API}/me/drive/root:/{clean_path}"
        
        response = requests.delete(url, headers=self.headers)
        if response.status_code == 404:
            return
        response.raise_for_status()

    def exists(self, path: str) -> bool:
        return self._get_drive_item(path) is not None

    def mkdir(self, path: str) -> None:
        # Creating folder recursively is hard with single call, assume parent exists or use simple create?
        # Graph API 'create folder' is POST to parent's children.
        # Simple implementation: Try to create leaf folder.
        
        parts = path.strip("/").split("/")
        if not parts: return

        # This logic is complex for deep paths. 
        # For this tool, let's assume one level or flat structure for output mostly.
        # But to be safe, let's just attempt creation of the target folder in the parent.
        
        parent_path = "/".join(parts[:-1])
        folder_name = parts[-1]
        
        if not parent_path:
            url = f"{self.GRAPH_API}/me/drive/root/children"
        else:
            url = f"{self.GRAPH_API}/me/drive/root:/{parent_path}:/children"

        payload = {
            "name": folder_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "replace" # or "fail"
        }
        
        requests.post(url, headers=self.headers, json=payload)
