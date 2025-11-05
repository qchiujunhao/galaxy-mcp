# Galaxy MCP Server

This project provides a Model Context Protocol (MCP) server for interacting with the Galaxy bioinformatics platform. It enables AI assistants and other clients to connect to Galaxy instances, search and execute tools, manage workflows, and access other features of the Galaxy ecosystem.

## Project Overview

This repository contains a Python-based MCP server implementation that provides comprehensive integration with Galaxy's API through BioBlend.

Note: There is also a work-in-progress TypeScript implementation available in a separate branch of this repository.

## Key Features

- **Galaxy Connection**: Connect to any Galaxy instance with a URL and API key
- **Server Information**: Retrieve comprehensive server details including version, configuration, and capabilities
- **Tools Management**: Search, view details, and execute Galaxy tools
- **Workflow Integration**: Access and import workflows from the Interactive Workflow Composer (IWC)
- **History Operations**: Manage Galaxy histories and datasets
- **File Management**: Upload files to Galaxy from local storage
- **Comprehensive Testing**: Full test suite with mock-based testing for reliability

## Quick Start

The fastest way to get started is using `uvx`:

```bash
# Run the server directly without installation
uvx galaxy-mcp

# Run with MCP developer tools for interactive exploration
uvx --from galaxy-mcp mcp dev galaxy_mcp.server

# Run as a deployed MCP server
uvx --from galaxy-mcp mcp run galaxy_mcp.server
```

You'll need to set up your Galaxy credentials via environment variables:

```bash
export GALAXY_URL=<galaxy_url>
export GALAXY_API_KEY=<galaxy_api_key>
```

### Alternative Installation

```bash
# Install from PyPI
pip install galaxy-mcp

# Or from source
cd mcp-server-galaxy-py
pip install -r requirements.txt
mcp run main.py
```

## Connect to Claude Desktop
- Ensure that GalaxyMCP runs with `uvx galaxy-mcp`
- Add `export GALAXY_SERVER=https://usegalaxy.org` to your .bashrc (or equiv)
- Download and install [claude desktop](https://www.claude.com/download)
- Go to Settings -> Developer -> Edit Config
- Add this to `claude_desktop_config.json`
```
{
  "mcpServers": {
    "galaxy-mcp": {
      "command": "uvx",
      "args": ["galaxy-mcp"],
      "env": {
        "GALAXY_URL": "https://usegalaxy.org",
        "GALAXY_API_KEY": "SECRETS"
      }
    }
  }
}
```
- Under the developer menu, you should now see `galaxy-mcp` as running (you may need to restart Claude desktop)
- Prompt Claude with "can you connect to galaxy"
- If you have not provided the optional env config you'll be asked for connection details which you can provide like "Use my Galaxy API key: XXXXXXX"
- Talk to Claude to work with your galaxy instance, e.g. "give a summary with my histories"

  
## Development Guidelines

See the [Python implementation README](mcp-server-galaxy-py/README.md) for specific instructions and documentation.

## License

[MIT](LICENSE)
