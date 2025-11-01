"""
Configuration management module.

This module handles loading, validating, and providing access to 
configuration parameters from config.yaml file.
"""

import os
from pathlib import Path
from typing import Any, Dict, List

import yaml


class Config:
    """
    Configuration manager that loads and validates config.yaml.
    
    Provides easy access to configuration parameters throughout the application.
    Validates required fields and provides sensible defaults.
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize configuration from YAML file.
        
        Args:
            config_path: Path to configuration file (default: config.yaml)
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file has invalid YAML syntax
            ValueError: If required config fields are missing
        """
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self._load_config()
        self._validate_config()
        self._create_directories()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}"
            )
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            try:
                self._config = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise yaml.YAMLError(
                    f"Error parsing config file {self.config_path}: {e}"
                )
    
    def _validate_config(self) -> None:
        """
        Validate required configuration fields.
        
        Raises:
            ValueError: If required fields are missing or invalid
        """
        required_sections = ['jira', 'scraping', 'output', 'logging']
        for section in required_sections:
            if section not in self._config:
                raise ValueError(
                    f"Required configuration section '{section}' is missing"
                )
        
        # Validate Jira config
        if 'base_url' not in self._config['jira']:
            raise ValueError("jira.base_url is required")
        
        if 'projects' not in self._config['jira'] or \
           not self._config['jira']['projects']:
            raise ValueError("jira.projects must contain at least one project")
        
        # Validate projects is a list
        if not isinstance(self._config['jira']['projects'], list):
            raise ValueError("jira.projects must be a list")
        
        # Validate numeric values are positive
        numeric_fields = [
            ('scraping', 'batch_size'),
            ('scraping', 'max_retries'),
            ('scraping', 'request_timeout'),
        ]
        
        for section, field in numeric_fields:
            value = self._config.get(section, {}).get(field)
            if value is not None and value <= 0:
                raise ValueError(f"{section}.{field} must be positive")
    
    def _create_directories(self) -> None:
        """Create required directories if they don't exist."""
        directories = [
            self.get('output.raw_data_dir'),
            self.get('output.processed_data_dir'),
            self.get('output.checkpoint_dir'),
            self.get('logging.log_dir'),
        ]
        
        for directory in directories:
            if directory:
                Path(directory).mkdir(parents=True, exist_ok=True)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            key: Configuration key in dot notation (e.g., 'jira.base_url')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
            
        Examples:
            >>> config.get('jira.base_url')
            'https://issues.apache.org/jira'
            >>> config.get('jira.projects')
            ['KAFKA', 'SPARK', 'HADOOP']
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    @property
    def jira_base_url(self) -> str:
        """Get Jira base URL."""
        return self.get('jira.base_url')
    
    @property
    def jira_projects(self) -> List[str]:
        """Get list of projects to scrape."""
        return self.get('jira.projects', [])
    
    @property
    def batch_size(self) -> int:
        """Get batch size for pagination."""
        return self.get('scraping.batch_size', 50)
    
    @property
    def max_retries(self) -> int:
        """Get maximum number of retries."""
        return self.get('scraping.max_retries', 5)
    
    @property
    def retry_delay(self) -> float:
        """Get initial retry delay in seconds."""
        return self.get('scraping.retry_delay', 2.0)
    
    @property
    def request_timeout(self) -> int:
        """Get request timeout in seconds."""
        return self.get('scraping.request_timeout', 30)
    
    @property
    def rate_limit_delay(self) -> int:
        """Get delay after rate limit in seconds."""
        return self.get('scraping.rate_limit_delay', 60)
    
    @property
    def log_level(self) -> str:
        """Get logging level."""
        return self.get('logging.level', 'INFO')
    
    @property
    def raw_data_dir(self) -> str:
        """Get raw data directory path."""
        return self.get('output.raw_data_dir', 'data/raw')
    
    @property
    def processed_data_dir(self) -> str:
        """Get processed data directory path."""
        return self.get('output.processed_data_dir', 'data/processed')
    
    @property
    def checkpoint_dir(self) -> str:
        """Get checkpoint directory path."""
        return self.get('output.checkpoint_dir', 'data/checkpoints')
    
    def __repr__(self) -> str:
        """String representation of config."""
        return f"Config(projects={self.jira_projects}, batch_size={self.batch_size})"


def load_config(config_path: str = "config.yaml") -> Config:
    """
    Load configuration from file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Config object
    """
    return Config(config_path)