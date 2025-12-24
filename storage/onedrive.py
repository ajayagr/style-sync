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

    def get_user_name(self) -> str:
        """Fetches the display name of the authenticated user."""
        try:
            url = f"{self.GRAPH_API}/me"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return data.get("displayName", "OneDrive User")
        except Exception as e:
            print(f"Warning: Could not fetch OneDrive username: {e}")
            return "OneDrive User"

    def _clean_path(self, path: str) -> str:
        """
        Standardizes path by removing API prefixes.
        Graph API often returns paths like /drive/root:/Path/To/File.
        We want just Path/To/File.
        """
        if path.startswith("/drive/root:"):
            path = path[len("/drive/root:"):]
        return path.strip("/")

    def _build_api_url(self, path: str, is_content: bool = False, is_children: bool = False) -> str:
        """
        Singleton function to construct graph API URLs from paths.
        Handles root checks and consistent formatting.
        """
        clean = self._clean_path(path)
        
        # Base URL construction
        if not clean:
            # Root folder
            base_url = f"{self.GRAPH_API}/me/drive/root"
        else:
            # Sub-item
            base_url = f"{self.GRAPH_API}/me/drive/root:/{clean}"

        # Append modifiers
        if is_children:
            # For root, it's /children. For others, it's :/children
            if not clean:
                return f"{base_url}/children"
            else:
                return f"{base_url}:/children"
        
        if is_content:
            # For root content (doesn't validly exist mostly, but consistent logic)
            # For files: :/content
            if not clean:
                 raise ValueError("Cannot read content of root.")
            return f"{base_url}:/content"

        return base_url

    def _get_drive_item(self, path: str):
        url = self._build_api_url(path)
        response = requests.get(url, headers=self.headers)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def list_files(self, path: str) -> Iterator[FileItem]:
        url = self._build_api_url(path, is_children=True)

        while url:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 404:
                return 
            response.raise_for_status()
            data = response.json()
            
            for item in data.get("value", []):
                is_dir = "folder" in item
                # Make sure we construct a path that this class can handle later
                # API returns parentReference.path like /drive/root:/Folder
                parent_path = item.get("parentReference", {}).get("path", "")
                full_path = f"{parent_path}/{item['name']}"
                
                yield FileItem(
                    name=item["name"],
                    is_dir=is_dir,
                    size=item.get("size") if not is_dir else None,
                    path=full_path 
                )
            
            url = data.get("@odata.nextLink")

    def read_file(self, path: str) -> bytes:
        url = self._build_api_url(path, is_content=True)
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.content

    def write_file(self, path: str, data: bytes) -> None:
        url = self._build_api_url(path, is_content=True)
        response = requests.put(url, headers=self.headers, data=data)
        response.raise_for_status()

    def delete_file(self, path: str) -> None:
        url = self._build_api_url(path)
        response = requests.delete(url, headers=self.headers)
        if response.status_code == 404:
            return
        response.raise_for_status()

    def exists(self, path: str) -> bool:
        return self._get_drive_item(path) is not None

    def mkdir(self, path: str) -> None:
        parts = self._clean_path(path).split("/")
        if not parts or parts == [""]: return

        parent_path = "/".join(parts[:-1])
        folder_name = parts[-1]
        
        url = self._build_api_url(parent_path, is_children=True)
        
        payload = {
            "name": folder_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "replace" 
        }
        requests.post(url, headers=self.headers, json=payload)
