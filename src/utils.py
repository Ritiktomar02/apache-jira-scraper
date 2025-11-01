"""
Utility functions for the scraper.

Includes logging setup, text cleaning, validation, and helper functions.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import html2text
from bs4 import BeautifulSoup


def setup_logging(config) -> logging.Logger:
    """
    Set up logging with file and console handlers.
    
    Args:
        config: Configuration object
        
    Returns:
        Configured logger
    """
    # Create logs directory
    log_dir = Path(config.get('logging.log_dir', 'logs'))
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate log filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d')
    log_file = log_dir / f"scraper_{timestamp}.log"
    
    # Configure logging
    log_level = getattr(logging, config.get('logging.level', 'INFO').upper())
    log_format = config.get(
        'logging.format',
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create formatter
    formatter = logging.Formatter(log_format)
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # Console handler with colors (if colorlog available)
    try:
        import colorlog
        console_handler = colorlog.StreamHandler()
        console_handler.setLevel(log_level)
        console_formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(levelname)-8s%(reset)s %(message)s',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(console_formatter)
    except ImportError:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
    
    # Configure root logger
    logger = logging.getLogger('jira_scraper')
    logger.setLevel(log_level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Suppress noisy libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    logger.info(f"Logging initialized. Log file: {log_file}")
    return logger


def clean_html(html_content: str, strip_html: bool = True) -> str:
    """
    Clean HTML content and extract plain text.
    
    Args:
        html_content: HTML string to clean
        strip_html: Whether to strip HTML tags
        
    Returns:
        Cleaned plain text
    """
    if not html_content:
        return ""
    
    if not strip_html:
        return html_content
    
    try:
        # Parse HTML
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'meta', 'link']):
            element.decompose()
        
        # Convert to plain text using html2text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.ignore_emphasis = False
        h.body_width = 0  # Don't wrap lines
        
        text = h.handle(str(soup))
        
        # Clean up excessive whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)  # Multiple newlines to double
        text = re.sub(r' +', ' ', text)  # Multiple spaces to single
        text = text.strip()
        
        return text
        
    except Exception as e:
        # Fallback to simple tag stripping
        return BeautifulSoup(html_content, 'lxml').get_text(strip=True)


def clean_text(text: str, max_length: Optional[int] = None) -> str:
    """
    Clean and normalize text content.
    
    Args:
        text: Text to clean
        max_length: Maximum length (truncate if longer)
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # Truncate if needed
    if max_length and len(text) > max_length:
        text = text[:max_length] + "..."
    
    return text


def safe_get(data: Dict, *keys, default=None) -> Any:
    """
    Safely get nested dictionary value.
    
    Args:
        data: Dictionary to query
        *keys: Keys to traverse
        default: Default value if not found
        
    Returns:
        Value at nested key or default
        
    Example:
        >>> safe_get(issue, 'fields', 'reporter', 'displayName', default='Unknown')
    """
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return default
        else:
            return default
    return current if current is not None else default


def validate_json_structure(data: Dict, required_fields: list) -> bool:
    """
    Validate that JSON has required fields.
    
    Args:
        data: Dictionary to validate
        required_fields: List of required field names
        
    Returns:
        True if valid, False otherwise
    """
    for field in required_fields:
        if field not in data or data[field] is None:
            return False
    return True


def format_timestamp(timestamp: Optional[str]) -> Optional[str]:
    """
    Format Jira timestamp to ISO format.
    
    Args:
        timestamp: Jira timestamp string
        
    Returns:
        ISO formatted timestamp or None
    """
    if not timestamp:
        return None
    
    try:
        # Jira uses ISO 8601 format
        return timestamp
    except Exception:
        return None


def calculate_file_size(file_path: str) -> str:
    """
    Calculate human-readable file size.
    
    Args:
        file_path: Path to file
        
    Returns:
        Formatted file size string
    """
    try:
        size = Path(file_path).stat().st_size
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        
        return f"{size:.2f} TB"
    except Exception:
        return "Unknown"


def write_jsonl(data: Dict, file_path: str, append: bool = True) -> None:
    """
    Write data to JSONL file.
    
    Args:
        data: Dictionary to write
        file_path: Output file path
        append: Whether to append or overwrite
    """
    mode = 'a' if append else 'w'
    
    with open(file_path, mode, encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
        f.write('\n')


def read_jsonl(file_path: str) -> list:
    """
    Read JSONL file.
    
    Args:
        file_path: Input file path
        
    Returns:
        List of dictionaries
    """
    data = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    
    return data


def create_progress_message(
    current: int,
    total: int,
    prefix: str = "",
    suffix: str = ""
) -> str:
    """
    Create progress message.
    
    Args:
        current: Current count
        total: Total count
        prefix: Prefix string
        suffix: Suffix string
        
    Returns:
        Formatted progress message
    """
    percentage = (current / total * 100) if total > 0 else 0
    return f"{prefix} {current}/{total} ({percentage:.1f}%) {suffix}".strip()


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    
    return filename


def get_current_timestamp() -> str:
    """
    Get current timestamp as string.
    
    Returns:
        ISO formatted timestamp
    """
    return datetime.now().isoformat()


def parse_jira_date(date_str: Optional[str]) -> Optional[str]:
    """
    Parse Jira date string.
    
    Args:
        date_str: Jira date string
        
    Returns:
        Parsed date or None
    """
    if not date_str:
        return None
    
    try:
        # Jira typically uses ISO 8601
        return date_str
    except Exception:
        return None