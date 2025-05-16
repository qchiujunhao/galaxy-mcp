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

```bash
# Install dependencies
pip install -r requirements.txt

# Or using uv package manager
uv pip install -r requirements.txt
```

## Configuration

The server requires Galaxy credentials to connect to an instance. You can provide these via environment variables:

```bash
export GALAXY_URL=<galaxy_url>
export GALAXY_API_KEY=<galaxy_api_key>
```

Alternatively, create a `.env` file in the project root with these variables.

## Usage

```bash
# Run the MCP server
mcp run main.py

# Run in development mode with interactive explorer
mcp dev main.py
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

## Development

### Code Style Guidelines
- Use Python 3.12+ features
- Employ type hints where appropriate
- Follow PEP 8 style guidelines

### Development Commands
- Lint the code: `ruff check .`
- Start the development server: `mcp dev main.py

## License

[MIT](../LICENSE)