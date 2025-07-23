# utils.py
import os
import datetime
import hashlib
import json
import requests # For web requests
import shutil # For file operations (e.g., download)

def get_file_icon(file_path):
    """
    Returns a suitable icon (emoji) for a given file path.
    """
    if os.path.isdir(file_path):
        return "📁"  # Folder icon
    
    file_extension = os.path.splitext(file_path)[1].lower()
    
    # Common file types
    if file_extension in [".txt", ".log", ".md"]:
        return "📄"  # Text file
    elif file_extension in [".pdf"]:
        return "📃"  # PDF
    elif file_extension in [".doc", ".docx"]:
        return "📝"  # Word document
    elif file_extension in [".xls", ".xlsx"]:
        return "📊"  # Excel spreadsheet
    elif file_extension in [".ppt", ".pptx"]:
        return " presentation"  # PowerPoint presentation
    elif file_extension in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico"]:
        return "🖼️"  # Image file
    elif file_extension in [".mp3", ".wav", ".flac"]:
        return "🎵"  # Audio file
    elif file_extension in [".mp4", ".avi", ".mkv"]:
        return "🎬"  # Video file
    elif file_extension in [".zip", ".rar", ".7z", ".tar", ".gz"]:
        return "📦"  # Archive file
    elif file_extension in [".exe", ".msi"]:
        return "⚙️"  # Executable file
    elif file_extension in [".py", ".js", ".html", ".css", ".json", ".xml"]:
        return "📄"  # Code file (generic)
    elif file_extension in [".dll", ".sys"]:
        return "🔗" # System/DLL file
    else:
        return "❓"  # Unknown file type

def format_size(size_in_bytes):
    """
    Formats file size into human-readable units (B, KB, MB, GB, TB).
    """
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    elif size_in_bytes < 1024**2:
        return f"{size_in_bytes / 1024:.2f} KB"
    elif size_in_bytes < 1024**3:
        return f"{size_in_bytes / (1024**2):.2f} MB"
    elif size_in_bytes < 1024**4:
        return f"{size_in_bytes / (1024**3):.2f} GB"
    else:
        return f"{size_in_bytes / (1024**4):.2f} TB"

def get_file_details(file_path):
    """
    Retrieves details for a given file or directory.
    Returns a dictionary with 'name', 'path', 'is_dir', 'size', 'formatted_size', 'modified_time', 'icon'.
    Returns None if path does not exist or cannot be accessed.
    """
    try:
        if not os.path.exists(file_path):
            return None

        name = os.path.basename(file_path)
        is_dir = os.path.isdir(file_path)
        
        size = 0
        formatted_size = ""
        if not is_dir:
            size = os.path.getsize(file_path)
            formatted_size = format_size(size)

        modified_timestamp = os.path.getmtime(file_path)
        modified_time = datetime.fromtimestamp(modified_timestamp).strftime('%Y-%m-%d %H:%M')
        
        icon = get_file_icon(file_path)

        return {
            'name': name,
            'path': file_path,
            'is_dir': is_dir,
            'size': size,
            'formatted_size': formatted_size,
            'modified_time': modified_time,
            'icon': icon
        }
    except Exception as e:
        print(f"Error getting file details for {file_path}: {e}")
        return None

def calculate_file_hash(file_path, block_size=65536):
    """
    Calculates the SHA256 hash of a file.
    Returns the hash string or None if an error occurs (e.g., permission denied).
    """
    hasher = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                hasher.update(block)
        return hasher.hexdigest()
    except (IOError, OSError) as e:
        # print(f"Error calculating hash for '{file_path}': {e}")
        return None
    except Exception as e:
        # print(f"An unexpected error occurred while hashing '{file_path}': {e}")
        return None

def get_github_file_content(url):
    """
    Fetches the raw content of a file from a GitHub raw URL.
    Returns the content as a string, or None if an error occurs.
    """
    try:
        response = requests.get(url, timeout=10) # 10 second timeout
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching content from {url}: {e}")
        return None

def download_file(url, destination_path):
    """
    Downloads a file from a URL to a specified destination path.
    Returns True on success, False on failure.
    """
    try:
        with requests.get(url, stream=True, timeout=30) as r: # 30 second timeout for download
            r.raise_for_status()
            with open(destination_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error downloading file from {url} to {destination_path}: {e}")
        return False

