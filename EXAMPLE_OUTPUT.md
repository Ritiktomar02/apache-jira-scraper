# Example Output

This document shows what the scraped and transformed data looks like.

## Directory Structure After Running

```
apache-jira-scraper/
├── data/
│   ├── processed/
│   │   ├── KAFKA_issues_20231115.jsonl    # 15.2 MB
│   │   ├── SPARK_issues_20231115.jsonl    # 22.8 MB
│   │   └── HADOOP_issues_20231115.jsonl   # 31.5 MB
│   ├── checkpoints/
│   │   ├── KAFKA_checkpoint.json
│   │   ├── SPARK_checkpoint.json
│   │   └── HADOOP_checkpoint.json
│   └── raw/                                # Optional, if enabled
└── logs/
    └── scraper_20231115.log
```

## Sample JSONL Record

Each line in the output JSONL file is a complete JSON object:

```json
{
  "metadata": {
    "issue_key": "KAFKA-14442",
    "project": "KAFKA",
    "title": "Improve performance of consumer group rebalancing protocol",
    "status": "Resolved",
    "priority": "Major",
    "type": "Improvement",
    "reporter": "Jason Gustafson",
    "assignee": "David Arthur",
    "created": "2022-11-15T10:30:45.000Z",
    "updated": "2023-02-20T14:15:32.000Z",
    "resolved": "2023-02-20T14:15:32.000Z",
    "resolution": "Fixed",
    "labels": ["performance", "rebalancing", "consumer"],
    "components": ["consumer", "core"],
    "affects_versions": ["3.0.0", "3.1.0"],
    "fix_versions": ["3.4.0"]
  },
  "content": {
    "description": "The current stop-the-world rebalancing protocol causes significant pauses in message consumption when group membership changes. This is particularly problematic in large consumer groups with hundreds of partitions.\n\nProposal: Implement the incremental cooperative rebalancing protocol (KIP-429) which allows consumers to continue processing during rebalances. This reduces the rebalance time from seconds to milliseconds in many cases.\n\nBenefits:\n- Reduced message processing latency\n- Better handling of transient failures\n- Improved scalability for large consumer groups\n\nImplementation will require changes to:\n1. Consumer coordinator protocol\n2. Group metadata handling\n3. Partition assignment strategies",
    "comments": [
      {
        "author": "Jun Rao",
        "created": "2022-11-16T09:15:00.000Z",
        "body": "This aligns well with our scalability goals. We should also consider backwards compatibility with older clients."
      },
      {
        "author": "Colin McCabe",
        "created": "2022-11-18T13:45:22.000Z",
        "body": "Agreed. We'll need to maintain support for the eager rebalancing protocol for at least 2 major versions to allow for smooth upgrades."
      },
      {
        "
": "Ismael Juma",
        "created": "2022-12-01T10:20:15.000Z",
        "body": "I've reviewed the implementation. The cooperative protocol looks solid. We should add comprehensive integration tests covering edge cases like partition revocation during leader changes."
      },
      {
        "author": "David Arthur",
        "created": "2023-01-15T08:30:00.000Z",
        "body": "Implementation complete. Performance testing shows 95% reduction in rebalance time for groups with 100+ partitions. PR submitted for review."
      },
      {
        "author": "Jason Gustafson",
        "created": "2023-02-20T14:00:00.000Z",
        "body": "Changes merged. This will be included in the 3.4.0 release. Closing this issue."
      }
    ],
    "comment_count": 5
  },
  "derived_tasks": {
    "summarization": {
      "instruction": "Summarize this Jira issue in 2-3 sentences.",
      "input": "Issue: Improve performance of consumer group rebalancing protocol\nType: Improvement\nStatus: Resolved\nDescription: The current stop-the-world rebalancing protocol causes significant pauses in message consumption when group membership changes. This is particularly problematic in large consumer groups with hundreds of partitions. Proposal: Implement the incremental cooperative rebalancing protocol (KIP-429) which allows consumers to continue processing during rebalances.\n\nKey Comments:\n- Jun Rao: This aligns well with our scalability goals. We should also consider backwards compatibility with older clients.\n- Colin McCabe: Agreed. We'll need to maintain support for the eager rebalancing protocol for at least 2 major versions to allow for smooth upgrades.\n- Ismael Juma: I've reviewed the implementation. The cooperative protocol looks solid. We should add comprehensive integration tests covering edge cases like partition revocation during leader changes.",
      "output": "This improvement addresses performance problems in Kafka's consumer group rebalancing by implementing an incremental cooperative protocol (KIP-429). The new approach reduces rebalance time from seconds to milliseconds by allowing consumers to continue processing during membership changes, particularly benefiting large consumer groups with hundreds of partitions. Current status: Resolved (Fixed) and included in Kafka 3.4.0 release."
    },
    "classification": {
      "instruction": "Classify the type, priority, and category of this Jira issue.",
      "input": "Title: Improve performance of consumer group rebalancing protocol\nDescription: The current stop-the-world rebalancing protocol causes significant pauses in message consumption when group membership changes. This is particularly problematic in large consumer groups with hundreds of partitions. Proposal: Implement the incremental cooperative rebalancing protocol (KIP-429) which allows consumers to continue processing during rebalances.",
      "output": "Type: Improvement, Priority: Major, Category: Performance"
    },
    "qa_generation": {
      "instruction": "Generate question-answer pairs from this Jira issue.",
      "pairs": [
        {
          "question": "What does KAFKA-14442 address?",
          "answer": "Improve performance of consumer group rebalancing protocol"
        },
        {
          "question": "What is the current status of KAFKA-14442?",
          "answer": "The issue is resolved as fixed"
        },
        {
          "question": "What is the main concern raised in KAFKA-14442?",
          "answer": "The current stop-the-world rebalancing protocol causes significant pauses in message consumption when group membership changes."
        }
      ]
    }
  }
}
```

