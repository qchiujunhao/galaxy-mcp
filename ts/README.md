# Galaxy MCP (Message Command Protocol)

A Message Command Protocol system that enables Claude and other AI assistants to interact with Galaxy, a bioinformatics platform.

## Overview

This project provides a bridge between AI assistants like Claude and Galaxy bioinformatics servers. It consists of:

1. **MCP Server**: A Node.js server that translates commands into Galaxy API calls
2. **MCP Client**: A client library for sending commands to the MCP server
3. **Claude Galaxy Adapter**: A high-level adapter specifically designed for Claude to interact with Galaxy

## Components

### Galaxy MCP Server

The server component listens for commands and interacts with the Galaxy API. It handles:

- Authentication with Galaxy servers
- Managing sessions and history
- Processing datasets
- Running tools and workflows
- Uploading files

### Galaxy MCP Client

A client library that sends commands to the MCP server. It provides methods for:

- Connecting to Galaxy
- Managing histories and datasets
- Running tools and workflows
- Searching for tools
- Uploading files

### Claude Galaxy Adapter

An adapter specifically designed for Claude to interact with Galaxy in a more natural way. It provides:

- Natural language interface for Galaxy operations
- Simplified command structure
- Human-readable responses

## Getting Started

### Prerequisites

- Node.js (v16+)
- TypeScript
- A Galaxy server instance and API key

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/galaxy-mcp.git
   cd galaxy-mcp
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Build the project:
   ```
   npm run build
   ```

### Running the Server

Start the MCP server:

```
npm start
```

By default, the server runs on port 3000. You can change this by setting the `PORT` environment variable.

### Example Usage

Run the included example:

```
npm run example
```

This will demonstrate how Claude can interact with Galaxy through the MCP system.

## Command Reference

The following commands are supported:

- `connect` - Connect to a Galaxy server
- `listHistories` - List all histories
- `getHistory` - Get details of a specific history
- `listDatasets` - List datasets in a history
- `getDataset` - Get details of a specific dataset
- `runWorkflow` - Run a workflow
- `searchTools` - Search for tools
- `runTool` - Run a tool
- `uploadFile` - Upload a file to Galaxy
- `getUser` - Get current user information

## Claude Integration

Claude can parse user requests and translate them into MCP commands. For example:

- "Connect to Galaxy URL: https://usegalaxy.org API Key: your-api-key"
- "List my histories"
- "Run FASTQC on my sequence data"
- "Upload this file to Galaxy"

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Galaxy Project (https://galaxyproject.org/)
- Anthropic's Claude