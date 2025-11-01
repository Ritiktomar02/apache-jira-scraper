"""
Apache Jira Scraper package.

A robust web scraping system for extracting public issue data
from Apache's Jira instance and transforming it into LLM training data.
"""

__version__ = '1.0.0'
__author__ = 'Your Name'
__description__ = 'Apache Jira Scraper for LLM Training Data'

from .config import Config, load_config
from .scraper import JiraScraper
from .state_manager import GlobalStateManager, StateManager
from .transformer import JiraTransformer

__all__ = [
    'Config',
    'load_config',
    'JiraScraper',
    'StateManager',
    'GlobalStateManager',
    'JiraTransformer',
]