# Galaxy MCP Server - TypeScript Implementation

This is the TypeScript implementation of the Galaxy MCP server, providing a Model Context Protocol server for interacting with Galaxy instances through Node.js.

## Features

- Full Galaxy API integration via MCP protocol
- Claude/Anthropic Galaxy adapter for AI tool usage
- TypeScript interfaces for Galaxy data structures
- Jest testing framework for unit and integration tests

## Requirements

- Node.js 16+
- NPM 7+
- A Galaxy instance with API access

## Installation

```bash
# Install dependencies
npm install

# Build the TypeScript code
npm run build
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
# Start the MCP server
npm start

# Run in development mode with auto-reload
npm run dev

# Run the example client
npm run example
```

## API Reference

The TypeScript implementation provides a client-server architecture:

- `galaxy-mcp-server.ts`: The MCP server implementation
- `galaxy-mcp-client.ts`: A client for interacting with the server
- `claude-galaxy-adapter.ts`: A Claude-specific adapter for Galaxy

## Testing

Run tests with Jest:

```bash
# Run all tests
npm test

# Run a specific test
npx jest -t "test name pattern"
```

## Development

### Code Style Guidelines
- Use TypeScript strict mode with ES2022 target and Node16 modules
- Use ES modules (project uses `"type": "module"`)
- Define interfaces for all data structures and use strict typing
- Prefer async/await pattern for all asynchronous operations

### Development Commands
- TypeCheck: `npx tsc --noEmit`
- Lint: `npx eslint src/**/*.ts`

## License

[MIT](../LICENSE)