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
async def test_exec_tool_ls():
    """Tests the execution of the 'ls' command in WSL."""
    # Execute the ls command
    result = await server_process.handle_call_tool("exec", {"input": "ls -la ~/"})
    
    # Check that the result is a non-empty list
    assert isinstance(result, list)
    assert len(result) > 0
    assert isinstance(result[0], TextContent)
    
    # Check that the output contains typical elements of the home directory
    assert "STDOUT" in result[0].text
    # At least one of these standard folders should be present in home
    standard_dirs = [".bashrc", ".profile", ".bash_history"]
    assert any(dirname in result[0].text for dirname in standard_dirs)

@pytest.mark.asyncio
@requires_shell
async def test_exec_tool_echo():
    """Tests the execution of the 'echo' command in WSL."""
    test_message = "Hello from WSL test"
    result = await server_process.handle_call_tool("exec", {"input": f'echo "{test_message}"'})
    
    assert isinstance(result, list)
    assert len(result) > 0
    assert isinstance(result[0], TextContent)
    assert "STDOUT" in result[0].text
    assert test_message in result[0].text

@pytest.mark.asyncio
@requires_shell
async def test_exec_tool_with_file_operations():
    """Tests file operations."""
    # Create a test file
    test_filename = f"tmp/test_file_{int(time.time())}.txt"
    test_content = f"Test content generated at {time.time()}"
    
    try:
        # File creation
        create_cmd = f'echo "{test_content}" > {test_filename}'
        result = await server_process.handle_call_tool("exec", {"input": create_cmd})
        assert (result[0].text.startswith("Code de sortie: 0") or result[0].text.startswith("return code: 0"))
        
        # Check that the file exists
        cat_cmd = f'cat {test_filename}'
        result = await server_process.handle_call_tool("exec", {"input": cat_cmd})
        assert test_content in result[0].text
        
    finally:
        # Cleanup: remove the test file
        await server_process.handle_call_tool("exec", {"input": f'rm -f {test_filename}'})

@pytest.mark.asyncio
@requires_shell
async def test_exec_tool_dangerous_command():
    """Tests detection of dangerous commands."""
    # Save the dangerous commands configuration
    original_validation_commands = server_process.config["forbidden_words"]
    
    try:
        # Define a test command as dangerous
        server_process.config["forbidden_words"] = ["test_dangerous"]
        
        # Execute the "dangerous" command
        result = await server_process.handle_call_tool("exec", {"input": "echo test_dangerous"})
        
        # Check that the command is blocked
        assert "⚠️" in result[0].text
        assert "test_dangerous" in result[0].text
        
    finally:
        # Restore the original configuration
        server_process.config["forbidden_words"] = original_validation_commands

@pytest.mark.asyncio
@requires_shell
async def test_exec_tool_with_timeout():
    """Tests command timeout."""
    # Execute a command that takes time (sleep)
    result = await server_process.handle_call_tool("exec", {
        "input": "sleep 3",
        "timeout": 1  # Short timeout to force expiration
    })
    
    # Check that the command timed out
    assert "The command timed out" in result[0].text or "La commande a expiré" in result[0].text

@pytest.mark.asyncio
@requires_shell
async def test_multiple_commands():
    """Tests execution of multiple commands in succession."""
    commands = [
        "echo 'Test 1'",
        "pwd",
        "whoami",
        "echo 'Test final'"
    ]
    
    results = []
    for cmd in commands:
        result = await server_process.handle_call_tool("exec", {"input": cmd})
        results.append(result)
    
    # Check that all commands worked
    assert all(("Code de sortie: 0" in r[0].text or "return code: 0" in r[0].text) for r in results)
    assert "Test 1" in results[0][0].text
    assert "Test final" in results[3][0].text


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
