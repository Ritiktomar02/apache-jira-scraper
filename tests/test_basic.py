"""
Basic tests for the scraper components.

Run with: pytest tests/
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from src.config import Config
from src.state_manager import StateManager
from src.transformer import JiraTransformer
from src.utils import (
    clean_html,
    clean_text,
    safe_get,
    truncate_text,
    validate_json_structure
)


class TestUtils:
    """Test utility functions."""
    
    def test_clean_html(self):
        """Test HTML cleaning."""
        html = '<p>This is <b>bold</b> text</p>'
        result = clean_html(html)
        assert 'bold' in result
        assert '<p>' not in result
        assert '<b>' not in result
    
    def test_clean_text(self):
        """Test text cleaning."""
        text = "  Multiple   spaces   and\n\nnewlines  "
        result = clean_text(text)
        assert '  ' not in result
        assert result.strip() == result
    
    def test_safe_get(self):
        """Test safe dictionary access."""
        data = {'a': {'b': {'c': 'value'}}}
        assert safe_get(data, 'a', 'b', 'c') == 'value'
        assert safe_get(data, 'x', 'y', default='default') == 'default'
    
    def test_truncate_text(self):
        """Test text truncation."""
        text = "This is a long text that should be truncated"
        result = truncate_text(text, 20)
        assert len(result) <= 20
        assert '...' in result
    
    def test_validate_json_structure(self):
        """Test JSON validation."""
        data = {'key': 'value', 'other': 'data'}
        assert validate_json_structure(data, ['key']) is True
        assert validate_json_structure(data, ['missing']) is False


class TestConfig:
    """Test configuration management."""
    
    def test_load_config(self):
        """Test config loading."""
        # Create temporary config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
jira:
  base_url: "https://issues.apache.org/jira"
  projects: ["KAFKA"]
  
scraping:
  batch_size: 50
  max_retries: 3
  
output:
  raw_data_dir: "data/raw"
  processed_data_dir: "data/processed"
  checkpoint_dir: "data/checkpoints"
  
logging:
  level: "INFO"
  log_dir: "logs"
""")
            config_path = f.name
        
        try:
            config = Config(config_path)
            assert config.jira_base_url == "https://issues.apache.org/jira"
            assert config.batch_size == 50
            assert 'KAFKA' in config.jira_projects
        finally:
            os.unlink(config_path)
    
    def test_config_validation(self):
        """Test config validation."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml")
            config_path = f.name
        
        try:
            # Should fail due to missing required sections
            with pytest.raises(ValueError):
                Config(config_path)
        finally:
            os.unlink(config_path)


class TestStateManager:
    """Test state management."""
    
    def test_state_initialization(self):
        """Test state manager initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state = StateManager(tmpdir, "TEST")
            assert state.project == "TEST"
            assert state.get_processed_count() == 0
            assert not state.is_completed()
    
    def test_mark_issue_processed(self):
        """Test marking issues as processed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state = StateManager(tmpdir, "TEST")
            
            state.mark_issue_processed("TEST-123")
            assert state.is_issue_processed("TEST-123")
            assert state.get_processed_count() == 1
    
    def test_save_and_load(self):
        """Test saving and loading state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and save state
            state1 = StateManager(tmpdir, "TEST")
            state1.mark_issue_processed("TEST-123")
            state1.mark_issue_processed("TEST-456")
            state1.save()
            
            # Load state in new instance
            state2 = StateManager(tmpdir, "TEST")
            assert state2.get_processed_count() == 2
            assert state2.is_issue_processed("TEST-123")
            assert state2.is_issue_processed("TEST-456")
    
    def test_pagination(self):
        """Test pagination state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state = StateManager(tmpdir, "TEST")
            
            state.update_pagination(start_at=50, total=200)
            assert state.get_last_batch_start() == 50
            assert state.state['total_issues'] == 200


class TestTransformer:
    """Test data transformation."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
jira:
  base_url: "https://issues.apache.org/jira"
  projects: ["KAFKA"]
  
scraping:
  batch_size: 50
  
output:
  raw_data_dir: "data/raw"
  processed_data_dir: "data/processed"
  checkpoint_dir: "data/checkpoints"
  
