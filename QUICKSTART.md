# Quick Start Guide

Get up and running with the Apache Jira Scraper in 5 minutes!

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Internet connection
- ~500MB free disk space

## Step-by-Step Setup

### 1. Create Project Directory

```bash
mkdir apache-jira-scraper
cd apache-jira-scraper
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Create Directory Structure

```bash
mkdir -p src tests data/raw data/processed data/checkpoints logs
```

### 4. Create Files

Copy all the provided code files into your project:

```
apache-jira-scraper/
├── main.py
├── config.yaml
├── requirements.txt
├── .gitignore
├── README.md
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── scraper.py
│   ├── transformer.py
│   ├── state_manager.py
│   └── utils.py
└── tests/
    └── test_basic.py
```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `requests` - For HTTP requests
- `PyYAML` - For config parsing
- `beautifulsoup4` - For HTML cleaning
- `html2text` - For HTML to text conversion
- `tqdm` - For progress bars
- And more...

### 6. Configure Projects

Edit `config.yaml` and choose 3 Apache projects:

```yaml
jira:
  projects:
    - "KAFKA"    # Apache Kafka
    - "SPARK"    # Apache Spark
    - "HADOOP"   # Apache Hadoop
```

Popular options:
- KAFKA (Distributed streaming)
- SPARK (Big data processing)
- HADOOP (Distributed storage)
- FLINK (Stream processing)
- CASSANDRA (NoSQL database)
- AIRFLOW (Workflow management)
- HBASE (Column-oriented database)

### 7. Run the Scraper!

```bash
python main.py
```

You'll see output like:

```
============================================================
Apache Jira Scraper for LLM Training Data
============================================================
Configuration loaded from: config.yaml
Projects to scrape: KAFKA, SPARK, HADOOP

============================================================
Starting scrape for project: KAFKA
============================================================
Fetching issues from KAFKA...
Fetching batch for KAFKA: startAt=0
Transforming KAFKA: 100%|████████████| 50/50 [00:05<00:00, 10.23it/s]
Writing KAFKA: 100%|██████████████████| 50/50 [00:01<00:00, 45.12it/s]
```

### 8. Check Output

Your scraped data will be in:

```bash
data/processed/KAFKA_issues_20231115.jsonl
data/processed/SPARK_issues_20231115.jsonl
data/processed/HADOOP_issues_20231115.jsonl
```

Each line is a JSON object with:
- Metadata (title, status, priority, etc.)
- Content (description, comments)
- Derived tasks (summarization, classification, Q&A)

### 9. View Results

```bash
# Count issues
wc -l data/processed/*.jsonl

# View first issue
head -n 1 data/processed/KAFKA_issues_20231115.jsonl | python -m json.tool

# Search for specific issues
grep "performance" data/processed/*.jsonl
```

## Common Commands

```bash
# Resume from last checkpoint
python main.py --resume

# Start fresh (clear all state)
python main.py --clean

# Scrape specific projects only
python main.py --projects KAFKA SPARK

# Enable debug logging
python main.py --debug

# Run tests
pytest tests/ -v
```

## Troubleshooting

### "No module named 'src'"

Make sure you're in the project root directory and have activated the virtual environment.

### "Connection refused"

Check your internet connection and verify Jira is accessible:

```bash
curl https://issues.apache.org/jira/rest/api/2/serverInfo
```

### "Rate limited (429)"xac

The scraper handles this automatically. If it persists:
1. Increase `rate_limit_delay` in config.yaml
2. Reduce `batch_size`
3. Wait a few minutes and try again

### Slow performance

1. Reduce `max_comments_per_issue` in config
2. Set `max_issues_per_project` to a smaller number for testing
3. Disable derived tasks temporarily:

```yaml
transformation:
  generate_derived_tasks: false
```

## What's Next?

1. **Customize**: Edit `config.yaml` to adjust scraping behavior
2. **Analyze**: Use the JSONL files for LLM training or analysis
3. **Extend**: Add custom transformations in `src/transformer.py`
4. **Monitor**: Check `logs/` directory for detailed logs
5. **Resume**: The scraper automatically saves progress - just run again to continue

## Quick Verification

Run these commands to verify everything works:

```bash
# 1. Check Python version
python --version  # Should be 3.8+

# 2. Check dependencies
pip list | grep requests
pip list | grep PyYAML

# 3. Test configuration
python -c "from src.config import load_config; c = load_config(); print(c.jira_projects)"

# 4. Run unit tests
pytest tests/ -v

# 5. Test API access
# Test API access for Hadoop
curl -s "https://issues.apache.org/jira/rest/api/2/search?jql=project=HADOOP&maxResults=5" | jq '.issues[].key'

# Example output:
# "HADOOP-19197"
# "HADOOP-19196"
# "HADOOP-19195"

```

## Getting Help

- Check `logs/scraper_*.log` for detailed error messages
- Review `README.md` for comprehensive documentation
- Examine `data/checkpoints/` to see progress
- Use `--debug` flag for verbose output

## Performance Tips

For faster scraping:

```yaml
scraping:
  batch_size: 100              # Fetch more per request
  max_comments_per_issue: 20   # Limit comments
  request_delay: 0.2           # Shorter delays

transformation:
  max_description_length: 2000  # Truncate long descriptions
```

For testing with small datasets:

```yaml
scraping:
  max_issues_per_project: 100  # Limit total issues
```

---

**Happy Scraping! 🚀**

For detailed information, see `README.md`