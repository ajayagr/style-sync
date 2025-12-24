from abc import ABC, abstractmethod
from typing import Iterator, NamedTuple, Optional
import io

class FileItem(NamedTuple):
    name: str
    is_dir: bool
    size: Optional[int] = None
    path: str = "" # Full path or ID relative to provider root

class StorageProvider(ABC):
    @abstractmethod
    def list_files(self, path: str) -> Iterator[FileItem]:
        """List files in the given path."""
        pass

    @abstractmethod
    def read_file(self, path: str) -> bytes:
        """Read content of a file."""
        pass

    @abstractmethod
    def write_file(self, path: str, data: bytes) -> None:
        """Write content to a file."""
        pass

    @abstractmethod
    def delete_file(self, path: str) -> None:
        """Delete a file."""
        pass
    
    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if file or directory exists."""
        pass
    
    @abstractmethod
    def mkdir(self, path: str) -> None:
        """Create directory if not exists."""
        pass