logging:
  level: "INFO"
  log_dir: "logs"
  
transformation:
  strip_html: true
  max_description_length: 5000
  generate_derived_tasks: true
  derived_tasks:
    summarization: true
    classification: true
    qa_generation: true
""")
            config_path = f.name
        
        config = Config(config_path)
        os.unlink(config_path)
        return config
    
    @pytest.fixture
    def sample_issue(self):
        """Create sample issue data."""
        return {
            'key': 'KAFKA-12345',
            'fields': {
                'summary': 'Improve consumer performance',
                'description': '<p>The consumer has performance issues</p>',
                'status': {'name': 'Open'},
                'priority': {'name': 'Major'},
                'issuetype': {'name': 'Improvement'},
                'created': '2023-01-01T00:00:00.000Z',
                'updated': '2023-01-02T00:00:00.000Z',
                'reporter': {'displayName': 'John Doe'},
                'assignee': {'displayName': 'Jane Smith'},
                'labels': ['performance'],
                'components': [{'name': 'consumer'}],
                'comment': {
                    'comments': [
                        {
                            'author': {'displayName': 'Reviewer'},
                            'created': '2023-01-01T12:00:00.000Z',
                            'body': 'Good suggestion'
                        }
                    ]
                }
            }
        }
    
    def test_transform_issue(self, config, sample_issue):
        """Test issue transformation."""
        transformer = JiraTransformer(config)
        result = transformer.transform_issue(sample_issue)
        
        assert result is not None
        assert 'metadata' in result
        assert 'content' in result
        assert 'derived_tasks' in result
        
        # Check metadata
        assert result['metadata']['issue_key'] == 'KAFKA-12345'
        assert result['metadata']['project'] == 'KAFKA'
        assert result['metadata']['title'] == 'Improve consumer performance'
        
        # Check content
        assert result['content']['description']
        assert len(result['content']['comments']) == 1
    
    def test_derived_tasks(self, config, sample_issue):
        """Test derived task generation."""
        transformer = JiraTransformer(config)
        result = transformer.transform_issue(sample_issue)
        
        tasks = result['derived_tasks']
        
        # Check summarization
        assert 'summarization' in tasks
        assert 'instruction' in tasks['summarization']
        assert 'input' in tasks['summarization']
        assert 'output' in tasks['summarization']
        
        # Check classification
        assert 'classification' in tasks
        
        # Check Q&A
        assert 'qa_generation' in tasks
        assert 'pairs' in tasks['qa_generation']
        assert len(tasks['qa_generation']['pairs']) > 0


class TestIntegration:
    """Integration tests."""
    
    def test_end_to_end_flow(self):
        """Test complete flow (config -> transform)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create config
            config_path = Path(tmpdir) / 'config.yaml'
            with open(config_path, 'w') as f:
                f.write("""
jira:
  base_url: "https://issues.apache.org/jira"
  projects: ["KAFKA"]
  
scraping:
  batch_size: 50
  
output:
  raw_data_dir: "{}/raw"
  processed_data_dir: "{}/processed"
  checkpoint_dir: "{}/checkpoints"
  
logging:
  level: "INFO"
  log_dir: "{}/logs"
  
transformation:
  strip_html: true
  generate_derived_tasks: true
""".format(tmpdir, tmpdir, tmpdir, tmpdir))
            
            # Load config
            config = Config(str(config_path))
            
            # Initialize components
            state = StateManager(config.checkpoint_dir, "KAFKA")
            transformer = JiraTransformer(config)
            
            # Create sample issue
            issue = {
                'key': 'KAFKA-1',
                'fields': {
                    'summary': 'Test issue',
                    'description': 'Test description',
                    'status': {'name': 'Open'},
                    'priority': {'name': 'Major'},
                    'issuetype': {'name': 'Bug'}
                }
            }
            
            # Transform
            result = transformer.transform_issue(issue)
            
            assert result is not None
            assert result['metadata']['issue_key'] == 'KAFKA-1'
            
            # Mark processed
            state.mark_issue_processed('KAFKA-1')
            assert state.is_issue_processed('KAFKA-1')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])