## Checkpoint File Example

`data/checkpoints/KAFKA_checkpoint.json`:

```json
{
  "project": "KAFKA",
  "processed_issues": [
    "KAFKA-14442",
    "KAFKA-14441",
    "KAFKA-14440",
    "KAFKA-14439"
  ],
  "total_issues": 15847,
  "last_batch_start": 200,
  "last_update": "2023-11-15T14:32:15.123456",
  "errors": [],
  "completed": false,
  "metadata": {
    "project_info": {
      "id": "12311107",
      "key": "KAFKA",
      "name": "Kafka",
      "description": "Apache Kafka"
    }
  }
}
```

## Log File Example

`logs/scraper_20231115.log`:

```
2023-11-15 10:30:00 - jira_scraper - INFO - ============================================================
2023-11-15 10:30:00 - jira_scraper - INFO - Apache Jira Scraper for LLM Training Data
2023-11-15 10:30:00 - jira_scraper - INFO - ============================================================
2023-11-15 10:30:00 - jira_scraper - INFO - Configuration loaded from: config.yaml
2023-11-15 10:30:00 - jira_scraper - INFO - Projects to scrape: KAFKA, SPARK, HADOOP
2023-11-15 10:30:01 - jira_scraper - INFO - 
============================================================
2023-11-15 10:30:01 - jira_scraper - INFO - Starting scrape for project: KAFKA
2023-11-15 10:30:01 - jira_scraper - INFO - ============================================================
2023-11-15 10:30:01 - jira_scraper.scraper - INFO - Starting scrape for project KAFKA
2023-11-15 10:30:01 - jira_scraper.scraper - INFO - Fetching project info for KAFKA
2023-11-15 10:30:02 - jira_scraper.scraper - DEBUG - Project KAFKA info retrieved successfully
2023-11-15 10:30:02 - jira_scraper.scraper - INFO - Fetching batch for KAFKA: startAt=0
2023-11-15 10:30:03 - jira_scraper.scraper - DEBUG - Searching issues for KAFKA: startAt=0, maxResults=50
2023-11-15 10:30:05 - jira_scraper.scraper - DEBUG - Processed KAFKA-14442 (1/15847 total)
2023-11-15 10:30:05 - jira_scraper.scraper - DEBUG - Processed KAFKA-14441 (2/15847 total)
...
2023-11-15 10:35:23 - jira_scraper.scraper - INFO - Scraping completed for KAFKA. Total issues: 250
2023-11-15 10:35:23 - jira_scraper.scraper - INFO - Scraping statistics: {'requests_made': 6, 'requests_failed': 0, 'rate_limit_hits': 0, 'retries': 0}
2023-11-15 10:35:23 - jira_scraper - INFO - Fetched 250 issues from KAFKA
2023-11-15 10:35:23 - jira_scraper - INFO - Transforming issues for KAFKA...
2023-11-15 10:35:45 - jira_scraper.transformer - INFO - Transformed 248/250 issues successfully
2023-11-15 10:35:45 - jira_scraper - INFO - Successfully transformed 248/250 issues
2023-11-15 10:35:45 - jira_scraper - INFO - Writing to data/processed/KAFKA_issues_20231115.jsonl...
2023-11-15 10:36:02 - jira_scraper - INFO - Output written to data/processed/KAFKA_issues_20231115.jsonl (4.52 MB)
```

