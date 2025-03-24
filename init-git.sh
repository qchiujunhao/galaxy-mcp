#!/bin/bash

# Navigate to the repository directory
cd ~/work/galaxy-mcp

# Initialize git repository
git init

# Add all files
git add .

# Commit the files
git commit -m "Initial commit: Galaxy MCP implementation"

echo "Git repository initialized successfully with initial commit"