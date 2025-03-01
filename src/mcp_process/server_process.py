import os
import sys
import subprocess
import asyncio
import argparse
import re

# Set this at the beginning of your script
asyncio.get_event_loop().set_debug(True)

# Configure default encoding
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding='utf-8')

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio

# Command line argument parsing
parser = argparse.ArgumentParser(description="MCP Server for process")
parser.add_argument("--process-path-args", type=str, help="Path to process and immutable args", default="wsl.exe --cd " + os.getcwd())
parser.add_argument("--forbidden-words", type=str, nargs="+", 
                    help="List of forbidden words in commands", 
                    default=["rm -rf", "shutdown", "reboot"])


parser.add_argument("--filter-patterns", type=str, nargs="+",
                    help="Patterns to filter from session outputs (regular expressions)", 
                    default=["\\x07", "\\x1b\\[25l"])  # "\\x1b\\[K", new line, bell, hide cursor 
parser.add_argument("--exec-name", type=str, help="Custom name for the exec tool", default="exec")
parser.add_argument("--exec-description", type=str,
                   help="Custom description for the exec tool",
                   default="Executes a static command (ls pwd cat echo ps mkdir cp grep find git sed ...) and returns its result")
parser.add_argument("--exec-timeout", type=int,
                    help="Timeout for exec commands (seconds)", default=60)

args, unknown = parser.parse_known_args()

# Default configuration
DEFAULT_CONFIG = {
    "process_path_args": args.process_path_args,
    "forbidden_words": args.forbidden_words,
    "filter_patterns": args.filter_patterns,

    "exec_name": args.exec_name,
    "exec_description": args.exec_description,
    "exec_timeout": args.exec_timeout,
}


# Load configuration
def load_config():
    """Loads configuration by combining arguments and default values."""
    config = DEFAULT_CONFIG.copy()
    
    # Compilation of filter patterns
    config["compiled_filters"] = [re.compile(pattern) for pattern in config["filter_patterns"]]
    
    return config

config = load_config()

server = Server("mcp-process")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Lists available tools."""
    tools = []
    
    # Add exec tool if exec_name is not empty
    if config["exec_name"]:
        tools.append(
            types.Tool(
                name=config["exec_name"],
                description=config["exec_description"],
                inputSchema={
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "string",
                            "description": "Command to execute in the process"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout before termination (seconds, optional)",
                            "default": config["exec_timeout"]
                        }
                    },
                    "required": ["input"]
                }
            )
        )
        
    return tools

def requires_validation(command: str) -> bool:
    """Checks if the command requires validation."""
    return any(cmd in command for cmd in config["forbidden_words"])

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handles tool executions."""
    global interactive_process
    global stream
    global screen
    
    if name == config["exec_name"]:
        if not arguments:
            raise ValueError("Missing arguments")

        command = arguments.get("input")
        timeout = arguments.get("timeout", config["exec_timeout"])
        
        if not command:
            return [types.TextContent(
                type="text", 
                text="Error: Command not specified."
            )]
        
        # Check if the command requires validation
        if requires_validation(command):
            return [types.TextContent(
                type="text", 
                text=f"⚠️ This command contains a potentially dangerous operation: {command}\n"
                     f"Please reformulate it or explicitly confirm that you want to execute it."
            )]

        try:
            # Execute the command in the shell and capture the output
            shell_exe = f"{args.process_path_args} {command}"
            result = subprocess.run(
                shell_exe,
                shell=False,  # Crucial to avoid Windows operator interpretation >, >>, &&
                capture_output=True,
                text=False,
                timeout=timeout
            )
            
            output = f"return code: {result.returncode}\n"
            if result.stdout:
                output += f"STDOUT:\n{result.stdout.decode('utf-8', errors='replace')}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr.decode('utf-8', errors='replace')}\n"

            return [types.TextContent(type="text", text=output)]
        
        except subprocess.TimeoutExpired:
            return [types.TextContent(
                type="text",
                text=f"The command timed out after {timeout} seconds"
            )]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"Error executing the command: {str(e)}"
            )]    
    else:
        print(f"Unknown tool: {name}", file=sys.stderr)
        raise ValueError(f"Unknown tool: {name}")

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    return []

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    return []
	
async def main():
    """Main function to start the MCP server."""
    print(f"Starting MCP-PROCESS server with process : {args.process_path_args}", file=sys.stderr)
    
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="mcp-process",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

def cli_entry_point():
    """Entry point for the mcp-process command."""
    try:
        asyncio.run(main())
    except* Exception as exc_group:
        for exc in exc_group.exceptions:
            print(f"Exception: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli_entry_point()
