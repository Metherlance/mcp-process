import select
import os
import sys
import json
import subprocess
import asyncio
import argparse
import time
import re
from typing import Optional, List, Dict, Any, Union, Pattern, Tuple
import pyte
from .clean_control_chars import fix_control_at_end


# Configure default encoding
os.environ["PYTHONIOENCODING"] = "utf-8"

# Determine if we're on Windows
IS_WINDOWS = sys.platform.startswith('win')

# For interactive mode, we use different implementations depending on the system
PTY_AVAILABLE = False

try:
    if IS_WINDOWS:
        from winpty import PtyProcess
        PTY_AVAILABLE = True
        print("winpty.PtyProcess available, interactive mode enabled")
    else:
        from ptyprocess import PtyProcess
        PTY_AVAILABLE = True
        print("ptyprocess.PtyProcess available, interactive mode enabled")
except ImportError:
    print("Warning: No PTY module available. Interactive mode disabled.")

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio

# Command line argument parsing
parser = argparse.ArgumentParser(description="MCP Server for process")
parser.add_argument("--process-path-args", type=str, help="Path to process and immutable args", default="wsl.exe --cd " + os.getcwd())
parser.add_argument("--forbidden-words", type=str, nargs="+", 
                    help="List of forbidden words in commands", 
                    default=["rm -rf", "sudo", "shutdown", "reboot"])


parser.add_argument("--filter-patterns", type=str, nargs="+",
                    help="Patterns to filter from session outputs (regular expressions)", 
                    default=["\\x07", "\\x1b\\[25l"])  # "\\x1b\\[K", new line, bell, hide cursor 
parser.add_argument("--exec-name", type=str, help="Custom name for the exec tool", default="exec")
parser.add_argument("--exec-description", type=str,
                   help="Custom description for the exec tool",
                   default="Executes a static command (ls pwd cat echo ps mkdir cp grep find git sed ...) and returns its result")
parser.add_argument("--exec-timeout", type=int,
                    help="Timeout for exec commands (seconds)", default=60)

parser.add_argument("--terminal-name", type=str, help="Custom name for the terminal tool", default="terminal")
parser.add_argument("--terminal-description", type=str,
                   help="Custom description for the terminal tool",
                   default="Create a persistent shell terminal session if it doesn't exist and send input to the shell (applications: vi top htop nano less python ssh mysql ftp ncdu ...) (\\ are forbidden for control key), asynchronous return (the screen may still refresh after the return) '▌' for cursor position in screen")
parser.add_argument("--terminal-wait", type=float,
                    help="Wait delay to get result (terminal async) (seconds)", default=0.2)
parser.add_argument("--no-fix-control", action="store_true", help="Do not fix control characters at end in input like \\n -> \n, \\r -> \r", default=False)
parser.add_argument("--terminal-width", type=int,
                    help="Terminal width for interactive sessions", default=80)
parser.add_argument("--terminal-height", type=int,
                    help="Terminal height for interactive sessions", default=24)

parser.add_argument("--terminate-description", type=str,
                   help="Custom description for the session_terminate tool",
                   default="Terminate the current interactive process/terminal if it exists")
parser.add_argument("--terminate-label", type=str, 
                   help="Custom label for the session_terminate tool", 
                   default="terminal_terminate")

args, unknown = parser.parse_known_args()

# Default configuration
DEFAULT_CONFIG = {
    "process_path_args": args.process_path_args,
    "forbidden_words": args.forbidden_words,
    "filter_patterns": args.filter_patterns,

    "exec_name": args.exec_name,
    "exec_description": args.exec_description,
    "exec_timeout": args.exec_timeout,

    "terminal_name": args.terminal_name,
    "terminal_description": args.terminal_description,
    "terminal_wait": args.terminal_wait,
    "terminal_dimensions": (args.terminal_height, args.terminal_width),

    "terminate_description": args.terminate_description,
    "terminate_name": args.terminate_label,
    "no_fix_control": args.no_fix_control,
}

