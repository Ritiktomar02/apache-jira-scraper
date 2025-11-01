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