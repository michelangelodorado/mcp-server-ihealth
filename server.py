#!/usr/bin/env python3
"""F5 iHealth MCP Server - Provides tools for interacting with the F5 iHealth qkview-analyzer REST API."""

import os
import sys
import json
import base64
import logging
import time
import httpx
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("f5-ihealth-mcp")

# Initialize MCP server
mcp = FastMCP("F5 iHealth MCP Server")

# API Configuration
TOKEN_URL = "https://identity.account.f5.com/oauth2/ausp95ykc80HOU7SQ357/v1/token"
API_BASE_URL = "https://ihealth2-api.f5.com/qkview-analyzer/api"
USER_AGENT = "F5iHealthMCPServer/1.0"
ACCEPT_HEADER = "application/vnd.f5.ihealth.api"

# Token cache
_token_cache = {"token": None, "expires_at": 0}


def get_credentials():
    """Retrieve F5 iHealth API credentials from environment variables."""
    client_id = os.environ.get("F5_IHEALTH_CLIENT_ID", "")
    client_secret = os.environ.get("F5_IHEALTH_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ValueError("F5_IHEALTH_CLIENT_ID and F5_IHEALTH_CLIENT_SECRET environment variables are required")
    return client_id, client_secret


def get_auth_token():
    """Get a valid Bearer token, refreshing if necessary."""
    global _token_cache
    current_time = time.time()
    if _token_cache["token"] and current_time < _token_cache["expires_at"] - 60:
        return _token_cache["token"]
    client_id, client_secret = get_credentials()
    credentials = f"{client_id}:{client_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    headers = {
        "Accept": "application/json",
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Cache-Control": "no-cache"
    }
    data = "grant_type=client_credentials&scope=ihealth"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(TOKEN_URL, headers=headers, content=data)
            response.raise_for_status()
            token_data = response.json()
            _token_cache["token"] = token_data["access_token"]
            _token_cache["expires_at"] = current_time + token_data.get("expires_in", 1800)
            logger.info("Successfully obtained new auth token")
            return _token_cache["token"]
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to obtain auth token: {e.response.status_code} - {e.response.text}")
        raise ValueError(f"Authentication failed: {e.response.status_code}")
    except Exception as e:
        logger.error(f"Failed to obtain auth token: {str(e)}")
        raise ValueError(f"Authentication failed: {str(e)}")


def make_api_request(method: str, endpoint: str, accept_type: str = "", data: dict = None, files: dict = None):
    """Make an authenticated request to the F5 iHealth API."""
    token = get_auth_token()
    accept = accept_type if accept_type else ACCEPT_HEADER
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": accept,
        "User-Agent": USER_AGENT
    }
    url = f"{API_BASE_URL}{endpoint}"
    try:
        with httpx.Client(timeout=120.0, follow_redirects=True) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                if files:
                    response = client.post(url, headers=headers, data=data, files=files)
                else:
                    response = client.post(url, headers=headers, data=data)
            elif method.upper() == "PUT":
                response = client.put(url, headers=headers, data=data)
            elif method.upper() == "DELETE":
                response = client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            if response.status_code == 202:
                return {"status": "processing", "message": "Request accepted, processing in progress. Retry in 10 seconds."}
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type or "application/vnd.f5.ihealth.api+json" in content_type:
                return response.json()
            elif "application/xml" in content_type or "text/xml" in content_type:
                return {"xml_content": response.text}
            elif "application/octet-stream" in content_type:
                return {"binary_size": len(response.content), "message": "Binary content retrieved successfully"}
            else:
                return {"content": response.text}
    except httpx.HTTPStatusError as e:
        logger.error(f"API request failed: {e.response.status_code} - {e.response.text}")
        return {"error": f"API request failed: {e.response.status_code}", "details": e.response.text}
    except Exception as e:
        logger.error(f"API request failed: {str(e)}")
        return {"error": f"API request failed: {str(e)}"}


def format_response(data: dict) -> str:
    """Format API response data as a readable string."""
    if isinstance(data, dict):
        if "error" in data:
            return f"Error: {data['error']}\nDetails: {data.get('details', 'No additional details')}"
        return json.dumps(data, indent=2, default=str)
    return str(data)


# ============================================================================
# QKView Collection Management Tools
# ============================================================================

@mcp.tool()
def list_qkviews() -> str:
    """List all QKView IDs in your iHealth account collection."""
    logger.info("Listing all QKViews")
    result = make_api_request("GET", "/qkviews")
    return format_response(result)