## Statistics Summary

After completing all three projects:

```
============================================================
SCRAPING SUMMARY
============================================================
Total projects: 3
Completed projects: 3
Total issues processed: 782

Successful projects (3):
  - KAFKA: 248 issues
  - SPARK: 312 issues
  - HADOOP: 222 issues

Output directory: data/processed
============================================================
```

## Sample Use Cases for the Data

### 1. LLM Training Examples

**Summarization:**
```python
{
  "prompt": "Summarize this Jira issue in 2-3 sentences.\n\nIssue: Improve performance of consumer group rebalancing protocol\nType: Improvement\nStatus: Resolved\nDescription: The current stop-the-world rebalancing protocol causes...",
  "completion": "This improvement addresses performance problems in Kafka's consumer group rebalancing by implementing..."
}
```

### 2. Classification Training

```python
{
  "prompt": "Classify this issue:\nTitle: Improve performance of consumer group rebalancing protocol",
  "completion": "Type: Improvement, Priority: Major, Category: Performance"
}
```

### 3. Q&A Training

```python
{
  "prompt": "What does KAFKA-14442 address?",
  "completion": "Improve performance of consumer group rebalancing protocol"
}
```

## File Formats

### JSONL (JSON Lines)

Each line is a complete, valid JSON object:
- **Advantage**: Streamable, can process line-by-line
- **Use case**: Large datasets, streaming processing
- **Compatible with**: Most LLM training frameworks

```bash
# Count total records
wc -l data/processed/KAFKA_issues_20231115.jsonl

# Process line by line
while read line; do
  echo $line | jq '.metadata.title'
done < data/processed/KAFKA_issues_20231115.jsonl
```

### Loading in Python

```python
import json

# Read all issues
issues = []
with open('data/processed/KAFKA_issues_20231115.jsonl', 'r') as f:
    for line in f:
        issues.append(json.loads(line))

print(f"Loaded {len(issues)} issues")

# Access first issue
first_issue = issues[0]
print(f"Title: {first_issue['metadata']['title']}")
print(f"Status: {first_issue['metadata']['status']}")
```

### Converting to Other Formats

```python
# To CSV (metadata only)
import pandas as pd
import json

data = []
with open('KAFKA_issues_20231115.jsonl', 'r') as f:
    for line in f:
        issue = json.loads(line)
        data.append(issue['metadata'])

df = pd.DataFrame(data)
df.to_csv('kafka_issues.csv', index=False)

# To Parquet (for big data processing)
df.to_parquet('kafka_issues.parquet')
```

## Data Quality Metrics

Typical output quality:
- **Completeness**: 95-98% of issues have all required fields
- **Text Quality**: HTML stripped, clean plain text
- **Comment Coverage**: Average 3-5 comments per issue
- **Derived Tasks**: 3 task types per issue
- **File Size**: ~15-30 MB per 1000 issues

---

This output is ready for:
- LLM fine-tuning (GPT, Claude, LLaMA, etc.)
- RAG (Retrieval Augmented Generation) systems
- Issue classification models
- Summarization model training
- Q&A system development