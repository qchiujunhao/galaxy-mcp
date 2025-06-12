# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2025-06-11

### Added

- `filter_tools_by_dataset` MCP tool to recommend Galaxy tools based on dataset types/keywords
- Comprehensive test suite for the new filtering functionality

### Changed

- Improved error handling consistency across all MCP tools

## [0.2.0] - 2025-05-21

### Added

- `get_server_info` MCP tool to retrieve comprehensive Galaxy server information including version, URL, and configuration details

## [0.1.0] - 2025-01-16

### Added

- Initial release of galaxy-mcp
- MCP server implementation for Galaxy bioinformatics platform
- Connection and authentication with Galaxy instances
- History management (create, list, get details)
- Tool operations (search, run)
- Dataset operations (upload, download)
- Workflow operations (import from IWC, list invocations)
- Comprehensive test suite
- Command-line interface via `galaxy-mcp` command
- Environment variable support for configuration
