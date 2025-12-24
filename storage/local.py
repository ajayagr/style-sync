from pathlib import Path
from typing import Iterator
from .base import StorageProvider, FileItem
import shutil

class LocalStorageProvider(StorageProvider):
    def __init__(self, root_path: str = "."):
        self.root = Path(root_path).resolve()
        
    def _resolve(self, path: str) -> Path:
        # Handle absolute paths if they match root, else append
        p = Path(path)
        if p.is_absolute():
            return p
        return self.root / path

    def list_files(self, path: str) -> Iterator[FileItem]:
        target = self._resolve(path)
        if not target.exists():
            return
            
        for item in target.iterdir():
            yield FileItem(
                name=item.name,
                is_dir=item.is_dir(),
                size=item.stat().st_size if item.is_file() else None,
                path=str(item)
            )

    def read_file(self, path: str) -> bytes:
        target = self._resolve(path)
        with open(target, "rb") as f:
            return f.read()

    def write_file(self, path: str, data: bytes) -> None:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as f:
            f.write(data)

    def delete_file(self, path: str) -> None:
        target = self._resolve(path)
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def mkdir(self, path: str) -> None:
        self._resolve(path).mkdir(parents=True, exist_ok=True)
