#!/usr/bin/env python3
"""
Configuration helper for scripts to load API base URL from environment.
Supports both local development and Docker environments.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from backend/.env
backend_env = Path(__file__).parent.parent / "backend" / ".env"
if backend_env.exists():
    load_dotenv(backend_env)

# Get API base URL from environment
# Defaults:
#   - Docker: http://web:8000 (uses internal Docker network)
#   - Local: http://localhost:8000
# Check if running in Docker by looking for DOCKER_CONTAINER env var
is_docker = os.getenv("DOCKER_CONTAINER") == "true"
default_url = "http://web:8000" if is_docker else "http://localhost:8000"

API_BASE_URL = os.getenv("API_BASE_URL", default_url)
API_BASE = f"{API_BASE_URL}/api"

__all__ = ["API_BASE_URL", "API_BASE"]
