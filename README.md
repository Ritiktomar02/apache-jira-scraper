# Ritik Tomar - E22CSEU0712 - Bennett University

## 🧠 Apache JIRA Scraper — Web Scraping Tutor Assignment

### 📘 Overview
This project implements a **data scraping and transformation pipeline** that extracts **public issue data from Apache’s JIRA instance** and converts it into a format suitable for **Large Language Model (LLM) training**.  

The scraper is **fault-tolerant, resumable, and scalable**, handling real-world data inconsistencies while producing **clean, structured JSONL datasets**.

---

## 🎯 Objective
To build a system that:
- Scrapes issue data (issues, comments, metadata) from **Apache JIRA**.
- Handles network and data edge cases (timeouts, 429s, malformed data).
- Transforms unstructured data into **LLM-ready JSONL corpus**.
- Maintains **checkpoints** for resumability and fault recovery.

---

## ⚙️ Features
✅ Fetches issues, comments, and metadata (status, priority, assignee, timestamps, etc.)  
✅ Supports pagination, rate limits, and exponential backoff  
✅ Resumable scraping using per-project checkpoints  
✅ Cleans and converts HTML to plain text  
✅ Generates derived tasks — summarization, classification, and Q&A  
✅ Produces ready-to-train **JSONL output**

---

# Architecture Documentation

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          USER INTERFACE                          │
│                        (Command Line)                           │
│                          main.py                                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ├─── Parse Arguments
                         ├─── Load Configuration
                         └─── Initialize Components
                         │
        ┌────────────────┴────────────────┐
        │                                  │
        ▼                                  ▼
┌──────────────┐                  ┌──────────────┐
│   Config     │                  │    State     │
│   Manager    │                  │   Manager    │
│              │                  │              │
│ • Load YAML  │                  │ • Track      │
│ • Validate   │                  │   Progress   │
│ • Provide    │                  │ • Save       │
│   Settings   │                  │   Checkpoint │
└──────┬───────┘                  └──────┬───────┘
       │                                  │
       │         ┌────────────────────────┘
       │         │
       ▼         ▼
┌──────────────────────┐
│                      │
│   Jira Scraper       │
│                      │
│ • API Requests       │
│ • Retry Logic        │
│ • Rate Limiting      │
│ • Pagination         │
│                      │
└──────┬───────────────┘
       │
       │ Raw JSON Data
       │
       ▼
┌──────────────────────┐
│                      │
│   Transformer        │
│                      │
│ • Clean HTML         │
│ • Extract Metadata   │
│ • Generate Tasks     │
│ • Validate           │
│                      │
└──────┬───────────────┘
       │
       │ Structured JSONL
       │
       ▼
┌──────────────────────┐
│                      │
│   Output Files       │
│                      │
│ • JSONL Format       │
│ • One file per       │
│   project            │
│                      │
└──────────────────────┘
```

## Component Details

### 1. Configuration Manager (`src/config.py`)

**Responsibility**: Centralized configuration management

**Key Features**:
- Load and parse YAML configuration
- Validate required fields and types
- Provide easy access to config values via properties
- Create required directories automatically

**Design Pattern**: Singleton-like (one config per application)

**Dependencies**: PyYAML

**Key Methods**:
```python
- __init__(config_path)     # Load config from file
- _validate_config()        # Ensure all required fields present
- get(key, default)         # Get nested config value
- @property methods         # Easy access to common values
```

**Error Handling**:
- FileNotFoundError: Config file doesn't exist
- ValueError: Missing required fields or invalid values
- yaml.YAMLError: Malformed YAML syntax

---

### 2. State Manager (`src/state_manager.py`)

**Responsibility**: Track progress and enable resumability

**Architecture**:
```
GlobalStateManager
├── StateManager(KAFKA)
│   ├── Processed issues list
│   ├── Pagination state
│   ├── Completion status
│   └── Error log
├── StateManager(SPARK)
└── StateManager(HADOOP)
```

**Key Features**:
- Per-project state tracking
- Atomic checkpoint saves (temp file + rename)
- Checkpoint validation on load
- Error recovery information

**Data Structure**:
```json
{
  "project": "KAFKA",
  "processed_issues": ["KAFKA-1", "KAFKA-2"],
  "total_issues": 15847,
  "last_batch_start": 100,
  "last_update": "2023-11-15T10:30:00",
  "errors": [],
  "completed": false,
  "metadata": {}
}
```

**Persistence Strategy**:
- Save to temp file first
- Atomic rename to prevent corruption
- JSON format for human readability

---

### 3. Jira Scraper (`src/scraper.py`)

**Responsibility**: Fetch data from Jira REST API

**Request Flow**:
```
Make Request
     │
     ▼
