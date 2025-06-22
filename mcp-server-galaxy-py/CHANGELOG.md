# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-06-22

### Added

- `get_dataset_details` MCP tool for comprehensive dataset metadata with optional content preview
- `download_dataset` MCP tool to download datasets to local filesystem with flexible naming options
- Binary file support in dataset content preview with hexadecimal display
- Enhanced parameter documentation with detailed Galaxy ID format examples and comprehensive descriptions

### Changed

- **BREAKING**: `get_job_details` now accepts `dataset_id` instead of `job_id` as primary parameter, using dataset provenance to find creating job
- Upgraded from FastMCP 1.0 to FastMCP2 with remote deployment support via SSE transport
- Simplified parameter validation by removing complex JSON string parsing across all functions
- Improved API consistency with plain string-only identifier parameters
- Consolidated dependency management to use uv with lock file
- Enhanced test coverage for job operations and dataset functionality

### Fixed

- Job lookup now works with the more commonly available dataset IDs instead of job IDs
- Fallback mechanism for job details when provenance data is unavailable
- Better error handling for dataset state validation in download operations

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
