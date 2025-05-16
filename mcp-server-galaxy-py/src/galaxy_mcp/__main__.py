"""Command-line entry point for Galaxy MCP server."""

import asyncio

from . import server


def run():
    """Run the MCP server."""
    # Use the FastMCP's built-in stdio handler
    return asyncio.run(server.mcp.run_stdio_async())


if __name__ == "__main__":
    run()