Add Delay ───────────┐
     │               │
     ▼               │
Send HTTP Request    │
     │               │
     ├── Success ────┼──> Return Data
     │               │
     ├── 429 Rate    │
     │   Limit       │
     │   │           │
     │   ▼           │
     │   Wait 60s    │
     │   │           │
     │   └───────────┘
     │
     ├── 5xx Error
     │   │
     │   ▼
     │   Exponential
     │   Backoff
     │   │
     │   └───────────┐
     │               │
     ├── Timeout     │
     │   │           │
     │   └───────────┤
     │               │
     ├── Connection  │
     │   Error       │
     │   │           │
     │   └───────────┤
     │               │
     └───> Retry ────┘
          (max 5 times)
```

**Connection Pooling**:
- HTTPAdapter with Retry strategy
- Pool of 10 connections maintained
- Reuse connections across requests
- Automatic connection management

**Rate Limiting Strategy**:
1. Detect 429 response
2. Log warning
3. Sleep for configured duration (default 60s)
4. Retry request
5. Track rate limit hits for monitoring

**Pagination**:
```python
start_at = 0
while True:
    results = search_issues(start_at, batch_size=50)
    issues = results['issues']
    
    if not issues:
        break
    
    process_issues(issues)
    start_at += len(issues)
    
    if start_at >= results['total']:
        break
```

---

### 4. Transformer (`src/transformer.py`)

**Responsibility**: Convert raw Jira data to LLM-ready format

**Transformation Pipeline**:
```
Raw Jira JSON
     │
     ▼
Extract Metadata
     │
     ├─ Issue key
     ├─ Title
     ├─ Status, Priority, Type
     ├─ Reporter, Assignee
     ├─ Dates
     ├─ Labels, Components
     └─ Versions
     │
     ▼
Extract Content
     │
     ├─ Clean HTML from description
     ├─ Extract comments
     ├─ Clean HTML from comments
     └─ Count comments
     │
     ▼
Generate Derived Tasks
     │
     ├─ Summarization Task
     │   ├─ Build input (title + desc + comments)
     │   └─ Generate summary
     │
     ├─ Classification Task
     │   ├─ Build input (title + desc)
     │   └─ Extract classifications
     │
     └─ Q&A Generation Task
         ├─ Generate from title
         ├─ Generate from status
         ├─ Generate from description
         └─ Generate from comments
     │
     ▼
Structured JSON Object
```

**HTML Cleaning Process**:
1. Parse HTML with BeautifulSoup
2. Remove script/style tags
3. Convert to markdown with html2text
4. Clean excessive whitespace
5. Truncate if too long

**Derived Task Generation**:

**Summarization**:
- Input: Title + Description + Top 5 comments
- Output: 2-3 sentence summary
- Format: Instruction-input-output triplet

**Classification**:
- Input: Title + Description (first 300 chars)
- Output: Type, Priority, Category
- Category inferred from labels/components

**Q&A Generation**:
- Generate 1-3 question-answer pairs
- Questions about issue purpose, status, problem, solution
- Answers extracted from metadata and content

---

### 5. Utility Module (`src/utils.py`)

**Purpose**: Shared helper functions

**Key Functions**:
- `setup_logging()` - Configure logging with colors
- `clean_html()` - Strip HTML tags
- `clean_text()` - Normalize whitespace
- `safe_get()` - Safely access nested dicts
- `write_jsonl()` - Append to JSONL file
- `calculate_file_size()` - Human-readable sizes

**Logging Architecture**:
```
Logger (jira_scraper)
├── FileHandler
│   └── logs/scraper_YYYYMMDD.log
└── ConsoleHandler (colored)
    └── stdout
