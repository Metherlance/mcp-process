# MCP-PROCESS

An MCP server (Model-Client-Protocol) allowing Claude to access a shell. This integration enables Claude to execute commands and interact with your file system via the command line.
## Warning / Disclaimer

⚠️ **CAUTION** ⚠️

This project has only been tested with WSL (Windows Subsystem for Linux) and has not been validated for production use. Using this MCP gives Claude direct access to your file system and shell, which presents significant security risks:

- It can potentially delete or modify critical files
- It can execute any command accessible to the user under which it runs
- The built-in security measures (such as the list of forbidden words) can be bypassed

**This is truly a Pandora's box** - use it at your own risk. The author assumes no responsibility for damages, data loss, or security issues resulting from the use of this software.

It is strongly recommended to use it only in an isolated or controlled environment.

## Features

- Execution of static commands
- Support for interactive mode for applications like vim, nano, htop, etc.
- Validation of potentially dangerous commands
- Flexible configuration of terminal dimensions and filtering of ANSI escape sequences

## Prerequisites

- Python 3.10 or higher (Python 3.11+ recommended)
- WSL installed and configured
- On Windows, the `pywinpty` package is required
- On Linux/Mac, the `ptyprocess` package is required

## Installation

```bash
pip install .
```

Or for development installation:

```bash
pip install -e ".[dev]"
```

## Claude Configuration

To use this MCP server with Claude, you need to add the following configuration to Claude's configuration file. Depending on your installation, this file is usually located at:

```
%AppData%/Claude/claude_desktop_config.json
```

Add the following section:

```json
"mcpServers": {
  "wsl": {
    "command": "mcp-process",
    "args": [
      "--process-path-args", "wsl.exe --cd /mnt/c/Users/YourName",
      "--terminal-width", "80",
      "--terminal-height", "24",
      "--filter-patterns", "\\x1b\\[[0-9;]*m",
      "--exec-name", "exec",
      "--exec-description", "Executes a static command (ls pwd cat echo ps mkdir cp grep find git sed ...) and returns its result",
      "--terminal-name", "terminal",
      "--terminal-description", "Creates a persistent shell terminal session if it doesn't exist and sends input to the shell (applications: vi top htop nano less python ssh mysql ftp ncdu ...) (Enter: \\r or \\n), asynchronous return (the screen may still refresh after the return)",
      "--terminate-description", "Terminates the current interactive process/terminal if it exists",
      "--terminate-label", "terminal_terminate",
    ]
  },
  "psql": {
		"command": "mcp-process",
		"args": [
			"--process-path-args", "psql.exe postgresql://postgres:password@localhost:5432/db",
			"--exec-name", "psql",
			"--exec-description", "Exécute une commande statique sql et retourne son résultat ex: -c \"SELECT * FROM table;\" ",
			"--terminal-name", ""
			"--terminate-name", ""
		]
   }
}
```


## Available Options

You can customize the behavior of the MCP server with the following options:

| Option | Description | Default Value |
|--------|-------------|-------------------|
| `--process-path-args` | Path to shell process including initial arguments (e.g., `wsl.exe --cd [dir]`) | `wsl.exe --cd [current_dir]` |
| `--filter-patterns` | Regex patterns to filter | `["\\x1b\\[K"]` |
| `--exec-name` | Custom name for the exec tool | `exec` |
| `--exec-description` | Custom description for the exec tool | (see default in args) |
| `--exec-timeout` | Command timeout (in sec.) | 60 |
| `--terminal-name` | Custom name for the terminal tool | `terminal` |
| `--terminal-description` | Custom description for the terminal tool | (see default in args) |
| `--terminal-wait` | Wait delay before reading (in sec.) | 0.2 |
| `--terminal-width` | Terminal width | 80 |
| `--terminal-height` | Terminal height | 24 |
| `--terminate-label` | Custom label for the terminate tool | `terminal_terminate` |
| `--terminate-description` | Custom description for the terminate tool | (see default in args) |

### Filter Examples

To filter ANSI color sequences:
```
--filter-patterns "\\x1b\\[[0-9;]*m"
```

To filter terminal titles:
```
--filter-patterns "\\x1b\\]0;.*?\\x07"
```

## Usage

Once installed and configured, you can ask Claude to execute WSL commands as follows:

1. Static commands:
   ```
   Can you run the command "ls -la" in WSL?
   ```

2. Interactive commands:
   ```
   Can you open nano in WSL and create a simple file?
   ```

## Development

To contribute to development:

1. Clone the repository
2. Install development dependencies :
   ```bash
   pip install -e ".[dev]"
   ```
3. Run tests (see README_tests.md for more details) :
   ```bash
   pytest
   ```

## License

MIT

## Contact

For any questions, bug reports, or suggestions, please create an issue on the project's GitHub repository.
GitHub repository: [https://github.com/Metherlance/mcp-process](https://github.com/Metherlance/mcp-process)

## Similar Projects and Resources

Here is a list of similar projects that also provide MCP servers for shell access:

- [mcp-server-commands](https://github.com/g0t4/mcp-server-commands) - An MCP server for executing system commands
- [mcp-process-server](https://github.com/tumf/mcp-process-server) - A TypeScript implementation of an MCP server for shell
- [mcp-server-shell](https://github.com/odysseus0/mcp-server-shell) - An MCP server for shell interactions