@mcp.tool()
def upload_qkview(file_path: str = "", description: str = "", visible_in_gui: str = "true", f5_support_case: str = "", share_with_case_owner: str = "false") -> str:
    """Upload a QKView file to iHealth for analysis."""
    if not file_path:
        return "Error: file_path parameter is required"
    if not os.path.exists(file_path):
        return f"Error: File not found: {file_path}"
    logger.info(f"Uploading QKView from: {file_path}")
    try:
        with open(file_path, "rb") as f:
            files = {"qkview": (os.path.basename(file_path), f, "application/octet-stream")}
            data = {}
            if description:
                data["description"] = description
            if visible_in_gui:
                data["visible_in_gui"] = visible_in_gui
            if f5_support_case:
                data["f5_support_case"] = f5_support_case
            if share_with_case_owner:
                data["share_with_case_owner"] = share_with_case_owner
            result = make_api_request("POST", "/qkviews", data=data, files=files)
        return format_response(result)
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        return f"Error uploading QKView: {str(e)}"


@mcp.tool()
def delete_qkview(qkview_id: str = "") -> str:
    """Delete a specific QKView from your iHealth account by its ID."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    logger.info(f"Deleting QKView: {qkview_id}")
    result = make_api_request("DELETE", f"/qkviews/{qkview_id}")
    return format_response(result)


@mcp.tool()
def delete_all_qkviews() -> str:
    """Delete ALL QKViews from your iHealth account. Use with extreme caution."""
    logger.warning("Deleting ALL QKViews from account")
    result = make_api_request("DELETE", "/qkviews")
    return format_response(result)


# ============================================================================
# QKView Metadata Tools
# ============================================================================

@mcp.tool()
def get_qkview_metadata(qkview_id: str = "") -> str:
    """Get metadata for a specific QKView including serial number, timestamps, and case info."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    logger.info(f"Getting metadata for QKView: {qkview_id}")
    result = make_api_request("GET", f"/qkviews/{qkview_id}")
    return format_response(result)


@mcp.tool()
def update_qkview_metadata(qkview_id: str = "", description: str = "", visible_in_gui: str = "", f5_support_case: str = "", non_f5_case: str = "") -> str:
    """Update metadata for a specific QKView such as description, visibility, and case numbers."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    data = {}
    if description:
        data["description"] = description
    if visible_in_gui:
        data["visible_in_gui"] = visible_in_gui
    if f5_support_case:
        data["f5_support_case"] = f5_support_case
    if non_f5_case:
        data["non_f5_case"] = non_f5_case
    if not data:
        return "Error: At least one metadata field must be provided to update"
    logger.info(f"Updating metadata for QKView: {qkview_id}")
    result = make_api_request("PUT", f"/qkviews/{qkview_id}", data=data)
    return format_response(result)


# ============================================================================
# QKView Diagnostics Tools
# ============================================================================

@mcp.tool()
def get_qkview_diagnostics(qkview_id: str = "", diagnostic_set: str = "", output_format: str = "json") -> str:
    """Get diagnostics for a QKView. Set diagnostic_set to 'hit' for issues found or 'miss' for passed checks."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    endpoint = f"/qkviews/{qkview_id}/diagnostics"
    if diagnostic_set in ["hit", "miss"]:
        endpoint += f"?set={diagnostic_set}"
    format_map = {
        "json": "application/vnd.f5.ihealth.api+json",
        "xml": "application/vnd.f5.ihealth.api+xml",
        "pdf": "application/pdf",
        "csv": "text/csv"
    }
    accept_type = format_map.get(output_format.lower(), "application/vnd.f5.ihealth.api+json")
    logger.info(f"Getting diagnostics for QKView: {qkview_id}, set: {diagnostic_set}, format: {output_format}")
    result = make_api_request("GET", endpoint, accept_type=accept_type)
    return format_response(result)


@mcp.tool()
def get_diagnostics_hits(qkview_id: str = "") -> str:
    """Get only the diagnostic hits (issues found) for a QKView."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    logger.info(f"Getting diagnostic hits for QKView: {qkview_id}")
    result = make_api_request("GET", f"/qkviews/{qkview_id}/diagnostics?set=hit")
    return format_response(result)


@mcp.tool()
def get_diagnostics_misses(qkview_id: str = "") -> str:
    """Get only the diagnostic misses (passed checks) for a QKView."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    logger.info(f"Getting diagnostic misses for QKView: {qkview_id}")
    result = make_api_request("GET", f"/qkviews/{qkview_id}/diagnostics?set=miss")
    return format_response(result)


# ============================================================================
# QKView Files Tools
# ============================================================================

@mcp.tool()
def list_qkview_files(qkview_id: str = "") -> str:
    """List all files contained within a QKView, referenced by hash."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    logger.info(f"Listing files for QKView: {qkview_id}")
    result = make_api_request("GET", f"/qkviews/{qkview_id}/files")
    return format_response(result)


@mcp.tool()
def get_qkview_file(qkview_id: str = "", file_hash: str = "") -> str:
    """Download a specific file from a QKView by its hash. Use 'qkview' as file_hash to get the original file."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    if not file_hash:
        return "Error: file_hash parameter is required"
    logger.info(f"Getting file {file_hash} from QKView: {qkview_id}")
    result = make_api_request("GET", f"/qkviews/{qkview_id}/files/{file_hash}", accept_type="application/octet-stream")
    return format_response(result)


