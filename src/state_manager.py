"""
State management for resumability.

Handles checkpoint creation, loading, and validation to enable
resuming interrupted scraping sessions.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger('jira_scraper.state')


class StateManager:
    """
    Manages scraping state and checkpoints for resumability.
    
    Tracks:
    - Processed issues per project
    - Current pagination state
    - Timestamp of last update
    - Error counts and retry information
    """
    
    def __init__(self, checkpoint_dir: str, project: str):
        """
        Initialize state manager for a project.
        
        Args:
            checkpoint_dir: Directory to store checkpoint files
            project: Project key (e.g., 'KAFKA')
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.project = project
        self.checkpoint_file = self.checkpoint_dir / f"{project}_checkpoint.json"
        
        # State data
        self.state: Dict[str, Any] = {
            'project': project,
            'processed_issues': [],
            'total_issues': 0,
            'last_batch_start': 0,
            'last_update': None,
            'errors': [],
            'completed': False,
            'metadata': {}
        }
        
        # Create checkpoint directory
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing state if available
        self.load()
    
    def load(self) -> bool:
        """
        Load state from checkpoint file.
        
        Returns:
            True if state loaded successfully, False otherwise
        """
        if not self.checkpoint_file.exists():
            logger.info(f"No checkpoint found for {self.project}, starting fresh")
            return False
        
        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                loaded_state = json.load(f)
            
            # Validate checkpoint structure
            if not self._validate_checkpoint(loaded_state):
                logger.warning(
                    f"Invalid checkpoint structure for {self.project}, "
                    "starting fresh"
                )
                return False
            
            self.state = loaded_state
            logger.info(
                f"Loaded checkpoint for {self.project}: "
                f"{len(self.state['processed_issues'])} issues processed"
            )
            return True
            
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load checkpoint for {self.project}: {e}")
            return False
    
    def save(self) -> None:
        """
        Save current state to checkpoint file.
        
        Uses atomic write (write to temp file, then rename) to prevent corruption.
        """
        try:
            # Update timestamp
            self.state['last_update'] = datetime.now().isoformat()
            
            # Write to temporary file first
            temp_file = self.checkpoint_file.with_suffix('.tmp')
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            temp_file.replace(self.checkpoint_file)
            
            logger.debug(f"Checkpoint saved for {self.project}")
            
        except IOError as e:
            logger.error(f"Failed to save checkpoint for {self.project}: {e}")
    
    def _validate_checkpoint(self, state: Dict) -> bool:
        """
        Validate checkpoint structure.
        
        Args:
            state: State dictionary to validate
            
        Returns:
            True if valid, False otherwise
        """
        required_keys = [
            'project',
            'processed_issues',
            'last_batch_start',
            'completed'
        ]
        
        return all(key in state for key in required_keys)
    
    def mark_issue_processed(self, issue_key: str) -> None:
        """
        Mark an issue as processed.
        
        Args:
            issue_key: Issue key (e.g., 'KAFKA-12345')
        """
        if issue_key not in self.state['processed_issues']:
            self.state['processed_issues'].append(issue_key)
    
    def is_issue_processed(self, issue_key: str) -> bool:
        """
        Check if an issue has been processed.
        
        Args:
            issue_key: Issue key to check
            
        Returns:
            True if processed, False otherwise
        """
        return issue_key in self.state['processed_issues']
    
    def get_processed_issues(self) -> List[str]:
        """
        Get list of processed issue keys.
        
        Returns:
            List of issue keys
        """
        return self.state['processed_issues'].copy()
    
    def get_processed_count(self) -> int:
        """
        Get count of processed issues.
        
        Returns:
            Number of processed issues
        """
        return len(self.state['processed_issues'])
    
    def update_pagination(self, start_at: int, total: int) -> None:
        """
        Update pagination state.
        
        Args:
            start_at: Start index of current batch
            total: Total number of issues in project
        """
        self.state['last_batch_start'] = start_at
        self.state['total_issues'] = total
    
    def get_last_batch_start(self) -> int:
        """
        Get start index of last processed batch.
        
        Returns:
            Start index
        """
        return self.state.get('last_batch_start', 0)
    
    def add_error(self, error_info: Dict[str, Any]) -> None:
        """
        Record an error.
        
        Args:
            error_info: Dictionary with error details
        """
        error_entry = {
            'timestamp': datetime.now().isoformat(),
            **error_info
        }
        self.state['errors'].append(error_entry)
    
    def get_errors(self) -> List[Dict[str, Any]]:
        """
        Get list of recorded errors.
        
        Returns:
            List of error dictionaries
        """
        return self.state['errors'].copy()
    
    def mark_completed(self) -> None:
        """Mark scraping as completed for this project."""
        self.state['completed'] = True
        self.save()
        logger.info(f"Project {self.project} marked as completed")
    
    def is_completed(self) -> bool:
        """
        Check if scraping is completed.
        
        Returns:
            True if completed, False otherwise
        """
        return self.state.get('completed', False)
    
    def set_metadata(self, key: str, value: Any) -> None:
        """
        Set metadata value.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.state['metadata'][key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get metadata value.
        
        Args:
            key: Metadata key
            default: Default value if not found
            
        Returns:
            Metadata value or default
        """
        return self.state['metadata'].get(key, default)
    
    def reset(self) -> None:
        """Reset state to initial values."""
        self.state = {
            'project': self.project,
            'processed_issues': [],
            'total_issues': 0,
            'last_batch_start': 0,
            'last_update': None,
            'errors': [],
            'completed': False,
            'metadata': {}
        }
        
        # Delete checkpoint file if exists
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
        
        logger.info(f"State reset for {self.project}")
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of current state.
        
        Returns:
            Dictionary with state summary
        """
        return {
            'project': self.project,
            'processed_count': self.get_processed_count(),
            'total_issues': self.state.get('total_issues', 0),
            'last_batch_start': self.get_last_batch_start(),
            'completed': self.is_completed(),
            'error_count': len(self.state['errors']),
            'last_update': self.state.get('last_update')
        }
    
    def __repr__(self) -> str:
        """String representation."""
        summary = self.get_summary()
        return (
            f"StateManager(project={summary['project']}, "
            f"processed={summary['processed_count']}, "
            f"total={summary['total_issues']}, "
            f"completed={summary['completed']})"
        )


class GlobalStateManager:
    """
    Manages state across all projects.
    
    Provides high-level operations for multi-project scraping.
    """
    
    def __init__(self, checkpoint_dir: str, projects: List[str]):
        """
        Initialize global state manager.
        
        Args:
            checkpoint_dir: Directory for checkpoint files
            projects: List of project keys
        """
        self.checkpoint_dir = checkpoint_dir
        self.projects = projects
        self.state_managers: Dict[str, StateManager] = {}
        
        # Initialize state manager for each project
        for project in projects:
            self.state_managers[project] = StateManager(checkpoint_dir, project)
    
    def get_state_manager(self, project: str) -> StateManager:
        """
        Get state manager for a project.
        
        Args:
            project: Project key
            
        Returns:
            StateManager instance
        """
        return self.state_managers.get(project)
    
    def save_all(self) -> None:
        """Save state for all projects."""
        for manager in self.state_managers.values():
            manager.save()
    
    def get_incomplete_projects(self) -> List[str]:
        """
        Get list of incomplete projects.
        
        Returns:
            List of project keys that are not completed
        """
        return [
            project for project, manager in self.state_managers.items()
            if not manager.is_completed()
        ]
    
    def get_global_summary(self) -> Dict[str, Any]:
        """
        Get summary across all projects.
        
        Returns:
            Dictionary with global summary
        """
        total_processed = sum(
            manager.get_processed_count()
            for manager in self.state_managers.values()
        )
        
        total_issues = sum(
            manager.state.get('total_issues', 0)
            for manager in self.state_managers.values()
        )
        
        completed_projects = sum(
            1 for manager in self.state_managers.values()
            if manager.is_completed()
        )
        
        return {
            'total_projects': len(self.projects),
            'completed_projects': completed_projects,
            'total_processed': total_processed,
            'total_issues': total_issues,
            'projects': {
                project: manager.get_summary()
                for project, manager in self.state_managers.items()
            }
        }
    
    def reset_all(self) -> None:
        """Reset state for all projects."""
        for manager in self.state_managers.values():
            manager.reset()