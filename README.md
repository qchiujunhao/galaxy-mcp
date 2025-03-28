# Galaxy MCP Server

This project provides Model Context Protocol (MCP) servers for interacting with the Galaxy bioinformatics platform. It enables AI assistants and other clients to connect to Galaxy instances, search and execute tools, manage workflows, and access other features of the Galaxy ecosystem.

## Project Structure

This repository contains two independent implementations:

- **[TypeScript Implementation](mcp-server-galaxy-ts/README.md)**: A Node.js-based MCP server
- **[Python Implementation](mcp-server-galaxy-py/README.md)**: A Python-based MCP server

Both implementations provide similar functionality but may have slightly different feature sets or interfaces.

## Key Features

- **Galaxy Connection**: Connect to any Galaxy instance with a URL and API key
- **Tools Management**: Search, view details, and execute Galaxy tools
- **Workflow Integration**: Access and import workflows from the Interactive Workflow Composer (IWC)
- **History Operations**: Manage Galaxy histories and datasets
- **File Management**: Upload files to Galaxy from local storage

## Quick Start

For the TypeScript implementation:
```bash
cd mcp-server-galaxy-ts
npm install
npm run build
npm start
```

For the Python implementation:
```bash
cd mcp-server-galaxy-py
pip install -r requirements.txt
mcp run main.py
```

For both implementations, you'll need to set up your Galaxy credentials via environment variables:
```bash
export GALAXY_URL=<galaxy_url>
export GALAXY_API_KEY=<galaxy_api_key>
```

## Development Guidelines

Each implementation directory contains a README with more specific instructions and documentation.

## License

[MIT](LICENSE)