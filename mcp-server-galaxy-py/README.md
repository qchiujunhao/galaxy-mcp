# Galaxy MCP Server - Python Implementation

This is the Python implementation of the Galaxy MCP server, providing a Model Context Protocol server for interacting with Galaxy instances.

## Features

- Complete Galaxy API integration through BioBlend
- Interactive Workflow Composer (IWC) integration
- FastMCP server for high-performance operation
- Type-annotated Python codebase

## Requirements

- Python 3.12+
- BioBlend 1.5.0+
- MCP SDK 1.6.0+
- Requests 2.32.3+

## Installation

### From PyPI (Recommended)

```bash
# Install from PyPI
pip install galaxy-mcp

# Or using uv package manager
uv pip install galaxy-mcp
```

### From Source

```bash
# Clone the repository
git clone https://github.com/galaxyproject/galaxy-mcp.git
cd galaxy-mcp/mcp-server-galaxy-py

# Install in development mode
pip install -e .

# Or using uv package manager
uv pip install -e .
```

## Configuration

The server requires Galaxy credentials to connect to an instance. You can provide these via environment variables:

```bash
export GALAXY_URL=<galaxy_url>
export GALAXY_API_KEY=<galaxy_api_key>
```

Alternatively, create a `.env` file in the project root with these variables.

## Usage

### Quick Start with uvx

The fastest way to run the Galaxy MCP server is using `uvx`:

```bash
# Run the server directly without installation
uvx galaxy-mcp

# Run with MCP developer tools for interactive exploration
uvx --from galaxy-mcp mcp dev galaxy_mcp.server

# Run as a deployed MCP server
uvx --from galaxy-mcp mcp run galaxy_mcp.server
```

### As a standalone MCP server

```bash
# Install and run the MCP server
pip install galaxy-mcp
galaxy-mcp

# The server will wait for MCP protocol messages on stdin
```

### With MCP clients

```bash
# Use with MCP CLI tools
mcp connect galaxy-mcp

# Use with MCP developer tools
mcp dev galaxy-mcp

# Use with other MCP-compatible clients
your-mcp-client galaxy-mcp
```

See [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) for detailed usage patterns and common examples.

## Available MCP Tools

The Python implementation provides the following MCP tools:

- `connect`: Establish connection to a Galaxy instance
- `search_tools`: Find Galaxy tools by name
- `get_tool_details`: Retrieve detailed tool information
- `run_tool`: Execute a Galaxy tool with parameters
- `get_tool_panel`: Retrieve the Galaxy tool panel structure
- `get_user`: Get current user information
- `get_histories`: List available Galaxy histories
- `list_history_ids`: Get simplified list of history IDs and names
- `get_history_details`: Get detailed information about a specific history
- `upload_file`: Upload local files to Galaxy
- `get_invocations`: View workflow executions
- `get_iwc_workflows`: Access Interactive Workflow Composer workflows
- `search_iwc_workflows`: Search IWC workflows by keywords
- `import_workflow_from_iwc`: Import an IWC workflow to Galaxy

## Testing

The project includes a comprehensive test suite using pytest with mock-based testing.

### Running Tests

```bash
# Install test dependencies
uv pip install -r requirements-test.txt

# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=main --cov-report=html

# Run specific test file
uv run pytest tests/test_history_operations.py

# Run tests with verbose output
uv run pytest -v
```

### Test Structure

Tests are organized by functionality:

- `test_connection.py` - Galaxy connection and authentication
- `test_history_operations.py` - History-related operations
- `test_dataset_operations.py` - Dataset upload/download
- `test_tool_operations.py` - Tool search and execution
- `test_workflow_operations.py` - Workflow import and invocation
- `test_integration.py` - End-to-end scenarios

See [tests/README.md](tests/README.md) for more details on the testing strategy.

## Development

### Code Style Guidelines

- Use Python 3.12+ features
- Employ type hints where appropriate
- Follow PEP 8 style guidelines

### Development Commands

- Lint the code: `ruff check .`
- Format the code: `ruff format .`
- Start the development server: `mcp dev main.py`

## License

[MIT](../LICENSE)
