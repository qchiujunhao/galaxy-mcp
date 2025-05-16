# Development Guide

This guide covers the development workflow for the Galaxy MCP Python implementation.

## Development Setup

### Quick Start

```bash
# Install all development dependencies
make install-dev

# Run all checks (lint + test)
make check

# Start development server
make dev
```

### Manual Setup

```bash
# Create virtual environment (optional)
python -m venv venv
source venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
uv pip install -r requirements-test.txt
uv pip install -e .

# Install pre-commit hooks
pre-commit install
```

### Pre-commit Setup

The project uses pre-commit hooks to maintain code quality. These hooks run automatically when you commit changes.

```bash
# Install pre-commit hooks (required)
uv run pre-commit install

# Run pre-commit manually on all files
uv run pre-commit run --all-files

# Run pre-commit on specific files
uv run pre-commit run --files src/galaxy_mcp/server.py

# Skip pre-commit temporarily (not recommended)
git commit --no-verify

# Update pre-commit hooks to latest versions
uv run pre-commit autoupdate
```

Pre-commit hooks include:
- Trailing whitespace removal
- End-of-file fixing
- YAML/JSON/TOML validation
- Python code formatting with ruff
- Python linting with ruff
- Markdown formatting with prettier

Note: The hooks will automatically fix many issues. If a commit fails due to pre-commit, simply review the changes and commit again.

## Available Commands

### Using Make (Recommended)

The project includes a Makefile with all common development commands:

```bash
make help          # Show all available commands
make install       # Install runtime dependencies
make install-dev   # Install development dependencies
make lint          # Run linting checks (via pre-commit)
make format        # Auto-format code (via pre-commit)
make format-quick  # Quick format (ruff + prettier only)
make test          # Run tests
make test-cov      # Run tests with coverage
make test-watch    # Run tests in watch mode
make clean         # Clean build artifacts
make build         # Build package
make check         # Run all checks (lint + test)
make run           # Run the MCP server
make dev           # Run MCP dev server
```

### Using uv Directly

All commands can also be run directly with uv:

```bash
# Formatting and linting
uv run ruff format .
uv run ruff check .
uv run ruff check --fix .

# Testing
uv run pytest
uv run pytest --cov=galaxy_mcp --cov-report=html
uv run pytest-watch

# Type checking
uv run mypy src/galaxy_mcp

# Building
uv run python -m build
```

### Using tox

Test across multiple Python versions:

```bash
# Test on all Python versions
tox

# Test specific version
tox -e py312

# Run only linting
tox -e lint

# Run type checking
tox -e type
```

## Code Quality Standards

### Formatting and Linting

- Code is formatted with `ruff`
- Linting follows PEP 8 guidelines
- Line length limit: 100 characters
- Import sorting is handled by `ruff`

### Type Checking

- All code should be type-annotated
- Use `mypy` for type checking
- Type stubs are included for external dependencies

### Pre-commit Hooks

The project uses pre-commit hooks for automated checks:

```bash
# Install hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

Hooks include:

- Trailing whitespace removal
- End-of-file fixing
- YAML/JSON/TOML validation
- Ruff formatting and linting
- Type checking with mypy

## Testing

### Test Structure

Tests are organized by functionality:

- `test_connection.py` - Galaxy connection and authentication
- `test_history_operations.py` - History-related operations
- `test_dataset_operations.py` - Dataset upload/download
- `test_tool_operations.py` - Tool search and execution
- `test_workflow_operations.py` - Workflow import and invocation
- `test_integration.py` - End-to-end scenarios

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
uv run pytest tests/test_history_operations.py

# Run with verbose output
uv run pytest -v

# Run in watch mode
make test-watch
```

### Test Coverage

- Aim for >90% test coverage
- Coverage reports are generated in HTML format
- View coverage report: `open htmlcov/index.html`

## Continuous Integration

### GitHub Actions

The project uses GitHub Actions for CI/CD:

1. **Python Tests** (`python-tests.yml`)

   - Runs on push/PR to main branch
   - Tests on Python 3.10, 3.11, 3.12
   - Includes linting, type checking, and coverage
   - Uploads coverage to Codecov

2. **Release** (`python-release.yml`)
   - Triggered on GitHub release
   - Builds and publishes to PyPI
   - Optionally publishes to Test PyPI first

### Local CI Simulation

Run the full CI suite locally:

```bash
# Run all checks that CI would run
make check
tox
```

## Release Process

### Version Management

Version is managed in `pyproject.toml`:

```toml
[project]
version = "0.1.0"
```

### Release Checklist

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Run all tests: `make check`
4. Build package: `make build`
5. Test package locally
6. Create git tag: `git tag v0.1.0`
7. Push tag: `git push origin v0.1.0`
8. Create GitHub release
9. CI will automatically publish to PyPI

### Manual Publishing

```bash
# Build package
make build

# Test upload to Test PyPI
uv run twine upload --repository testpypi dist/*

# Upload to PyPI
uv run twine upload dist/*
```

## Development Tips

### Environment Variables

Create a `.env` file for local development:

```bash
GALAXY_URL=https://your-galaxy-instance.org
GALAXY_API_KEY=your-api-key
```

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Performance Profiling

Use `cProfile` for performance analysis:

```bash
python -m cProfile -s cumulative src/galaxy_mcp/server.py
```

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure package is installed in development mode: `pip install -e .`
2. **Type errors**: Run `mypy` to catch type issues early
3. **Test failures**: Check test isolation and mock setup
4. **Build errors**: Clean build artifacts: `make clean`

### Getting Help

- Check existing issues on GitHub
- Run tests with verbose output: `pytest -vv`
- Enable debug logging for detailed output
- Use `pdb` for interactive debugging
