"""
Data transformation module.

Converts raw Jira API responses to structured JSONL format
suitable for LLM training, with derived tasks like summarization,
classification, and Q&A generation.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import Config
from .utils import (
    clean_html,
    clean_text,
    safe_get,
    truncate_text,
    validate_json_structure
)

logger = logging.getLogger('jira_scraper.transformer')


class JiraTransformer:
    """
    Transforms raw Jira data into LLM-ready JSONL format.
    
    Extracts clean metadata and content, generates derived tasks
    for training (summarization, classification, Q&A).
    """
    
    def __init__(self, config: Config):
        """
        Initialize transformer.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.strip_html = config.get('transformation.strip_html', True)
        self.max_desc_length = config.get('transformation.max_description_length', 5000)
        self.max_comment_length = config.get('transformation.max_comment_length', 2000)
    
    def transform_issue(self, raw_issue: Dict) -> Optional[Dict]:
        """
        Transform a raw issue into structured format.
        
        Args:
            raw_issue: Raw issue data from Jira API
            
        Returns:
            Transformed issue dictionary or None if invalid
        """
        try:
            # Extract basic fields
            issue_key = raw_issue.get('key')
            fields = raw_issue.get('fields', {})
            
            if not issue_key:
                logger.warning("Issue missing key, skipping")
                return None
            
            # Validate required fields
            required_fields = self.config.get('validation.required_fields', ['key'])
            if not validate_json_structure({'key': issue_key, **fields}, required_fields):
                if self.config.get('validation.skip_invalid', True):
                    logger.warning(f"Issue {issue_key} missing required fields, skipping")
                    return None
            
            # Build transformed issue
            transformed = {
                'metadata': self._extract_metadata(issue_key, fields),
                'content': self._extract_content(fields),
            }
            
            # Generate derived tasks if enabled
            if self.config.get('transformation.generate_derived_tasks', True):
                transformed['derived_tasks'] = self._generate_derived_tasks(
                    transformed['metadata'],
                    transformed['content']
                )
            
            return transformed
            
        except Exception as e:
            logger.error(f"Error transforming issue: {e}", exc_info=True)
            return None
    
    def _extract_metadata(self, issue_key: str, fields: Dict) -> Dict[str, Any]:
        """
        Extract metadata from issue fields.
        
        Args:
            issue_key: Issue key
            fields: Issue fields dictionary
            
        Returns:
            Metadata dictionary
        """
        metadata = {
            'issue_key': issue_key,
            'project': issue_key.split('-')[0] if '-' in issue_key else None,
            'title': clean_text(safe_get(fields, 'summary', default='')),
            'status': safe_get(fields, 'status', 'name', default=None),
            'priority': safe_get(fields, 'priority', 'name', default=None),
            'type': safe_get(fields, 'issuetype', 'name', default=None),
            'reporter': safe_get(fields, 'reporter', 'displayName', default=None),
            'assignee': safe_get(fields, 'assignee', 'displayName', default=None),
            'created': safe_get(fields, 'created', default=None),
            'updated': safe_get(fields, 'updated', default=None),
            'resolved': safe_get(fields, 'resolutiondate', default=None),
            'resolution': safe_get(fields, 'resolution', 'name', default=None),
        }
        
        # Extract labels
        labels = fields.get('labels', [])
        metadata['labels'] = labels if isinstance(labels, list) else []
        
        # Extract components
        components = fields.get('components', [])
        metadata['components'] = [
            comp.get('name') for comp in components
            if isinstance(comp, dict) and 'name' in comp
        ]
        
        # Extract versions
        versions = fields.get('versions', [])
        metadata['affects_versions'] = [
            ver.get('name') for ver in versions
            if isinstance(ver, dict) and 'name' in ver
        ]
        
        fix_versions = fields.get('fixVersions', [])
        metadata['fix_versions'] = [
            ver.get('name') for ver in fix_versions
            if isinstance(ver, dict) and 'name' in ver
        ]
        
        return metadata
    
    def _extract_content(self, fields: Dict) -> Dict[str, Any]:
        """
        Extract content (description, comments) from issue.
        
        Args:
            fields: Issue fields dictionary
            
        Returns:
            Content dictionary
        """
        # Extract and clean description
        description = fields.get('description', '')
        if description:
            description = clean_html(description, self.strip_html)
            if self.max_desc_length > 0:
                description = truncate_text(description, self.max_desc_length)
        
        # Extract comments
        comments = []
        comment_data = fields.get('comment', {})
        comment_list = comment_data.get('comments', [])
        
        for comment in comment_list:
            if not isinstance(comment, dict):
                continue
            
            body = comment.get('body', '')
            if body:
                body = clean_html(body, self.strip_html)
                if self.max_comment_length > 0:
                    body = truncate_text(body, self.max_comment_length)
            
            comments.append({
                'author': safe_get(comment, 'author', 'displayName', default='Unknown'),
                'created': comment.get('created'),
                'body': body
            })
        
        return {
            'description': description,
            'comments': comments,
            'comment_count': len(comments)
        }
    
    def _generate_derived_tasks(
        self,
        metadata: Dict,
        content: Dict
    ) -> Dict[str, Any]:
        """
        Generate derived tasks for LLM training.
        
        Args:
            metadata: Issue metadata
            content: Issue content
            
        Returns:
            Dictionary with derived tasks
        """
        tasks = {}
        
        task_config = self.config.get('transformation.derived_tasks', {})
        
        # Summarization task
        if task_config.get('summarization', True):
            tasks['summarization'] = self._generate_summarization_task(
                metadata,
                content
            )
        
        # Classification task
        if task_config.get('classification', True):
            tasks['classification'] = self._generate_classification_task(
                metadata,
                content
            )
        
        # Q&A generation task
        if task_config.get('qa_generation', True):
            tasks['qa_generation'] = self._generate_qa_task(
                metadata,
                content
            )
        
        return tasks
    
    def _generate_summarization_task(
        self,
        metadata: Dict,
        content: Dict
    ) -> Dict[str, str]:
        """
        Generate summarization task.
        
        Args:
            metadata: Issue metadata
            content: Issue content
            
        Returns:
            Summarization task dictionary
        """
        # Build input text
        input_parts = [
            f"Issue: {metadata.get('title', '')}",
            f"Type: {metadata.get('type', '')}",
            f"Status: {metadata.get('status', '')}",
        ]
        
        if content.get('description'):
            input_parts.append(f"Description: {content['description'][:500]}")
        
        # Include comments if configured
        summ_config = self.config.get('transformation.summarization', {})
        if summ_config.get('include_comments', True):
            max_comments = summ_config.get('max_comments', 5)
            comments = content.get('comments', [])[:max_comments]
            
            if comments:
                comment_texts = [
                    f"- {c['author']}: {c['body'][:200]}"
                    for c in comments
                ]
                input_parts.append("Key Comments:\n" + "\n".join(comment_texts))
        
        input_text = "\n\n".join(input_parts)
        
        # Generate output summary
        output_summary = self._create_summary(metadata, content)
        
        return {
            'instruction': 'Summarize this Jira issue in 2-3 sentences.',
            'input': input_text,
            'output': output_summary
        }
    
    def _create_summary(self, metadata: Dict, content: Dict) -> str:
        """
        Create a summary of the issue.
        
        Args:
            metadata: Issue metadata
            content: Issue content
            
        Returns:
            Summary text
        """
        parts = []
        
        # Main issue description
        title = metadata.get('title', 'Unknown issue')
        issue_type = metadata.get('type', 'Issue')
        parts.append(f"This {issue_type.lower()} addresses: {title}.")
        
        # Description summary
        desc = content.get('description', '')
        if desc:
            # Take first sentence or first 150 chars
            first_sentence = desc.split('.')[0]
            if len(first_sentence) > 150:
                first_sentence = desc[:150]
            parts.append(first_sentence.strip() + ".")
        
        # Status
        status = metadata.get('status')
        resolution = metadata.get('resolution')
        if status:
            status_text = f"Current status: {status}"
            if resolution:
                status_text += f" ({resolution})"
            parts.append(status_text + ".")
        
        return " ".join(parts)
    
    def _generate_classification_task(
        self,
        metadata: Dict,
        content: Dict
    ) -> Dict[str, str]:
        """
        Generate classification task.
        
        Args:
            metadata: Issue metadata
            content: Issue content
            
        Returns:
            Classification task dictionary
        """
        # Build input
        input_text = f"Title: {metadata.get('title', '')}\n"
        
        desc = content.get('description', '')
        if desc:
            input_text += f"Description: {desc[:300]}"
        
        # Build output classification
        classifications = []
        
        if metadata.get('type'):
            classifications.append(f"Type: {metadata['type']}")
        
        if metadata.get('priority'):
            classifications.append(f"Priority: {metadata['priority']}")
        
        # Determine category from labels/components
        category = self._determine_category(metadata)
        if category:
            classifications.append(f"Category: {category}")
        
        output = ", ".join(classifications)
        
        return {
            'instruction': 'Classify the type, priority, and category of this Jira issue.',
            'input': input_text,
            'output': output
        }
    
    def _determine_category(self, metadata: Dict) -> Optional[str]:
        """
        Determine issue category from labels and components.
        
        Args:
            metadata: Issue metadata
            
        Returns:
            Category string or None
        """
        # Common categories
        categories = {
            'performance': ['performance', 'perf', 'optimization', 'slow'],
            'bug': ['bug', 'defect', 'error', 'exception'],
            'feature': ['feature', 'enhancement', 'improvement'],
            'documentation': ['docs', 'documentation', 'readme'],
            'testing': ['test', 'testing', 'qa'],
            'security': ['security', 'vulnerability', 'cve']
        }
        
        # Check labels
        labels = [l.lower() for l in metadata.get('labels', [])]
        components = [c.lower() for c in metadata.get('components', [])]
        
        all_tags = labels + components
        
        for category, keywords in categories.items():
            if any(keyword in tag for tag in all_tags for keyword in keywords):
                return category.title()
        
        return None
    
    def _generate_qa_task(
        self,
        metadata: Dict,
        content: Dict
    ) -> Dict[str, Any]:
        """
        Generate Q&A pairs from issue.
        
        Args:
            metadata: Issue metadata
            content: Issue content
            
        Returns:
            Q&A task dictionary
        """
        qa_config = self.config.get('transformation.qa_generation', {})
        min_pairs = qa_config.get('min_pairs', 1)
        max_pairs = qa_config.get('max_pairs', 3)
        
        pairs = []
        
        # Generate Q&A pairs
        
        # Pair 1: What is the issue about?
        if metadata.get('title'):
            pairs.append({
                'question': f"What does {metadata['issue_key']} address?",
                'answer': metadata['title']
            })
        
        # Pair 2: What's the status?
        if metadata.get('status'):
            pairs.append({
                'question': f"What is the current status of {metadata['issue_key']}?",
                'answer': f"The issue is {metadata['status'].lower()}"
                          + (f" as {metadata['resolution'].lower()}"
                             if metadata.get('resolution') else "")
            })
        
        # Pair 3: From description
        desc = content.get('description', '')
        if desc and len(desc) > 50:
            # Extract first meaningful sentence
            sentences = desc.split('.')
            if sentences:
                first_sentence = sentences[0].strip()
                if len(first_sentence) > 20:
                    pairs.append({
                        'question': f"What is the main concern raised in {metadata['issue_key']}?",
                        'answer': first_sentence + "."
                    })
        
        # Pair 4: From comments (if enabled and available)
        if qa_config.get('use_comments', True):
            comments = content.get('comments', [])
            if comments:
                # Find a substantial comment
                for comment in comments[:3]:
                    body = comment.get('body', '')
                    if len(body) > 50:
                        pairs.append({
                            'question': f"What solution was proposed for {metadata['issue_key']}?",
                            'answer': truncate_text(body, 200)
                        })
                        break
        
        # Limit pairs
        pairs = pairs[:max_pairs]
        
        return {
            'instruction': 'Generate question-answer pairs from this Jira issue.',
            'pairs': pairs
        }
    
    def transform_batch(self, raw_issues: List[Dict]) -> List[Dict]:
        """
        Transform a batch of issues.
        
        Args:
            raw_issues: List of raw issue dictionaries
            
        Returns:
            List of transformed issues
        """
        transformed = []
        
        for issue in raw_issues:
            result = self.transform_issue(issue)
            if result:
                transformed.append(result)
        
        logger.info(
            f"Transformed {len(transformed)}/{len(raw_issues)} issues successfully"
        )
        
        return transformed