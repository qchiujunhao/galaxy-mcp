# Galaxy MCP Server Usage Examples

This document provides common usage patterns and examples for the Galaxy MCP server.

## Quick Start

### 1. Connect to Galaxy

First, you need to establish a connection to your Galaxy instance:

```python
# Option 1: Use environment variables (recommended)
# Set GALAXY_URL and GALAXY_API_KEY in your environment or .env file
connect()

# Option 2: Provide credentials directly
connect(url="https://your-galaxy-instance.org", api_key="your-api-key")
```

#### Get server information

Once connected, you can retrieve comprehensive information about the Galaxy server:

```python
server_info = get_server_info()
# Returns: {
#   "url": "https://your-galaxy-instance.org/",
#   "version": {"version_major": "23.1", "version_minor": "1", ...},
#   "config": {
#     "brand": "Galaxy",
#     "allow_user_creation": true,
#     "enable_quotas": false,
#     "ftp_upload_site": "ftp.galaxy.org",
#     "support_url": "https://help.galaxyproject.org/",
#     ...
#   }
# }
```

### 2. Working with Histories

#### List all histories

```python
histories = get_histories()
# Returns: [{"id": "abc123", "name": "My Analysis", ...}, ...]
```

#### Get just IDs and names (simplified)

```python
history_list = list_history_ids()
# Returns: [{"id": "abc123", "name": "My Analysis"}, ...]
```

#### Get history details

```python
# IMPORTANT: Pass only the ID string, not the entire history object
history_id = "abc123"  # or history_list[0]["id"]
details = get_history_details(history_id)
# Returns: {"history": {...}, "contents": [...]}
```

### 3. Working with Tools

#### Search for tools

```python
tools = search_tools("fastqc")
# Returns: {"tools": [...]}
```

#### Get tool details

```python
tool_details = get_tool_details("toolshed.g2.bx.psu.edu/repos/devteam/fastqc/fastqc/0.72")
# Returns: Detailed tool information including parameters
```

#### Run a tool

```python
# First, create or select a history
history_id = "abc123"

# Prepare tool inputs (depends on the specific tool)
inputs = {
    "input_file": {"src": "hda", "id": "dataset_id"},
    "param1": "value1"
}

# Run the tool
result = run_tool(history_id, tool_id, inputs)
```

### 4. File Operations

#### Upload a file

```python
# Upload to default history
upload_result = upload_file("/path/to/your/file.txt")

# Upload to specific history
upload_result = upload_file("/path/to/your/file.txt", history_id="abc123")
```

### 5. Workflow Operations

#### Browse IWC workflows

```python
# Get all workflows from Interactive Workflow Composer
iwc_workflows = get_iwc_workflows()

# Search for specific workflows
matching_workflows = search_iwc_workflows("RNA-seq")
```

#### Import a workflow

```python
# Import from IWC using TRS ID
imported = import_workflow_from_iwc("github.com/galaxyproject/iwc/tree/main/workflows/epigenetics/chipseq-pe")
```

## Common Patterns

### Pattern 1: Complete Analysis Pipeline

```python
# 1. Connect to Galaxy
connect()

# 2. Create a new history for the analysis
new_history = create_history("RNA-seq Analysis")
history_id = new_history["id"]

# 3. Upload data files
upload_file("/data/sample1_R1.fastq", history_id)
upload_file("/data/sample1_R2.fastq", history_id)

# 4. Search and run quality control
qc_tools = search_tools("fastqc")
tool_id = qc_tools["tools"][0]["id"]

# 5. Get history contents to find dataset IDs
history_details = get_history_details(history_id)
datasets = history_details["contents"]

# 6. Run FastQC on uploaded files
for dataset in datasets:
    if dataset["extension"] == "fastq":
        inputs = {"input_file": {"src": "hda", "id": dataset["id"]}}
        run_tool(history_id, tool_id, inputs)
```

### Pattern 2: Working with Existing Data

```python
# 1. Connect and list histories
connect()
histories = list_history_ids()

# 2. Find a specific history
target_history = None
for h in histories:
    if "Project X" in h["name"]:
        target_history = h
        break

if target_history:
    # 3. Get history details
    details = get_history_details(target_history["id"])

    # 4. Find specific datasets
    for item in details["contents"]:
        if item["name"] == "results.txt":
            print(f"Found results: {item['id']}")
```

## Error Handling

### Common Issues and Solutions

1. **"History ID invalid" error**

    - Problem: Passing the entire history object instead of just the ID
    - Solution: Use `history["id"]` not `history`

2. **"Not connected to Galaxy" error**

    - Problem: Trying to use tools before connecting
    - Solution: Always call `connect()` first

3. **"Tool not found" error**
    - Problem: Using incorrect tool ID format
    - Solution: Use the full tool ID from `search_tools()` or `get_tool_panel()`

## Best Practices

1. **Always connect first**: Before using any other tools, establish a connection
2. **Use IDs correctly**: When functions ask for an ID, pass just the ID string, not the entire object
3. **Check return types**: Some functions return lists, others return dictionaries
4. **Handle errors gracefully**: Wrap operations in try-except blocks
5. **Use environment variables**: Store credentials in .env file for security

## Advanced Usage

### Custom Tool Parameters

Different tools require different input formats. Here's how to determine the correct format:

```python
# 1. Get tool details to see required parameters
tool_info = get_tool_details(tool_id, io_details=True)

# 2. Examine the inputs section
for input_param in tool_info["inputs"]:
    print(f"Parameter: {input_param['name']}")
    print(f"Type: {input_param['type']}")
    print(f"Optional: {input_param.get('optional', False)}")
```

### Working with Collections

Galaxy collections group related datasets. Here's how to work with them:

```python
# Check if a history item is a collection
history_details = get_history_details(history_id)
for item in history_details["contents"]:
    if item["history_content_type"] == "dataset_collection":
        print(f"Collection: {item['name']}")
        print(f"Collection type: {item['collection_type']}")
```

## Troubleshooting

If you encounter issues:

1. Check the logs for detailed error messages
2. Verify your Galaxy URL ends with a slash (/)
3. Ensure your API key has the necessary permissions
4. Test with simple operations first (e.g., `get_user()`)

For more help, consult the Galaxy API documentation or the MCP server logs.
