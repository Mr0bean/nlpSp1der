"""
File utility functions.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict


def ensure_directory(path: str) -> Path:
    """
    Ensure directory exists, create if it doesn't.
    
    Args:
        path: Directory path
        
    Returns:
        Path object
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def save_json(data: Any, file_path: str, indent: int = 2) -> None:
    """
    Save data to JSON file.
    
    Args:
        data: Data to save
        file_path: File path
        indent: JSON indentation
    """
    path = Path(file_path)
    ensure_directory(path.parent)
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def load_json(file_path: str, default: Any = None) -> Any:
    """
    Load data from JSON file.
    
    Args:
        file_path: File path
        default: Default value if file doesn't exist
        
    Returns:
        Loaded data or default value
    """
    path = Path(file_path)
    
    if not path.exists():
        return default
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def get_project_root() -> Path:
    """
    Get the project root directory.
    
    Returns:
        Project root path
    """
    current = Path(__file__)
    for parent in current.parents:
        if (parent / "requirements.txt").exists() or (parent / "pyproject.toml").exists():
            return parent
    return current.parent.parent.parent  # Fallback