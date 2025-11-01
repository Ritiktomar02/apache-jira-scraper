"""
Main entry point for Apache Jira Scraper.

Usage:
    python main.py                    # Normal run
    python main.py --resume           # Resume from checkpoint
    python main.py --clean            # Clean state and start fresh
    python main.py --debug            # Debug mode
    python main.py --projects KAFKA SPARK  # Specific projects
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List

from tqdm import tqdm

from src.config import load_config
from src.scraper import JiraScraper
from src.state_manager import GlobalStateManager, StateManager
from src.transformer import JiraTransformer
from src.utils import (
    calculate_file_size,
    setup_logging,
    write_jsonl
)

logger = None  # Will be initialized after config is loaded


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Apache Jira Scraper for LLM Training Data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                           # Scrape all configured projects
  python main.py --resume                  # Resume from last checkpoint
  python main.py --clean                   # Start fresh (clear all state)
  python main.py --projects KAFKA SPARK    # Scrape specific projects
  python main.py --debug                   # Enable debug logging
  python main.py --incremental             # Only fetch new issues
        """
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    
    parser.add_argument(
        '--projects',
        nargs='+',
        help='Specific projects to scrape (overrides config)'
    )
    
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from last checkpoint'
    )
    
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Clear all state and start fresh'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    parser.add_argument(
        '--incremental',
        action='store_true',
        help='Only fetch new issues (since last run)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        help='Override output directory'
    )
    
    return parser.parse_args()


def scrape_project(
    project: str,
    config,
    state_manager: StateManager,
    transformer: JiraTransformer,
    output_dir: Path
) -> bool:
    """
    Scrape a single project.
    
    Args:
        project: Project key
        config: Configuration object
        state_manager: State manager for the project
        transformer: Data transformer
        output_dir: Output directory for JSONL files
        
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Starting scrape for project: {project}")
    logger.info(f"{'='*60}")
    
    # Check if already completed
    if state_manager.is_completed() and not config.get('resume', False):
        logger.info(f"Project {project} already completed. Skipping.")
        return True
    
    try:
        # Initialize scraper
        scraper = JiraScraper(config, state_manager)
        
        # Scrape issues
        logger.info(f"Fetching issues from {project}...")
        raw_issues = scraper.scrape_project()
        
        if not raw_issues:
            logger.warning(f"No issues fetched for {project}")
            return False
        
        logger.info(f"Fetched {len(raw_issues)} issues from {project}")
        
        # Transform issues
        logger.info(f"Transforming issues for {project}...")
        transformed_issues = []
        
        with tqdm(total=len(raw_issues), desc=f"Transforming {project}") as pbar:
            for issue in raw_issues:
                result = transformer.transform_issue(issue)
                if result:
                    transformed_issues.append(result)
                pbar.update(1)
        
        logger.info(
            f"Successfully transformed {len(transformed_issues)}/{len(raw_issues)} issues"
        )
        
        # Write to JSONL
        output_file = output_dir / f"{project}_issues_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        logger.info(f"Writing to {output_file}...")
        
        # Clear file if starting fresh
        if output_file.exists():
            output_file.unlink()
        
        with tqdm(total=len(transformed_issues), desc=f"Writing {project}") as pbar:
            for issue in transformed_issues:
                write_jsonl(issue, str(output_file))
                pbar.update(1)
        
        file_size = calculate_file_size(str(output_file))
        logger.info(f"Output written to {output_file} ({file_size})")
        
        # Get statistics
        stats = scraper.get_stats()
        logger.info(f"Scraping statistics for {project}:")
        logger.info(f"  - Total requests: {stats['requests_made']}")
        logger.info(f"  - Failed requests: {stats['requests_failed']}")
        logger.info(f"  - Retries: {stats['retries']}")
        logger.info(f"  - Rate limit hits: {stats['rate_limit_hits']}")
        
        # Cleanup
        scraper.close()
        
        return True
        
    except KeyboardInterrupt:
        logger.warning(f"Interrupted while scraping {project}")
        state_manager.save()
        raise
        
    except Exception as e:
        logger.error(f"Error scraping {project}: {e}", exc_info=True)
        state_manager.add_error({
            'project': project,
            'error': str(e),
            'type': type(e).__name__
        })
        state_manager.save()
        return False


def main():
    """Main entry point."""
    global logger
    
    # Parse arguments
    args = parse_arguments()
    
    try:
        # Load configuration
        config = load_config(args.config)
        
        # Override debug mode if specified
        if args.debug:
            config._config['logging']['level'] = 'DEBUG'
        
        # Setup logging
        logger = setup_logging(config)
        
        logger.info("="*60)
        logger.info("Apache Jira Scraper for LLM Training Data")
        logger.info("="*60)
        logger.info(f"Configuration loaded from: {args.config}")
        
        # Determine projects to scrape
        projects = args.projects if args.projects else config.jira_projects
        
        if not projects:
            logger.error("No projects specified in config or arguments")
            sys.exit(1)
        
        logger.info(f"Projects to scrape: {', '.join(projects)}")
        
        # Override output directory if specified
        output_dir = Path(args.output_dir) if args.output_dir else Path(config.processed_data_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize global state manager
        global_state = GlobalStateManager(config.checkpoint_dir, projects)
        
        # Handle clean flag
        if args.clean:
            logger.warning("Cleaning all state and starting fresh...")
            global_state.reset_all()
            logger.info("State cleared successfully")
        
        # Initialize transformer
        transformer = JiraTransformer(config)
        
        # Scrape each project
        successful = []
        failed = []
        
        for project in projects:
            logger.info(f"\n\nProcessing project: {project}")
            
            state_manager = global_state.get_state_manager(project)
            
            success = scrape_project(
                project,
                config,
                state_manager,
                transformer,
                output_dir
            )
            
            if success:
                successful.append(project)
            else:
                failed.append(project)
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("SCRAPING SUMMARY")
        logger.info("="*60)
        
        summary = global_state.get_global_summary()
        
        logger.info(f"Total projects: {summary['total_projects']}")
        logger.info(f"Completed projects: {summary['completed_projects']}")
        logger.info(f"Total issues processed: {summary['total_processed']}")
        
        if successful:
            logger.info(f"\nSuccessful projects ({len(successful)}):")
            for project in successful:
                proj_summary = summary['projects'][project]
                logger.info(
                    f"  - {project}: {proj_summary['processed_count']} issues"
                )
        
        if failed:
            logger.warning(f"\nFailed projects ({len(failed)}):")
            for project in failed:
                logger.warning(f"  - {project}")
        
        logger.info(f"\nOutput directory: {output_dir}")
        logger.info("="*60)
        
        # Exit with appropriate code
        if failed:
            logger.warning("Some projects failed. Check logs for details.")
            sys.exit(1)
        else:
            logger.info("All projects completed successfully!")
            sys.exit(0)
            
    except KeyboardInterrupt:
        logger.warning("\n\nInterrupted by user. Progress has been saved.")
        sys.exit(130)
        
    except Exception as e:
        if logger:
            logger.error(f"Fatal error: {e}", exc_info=True)
        else:
            print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()