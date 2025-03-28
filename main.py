# Galaxy MCP Server
import os
from typing import Any
from mcp.server.fastmcp import FastMCP
from bioblend.galaxy import GalaxyInstance

# Create an MCP server
mcp = FastMCP("Galaxy")

# Galaxy client state
galaxy_state = {
    "url": os.environ.get("GALAXY_URL"),
    "api_key": os.environ.get("GALAXY_API_KEY"),
    "gi": None,
    "connected": False,
}


# Initialize Galaxy client if environment variables are set
if galaxy_state["url"] and galaxy_state["api_key"]:
    galaxy_url = (
        galaxy_state["url"]
        if galaxy_state["url"].endswith("/")
        else f"{galaxy_state['url']}/"
    )
    galaxy_state["url"] = galaxy_url
    galaxy_state["gi"] = GalaxyInstance(url=galaxy_url, key=galaxy_state["api_key"])
    galaxy_state["connected"] = True
    print(f"Galaxy client initialized from environment variables (URL: {galaxy_url})")


def ensure_connected():
    """Helper function to ensure Galaxy connection is established"""
    if not galaxy_state["connected"] or not galaxy_state["gi"]:
        raise ValueError("Not connected to Galaxy. Use connect command first.")


@mcp.tool()
def connect(url: str | None = None, api_key: str | None = None) -> dict[str, Any]:
    """
    Connect to Galaxy server

    Args:
        url: Galaxy server URL (optional, uses GALAXY_URL env var if not provided)
        api_key: Galaxy API key (optional, uses GALAXY_API_KEY env var if not provided)

    Returns:
        Connection status and user information
    """
    try:
        # Use provided parameters or fall back to environment variables
        use_url = url or os.environ.get("GALAXY_URL")
        use_api_key = api_key or os.environ.get("GALAXY_API_KEY")

        # Check if we have the necessary credentials
        if not use_url or not use_api_key:
            missing = []
            if not use_url:
                missing.append("URL")
            if not use_api_key:
                missing.append("API key")
            missing_str = " and ".join(missing)
            raise ValueError(
                f"Missing Galaxy {missing_str}. Please provide as arguments or set environment variables."
            )

        galaxy_url = use_url if use_url.endswith("/") else f"{use_url}/"

        # Create a new Galaxy instance to test connection
        gi = GalaxyInstance(url=galaxy_url, key=use_api_key)

        # Test the connection by fetching user info
        user_info = gi.users.get_current_user()

        # Update galaxy state
        galaxy_state["url"] = galaxy_url
        galaxy_state["api_key"] = use_api_key
        galaxy_state["gi"] = gi
        galaxy_state["connected"] = True

        return {"connected": True, "user": user_info}
    except Exception as e:
        # Reset state on failure
        galaxy_state["url"] = None
        galaxy_state["api_key"] = None
        galaxy_state["gi"] = None
        galaxy_state["connected"] = False

        raise ValueError(f"Failed to connect to Galaxy: {str(e)}")


@mcp.tool()
def search_tools(query: str) -> dict[str, Any]:
    """
    Search for tools in Galaxy

    Args:
        query: Search query (tool name to filter on)

    Returns:
        List of tools matching the query
    """
    ensure_connected()

    try:
        # The get_tools method is used with name filter parameter
        tools = galaxy_state["gi"].tools.get_tools(name=query)
        return {"tools": tools}
    except Exception as e:
        raise ValueError(f"Failed to search tools: {str(e)}")


@mcp.tool()
def get_tool_details(tool_id: str, io_details: bool = False) -> dict[str, Any]:
    """
    Get detailed information about a specific tool

    Args:
        tool_id: ID of the tool
        io_details: Whether to include input/output details

    Returns:
        Tool details
    """
    ensure_connected()

    try:
        # Get detailed information about the tool
        tool_info = galaxy_state["gi"].tools.show_tool(tool_id, io_details=io_details)
        return tool_info
    except Exception as e:
        raise ValueError(f"Failed to get tool details: {str(e)}")


