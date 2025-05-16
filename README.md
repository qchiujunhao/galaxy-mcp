# Galaxy MCP Server

This project provides a Model Context Protocol (MCP) server for interacting with the Galaxy bioinformatics platform. It enables AI assistants and other clients to connect to Galaxy instances, search and execute tools, manage workflows, and access other features of the Galaxy ecosystem.

## Project Overview

This repository contains a Python-based MCP server implementation that provides comprehensive integration with Galaxy's API through BioBlend.

Note: There is also a work-in-progress TypeScript implementation available in a separate branch of this repository.

## Key Features

- **Galaxy Connection**: Connect to any Galaxy instance with a URL and API key
- **Tools Management**: Search, view details, and execute Galaxy tools
- **Workflow Integration**: Access and import workflows from the Interactive Workflow Composer (IWC)
- **History Operations**: Manage Galaxy histories and datasets
- **File Management**: Upload files to Galaxy from local storage
- **Comprehensive Testing**: Full test suite with mock-based testing for reliability

## Quick Start

```bash
cd mcp-server-galaxy-py
pip install -r requirements.txt
mcp run main.py
```

You'll need to set up your Galaxy credentials via environment variables:
```bash
export GALAXY_URL=<galaxy_url>
export GALAXY_API_KEY=<galaxy_api_key>
```

## Development Guidelines

See the [Python implementation README](mcp-server-galaxy-py/README.md) for specific instructions and documentation.

## License

[MIT](LICENSE)