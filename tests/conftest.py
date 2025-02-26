import os
import sys
import pytest
import asyncio

# Print current path for debugging
current_path = os.path.abspath(__file__)
print(f"LOADING CONFTEST FROM: {current_path}")

# Ensure our package is in PYTHONPATH
proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(proj_dir, "src"))
print(f"PROJECT DIRECTORY: {proj_dir}")
print(f"SRC DIRECTORY: {os.path.join(proj_dir, 'src')}")

# For newer versions of pytest-asyncio
@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for asyncio tests."""
    print("Creating event loop...")
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
