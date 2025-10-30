# Galaxy MCP Server
import concurrent.futures
import logging
import os
import threading
from typing import Any

import requests
from bioblend.galaxy import GalaxyInstance
from dotenv import find_dotenv, load_dotenv
from fastmcp import FastMCP

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def format_error(action: str, error: Exception, context: dict | None = None) -> str:
    """Format error messages consistently"""
    if context is None:
        context = {}
    msg = f"{action} failed: {str(error)}"

    # Add HTTP status code interpretations
    error_str = str(error)
    if "401" in error_str:
        msg += " (Authentication failed - check your API key)"
    elif "403" in error_str:
        msg += " (Permission denied - check your account permissions)"
    elif "404" in error_str:
        msg += " (Resource not found - check IDs and URLs)"
    elif "500" in error_str:
        msg += " (Server error - try again later or contact admin)"

    # Add context if provided
    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        msg += f". Context: {context_str}"

    return msg


# Try to load environment variables from .env file
dotenv_path = find_dotenv(usecwd=True)
if dotenv_path:
    load_dotenv(dotenv_path)
    print(f"Loaded environment variables from {dotenv_path}")

# Create an MCP server
mcp: FastMCP = FastMCP("Galaxy")

# Galaxy client state
galaxy_state: dict[str, Any] = {
    "url": os.environ.get("GALAXY_URL"),
    "api_key": os.environ.get("GALAXY_API_KEY"),
    "gi": None,
    "connected": False,
}


# Initialize Galaxy client if environment variables are set
if galaxy_state["url"] and galaxy_state["api_key"]:
    try:
        galaxy_url = (
            galaxy_state["url"] if galaxy_state["url"].endswith("/") else f"{galaxy_state['url']}/"
        )
        galaxy_state["url"] = galaxy_url
        galaxy_state["gi"] = GalaxyInstance(url=galaxy_url, key=galaxy_state["api_key"])
        galaxy_state["connected"] = True
        logger.info(f"Galaxy client initialized from environment variables (URL: {galaxy_url})")
    except Exception as e:
        logger.warning(f"Failed to initialize Galaxy client from environment variables: {e}")
        logger.warning("You'll need to use connect() to establish a connection.")


