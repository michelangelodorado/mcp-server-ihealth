# F5 iHealth MCP Server

A production-ready Model Context Protocol (MCP) server that provides tools for interacting with the F5 iHealth qkview-analyzer REST API. This server enables AI assistants like Claude to manage and analyze QKView diagnostic files from F5 BIG-IP systems.

## Features

### QKView Collection Management
- **list_qkviews** - List all QKView IDs in your account
- **upload_qkview** - Upload a new QKView file for analysis
- **delete_qkview** - Delete a specific QKView by ID
- **delete_all_qkviews** - Delete all QKViews (use with caution!)

### QKView Metadata
- **get_qkview_metadata** - Get metadata including serial number, timestamps, case info
- **update_qkview_metadata** - Update description, visibility, and case numbers

### QKView Diagnostics
- **get_qkview_diagnostics** - Get all diagnostics with format options (JSON, XML, PDF, CSV)
- **get_diagnostics_hits** - Get only issues found
- **get_diagnostics_misses** - Get only passed checks

### QKView Files
- **list_qkview_files** - List all files in a QKView
- **get_qkview_file** - Download a specific file by hash
- **download_original_qkview** - Download the original QKView file

### QKView Command Output
- **list_available_commands** - List available tmsh commands
- **get_command_output** - Get output of a specific command

### BIG-IP System Data
- **get_bigip_info** - Get complete BIG-IP system information
- **get_bigip_slot_info** - Get info for a specific slot
- **get_hardware_info** - Get hardware details
- **get_software_info** - Get software version details
- **get_license_info** - Get licensing information

### Utilities
- **get_api_info** - Get API version and parameters
- **search_qkview_logs** - Search log files for specific terms
- **validate_credentials** - Verify API credentials are working

## Prerequisites

1. **F5 iHealth Account** - Create a free account at [account.f5.com](https://account.f5.com/ihealth2)
2. **API Credentials** - Generate Client ID and Client Secret from [iHealth Settings](https://ihealth2.f5.com/qkview-analyzer/settings)
3. **Docker** - Installed and running on your system

## Installation

### Step 1: Clone or Download

```bash
# Create the project directory
mkdir f5-ihealth-mcp
cd f5-ihealth-mcp
```

Copy the following files to this directory:
- `server.py`
- `requirements.txt`
- `Dockerfile`
- `.env.example`

### Step 2: Configure Credentials

```bash
# Copy the example environment file
cp .env.example .env

# Edit the .env file with your credentials
nano .env
```

Add your F5 iHealth API credentials:
```
F5_IHEALTH_CLIENT_ID=your_actual_client_id
F5_IHEALTH_CLIENT_SECRET=your_actual_client_secret
```

### Step 3: Build the Docker Image

```bash
docker build -t f5-ihealth-mcp .
```

### Step 4: Test the Server

```bash
# Test that the server starts correctly
docker run --rm --env-file .env f5-ihealth-mcp
```

Press `Ctrl+C` to stop.

## Claude Desktop Integration

### Step 1: Locate Claude Desktop Config

**macOS:**
```bash
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Windows:**
```bash
notepad %APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```bash
nano ~/.config/Claude/claude_desktop_config.json
```

### Step 2: Add MCP Server Configuration

Add or merge the following into your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "f5-ihealth": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-e", "F5_IHEALTH_CLIENT_ID",
        "-e", "F5_IHEALTH_CLIENT_SECRET",
        "f5-ihealth-mcp"
      ],
      "env": {
        "F5_IHEALTH_CLIENT_ID": "your_client_id_here",
        "F5_IHEALTH_CLIENT_SECRET": "your_client_secret_here"
      }
    }
  }
}
```

Replace the placeholder values with your actual credentials.

### Step 3: Restart Claude Desktop

Completely quit and restart Claude Desktop to load the new MCP server.

## Usage Examples

Once configured, you can ask Claude to interact with F5 iHealth:

### List QKViews
> "Show me all my QKViews in iHealth"

### Upload a QKView
> "Upload the QKView file at /path/to/qkview.tar.gz to iHealth"

### Get Diagnostics
> "Get the diagnostic hits for QKView ID 12345678"

### Check System Info
> "What's the BIG-IP software version in QKView 12345678?"

### Search Logs
> "Search for 'error' in the logs of QKView 12345678"

## API Reference

### Authentication

The server uses OAuth2 client credentials flow:
1. Credentials are Base64 encoded
2. Token is requested from F5's identity server
3. Bearer token is cached for 30 minutes
4. Token is automatically refreshed when expired

### Base URL
```
https://ihealth2-api.f5.com/qkview-analyzer/api
```

### Required Headers
- `Authorization: Bearer {token}`
- `Accept: application/vnd.f5.ihealth.api`
- `User-Agent: F5iHealthMCPServer/1.0`

## Troubleshooting

### Common Issues

**"Authentication failed" error:**
- Verify your Client ID and Client Secret are correct
- Regenerate credentials in iHealth Settings if needed
- Ensure credentials are not expired

**"API request failed: 403":**
- Your token may have expired - the server should auto-refresh
- Check that your F5 account has access to the QKView

**"API request failed: 404":**
- The QKView ID doesn't exist or isn't accessible
- Verify the QKView ID is correct

**Docker connection issues:**
- Ensure Docker is running
- Check Docker has network access

### Debug Mode

To see detailed logs, run the container interactively:

```bash
docker run --rm -it --env-file .env f5-ihealth-mcp 2>&1 | tee debug.log
```

## Security Notes

1. **Never commit credentials** - Keep `.env` in `.gitignore`
2. **Use environment variables** - Don't hardcode credentials
3. **Rotate credentials** - Periodically regenerate API credentials
4. **Container isolation** - Server runs as non-root user

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions are welcome! Please submit issues and pull requests.

## Support

- **F5 iHealth API Documentation:** https://clouddocs.f5.com/api/ihealth/
- **F5 DevCentral Community:** https://community.f5.com/
- **MCP Documentation:** https://modelcontextprotocol.io/