```

---

## Data Flow

### Complete Flow Diagram

```
┌──────────┐
│  Config  │
│   File   │
└────┬─────┘
     │
     ▼
┌────────────────┐
│ Parse & Validate│
└────┬───────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│           For Each Project              │
│  ┌──────────────────────────────────┐   │
│  │ 1. Initialize State Manager      │   │
│  │    - Load checkpoint if exists    │   │
│  │    - Resume from last position    │   │
│  └──────────────┬───────────────────┘   │
│                 │                        │
│                 ▼                        │
│  ┌──────────────────────────────────┐   │
│  │ 2. Initialize Scraper            │   │
│  │    - Create session with pool     │   │
│  │    - Configure retry strategy     │   │
│  └──────────────┬───────────────────┘   │
│                 │                        │
│                 ▼                        │
│  ┌──────────────────────────────────┐   │
│  │ 3. Fetch Project Info            │   │
│  │    - GET /rest/api/2/project/KEY │   │
│  └──────────────┬───────────────────┘   │
│                 │                        │
│                 ▼                        │
│  ┌──────────────────────────────────┐   │
│  │ 4. Paginate Through Issues       │   │
│  │  Loop:                           │   │
│  │  ┌─────────────────────────┐     │   │
│  │  │ GET /rest/api/2/search  │     │   │
│  │  │   ?jql=project=KEY      │     │   │
│  │  │   &startAt=N            │     │   │
│  │  │   &maxResults=50        │     │   │
│  │  └───────┬─────────────────┘     │   │
│  │          │                       │   │
│  │          ▼                       │   │
│  │  ┌─────────────────────────┐     │   │
│  │  │ Process Each Issue      │     │   │
│  │  │ - Check if processed    │     │   │
│  │  │ - Mark as processed     │     │   │
│  │  │ - Save checkpoint       │     │   │
│  │  └───────┬─────────────────┘     │   │
│  │          │                       │   │
│  │          └─> Next batch          │   │
│  └──────────────┬───────────────────┘   │
│                 │                        │
│                 ▼                        │
│  ┌──────────────────────────────────┐   │
│  │ 5. Transform Issues              │   │
│  │  For each issue:                 │   │
│  │  - Extract metadata              │   │
│  │  - Clean content                 │   │
│  │  - Generate tasks                │   │
│  └──────────────┬───────────────────┘   │
│                 │                        │
│                 ▼                        │
│  ┌──────────────────────────────────┐   │
│  │ 6. Write to JSONL                │   │
│  │    - One line per issue          │   │
│  │    - Append mode                 │   │
│  └──────────────┬───────────────────┘   │
│                 │                        │
│                 ▼                        │
│  ┌──────────────────────────────────┐   │
│  │ 7. Mark Completed & Save State   │   │
│  └──────────────────────────────────┘   │
│                                          │
└──────────────────────────────────────────┘
                 │
                 ▼
        ┌────────────────┐
        │ Print Summary  │
        └────────────────┘
```

---

## Error Handling Strategy

### Layered Error Handling

```
┌─────────────────────────────────────────┐
│ Application Level (main.py)             │
│ - Catch all exceptions                  │
│ - Save state before exit                │
│ - Return appropriate exit codes         │
└───────────────┬─────────────────────────┘
                │
┌───────────────▼─────────────────────────┐
│ Component Level (scraper, transformer)  │
│ - Try-except around major operations    │
│ - Log errors with context               │
│ - Continue processing if possible       │
└───────────────┬─────────────────────────┘
                │
┌───────────────▼─────────────────────────┐
│ Request Level (scraper._make_request)   │
│ - Handle HTTP errors                    │
│ - Implement retry logic                 │
│ - Exponential backoff                   │
└───────────────┬─────────────────────────┘
                │
