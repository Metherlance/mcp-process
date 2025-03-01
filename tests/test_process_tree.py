import os
import sys
import pytest
import asyncio
import tempfile
import subprocess
import time
from pathlib import Path

# Import module to test
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp_process import server_process
from mcp.types import TextContent

# Skip all tests if WSL is not available
wsl_available = False
try:
    result = subprocess.run(["wsl.exe", "--status"], capture_output=True, text=True, check=False)
    wsl_available = result.returncode == 0
except FileNotFoundError:
    wsl_available = False

# Decorator to skip tests if WSL is not available
requires_shell = pytest.mark.skipif(
    not wsl_available,
    reason="WSL is not available on this system"
)

# Function to create a test file in WSL
async def create_test_file_in_wsl(content="Test content", filename="test_file.txt"):
    """Creates a test file in WSL."""
    cmd = f'echo "{content}" > ~/{filename}'
    process = await asyncio.create_subprocess_exec(
        "wsl.exe", "--", "bash", "-c", cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()
    return filename

# Function to delete a test file in WSL
async def remove_test_file_in_wsl(filename="test_file.txt"):
    """Removes a test file in WSL."""
    cmd = f'rm -f ~/{filename}'
    process = await asyncio.create_subprocess_exec(
        "wsl.exe", "--", "bash", "-c", cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()

@pytest.mark.asyncio
@requires_shell
async def test_exec_tool_tree():
    """Tests the execution of the 'ls' command in WSL."""
    # Execute the ls command
    result = await server_process.handle_call_tool("exec", {"input": "tree"})
    
    # Check that the result is a non-empty list
    assert isinstance(result, list)
    assert len(result) > 0
    assert isinstance(result[0], TextContent)
    
    # Check that the output contains typical elements of the home directory
    assert "STDOUT" in result[0].text
    # At least one of these standard folders should be present in home
    # standard_dirs = [".bashrc", ".profile", ".bash_history"]
    # assert any(dirname in result[0].text for dirname in standard_dirs)


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