def ensure_connected():
    """Helper function to ensure Galaxy connection is established"""
    if not galaxy_state["connected"] or not galaxy_state["gi"]:
        raise ValueError(
            "Not connected to Galaxy. "
            "Please run connect() first with your Galaxy URL and API key. "
            "Example: connect(url='https://your-galaxy.org', api_key='your-key')"
        )


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
            # Try to reload from .env file in case it was added after startup
            dotenv_path = find_dotenv(usecwd=True)
            if dotenv_path:
                load_dotenv(dotenv_path, override=True)
                # Check again after loading .env
                use_url = url or os.environ.get("GALAXY_URL")
                use_api_key = api_key or os.environ.get("GALAXY_API_KEY")

            # If still missing credentials, report error
            if not use_url or not use_api_key:
                missing = []
                if not use_url:
                    missing.append("URL")
                if not use_api_key:
                    missing.append("API key")
                missing_str = " and ".join(missing)
                raise ValueError(
                    f"Missing Galaxy {missing_str}. Please provide as arguments, "
                    f"set environment variables, or create a .env file with "
                    f"GALAXY_URL and GALAXY_API_KEY."
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

        error_msg = f"Failed to connect to Galaxy at {galaxy_url}: {str(e)}"
        if "401" in str(e) or "authentication" in str(e).lower():
            error_msg += " Check that your API key is valid and has the necessary permissions."
        elif "404" in str(e) or "not found" in str(e).lower():
            error_msg += " Check that the Galaxy URL is correct and accessible."
        elif "connection" in str(e).lower() or "timeout" in str(e).lower():
            error_msg += " Check your network connection and that the Galaxy server is running."
        else:
            error_msg += " Verify the URL format (should end with /) and API key."

        raise ValueError(error_msg) from e


@mcp.tool()
def search_tools_by_name(query: str) -> dict[str, Any]:
    """
    Search Galaxy tools whose name contains the given query (substring match).

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
        raise ValueError(
            f"Failed to search tools with query '{query}': {str(e)}. "
            "Check that the Galaxy instance is accessible and the tool name is correct."
        ) from e


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
        raise ValueError(
            f"Failed to get tool details for ID '{tool_id}': {str(e)}. "
            "Verify the tool ID is correct and the tool is installed on this "
            "Galaxy instance."
        ) from e


@mcp.tool()
def get_tool_citations(tool_id: str) -> dict[str, Any]:
    """
    Get citation information for a specific tool

    Args:
        tool_id: ID of the tool

    Returns:
        Tool citation information
    """
    ensure_connected()

    try:
        # Get the tool information which includes citations
        tool_info = galaxy_state["gi"].tools.show_tool(tool_id)

        # Extract citation information
        citations = tool_info.get("citations", [])

        return {
            "tool_name": tool_info.get("name", tool_id),
            "tool_version": tool_info.get("version", "unknown"),
            "citations": citations,
        }
    except Exception as e:
        raise ValueError(f"Failed to get tool citations: {str(e)}") from e


@mcp.tool()
def run_tool(history_id: str, tool_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Run a tool in Galaxy

    Args:
        history_id: Galaxy history ID where to run the tool - a hexadecimal hash string
                   (e.g., '1cd8e2f6b131e5aa', typically 16 characters)
        tool_id: Galaxy tool identifier - typically in format 'toolshed.g2.bx.psu.edu/repos/...'
                (e.g., 'Cut1' for simple tools or full toolshed URLs for complex tools)
        inputs: Dictionary of tool input parameters and dataset references matching tool schema

    Returns:
        Dictionary containing tool execution information including job IDs and output dataset IDs
    """
    ensure_connected()

    try:
        # Run the tool with provided inputs
        result = galaxy_state["gi"].tools.run_tool(history_id, tool_id, inputs)
        return result
    except Exception as e:
        error_msg = f"Failed to run tool '{tool_id}' in history '{history_id}': {str(e)}"
        if "400" in str(e) or "bad request" in str(e).lower():
            error_msg += " Check that all required tool parameters are provided correctly."
        elif "404" in str(e):
            error_msg += " Verify the tool ID and history ID are valid."
        else:
            error_msg += " Check the tool inputs format matches the tool's requirements."

        raise ValueError(error_msg) from e


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
        raise ValueError(f"Failed to get tool panel: {str(e)}") from e


@mcp.tool()
def create_history(history_name: str) -> dict[str, Any]:
    """
    Create a new history in Galaxy

    Args:
        history_name: Human-readable name for the new history (e.g., 'RNA-seq Analysis')

    Returns:
        Dictionary containing the created history details including the new history ID hash
    """
    ensure_connected()
    return galaxy_state["gi"].histories.create_history(history_name)


@mcp.tool()
def search_tool_by_keywords(keywords: list[str]) -> dict[str, Any]:
    """
    Recommend Galaxy tools based on a list of keywords.

    Args:
        keywords (list[str]): A list of keywords or phrases describing what you're looking for,
            e.g., ["csv", "rna", "alignment", "visualization"]. The search will match tools
            whose name, description, or accepted input formats contain any of these keywords.

    Returns:
        dict: {
            "recommended_tools": [ {id, name, description, versions}, ... ],
            "count": <number_of_tools>
        }
    """

    ensure_connected()

    lock = threading.Lock()

    keywords_lower = [k.lower() for k in keywords]

    try:
        tool_panel = galaxy_state["gi"].tools.get_tool_panel()

        def flatten_tools(panel):
            tools = []
            if isinstance(panel, list):
                for item in panel:
                    tools.extend(flatten_tools(item))
            elif isinstance(panel, dict):
                if "elems" in panel:
                    for item in panel["elems"]:
                        tools.extend(flatten_tools(item))
                else:
                    # Assume this dict represents a tool if no sub-elements exist.
                    tools.append(panel)
            return tools

        all_tools = flatten_tools(tool_panel)
        recommended_tools = []

        # Separate tools that already match by name/description.
        tools_to_fetch = []
        for tool in all_tools:
            name = (tool.get("name") or "").lower()
            description = (tool.get("description") or "").lower()
            if any(kw in name for kw in keywords_lower) or any(
                kw in description for kw in keywords_lower
            ):
                recommended_tools.append(tool)
            else:
                tools_to_fetch.append(tool)

        # Define a helper to check each tool's details.
        def check_tool(tool):
            tool_id = tool.get("id")
            if not tool_id:
                return None
            if tool_id.endswith("_label"):
                return None
            try:
                tool_details = galaxy_state["gi"].tools.show_tool(tool_id, io_details=True)
                tool_inputs = tool_details.get("inputs", [{}])
                for input_spec in tool_inputs:
                    if not isinstance(input_spec, dict):
                        continue
                    fmt = input_spec.get("extensions", "")
                    # 'extensions' might be a list or a string.
                    if isinstance(fmt, list):
                        for ext in fmt:
                            if ext and any(kw in ext.lower() for kw in keywords_lower):
                                return tool
                    elif (
                        isinstance(fmt, str)
                        and fmt
                        and any(kw in fmt.lower() for kw in keywords_lower)
                    ):
                        return tool
                return None
            except Exception:
                return None

        # Use a thread pool to concurrently check tools that require detail retrieval.
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_tool = {executor.submit(check_tool, tool): tool for tool in tools_to_fetch}
            for future in concurrent.futures.as_completed(future_to_tool):
                result = future.result()
                if result is not None:
                    # Use the lock to ensure thread-safe appending.
                    with lock:
                        recommended_tools.append(result)

        slim_tools = []
        for tool in recommended_tools:
            slim_tools.append(
                {
                    "id": tool.get("id", ""),
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "versions": tool.get("versions", []),
                }
            )
        return {"recommended_tools": slim_tools, "count": len(slim_tools)}
    except Exception as e:
        raise ValueError(f"Failed to filter tools based on dataset: {str(e)}") from e


@mcp.tool()
def get_server_info() -> dict[str, Any]:
    """
    Get Galaxy server information including version, URL, and configuration details

    Returns:
        Server information including version, URL, and other configuration details
    """
    ensure_connected()

    try:
        # Get server configuration info
        config_info = galaxy_state["gi"].config.get_config()

        # Get server version info
        version_info = galaxy_state["gi"].config.get_version()

        # Build comprehensive server info response
        server_info = {
            "url": galaxy_state["url"],
            "version": version_info,
            "config": {
                "brand": config_info.get("brand", "Galaxy"),
                "logo_url": config_info.get("logo_url"),
                "welcome_url": config_info.get("welcome_url"),
                "support_url": config_info.get("support_url"),
                "citation_url": config_info.get("citation_url"),
                "terms_url": config_info.get("terms_url"),
                "allow_user_creation": config_info.get("allow_user_creation"),
                "allow_user_deletion": config_info.get("allow_user_deletion"),
                "enable_quotas": config_info.get("enable_quotas"),
                "ftp_upload_site": config_info.get("ftp_upload_site"),
                "wiki_url": config_info.get("wiki_url"),
                "screencasts_url": config_info.get("screencasts_url"),
                "library_import_dir": config_info.get("library_import_dir"),
                "user_library_import_dir": config_info.get("user_library_import_dir"),
                "allow_library_path_paste": config_info.get("allow_library_path_paste"),
                "enable_unique_workflow_defaults": config_info.get(
                    "enable_unique_workflow_defaults"
                ),
            },
        }

        return server_info
    except Exception as e:
        raise ValueError(f"Failed to get server information: {str(e)}") from e


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
        raise ValueError(f"Failed to get user: {str(e)}") from e


@mcp.tool()
def get_histories(
    limit: int | None = None, offset: int = 0, name: str | None = None
) -> dict[str, Any]:
    """
    Get paginated list of user histories

    Args:
        limit: Maximum number of histories to return (default: None for all histories)
        offset: Number of histories to skip from the beginning (default: 0, for pagination)
        name: Filter histories by name pattern (optional, case-sensitive partial match)

    Returns:
        Dictionary containing list of histories and pagination metadata
    """
    ensure_connected()

    try:
        # Get histories with pagination and optional filtering
        histories = galaxy_state["gi"].histories.get_histories(
            limit=limit, offset=offset, name=name
        )

        # If pagination is used, get total count for metadata
        if limit is not None:
            # Get total count without pagination
            all_histories = galaxy_state["gi"].histories.get_histories(name=name)
            total_items = len(all_histories) if all_histories else 0

            # Calculate pagination metadata
            has_next = (offset + limit) < total_items
            has_previous = offset > 0
            current_page = (offset // limit) + 1 if limit > 0 else 1
            total_pages = ((total_items - 1) // limit) + 1 if limit > 0 and total_items > 0 else 1

            pagination = {
                "total_items": total_items,
                "returned_items": len(histories),
                "limit": limit,
                "offset": offset,
                "current_page": current_page,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_previous": has_previous,
                "next_offset": offset + limit if has_next else None,
                "previous_offset": max(0, offset - limit) if has_previous else None,
                "helper_text": f"Page {current_page} of {total_pages}. "
                + (
                    f"Use offset={offset + limit} for next page."
                    if has_next
                    else "This is the last page."
                ),
            }
        else:
            # No pagination requested, return simple count
            pagination = {
                "total_items": len(histories),
                "returned_items": len(histories),
                "paginated": False,
            }

        return {"histories": histories, "pagination": pagination}
    except Exception as e:
        raise ValueError(
            f"Failed to get histories: {str(e)}. "
            "Check your connection to Galaxy and that you have "
            "permission to view histories."
        )


@mcp.tool()
def list_history_ids() -> list[dict[str, str]]:
    """
    Get a simplified list of history IDs and names for easy reference

    Returns:
        List of dictionaries containing 'id' and 'name' fields
    """
    ensure_connected()

    try:
        histories = galaxy_state["gi"].histories.get_histories()
        if not histories:
            return []
        # Extract just the id and name for convenience
        simplified = [{"id": h["id"], "name": h.get("name", "Unnamed")} for h in histories]
        return simplified
    except Exception as e:
        raise ValueError(f"Failed to list history IDs: {str(e)}") from e


@mcp.tool()
def get_history_details(history_id: str) -> dict[str, Any]:
    """
    Get history metadata and summary count ONLY - does not return actual datasets

    This function provides quick access to history information without loading all datasets.
    For the actual datasets/contents, use get_history_contents() which supports
    pagination and ordering.

    Args:
        history_id: Galaxy history ID - a hexadecimal hash string identifying the history
                   (e.g., '1cd8e2f6b131e5aa', typically 16 characters)

    Returns:
        Dictionary containing:
        - history: Basic history metadata (name, id, state, etc.)
        - contents_summary: Just the count of datasets, not the datasets themselves

        To get actual datasets: Use get_history_contents(history_id, limit=N,
                                         order="create_time-dsc")
    """
    ensure_connected()

    try:
        logger.info(f"Getting details for history ID: {history_id}")

        # Get history details
        history_info = galaxy_state["gi"].histories.show_history(history_id, contents=False)
        logger.info(f"Successfully retrieved history info: {history_info.get('name', 'Unknown')}")

        # Get total count by calling without limit
        all_contents = galaxy_state["gi"].histories.show_history(history_id, contents=True)
        total_items = len(all_contents) if all_contents else 0

        return {
            "history": history_info,
            "contents_summary": {
                "total_items": total_items,
                "note": "This is just a count. To get actual datasets, use get_history_contents("
                "history_id, limit=25, order='create_time-dsc') for newest datasets first.",
            },
        }
    except Exception as e:
        logger.error(f"Failed to get history details for ID '{history_id}': {str(e)}")
        if "404" in str(e) or "No route" in str(e):
            raise ValueError(
                f"History ID '{history_id}' not found. Make sure to pass a valid history ID string."
            ) from e
        raise ValueError(f"Failed to get history details for ID '{history_id}': {str(e)}") from e


@mcp.tool()
def get_history_contents(
    history_id: str,
    limit: int = 100,
    offset: int = 0,
    deleted: bool = False,
    visible: bool = True,
    details: bool = False,
    order: str = "hid-asc",
) -> dict[str, Any]:
    """
    Get paginated contents (datasets) from a specific history with ordering support

    Args:
        history_id: Galaxy history ID - a hexadecimal hash string identifying the history
                   (e.g., '1cd8e2f6b131e5aa', typically 16 characters)
        limit: Maximum number of items to return per page (default: 100, max recommended: 500)
        offset: Number of items to skip from the beginning (default: 0, for pagination)
        deleted: Include deleted datasets in results (default: False)
        visible: Include only visible datasets (default: True, set False to include hidden)
        details: Include detailed metadata for each dataset (default: False, impacts performance)
        order: Sort order for results. Options include:
              - 'hid-asc': History ID ascending (default, oldest first)
              - 'hid-dsc': History ID descending (newest first)
              - 'create_time-dsc': Creation time descending (most recent first)
              - 'create_time-asc': Creation time ascending (oldest first)
              - 'update_time-dsc': Last updated descending (most recently modified first)
              - 'name-asc': Dataset name ascending (alphabetical)

    Returns:
        Dictionary containing paginated dataset list, pagination metadata, and history reference
    """
    ensure_connected()

    try:
        logger.info(
            f"Getting contents for history ID: {history_id} "
            f"(limit={limit}, offset={offset}, order={order})"
        )

        # Use datasets API for better ordering support
        contents = galaxy_state["gi"].datasets.get_datasets(
            limit=limit,
            offset=offset,
            history_id=history_id,
            order=order,
            # Note: datasets API uses different parameter names
            # deleted and visible filtering is done post-query if needed
        )

        # Filter by visibility and deleted status if needed
        if not deleted:
            contents = [item for item in contents if not item.get("deleted", False)]
        if visible:
            contents = [item for item in contents if item.get("visible", True)]

        # Get total count for pagination metadata
        all_contents = galaxy_state["gi"].datasets.get_datasets(
            history_id=history_id,
            order=order,
        )

        # Apply same filtering to total count
        if not deleted:
            all_contents = [item for item in all_contents if not item.get("deleted", False)]
        if visible:
            all_contents = [item for item in all_contents if item.get("visible", True)]

        total_items = len(all_contents) if all_contents else 0

        # Calculate pagination metadata
        has_next = (offset + limit) < total_items
        has_previous = offset > 0
        current_page = (offset // limit) + 1 if limit > 0 else 1
        total_pages = ((total_items - 1) // limit) + 1 if limit > 0 and total_items > 0 else 1

        logger.info(f"Retrieved {len(contents)} items (page {current_page} of {total_pages})")

        return {
            "history_id": history_id,
            "contents": contents,
            "pagination": {
                "total_items": total_items,
                "returned_items": len(contents),
                "limit": limit,
                "offset": offset,
                "current_page": current_page,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_previous": has_previous,
                "next_offset": offset + limit if has_next else None,
                "previous_offset": max(0, offset - limit) if has_previous else None,
                "helper_text": f"Showing page {current_page} of {total_pages}. "
                + (
                    f"Use offset={offset + limit} for next page."
                    if has_next
                    else "This is the last page."
                ),
            },
        }
    except Exception as e:
        logger.error(f"Failed to get history contents for ID '{history_id}': {str(e)}")
        if "404" in str(e) or "No route" in str(e):
            raise ValueError(
                f"History ID '{history_id}' not found. Make sure to pass a valid history ID string."
            ) from e
        raise ValueError(f"Failed to get history contents for ID '{history_id}': {str(e)}") from e


@mcp.tool()
def get_job_details(dataset_id: str, history_id: str | None = None) -> dict[str, Any]:
    """
    Get detailed information about the job that created a specific dataset

    Args:
        dataset_id: Galaxy dataset ID - a hexadecimal hash string identifying the dataset
                   (e.g., 'f2db41e1fa331b3e', typically 16 characters)
        history_id: Galaxy history ID containing the dataset - optional for performance optimization
                   (e.g., '1cd8e2f6b131e5aa', typically 16 characters)

    Returns:
        Dictionary containing job metadata, tool information, dataset ID, and job ID
    """
    ensure_connected()

    try:
        # Get dataset provenance to find the creating job
        try:
            provenance = galaxy_state["gi"].histories.show_dataset_provenance(
                history_id=history_id, dataset_id=dataset_id
            )

            # Extract job ID from provenance
            job_id = provenance.get("job_id")
            if not job_id:
                raise ValueError(
                    f"No job information found for dataset '{dataset_id}'. "
                    "The dataset may not have been created by a job."
                )

        except Exception as provenance_error:
            # If provenance fails, try getting dataset details which might contain job info
            try:
                dataset_details = galaxy_state["gi"].datasets.show_dataset(dataset_id)
                job_id = dataset_details.get("creating_job")
                if not job_id:
                    raise ValueError(
                        f"No job information found for dataset '{dataset_id}'. "
                        "The dataset may not have been created by a job."
                    )
            except Exception:
                raise ValueError(
                    f"Failed to get job information for dataset '{dataset_id}': "
                    f"{str(provenance_error)}"
                ) from provenance_error

        # Get job details using the Galaxy API directly
        # (Bioblend doesn't have a direct method for this)
        url = f"{galaxy_state['url']}api/jobs/{job_id}"
        headers = {"x-api-key": galaxy_state["api_key"]}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        job_info = response.json()

        return {"job": job_info, "dataset_id": dataset_id, "job_id": job_id}
    except Exception as e:
        if "404" in str(e):
            raise ValueError(
                f"Dataset ID '{dataset_id}' not found or job not accessible. "
                "Make sure the dataset exists and you have permission to view it."
            ) from e
        raise ValueError(f"Failed to get job details for dataset '{dataset_id}': {str(e)}") from e


@mcp.tool()
def get_dataset_details(
    dataset_id: str, include_preview: bool = True, preview_lines: int = 10
) -> dict[str, Any]:
    """
    Get detailed information about a specific dataset, optionally including a content preview

    Args:
        dataset_id: Galaxy dataset ID - a hexadecimal hash string identifying the dataset
                   (e.g., 'f2db41e1fa331b3e', typically 16 characters)
        include_preview: Whether to include a preview of the dataset content showing first N lines
                        (default: True, only works for datasets in 'ok' state)
        preview_lines: Number of lines to include in the content preview (default: 10)

    Returns:
        Dictionary containing dataset metadata (name, size, state, extension) and optional
        content preview with line count and truncation information
    """
    ensure_connected()

    try:
        # Get dataset details using bioblend
        dataset_info = galaxy_state["gi"].datasets.show_dataset(dataset_id)

        result = {"dataset": dataset_info, "dataset_id": dataset_id}

        # Add content preview if requested and dataset is in 'ok' state
        if include_preview and dataset_info.get("state") == "ok":
            try:
                # Get dataset content for preview
                content = galaxy_state["gi"].datasets.download_dataset(
                    dataset_id, use_default_filename=False, require_ok_state=False
                )

                # Convert bytes to string if needed
                if isinstance(content, bytes):
                    try:
                        content_str = content.decode("utf-8")
                    except UnicodeDecodeError:
                        # For binary files, show first part as hex
                        content_str = (
                            f"[Binary content - first 100 bytes as hex: {content[:100].hex()}]"
                        )
                else:
                    content_str = content

                # Get preview lines
                lines = content_str.split("\n")
                preview = "\n".join(lines[:preview_lines])

                result["preview"] = {
                    "lines": preview,
                    "total_lines": len(lines),
                    "preview_lines": min(preview_lines, len(lines)),
                    "truncated": len(lines) > preview_lines,
                }

            except Exception as preview_error:
                logger.warning(f"Could not get preview for dataset {dataset_id}: {preview_error}")
                result["preview"] = {
                    "error": f"Preview unavailable: {str(preview_error)}",
                    "lines": None,
                }

        return result

    except Exception as e:
        if "404" in str(e):
            raise ValueError(
                f"Dataset ID '{dataset_id}' not found. "
                "Make sure the dataset exists and you have permission to view it."
            ) from e
        raise ValueError(f"Failed to get dataset details for '{dataset_id}': {str(e)}") from e


@mcp.tool()
def download_dataset(
    dataset_id: str,
    file_path: str | None = None,
    use_default_filename: bool = True,
    require_ok_state: bool = True,
) -> dict[str, Any]:
    """
    Download a dataset from Galaxy to the local filesystem or memory

    Args:
        dataset_id: Galaxy dataset ID - a hexadecimal hash string identifying the dataset
                   (e.g., 'f2db41e1fa331b3e', typically 16 characters)
        file_path: Local filesystem path where to save the downloaded file
                  (e.g., '/path/to/data.txt', requires write access to filesystem)
                  If not provided, downloads to memory instead
        use_default_filename: Deprecated - use file_path for specific locations
                             (default: True, ignored when file_path not provided)
        require_ok_state: Only allow download if dataset processing state is 'ok'
                         (default: True, set False to download datasets in other states)

    Returns:
        Dictionary containing download information:
        - file_path: Path where file was saved (None if downloaded to memory)
        - suggested_filename: Recommended filename based on dataset name
        - content_available: Whether content was successfully downloaded
        - file_size: Size of downloaded content in bytes
        - dataset_info: Dataset metadata (name, extension, state, genome build)

    IMPORTANT FOR LLMs: If you don't have filesystem write access (common in sandboxed
    environments), omit the file_path parameter to download content to memory. Only
    specify file_path if you can actually write files to the local filesystem.
    """
    ensure_connected()

    try:
        # Get dataset info first to check state and get metadata
        dataset_info = galaxy_state["gi"].datasets.show_dataset(dataset_id)

        # Check dataset state if required
        if require_ok_state and dataset_info.get("state") != "ok":
            raise ValueError(
                f"Dataset '{dataset_id}' is in state '{dataset_info.get('state')}', not 'ok'. "
                "Set require_ok_state=False to download anyway."
            )

        # Download the dataset
        if file_path:
            # Download to specific path
            result_path = galaxy_state["gi"].datasets.download_dataset(
                dataset_id,
                file_path=file_path,
                use_default_filename=False,
                require_ok_state=require_ok_state,
            )
            download_path = file_path

            # Get file size
            import os

            file_size = os.path.getsize(download_path) if os.path.exists(download_path) else None

        else:
            # Download content to memory (don't save to filesystem)
            result_path = galaxy_state["gi"].datasets.download_dataset(
                dataset_id,
                use_default_filename=False,  # Get content in memory
                require_ok_state=require_ok_state,
            )

            # Create suggested filename from dataset info
            filename = dataset_info.get("name", f"dataset_{dataset_id}")
            extension = dataset_info.get("extension", "")
            if extension and not filename.endswith(f".{extension}"):
                filename = f"{filename}.{extension}"

            download_path = None  # No file saved
            file_size = len(result_path) if isinstance(result_path, bytes | str) else None

        return {
            "dataset_id": dataset_id,
            "file_path": download_path,
            "suggested_filename": filename if not file_path else None,
            "content_available": result_path is not None,
            "file_size": file_size,  # Keep consistent with existing API
            "note": (
                "Content downloaded to memory. Use file_path parameter to save to a location."
                if not file_path
                else "File saved to specified path."
            ),
            "dataset_info": {
                "name": dataset_info.get("name"),
                "extension": dataset_info.get("extension"),
                "state": dataset_info.get("state"),
                "genome_build": dataset_info.get("genome_build"),
                "file_size": dataset_info.get("file_size"),
            },
        }

    except Exception as e:
        if "404" in str(e):
            raise ValueError(
                f"Dataset ID '{dataset_id}' not found. "
                "Make sure the dataset exists and you have permission to view it."
            ) from e
        raise ValueError(f"Failed to download dataset '{dataset_id}': {str(e)}") from e


@mcp.tool()
def upload_file(path: str, history_id: str | None = None) -> dict[str, Any]:
    """
    Upload a local file to Galaxy

    Args:
        path: Local filesystem path to the file to upload (e.g., '/path/to/data.csv')
        history_id: Galaxy history ID where to upload the file - optional, uses current history
                   (e.g., '1cd8e2f6b131e5aa', typically 16 characters)

    Returns:
        Dictionary containing upload status and information about the created dataset(s)
    """
    ensure_connected()

    try:
        if not os.path.exists(path):
            abs_path = os.path.abspath(path)
            raise ValueError(
                f"File not found: '{path}' (absolute: '{abs_path}'). "
                "Check that the file exists and you have read permissions."
            )

        result = galaxy_state["gi"].tools.upload_file(path, history_id=history_id)
        return result
    except Exception as e:
        raise ValueError(f"Failed to upload file: {str(e)}") from e


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
        invocation_id: Specific workflow invocation ID to view - a hexadecimal hash string
                      (e.g., 'a1b2c3d4e5f6789a', typically 16 characters, optional)
        workflow_id: Filter invocations by workflow ID - a hexadecimal hash string
                    (e.g., 'b2c3d4e5f6789abc', typically 16 characters, optional)
        history_id: Filter invocations by history ID - a hexadecimal hash string
                   (e.g., '1cd8e2f6b131e5aa', typically 16 characters, optional)
        limit: Maximum number of invocations to return (optional, default: no limit)
        view: Level of detail to return - 'element' for detailed or 'collection' for summary
             (default: 'collection')
        step_details: Include details on individual workflow steps
                     (only applies when view is 'element', default: False)

    Returns:
        Dictionary containing workflow invocation information, execution status, and step details
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
        raise ValueError(f"Failed to get workflow invocations: {str(e)}") from e


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
        manifest = response.json()

        # Collect workflows from all manifest entries
        all_workflows = []
        for entry in manifest:
            if "workflows" in entry:
                all_workflows.extend(entry["workflows"])

        return {"workflows": all_workflows}
    except Exception as e:
        raise ValueError(f"Failed to fetch IWC workflows: {str(e)}") from e


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
        manifest = get_iwc_workflows.fn()["workflows"]

        # Filter workflows based on the search query
        results = []
        query = query.lower()

        for workflow in manifest:
            # Check if query matches name, description or tags
            name = workflow.get("definition", {}).get("name", "").lower()
            description = workflow.get("definition", {}).get("annotation", "").lower()
            tags = [tag.lower() for tag in workflow.get("definition", {}).get("tags", [])]

            if (
                query in name
                or query in description
                or (tags and any(query in tag for tag in tags))
            ):
                results.append(workflow)

        return {"workflows": results, "count": len(results)}
    except Exception as e:
        raise ValueError(f"Failed to search IWC workflows: {str(e)}") from e


@mcp.tool()
def import_workflow_from_iwc(trs_id: str) -> dict[str, Any]:
    """
    Import a workflow from IWC to the user's Galaxy instance

    Args:
        trs_id: TRS ID of the workflow in the IWC manifest

    Returns:
        Imported workflow information
    """
    ensure_connected()

    try:
        # Get the workflow manifest
        manifest = get_iwc_workflows.fn()["workflows"]

        # Find the specified workflow
        workflow = None
        for wf in manifest:
            if wf.get("trsID") == trs_id:
                workflow = wf
                break

        if not workflow:
            raise ValueError(
                f"Workflow with trsID '{trs_id}' not found in IWC manifest. "
                "Check the trsID format and that it exists in the IWC. "
                "You can search workflows using search_iwc_workflows() first."
            )

        # Extract the workflow definition
        workflow_definition = workflow.get("definition")
        if not workflow_definition:
            raise ValueError(
                f"No definition found for workflow with trsID '{trs_id}'. "
                "The workflow exists but has no valid definition. "
                "This may be a problem with the IWC manifest."
            )

        # Import the workflow into Galaxy
        imported_workflow = galaxy_state["gi"].workflows.import_workflow_dict(workflow_definition)
        return {"imported_workflow": imported_workflow}
    except Exception as e:
        raise ValueError(f"Failed to import workflow from IWC: {str(e)}") from e


if __name__ == "__main__":
    mcp.run()