@mcp.tool()
def download_original_qkview(qkview_id: str = "") -> str:
    """Download the original QKView file that was uploaded."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    logger.info(f"Downloading original QKView file: {qkview_id}")
    result = make_api_request("GET", f"/qkviews/{qkview_id}/files/qkview", accept_type="application/octet-stream")
    return format_response(result)


# ============================================================================
# QKView Command Output Tools
# ============================================================================

@mcp.tool()
def list_available_commands(qkview_id: str = "") -> str:
    """List available tmsh commands that can be retrieved from a QKView."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    logger.info(f"Listing available commands for QKView: {qkview_id}")
    result = make_api_request("GET", f"/qkviews/{qkview_id}/commands")
    return format_response(result)


@mcp.tool()
def get_command_output(qkview_id: str = "", command_name: str = "") -> str:
    """Get the output of a specific tmsh command captured in the QKView."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    if not command_name:
        return "Error: command_name parameter is required"
    logger.info(f"Getting command output for {command_name} from QKView: {qkview_id}")
    result = make_api_request("GET", f"/qkviews/{qkview_id}/commands/{command_name}")
    return format_response(result)


# ============================================================================
# QKView BIG-IP Data Tools
# ============================================================================

@mcp.tool()
def get_bigip_info(qkview_id: str = "") -> str:
    """Get BIG-IP system information from a QKView including hardware, software, and licensing details."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    logger.info(f"Getting BIG-IP info for QKView: {qkview_id}")
    result = make_api_request("GET", f"/qkviews/{qkview_id}/bigip")
    return format_response(result)


@mcp.tool()
def get_bigip_slot_info(qkview_id: str = "", slot_number: str = "0") -> str:
    """Get BIG-IP information for a specific slot. Use slot 0 for appliances or specify blade slot for chassis."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    logger.info(f"Getting BIG-IP slot {slot_number} info for QKView: {qkview_id}")
    result = make_api_request("GET", f"/qkviews/{qkview_id}/bigip/{slot_number}")
    return format_response(result)


@mcp.tool()
def get_hardware_info(qkview_id: str = "", slot_number: str = "0") -> str:
    """Get hardware information from a QKView for a specific slot."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    logger.info(f"Getting hardware info for QKView: {qkview_id}, slot: {slot_number}")
    result = make_api_request("GET", f"/qkviews/{qkview_id}/bigip/{slot_number}/hardware")
    return format_response(result)


@mcp.tool()
def get_software_info(qkview_id: str = "", slot_number: str = "0") -> str:
    """Get software version information from a QKView for a specific slot."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    logger.info(f"Getting software info for QKView: {qkview_id}, slot: {slot_number}")
    result = make_api_request("GET", f"/qkviews/{qkview_id}/bigip/{slot_number}/software")
    return format_response(result)


@mcp.tool()
def get_license_info(qkview_id: str = "", slot_number: str = "0") -> str:
    """Get licensing information from a QKView for a specific slot."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    logger.info(f"Getting license info for QKView: {qkview_id}, slot: {slot_number}")
    result = make_api_request("GET", f"/qkviews/{qkview_id}/bigip/{slot_number}/license")
    return format_response(result)


# ============================================================================
# Utility Tools
# ============================================================================

@mcp.tool()
def get_api_info() -> str:
    """Get F5 iHealth API version and operating parameters."""
    logger.info("Getting API info")
    result = make_api_request("GET", "/")
    return format_response(result)


@mcp.tool()
def search_qkview_logs(qkview_id: str = "", search_term: str = "") -> str:
    """Search through log files in a QKView for a specific term."""
    if not qkview_id:
        return "Error: qkview_id parameter is required"
    if not search_term:
        return "Error: search_term parameter is required"
    logger.info(f"Searching logs in QKView {qkview_id} for: {search_term}")
    result = make_api_request("GET", f"/qkviews/{qkview_id}/logs?search={search_term}")
    return format_response(result)


@mcp.tool()
def validate_credentials() -> str:
    """Validate that the F5 iHealth API credentials are configured and working."""
    try:
        token = get_auth_token()
        if token:
            return "Success: F5 iHealth API credentials are valid and authentication successful."
        return "Error: Failed to obtain auth token"
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error validating credentials: {str(e)}"


if __name__ == "__main__":
    logger.info("Starting F5 iHealth MCP Server")
    mcp.run(transport="stdio")
