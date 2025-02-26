import os
import sys
import pytest
import asyncio
import time

# Import module to test
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mcp_process.server_process as server_process

# Skip tests if PTY is not available
pty_available = server_process.PTY_AVAILABLE
requires_pty = pytest.mark.skipif(
    not pty_available,
    reason="PTY is not available on this system"
)

@pytest.fixture(scope="function")
async def cleanup_session():
    """Fixture to clean up any session that might be active."""
    yield
    if server_process.interactive_process is not None:
        try:
            server_process.interactive_process.terminate(force=True)
            server_process.interactive_process = None
            print("Session cleaned up after test")
        except Exception as e:
            print(f"Error during cleanup: {e}")

@pytest.mark.asyncio
@requires_pty
async def test_control_key_sequences(cleanup_session):
    """
    Test if control key sequences are interpreted correctly.
    
    This test:
    1. Starts a showkey -a process to display pressed key codes
    2. Sends various control sequences (arrows, F1, Escape)
    3. Checks the output to verify correct interpretation
    """
    try:
        # Step 1: Start showkey -a to capture keypress codes
        start_result = await server_process.handle_call_tool("terminal", {
            "input": "showkey -a\n",
            "wait": 1.0
        })
        
        # Verify session started
        assert isinstance(start_result, list)
        assert len(start_result) > 0
        assert "alive" in start_result[0].text
        
        # Wait for showkey to be ready
        await asyncio.sleep(1)
        
        # Step 2: Send Escape key
        esc_result = await server_process.handle_call_tool("terminal", {
            "input": "\x1b",
            "wait": 0.5
        })
        
        # Step 3: Send arrow keys
        up_arrow_result = await server_process.handle_call_tool("terminal", {
            "input": "\x1b[A",
            "wait": 0.5
        })
        
        down_arrow_result = await server_process.handle_call_tool("terminal", {
            "input": "\x1b[B",
            "wait": 0.5
        })
        
        left_arrow_result = await server_process.handle_call_tool("terminal", {
            "input": "\x1b[D",
            "wait": 0.5
        })
        
        right_arrow_result = await server_process.handle_call_tool("terminal", {
            "input": "\x1b[C",
            "wait": 0.5
        })
        
        # Step 4: Send F1 key
        f1_result = await server_process.handle_call_tool("terminal", {
            "input": "\x1bOP",
            "wait": 0.5
        })
        
        # Step 5: Check results
        # For escape, we expect to see 0x1b (27 decimal) or "^[" in the output
        assert "^[" in esc_result[0].text or "0x1b" in esc_result[0].text or "27" in esc_result[0].text
        
        # For arrow keys, check if the sequence is correctly captured
        # Note: The exact output depends on the terminal and might vary
        assert any(seq in up_arrow_result[0].text for seq in ["^[[A", "\\e[A", "escape sequence"])
        assert any(seq in down_arrow_result[0].text for seq in ["^[[B", "\\e[B", "escape sequence"])
        assert any(seq in left_arrow_result[0].text for seq in ["^[[D", "\\e[D", "escape sequence"])
        assert any(seq in right_arrow_result[0].text for seq in ["^[[C", "\\e[C", "escape sequence"])
        
        # For F1, check if the sequence is correctly captured
        assert any(seq in f1_result[0].text for seq in ["^[OP", "\\eOP", "escape sequence"])
        
    finally:
        # Clean up: terminate showkey
        if server_process.interactive_process is not None and server_process.interactive_process.isalive():
            # Send Ctrl+C
            await server_process.handle_call_tool("terminal", {
                "input": "\x03",
                "wait": 0.5
            })
            
            # If still alive, terminate forcefully
            if server_process.interactive_process is not None and server_process.interactive_process.isalive():
                await server_process.handle_call_tool("terminal_terminate", {})

@pytest.mark.asyncio
@requires_pty
async def test_editor_with_control_keys(cleanup_session):
    """
    Test control keys with a simple editor (nano).
    
    This test:
    1. Opens nano with a test file
    2. Types some text
    3. Uses control keys to save and exit
    4. Checks if the file was created with correct content
    """
    test_file = "test_nano_control.txt"
    test_content = "This is a control key test"
    
    try:
        # Step 1: Open nano with the test file
        start_result = await server_process.handle_call_tool("terminal", {
            "input": f"nano {test_file}\n",
            "wait": 1.0
        })
        
        # Check that the session started
        assert isinstance(start_result, list)
        assert len(start_result) > 0
        assert "alive" in start_result[0].text
        
        # Wait for nano to be ready
        await asyncio.sleep(1)
        
        # Step 2: Type text
        type_result = await server_process.handle_call_tool("terminal", {
            "input": test_content,
            "wait": 0.5
        })
        
        # Step 3: Save with Ctrl+O
        save_result = await server_process.handle_call_tool("terminal", {
            "input": "\x0F",  # Ctrl+O
            "wait": 0.5
        })
        
        # Press Enter to confirm filename
        enter_result = await server_process.handle_call_tool("terminal", {
            "input": "\r",  # Enter
            "wait": 1.5
        })
        
        # Step 4: Exit with Ctrl+X
        exit_result = await server_process.handle_call_tool("terminal", {
            "input": "\x18",  # Ctrl+X
            "wait": 0.5
        })
        
        # Step 5: Check if file exists with correct content
        cat_result = await server_process.handle_call_tool("exec", {
            "input": f"cat {test_file}"
        })
        
        # Check that the file contains the expected text
        assert isinstance(cat_result, list)
        assert len(cat_result) > 0
        assert test_content in cat_result[0].text
        
    finally:
        # Clean up: terminate session if necessary
        if server_process.interactive_process is not None and server_process.interactive_process.isalive():
            await server_process.handle_call_tool("terminal_terminate", {})
            
        # Delete test file
        try:
            await server_process.handle_call_tool("exec", {
                "input": f"rm -f {test_file}"
            })
        except Exception as e:
            print(f"Error cleaning up file: {e}")

if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