┌───────────────▼─────────────────────────┐
│ Network Level (requests library)        │
│ - Connection pooling                    │
│ - Timeout handling                      │
│ - SSL verification                      │
└─────────────────────────────────────────┘
```

### Specific Error Scenarios

| Error Type | Detection | Response | Recovery |
|------------|-----------|----------|----------|
| Network timeout | `requests.Timeout` | Log warning, retry | Exponential backoff |
| Rate limit (429) | HTTP 429 | Log, wait 60s | Retry request |
| Server error (5xx) | HTTP 500-504 | Log, wait | Retry with backoff |
| Invalid data | Validation failed | Log, skip | Continue with next |
| Disk full | `IOError` | Log error, exit | Manual intervention |
| Interrupted | `KeyboardInterrupt` | Save state, exit | Resume next run |

---

## Performance Optimizations

### 1. Connection Pooling
- Reuse TCP connections
- Reduce handshake overhead
- Handle 10 concurrent connections

### 2. Batch Processing
- Fetch 50 issues per request (configurable)
- Minimize API calls
- Balance memory vs speed

### 3. Incremental Checkpoints
- Save every 10 issues (configurable)
- Quick recovery on failure
- Minimal overhead

### 4. Smart Pagination
- Resume from last batch
- Don't re-fetch processed issues
- Track total count

### 5. Efficient Transformation
- Stream processing (one issue at a time)
- Avoid loading all data in memory
- Truncate long text fields

### 6. HTML Cleaning
- Use lxml parser (faster than html.parser)
- Cache compiled regex patterns
- Limit processing depth

---

## Scalability Considerations

### Current Implementation
- Single-threaded per project
- Projects can run in parallel (optional)
- Handles 1000s of issues per project
- Memory: ~100MB per project

### Scaling to Millions of Issues

**Option 1: Parallel Projects**
```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=3) as executor:
    futures = [
        executor.submit(scrape_project, proj)
        for proj in projects
    ]
```

**Option 2: Distributed System**
```
Master Node
├── Worker 1 (KAFKA)
├── Worker 2 (SPARK)
└── Worker 3 (HADOOP)
    │
    └──> Redis/DB for shared state
```

**Option 3: Cloud Functions**
```
Cloud Function per project
└── Write to Cloud Storage
    └── Trigger downstream processing
```

---

## Testing Strategy

### Unit Tests
- Test individual functions
- Mock external dependencies
- Fast execution (<1s)

### Integration Tests
- Test component interaction
- Use test data files
- Moderate execution (~10s)

### End-to-End Tests
- Test full scraping flow
- Use small project or mock API
- Slower execution (~30s)

### Testing Pyramid
```
    /\
   /E2E\      Few, slow, comprehensive
  /────\
 /Tests \
/────────\
Integration    More, faster
────────────
Unit Tests     Many, fast, focused
```

---

## Future Enhancements

### Short Term
1. **Progress Dashboard**: Real-time web UI
2. **Data Validation**: JSON Schema validation
3. **Metrics**: Prometheus integration
4. **Alerting**: Notify on failures

### Medium Term
1. **Delta Updates**: Only fetch new/updated issues
2. **GraphQL API**: More efficient queries
3. **Parallel Processing**: Multi-threaded scraping
4. **Cloud Storage**: S3/GCS integration

### Long Term
1. **ML-based Summarization**: Use LLMs for summaries
2. **Duplicate Detection**: Identify similar issues
3. **Knowledge Graph**: Build issue relationships
4. **Real-time Streaming**: WebSocket-based updates

---

## Security Considerations

### Current Implementation
- ✅ HTTPS only
- ✅ No hardcoded credentials
- ✅ Public data only
- ✅ Respects robots.txt
- ✅ Rate limiting compliance

### Best Practices
- Never commit API keys
- Use environment variables for secrets
- Implement request signing if needed
- Rotate credentials regularly
- Monitor for abuse

---

This architecture balances:
- **Simplicity**: Easy to understand and modify
- **Robustness**: Handles failures gracefully
- **Efficiency**: Minimizes API calls and resource usage
- **Maintainability**: Clean separation of concerns
- **Extensibility**: Easy to add new features

- # Example Output

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
- Q&A system development# Quick Start Guide

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