# Singleton for the interactive process
interactive_process = None

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
    
    # Only add the interactive tool if PTY is available and terminal_name is not empty
    if PTY_AVAILABLE and config["terminal_name"]:
        tools.append(
            types.Tool(
                name=config["terminal_name"],
                description=config["terminal_description"],
                inputSchema={
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "string",
                            "description": "Input to send to the running interactive process. All keys are in hexadecimal format: Enter: \x0A (if doesnt work use \x0D)  Escape: \x1b"
                        }, 
                        # "control": {
                        #     "type": "string",
                        #     "description": "control key (only 1) to send to the running interactive process (will be send after input). Use \n for run a input command. Exemple of keyboard: Left arrow: \x1b[D  Escape: \x1b Ctrl-C: \x03 Home: \x1b[H End: \x1b[F or \x1bOF Backspace: \x7f Delete: \x1b[3~ Tab: \x09 Enter: \x0A (if doesnt work use \x0D) Page Down: \x1b[6~"
                        # },
                        "wait": {
                            "type": "number",
                            "description": "Wait delay to get response (seconds, optional)",
                            "default": config["terminal_wait"]
                        }
                    },                    
                }
            )
        )
        
        tools.append(
            types.Tool(
                name=config["terminate_name"],
                description=config["terminate_description"],
                inputSchema={
                    "type": "object",
                    "properties": {}
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
    
    elif name == config["terminal_name"] and PTY_AVAILABLE:
        # Screen for terminal emulation
        if not arguments:
            raise ValueError("Missing arguments")
            
        command = arguments.get("input")
        # control = arguments.get("control")
        wait = float(arguments.get("wait", config["terminal_wait"]))
        
        # if not command:
        #     return [types.TextContent(
        #         type="text", 
        #         text="Error: Command not specified."
        #     )]
        
        # Ensure the command ends with a newline
        # if not command.endswith('\n'):
        #     command += '\n'
        
        # Check if the command requires validation
        if requires_validation(command):
            return [types.TextContent(
                type="text", 
                text=f"⚠️ This command contains a potentially dangerous operation: {command}\n"
                     f"Please reformulate it or explicitly confirm that you want to execute it."
            )]
        
        try:
            if interactive_process is None or not interactive_process.isalive():
                # Launch the interactive process if not existing or terminated
                # Get terminal dimensions
                dimensions = config["terminal_dimensions"]
                
                interactive_process = PtyProcess.spawn(
                    f"{args.process_path_args}",
                    dimensions=dimensions
                )
                
                screen = pyte.Screen(config["terminal_dimensions"][1], config["terminal_dimensions"][0])
                stream = pyte.Stream(screen)

                # Wait for the shell to be ready
                time.sleep(1+wait)
                # Read initial prompt
                #initial_output = interactive_process.read(4096)
                rlist, _, _ = select.select([interactive_process.fd], [], [], 1)
                if rlist:
                    initial_output = interactive_process.read(16384)
                    stream.feed(initial_output)
            
            # Send the command
            if command is not None:
                # Process control characters if fix is enabled
                if not config["no_fix_control"]:
                    command = fix_control_at_end(command)
                interactive_process.write(command)
            
            # if control is not None:
            #     control = control.replace("\\n", "\n").replace("\\r", "\r").replace("\\r", "\r").replace("\\", "")
            #     if control == "\\n":
            #     # interactive_process.sendcontrol(control)
            #         interactive_process.sendcontrol('j')
                        
            # Wait for the command to be processed
            time.sleep(wait)
            
            # Read the output
            try:
                # Use select to implement a timeout for read
                rlist, _, _ = select.select([interactive_process.fd], [], [], .1)  # timeout
                if rlist:
                    output = interactive_process.read(16384)
                    stream.feed(output)
                else:
                    output = "Reading timed out after "+wait+"s"
                
                if isinstance(output, bytes):
                    output = output.decode('utf-8', errors='replace')
                
                # Update screen with output
                stream = pyte.Stream(screen)
                if isinstance(output, str):
                    stream.feed(output)
                
                screen_lines = []
                for y, line in enumerate(screen.display):
                    if y == screen.cursor.y:
                        # Cette ligne contient le curseur                    
                        # Insérer le curseur dans la ligne existante
                        new_line = line[:screen.cursor.x] + "▌" + line[screen.cursor.x:]
                        screen_lines.append(new_line)
                    else:
                        # Ligne sans curseur
                        screen_lines.append(line)

                output = "\n".join(line.rstrip() for line in screen_lines)
                #cursor_pos = (screen.cursor.x, screen.cursor.y)

                # Apply filters if defined
                # if config["compiled_filters"]:
                #     for pattern in config["compiled_filters"]:
                #         output = pattern.sub('', output)
                
                        
            except Exception as e:
                output = f"Error reading output: {str(e)}"
            
            # Check process state
            if interactive_process.isalive():
                return [types.TextContent(
                    type="text",
                    text=f"pid: {interactive_process.pid}\n"
                         f"screen:\n{output}"
                )]
            else:
                # The process has terminated
                exitcode = interactive_process.exitcode
                interactive_process = None
                return [types.TextContent(
                    type="text",
                    text=f"terminal terminated, code: {exitcode}\n"
                         f"screen:\n{output}"
                )]
                
        except Exception as e:
            if interactive_process is not None:
                try:
                    interactive_process.terminate(force=True)
                except:
                    pass
                interactive_process = None
            
            return [types.TextContent(
                type="text",
                text=f"Error executing interactive process: {str(e)}"
            )]
    
    elif name == config["terminate_name"] and PTY_AVAILABLE:
        if interactive_process is None:
            return [types.TextContent(
                type="text",
                text="No interactive process currently running."
            )]
        
        try:
            pid = interactive_process.pid
            interactive_process.terminate(force=True)
            interactive_process = None
            return [types.TextContent(
                type="text",
                text=f"Interactive process (PID: {pid}) successfully terminated."
            )]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"Error terminating process: {str(e)}"
            )]
    
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    """Main function to start the MCP server."""
    print(f"Starting MCP-PROCESS server with process : {args.process_path_args}")
    
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
    except KeyboardInterrupt:
        print("Server stopped by user")
    except Exception as e:
        print(f"Error running the server: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    cli_entry_point()