@mcp.tool()
def run_tool(history_id: str, tool_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Run a tool in Galaxy

    Args:
        history_id: ID of the history where to run the tool
        tool_id: ID of the tool to run
        inputs: Tool input parameters and datasets

    Returns:
        Information about the tool execution
    """
    ensure_connected()

    try:
        # Run the tool with provided inputs
        result = galaxy_state["gi"].tools.run_tool(history_id, tool_id, inputs)
        return result
    except Exception as e:
        raise ValueError(f"Failed to run tool: {str(e)}")


@mcp.tool()
def get_tool_panel() -> dict[str, Any]:
    """
    Get the tool panel structure (toolbox)

    Returns:
        Tool panel hierarchy
    """
    ensure_connected()

    try:
        # Get the tool panel structure
        tool_panel = galaxy_state["gi"].tools.get_tool_panel()
        return {"tool_panel": tool_panel}
    except Exception as e:
        raise ValueError(f"Failed to get tool panel: {str(e)}")


@mcp.tool()
def get_user() -> dict[str, Any]:
    """
    Get current user information

    Returns:
        Current user details
    """
    ensure_connected()

    try:
        user_info = galaxy_state["gi"].users.get_current_user()
        return user_info
    except Exception as e:
        raise ValueError(f"Failed to get user: {str(e)}")


@mcp.tool()
def get_histories() -> dict[str, Any]:
    """
    Get list of user histories

    Returns:
        List of histories
    """
    ensure_connected()

    try:
        histories = galaxy_state["gi"].histories.get_histories()
        return histories
    except Exception as e:
        raise ValueError(f"Failed to get histories: {str(e)}")


@mcp.tool()
def upload_file(path: str, history_id: str | None = None) -> dict[str, Any]:
    """
    Upload a local file to Galaxy

    Args:
        path: Path to local file
        history_id: Target history ID (optional)

    Returns:
        Upload status
    """
    ensure_connected()

    try:
        if not os.path.exists(path):
            raise ValueError(f"File not found: {path}")

        result = galaxy_state["gi"].tools.upload_file(path, history_id=history_id)
        return result
    except Exception as e:
        raise ValueError(f"Failed to upload file: {str(e)}")


@mcp.tool()
def get_invocations(
    invocation_id: str | None = None,
    workflow_id: str | None = None,
    history_id: str | None = None,
    limit: int | None = None,
    view: str = "collection",
    step_details: bool = False,
) -> dict[str, Any]:
    """
    View workflow invocations in Galaxy

    Args:
        invocation_id: Specific invocation ID to view details (optional)
        workflow_id: Filter invocations by workflow ID (optional)
        history_id: Filter invocations by history ID (optional)
        limit: Maximum number of invocations to return (optional)
        view: Level of detail to return, either 'element' or 'collection' (default: collection)
        step_details: Include details on individual steps (only if view is 'element')

    Returns:
        Workflow invocation(s) information
    """
    ensure_connected()

    try:
        # If invocation_id is provided, get details of a specific invocation
        if invocation_id:
            invocation = galaxy_state["gi"].invocations.show_invocation(invocation_id)
            return {"invocation": invocation}

        # Otherwise get a list of invocations with optional filters
        invocations = galaxy_state["gi"].invocations.get_invocations(
            workflow_id=workflow_id,
            history_id=history_id,
            limit=limit,
            view=view,
            step_details=step_details,
        )
        return {"invocations": invocations}
    except Exception as e:
        raise ValueError(f"Failed to get workflow invocations: {str(e)}")


@mcp.tool()
def get_iwc_workflows() -> dict[str, Any]:
    """
    Fetch all workflows from the IWC (Interactive Workflow Composer)

    Returns:
        Complete workflow manifest from IWC
    """
    try:
        response = requests.get("https://iwc.galaxyproject.org/workflow_manifest.json")
        response.raise_for_status()
        workflows = response.json()
        return {"workflows": workflows}
    except Exception as e:
        raise ValueError(f"Failed to fetch IWC workflows: {str(e)}")


@mcp.tool()
def search_iwc_workflows(query: str) -> dict[str, Any]:
    """
    Search for workflows in the IWC manifest

    Args:
        query: Search query (matches against name, description, and tags)

    Returns:
        List of matching workflows
    """
    try:
        # Get the full manifest
        manifest = get_iwc_workflows()["workflows"]

        # Filter workflows based on the search query
        results = []
        query = query.lower()

        for workflow in manifest:
            # Check if query matches name, description or tags
            name = workflow.get("name", "").lower()
            description = workflow.get("description", "").lower()
            tags = [tag.lower() for tag in workflow.get("tags", [])]

            if (
                query in name
                or query in description
                or any(query in tag for tag in tags)
            ):
                results.append(workflow)

        return {"workflows": results, "count": len(results)}
    except Exception as e:
        raise ValueError(f"Failed to search IWC workflows: {str(e)}")


@mcp.tool()
def import_workflow_from_iwc(workflow_id: str) -> dict[str, Any]:
    """
    Import a workflow from IWC to the user's Galaxy instance

    Args:
        workflow_id: ID of the workflow in the IWC manifest

    Returns:
        Imported workflow information
    """
    ensure_connected()

    try:
        # Get the workflow manifest
        manifest = get_iwc_workflows()["workflows"]

        # Find the specified workflow
        workflow = None
        for wf in manifest:
            if wf.get("id") == workflow_id:
                workflow = wf
                break

        if not workflow:
            raise ValueError(
                f"Workflow with ID {workflow_id} not found in IWC manifest"
            )

        # Get the workflow download URL
        download_url = workflow.get("download_url")
        if not download_url:
            raise ValueError(f"No download URL available for workflow {workflow_id}")

        # Download the workflow
        response = requests.get(download_url)
        response.raise_for_status()
        workflow_json = response.json()

        # Import the workflow into Galaxy
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ga") as temp:
            json.dump(workflow_json, temp)
            temp.flush()

            imported_workflow = galaxy_state[
                "gi"
            ].workflows.import_workflow_from_local_path(temp.name)

        return {"imported_workflow": imported_workflow}
    except Exception as e:
        raise ValueError(f"Failed to import workflow from IWC: {str(e)}")


if __name__ == "__main__":
    mcp.run()
