import os
import requests
import zipfile
import pandas as pd
from typing import Optional

def download_file(url: str, output_path: Optional[str] = None) -> str:
    """
    Downloads a file from a URL.
    
    Args:
        url: The URL to download from.
        output_path: The path to save the file to. If None, infers from URL.
        
    Returns:
        The absolute path to the downloaded file.
    """
    if not output_path:
        filename = url.split('/')[-1]
        # Remove query parameters if present
        if '?' in filename:
            filename = filename.split('?')[0]
        output_path = os.path.join(os.getcwd(), "downloads", filename)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print(f"Downloading {url} to {output_path}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, stream=True, headers=headers)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return os.path.abspath(output_path)
    except Exception as e:
        return f"Error downloading file: {str(e)}"

def unzip_file(zip_path: str, extract_to: Optional[str] = None) -> str:
    """
    Unzips a zip file.
    
    Args:
        zip_path: Path to the zip file.
        extract_to: Directory to extract to. If None, creates a folder with the zip name.
        
    Returns:
        The directory containing the extracted files.
    """
    if not extract_to:
        extract_to = os.path.splitext(zip_path)[0]
        
    os.makedirs(extract_to, exist_ok=True)
    
    print(f"Extracting {zip_path} to {extract_to}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
        
    return os.path.abspath(extract_to)

def read_csv_head(csv_path: str, n: int = 5) -> str:
    """
    Reads the first n rows of a CSV file.
    
    Args:
        csv_path: Path to the CSV file.
        n: Number of rows to read.
        
    Returns:
        Markdown string of the dataframe head.
    """
    try:
        df = pd.read_csv(csv_path, nrows=n)
        return df.to_markdown(index=False)
    except Exception as e:
        return f"Error reading CSV: {str(e)}"

def list_files(directory: str) -> str:
    """
    Lists files in a directory recursively.
    
    Args:
        directory: The directory to list.
        
    Returns:
        List of file paths.
    """
    files_list = []
    for root, _, files in os.walk(directory):
        for file in files:
            files_list.append(os.path.join(root, file))
    return "\n".join(files_list)
