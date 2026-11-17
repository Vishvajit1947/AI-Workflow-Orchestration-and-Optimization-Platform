"""
File operation utilities for workspace management.

Low-level async file I/O operations with proper error handling,
encoding detection, and resource management.
"""

import asyncio
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
import aiofiles.os

from .exceptions import FileOperationError, WorkspaceQuotaExceededError


class FileOperations:
    """Low-level file I/O utilities."""

    DEFAULT_ENCODING = "utf-8"
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB default

    @staticmethod
    async def read_text(path: Path, encoding: str = DEFAULT_ENCODING) -> str:
        """
        Read text file content.

        Args:
            path: Absolute file path
            encoding: Text encoding (default: utf-8)

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If file doesn't exist
            FileOperationError: If read fails
        """
        try:
            async with aiofiles.open(path, "r", encoding=encoding) as f:
                return await f.read()
        except FileNotFoundError:
            raise
        except Exception as e:
            raise FileOperationError(f"Failed to read file {path}: {e}") from e

    @staticmethod
    async def read_bytes(path: Path) -> bytes:
        """
        Read binary file content.

        Args:
            path: Absolute file path

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
            FileOperationError: If read fails
        """
        try:
            async with aiofiles.open(path, "rb") as f:
                return await f.read()
        except FileNotFoundError:
            raise
        except Exception as e:
            raise FileOperationError(f"Failed to read file {path}: {e}") from e

    @staticmethod
    async def write_text(
        path: Path,
        content: str,
        encoding: str = DEFAULT_ENCODING,
        max_size: Optional[int] = None,
    ) -> None:
        """
        Write text file content.

        Args:
            path: Absolute file path
            content: Text content to write
            encoding: Text encoding (default: utf-8)
            max_size: Maximum file size in bytes (None for no limit)

        Raises:
            WorkspaceQuotaExceededError: If content exceeds max_size
            FileOperationError: If write fails
        """
        # Check size limit
        if max_size is not None:
            content_bytes = content.encode(encoding)
            if len(content_bytes) > max_size:
                raise WorkspaceQuotaExceededError(
                    f"File size {len(content_bytes)} exceeds limit {max_size}"
                )

        try:
            async with aiofiles.open(path, "w", encoding=encoding) as f:
                await f.write(content)
        except Exception as e:
            raise FileOperationError(f"Failed to write file {path}: {e}") from e

    @staticmethod
    async def write_bytes(
        path: Path, content: bytes, max_size: Optional[int] = None
    ) -> None:
        """
        Write binary file content.

        Args:
            path: Absolute file path
            content: Binary content to write
            max_size: Maximum file size in bytes (None for no limit)

        Raises:
            WorkspaceQuotaExceededError: If content exceeds max_size
            FileOperationError: If write fails
        """
        # Check size limit
        if max_size is not None and len(content) > max_size:
            raise WorkspaceQuotaExceededError(
                f"File size {len(content)} exceeds limit {max_size}"
            )

        try:
            async with aiofiles.open(path, "wb") as f:
                await f.write(content)
        except Exception as e:
            raise FileOperationError(f"Failed to write file {path}: {e}") from e

    @staticmethod
    async def ensure_directory(path: Path) -> None:
        """
        Create directory and all parent directories if they don't exist.

        Args:
            path: Absolute directory path

        Raises:
            FileOperationError: If directory creation fails
        """
        try:
            await aiofiles.os.makedirs(path, exist_ok=True)
        except Exception as e:
            raise FileOperationError(
                f"Failed to create directory {path}: {e}"
            ) from e

    @staticmethod
    async def delete_path(path: Path, recursive: bool = False) -> None:
        """
        Delete file or directory.

        Args:
            path: Absolute path to delete
            recursive: If True, delete directories recursively

        Raises:
            FileNotFoundError: If path doesn't exist
            FileOperationError: If deletion fails
        """
        try:
            if not await aiofiles.os.path.exists(path):
                raise FileNotFoundError(f"Path does not exist: {path}")

            if await aiofiles.os.path.isdir(path):
                if not recursive:
                    await aiofiles.os.rmdir(path)
                else:
                    # Use shutil.rmtree via run_in_executor for recursive delete
                    import shutil

                    await asyncio.get_event_loop().run_in_executor(
                        None, shutil.rmtree, path
                    )
            else:
                await aiofiles.os.remove(path)
        except FileNotFoundError:
            raise
        except Exception as e:
            raise FileOperationError(f"Failed to delete {path}: {e}") from e

    @staticmethod
    async def move_path(source: Path, destination: Path) -> None:
        """
        Move/rename file or directory.

        Args:
            source: Source path
            destination: Destination path

        Raises:
            FileNotFoundError: If source doesn't exist
            FileOperationError: If move fails
        """
        try:
            if not await aiofiles.os.path.exists(source):
                raise FileNotFoundError(f"Source does not exist: {source}")

            await aiofiles.os.rename(source, destination)
        except FileNotFoundError:
            raise
        except Exception as e:
            raise FileOperationError(
                f"Failed to move {source} to {destination}: {e}"
            ) from e

    @staticmethod
    async def get_file_info(path: Path) -> dict:
        """
        Get file metadata.

        Args:
            path: Absolute file path

        Returns:
            Dictionary with file metadata

        Raises:
            FileNotFoundError: If file doesn't exist
            FileOperationError: If stat fails
        """
        try:
            stat = await aiofiles.os.stat(path)
            is_dir = await aiofiles.os.path.isdir(path)

            return {
                "path": str(path),
                "name": path.name,
                "is_directory": is_dir,
                "size_bytes": stat.st_size if not is_dir else 0,
                "created_at": datetime.fromtimestamp(stat.st_ctime),
                "updated_at": datetime.fromtimestamp(stat.st_mtime),
            }
        except FileNotFoundError:
            raise
        except Exception as e:
            raise FileOperationError(f"Failed to get info for {path}: {e}") from e

    @staticmethod
    async def list_directory(path: Path) -> list[dict]:
        """
        List directory contents with metadata.

        Args:
            path: Absolute directory path

        Returns:
            List of file/directory metadata dictionaries

        Raises:
            FileNotFoundError: If directory doesn't exist
            FileOperationError: If listing fails
        """
        try:
            if not await aiofiles.os.path.exists(path):
                raise FileNotFoundError(f"Directory does not exist: {path}")

            if not await aiofiles.os.path.isdir(path):
                raise FileOperationError(f"Path is not a directory: {path}")

            entries = []
            for entry_name in await aiofiles.os.listdir(path):
                entry_path = path / entry_name
                try:
                    info = await FileOperations.get_file_info(entry_path)
                    entries.append(info)
                except Exception:
                    # Skip files we can't read (permissions, etc.)
                    continue

            return sorted(entries, key=lambda x: (not x["is_directory"], x["name"]))
        except FileNotFoundError:
            raise
        except Exception as e:
            raise FileOperationError(
                f"Failed to list directory {path}: {e}"
            ) from e

    @staticmethod
    async def calculate_hash(path: Path, algorithm: str = "sha256") -> str:
        """
        Calculate file content hash.

        Args:
            path: Absolute file path
            algorithm: Hash algorithm (sha256, md5, etc.)

        Returns:
            Hex digest of file hash

        Raises:
            FileNotFoundError: If file doesn't exist
            FileOperationError: If hash calculation fails
        """
        try:
            hasher = hashlib.new(algorithm)
            async with aiofiles.open(path, "rb") as f:
                while chunk := await f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except FileNotFoundError:
            raise
        except Exception as e:
            raise FileOperationError(
                f"Failed to calculate hash for {path}: {e}"
            ) from e

    @staticmethod
    async def calculate_directory_size(path: Path) -> int:
        """
        Calculate total size of directory and all contents.

        Args:
            path: Absolute directory path

        Returns:
            Total size in bytes

        Raises:
            FileNotFoundError: If directory doesn't exist
            FileOperationError: If calculation fails
        """
        try:
            if not await aiofiles.os.path.exists(path):
                raise FileNotFoundError(f"Directory does not exist: {path}")

            total_size = 0

            async def walk_dir(current_path: Path):
                nonlocal total_size
                try:
                    for entry_name in await aiofiles.os.listdir(current_path):
                        entry_path = current_path / entry_name
                        if await aiofiles.os.path.isdir(entry_path):
                            await walk_dir(entry_path)
                        else:
                            stat = await aiofiles.os.stat(entry_path)
                            total_size += stat.st_size
                except (PermissionError, OSError):
                    # Skip directories/files we can't access
                    pass

            await walk_dir(path)
            return total_size
        except FileNotFoundError:
            raise
        except Exception as e:
            raise FileOperationError(
                f"Failed to calculate size for {path}: {e}"
            ) from e

    @staticmethod
    async def build_tree(
        path: Path, max_depth: Optional[int] = None, current_depth: int = 0
    ) -> dict:
        """
        Build directory tree structure.

        Args:
            path: Absolute directory path
            max_depth: Maximum depth to traverse (None for unlimited)
            current_depth: Current recursion depth (internal)

        Returns:
            Tree structure as nested dict

        Raises:
            FileNotFoundError: If path doesn't exist
            FileOperationError: If tree building fails
        """
        try:
            if not await aiofiles.os.path.exists(path):
                raise FileNotFoundError(f"Path does not exist: {path}")

            info = await FileOperations.get_file_info(path)
            tree = {
                "name": info["name"],
                "path": str(path),
                "is_directory": info["is_directory"],
                "size_bytes": info["size_bytes"],
            }

            if info["is_directory"]:
                if max_depth is None or current_depth < max_depth:
                    children = []
                    for entry_name in await aiofiles.os.listdir(path):
                        entry_path = path / entry_name
                        try:
                            child_tree = await FileOperations.build_tree(
                                entry_path, max_depth, current_depth + 1
                            )
                            children.append(child_tree)
                        except Exception:
                            # Skip inaccessible entries
                            continue

                    tree["children"] = sorted(
                        children, key=lambda x: (not x["is_directory"], x["name"])
                    )
                else:
                    tree["children"] = []

            return tree
        except FileNotFoundError:
            raise
        except Exception as e:
            raise FileOperationError(f"Failed to build tree for {path}: {e}") from e
