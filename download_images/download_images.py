"""
Marvel Trading Cards Image Downloader

This script downloads Marvel trading card images from markdown text and extracts character information.
It handles parallel downloads, error logging, and stores character information in a CSV file.
"""

import re
import os
import requests
import urllib.parse
from pathlib import Path
import concurrent.futures
import csv
from typing import List, Tuple
from queue import Queue
from dataclasses import dataclass

@dataclass
class DownloadResult:
    """
    Container for storing download operation results.
    
    Attributes:
        success (bool): Whether the download was successful
        character_name (str): Name of the Marvel character
        universe (str): Universe designation (e.g., Earth-616)
        year (str): Year of card publication
        pseudonym (str): Alternative name/alias of the character
        filename (str): Name of the downloaded file
        error (str): Error message if download failed
    """
    success: bool
    character_name: str = ""
    universe: str = ""
    year: str = ""
    pseudonym: str = ""
    filename: str = ""
    error: str = ""

def extract_pseudonym(markdown_line: str) -> str:
    """
    Extract character pseudonym from markdown image alt text.
    
    Args:
        markdown_line (str): Line of markdown text containing image information
        
    Returns:
        str or None: Extracted pseudonym if found, None otherwise
        
    Example:
        "[1. Super Harpreet Man] some text" -> "Super Harpreet Man"
    """
    pseudonym_match = re.search(r'\[\d+\.\s+([^\]]+)\]', markdown_line)
    return pseudonym_match.group(1).strip() if pseudonym_match else None

def clean_character_info(encoded_string: str, markdown_line: str = "") -> Tuple[str, str, str, str]:
    """
    Extract and clean character information from an encoded filename.
    
    Args:
        encoded_string (str): URL-encoded filename containing character information
        markdown_line (str): Original markdown line for additional context
        
    Returns:
        Tuple[str, str, str, str]: (character_name, universe, year, pseudonym)
        
    Example:
        "Spider-Man_(Earth-616)_from_Marvel_Masterpieces_1994" ->
        ("Spider-Man", "Earth-616", "1994", "Peter Parker")
    """
    # Decode URL-encoded string
    decoded = urllib.parse.unquote(encoded_string)
    
    # Extract year (1990s or 2000s)
    year_match = re.search(r'(199\d|20\d{2})', decoded)
    year = year_match.group(0) if year_match else "Unknown"
    
    # Extract universe designation
    universe_match = re.search(r'_\((Earth-[^)]+)\)', decoded)
    if universe_match:
        name_part = decoded.split('_(' + universe_match.group(1) + ')')[0]
        universe = universe_match.group(1)
    else:
        # Handle cases without explicit universe designation
        name_part = re.split(r'_from_Marvel_Masterpieces|_\(Mojoverse\)', decoded)[0]
        universe = "Unknown Universe"
    
    # Clean up character name and get pseudonym
    name = name_part.split('/')[-1].replace('_', ' ').strip()
    pseudonym = extract_pseudonym(markdown_line)
    
    return name, universe, year, pseudonym

def download_single_image(url_data: Tuple[str, str], output_dir: Path) -> DownloadResult:
    """
    Download a single Marvel trading card image and extract its information.
    
    Args:
        url_data (Tuple[str, str]): Tuple of (image_url, markdown_line)
        output_dir (Path): Directory to save downloaded images
        
    Returns:
        DownloadResult: Object containing download results and character information
    """
    url, markdown_line = url_data
    try:
        # Extract filename from URL
        filename = url.split('/')[-1]
        
        # Get character information
        character_name, universe, year, pseudonym = clean_character_info(filename, markdown_line)

        # Set up request headers to mimic browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Download image with timeout
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Save image to file
        image_path = output_dir / filename
        with open(image_path, 'wb') as img_file:
            img_file.write(response.content)

        # Print progress information
        print(f"Downloaded: {filename}")
        print(f"Character: {character_name} | Universe: {universe} | Year: {year} | Pseudonym: {pseudonym}")
        print("-" * 70)

        return DownloadResult(
            success=True,
            character_name=character_name,
            universe=universe,
            year=year,
            pseudonym=pseudonym or "",
            filename=filename
        )

    except Exception as e:
        # Handle any errors during download
        return DownloadResult(
            success=False,
            filename=filename if 'filename' in locals() else url.split('/')[-1],
            error=str(e)
        )

def download_marvel_images(markdown_text: str) -> None:
    """
    Download Marvel Masterpieces trading card images from markdown text in parallel.
    
    Args:
        markdown_text (str): Markdown text containing image URLs and information
    
    Creates:
        - Directory with downloaded images
        - CSV file with character information
        - Debug log file with error information
    """
    # Set up output directory and files
    output_dir = Path('marvel_masterpieces_images')
    output_dir.mkdir(exist_ok=True)

    debug_file = output_dir / 'debug_log.txt'
    info_file = output_dir / 'character_info.csv'

    # Extract URLs and their corresponding markdown lines
    url_data = []
    for line in markdown_text.split('\n'):
        # Find URLs in markdown text
        url_match = re.search(r'https://static\.wikia\.nocookie\.net/marveldatabase/images/[^\s\)"]+(?=[\s\)])', line)
        if url_match:
            # Remove revision information from URL
            url = url_match.group(0).split('/revision/')[0]
            url_data.append((url, line))

    # Remove duplicate URLs while preserving markdown line information
    url_data = list(set(url_data))

    # Initialize CSV file with headers
    with open(info_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Character Name", "Universe", "Year", "Pseudonym", "Filename"])

    # Use ThreadPoolExecutor for parallel downloads
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Create future objects for all downloads
        future_to_url = {
            executor.submit(download_single_image, url_info, output_dir): url_info[0]
            for url_info in url_data
        }
        
        # Process completed downloads as they finish
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append(DownloadResult(success=False, filename=url.split('/')[-1], error=str(e)))

    # Write successful downloads to CSV file
    with open(info_file, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for result in results:
            if result.success:
                writer.writerow([
                    result.character_name,
                    result.universe,
                    result.year,
                    result.pseudonym,
                    result.filename
                ])

    # Write error information to debug log
    with open(debug_file, 'w', encoding='utf-8') as f:
        f.write(f"Total URLs processed: {len(results)}\n\n")
        for result in results:
            if not result.success:
                f.write(f"Error with {result.filename}: {result.error}\n")

if __name__ == "__main__":
    # Read markdown file and start download process
    with open('Marvel Masterpieces (Trading Cards)  Marvel Database  Fandom.md', 'r', encoding='utf-8') as file:
        content = file.read()

    download_marvel_images(content)