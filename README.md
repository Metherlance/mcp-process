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
- Validation of potentially dangerous commands
- Flexible configuration of command filtering and timeout

## Prerequisites

- Python 3.10 or higher (Python 3.11+ recommended)
- WSL installed and configured
- On Windows, the `pywinpty` package is required
- On Linux/Mac, the `ptyprocess` package is required

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Metherlance/mcp-process.git
cd mcp-process
```

2. Install the package:
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
      "--filter-patterns", "\\x1b\\[[0-9;]*m",
      "--exec-name", "exec",
      "--exec-description", "Exécute une commande statique (ls pwd cat tree ps mkdir cp grep find git sed echo rg ...) et retourne son résultat",
      "--exec-timeout", "60"
    ]
  },
  "psql": {
    "command": "mcp-process",
    "args": [
      "--process-path-args", "psql.exe postgresql://postgres:password@localhost:5432/db",
      "--exec-name", "psql",
      "--exec-description", "Exécute une commande statique sql et retourne son résultat ex: -c \"SELECT * FROM table;\" ",
      "--exec-timeout", "120"
    ]
  }
}
```


| Option | Description | Default Value |
|--------|-------------|-------------------|
| `--process-path-args` | Path to shell process including initial arguments (e.g., `wsl.exe --cd [dir]`) | `wsl.exe --cd [current_dir]` |
| `--forbidden-words` | List of words not allowed in commands | `[several_default_items]` |
| `--filter-patterns` | Regex patterns to filter | `["\x07", "\x1b\[25l"]` |
| `--exec-name` | Custom name for the exec tool | `exec` |
| `--exec-description` | Custom description for the exec tool | (see default in args) |
| `--exec-timeout` | Command timeout (in sec.) | 60 |

### Filter Examples

To filter ANSI color sequences:
```
--filter-patterns "\x1b\[[0-9;]*m"
```

To filter terminal titles:
```
--filter-patterns "\x1b\]0;.*?\x07"
```

## Usage

Once installed and configured, you can ask Claude to execute WSL commands as follows:

```
Can you run the command "ls -la" in WSL?
```

## Development

To contribute to development:

1. Clone the repository
2. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
3. Run tests:
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
