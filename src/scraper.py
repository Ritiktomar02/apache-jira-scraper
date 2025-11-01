"""
Core scraping module for Apache Jira.

This module handles:
- API requests with retry logic
- Rate limiting and error handling
- Pagination management
- Data extraction and validation
"""

import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import Config
from .state_manager import StateManager
from .utils import safe_get

logger = logging.getLogger('jira_scraper.scraper')


class JiraScraper:
    """
    Scraper for Apache Jira REST API.
    
    Implements robust scraping with:
    - Automatic retry with exponential backoff
    - Rate limit handling
    - Connection pooling
    - Pagination support
    - Error recovery
    """
    
    def __init__(self, config: Config, state_manager: StateManager):
        """
        Initialize Jira scraper.
        
        Args:
            config: Configuration object
            state_manager: State manager for resumability
        """
        self.config = config
        self.state_manager = state_manager
        self.base_url = config.jira_base_url
        self.project = state_manager.project
        
        # Initialize session with connection pooling
        self.session = self._create_session()
        
        # Statistics
        self.stats = {
            'requests_made': 0,
            'requests_failed': 0,
            'rate_limit_hits': 0,
            'retries': 0
        }
    
    def _create_session(self) -> requests.Session:
        """
        Create requests session with retry logic and connection pooling.
        
        Returns:
            Configured requests.Session
        """
        session = requests.Session()
        
        retry_strategy = Retry(
            total=self.config.max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            backoff_factor=self.config.retry_delay
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=self.config.get('performance.max_pool_connections', 10),
            pool_maxsize=self.config.get('performance.max_pool_connections', 10)
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        session.headers.update({
            'User-Agent': self.config.get(
                'advanced.user_agent',
                'Apache-Jira-Scraper/1.0 (Educational)'
            ),
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        return session

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Optional[Dict]:
        """
        Make API request with error handling and retries.
        """
        url = self.base_url.rstrip("/") + endpoint
        self.stats['requests_made'] += 1
        
        try:
            time.sleep(self.config.get('scraping.request_delay', 0.5))
            
            response = self.session.get(
                url,
                params=params,
                timeout=self.config.request_timeout,
                verify=self.config.get('advanced.verify_ssl', True),
                allow_redirects=self.config.get('advanced.allow_redirects', True)
            )
            
            if response.status_code == 429:
                self.stats['rate_limit_hits'] += 1
                logger.warning(
                    f"Rate limit hit (429) for {self.project}. "
                    f"Waiting {self.config.rate_limit_delay} seconds..."
                )
                time.sleep(self.config.rate_limit_delay)
                
                if retry_count < self.config.max_retries:
                    self.stats['retries'] += 1
                    return self._make_request(endpoint, params, retry_count + 1)
                else:
                    logger.error(
                        f"Max retries exceeded for rate limiting on {self.project}"
                    )
                    return None
            
            if 400 <= response.status_code < 500:
                logger.error(
                    f"Client error {response.status_code} for {url}: "
                    f"{response.text[:200]}"
                )
                self.stats['requests_failed'] += 1
                return None
            
            if response.status_code >= 500:
                logger.warning(
                    f"Server error {response.status_code} for {url}. "
                    f"Retry {retry_count + 1}/{self.config.max_retries}"
                )
                
                if retry_count < self.config.max_retries:
                    delay = min(
                        self.config.retry_delay * (2 ** retry_count),
                        self.config.get('scraping.max_retry_delay', 60)
                    )
                    logger.info(f"Waiting {delay} seconds before retry...")
                    time.sleep(delay)
                    
                    self.stats['retries'] += 1
                    return self._make_request(endpoint, params, retry_count + 1)
                else:
                    logger.error(f"Max retries exceeded for {url}")
                    self.stats['requests_failed'] += 1
                    return None
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.warning(f"Request timeout for {url}")
            
            if retry_count < self.config.max_retries:
                self.stats['retries'] += 1
                delay = self.config.retry_delay * (2 ** retry_count)
                time.sleep(delay)
                return self._make_request(endpoint, params, retry_count + 1)
            else:
                logger.error(f"Max retries exceeded for timeout on {url}")
                self.stats['requests_failed'] += 1
                return None
                
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Connection error for {url}: {e}")
            
            if retry_count < self.config.max_retries:
                self.stats['retries'] += 1
                delay = self.config.retry_delay * (2 ** retry_count)
                time.sleep(delay)
                return self._make_request(endpoint, params, retry_count + 1)
            else:
                logger.error(f"Max retries exceeded for connection error on {url}")
                self.stats['requests_failed'] += 1
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            self.stats['requests_failed'] += 1
            return None
        
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {e}", exc_info=True)
            self.stats['requests_failed'] += 1
            return None
    
    def get_project_info(self) -> Optional[Dict]:
        endpoint = f"/rest/api/2/project/{self.project}"
        logger.info(f"Fetching project info for {self.project}")
        data = self._make_request(endpoint)
        if data:
            logger.debug(f"Project {self.project} info retrieved successfully")
        return data
    
    def search_issues(
        self,
        start_at: int = 0,
        max_results: Optional[int] = None
    ) -> Optional[Dict]:
        if max_results is None:
            max_results = self.config.batch_size
        
        jql = f"project = {self.project} ORDER BY created DESC"
        
        fields = self.config.get('jira.fields', [])
        fields_str = ','.join(fields) if isinstance(fields, list) and fields else "*all"
        
        params = {
            'jql': jql,
            'startAt': start_at,
            'maxResults': max_results,
            'fields': fields_str,
            'expand': 'renderedFields'
        }
        
        endpoint = "/rest/api/2/search"
        logger.debug(
            f"Searching issues for {self.project}: "
            f"startAt={start_at}, maxResults={max_results}"
        )
        return self._make_request(endpoint, params)
    
    def get_issue_comments(self, issue_key: str) -> Optional[List[Dict]]:
        endpoint = f"/rest/api/2/issue/{issue_key}/comment"
        params = {
            'maxResults': self.config.get('scraping.max_comments_per_issue', 50)
        }
        
        logger.debug(f"Fetching comments for {issue_key}")
        data = self._make_request(endpoint, params)
        
        if data and 'comments' in data:
            return data['comments']
        
        return None
    
    def scrape_project(self) -> List[Dict]:
        logger.info(f"Starting scrape for project {self.project}")
        project_info = self.get_project_info()
        if project_info:
            self.state_manager.set_metadata('project_info', project_info)
        
        all_issues = []
        start_at = self.state_manager.get_last_batch_start()
        max_issues = self.config.get('scraping.max_issues_per_project', 0)
        
        while True:
            logger.info(f"Fetching batch for {self.project}: startAt={start_at}")
            results = self.search_issues(start_at=start_at)
            
            if not results:
                logger.error(f"Failed to fetch issues for {self.project}")
                break
            
            issues = results.get('issues', [])
            total = results.get('total', 0)
            
            if not issues:
                logger.info(f"No more issues to fetch for {self.project}")
                break
            
            self.state_manager.update_pagination(start_at, total)
            
            for issue in issues:
                issue_key = issue.get('key')
                
                if not issue_key:
                    logger.warning("Issue without key, skipping")
                    continue
                
                if self.state_manager.is_issue_processed(issue_key):
                    logger.debug(f"Skipping already processed issue {issue_key}")
                    continue
                
                comment_count = safe_get(issue, 'fields', 'comment', 'total', default=0)
                self.state_manager.mark_issue_processed(issue_key)
                all_issues.append(issue)
                
                logger.debug(
                    f"Processed {issue_key} ({len(all_issues)}/{total} total)"
                )
            
            if len(all_issues) % self.config.get('resume.checkpoint_frequency', 10) == 0:
                self.state_manager.save()
            
            if max_issues > 0 and len(all_issues) >= max_issues:
                logger.info(f"Reached max issues limit ({max_issues}) for {self.project}")
                break
            
            start_at += len(issues)
            if start_at >= total:
                logger.info(f"Fetched all issues for {self.project}")
                break
        
        self.state_manager.mark_completed()
        self.state_manager.save()
        
        logger.info(
            f"Scraping completed for {self.project}. Total issues: {len(all_issues)}"
        )
        logger.info(f"Scraping statistics: {self.stats}")
        
        return all_issues
    
    def get_stats(self) -> Dict[str, int]:
        return self.stats.copy()
    
    def close(self) -> None:
        if self.session:
            self.session.close()
            logger.debug(f"Session closed for {self.project}")
