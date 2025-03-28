# Galaxy MCP Server

This project is a Model Context Protocol (MCP) server that provides tools for interacting with Galaxy instances and other things in the Galaxy ecosystem (IWC). It allows users to connect to a Galaxy server, search for tools, get tool details, run tools, manage histories, and more.

## Features

*   **Connect to Galaxy:** Connect to a Galaxy server using a URL and API key.
*   **Search Tools:** Search for tools in Galaxy by name.
*   **Get Tool Details:** Get detailed information about a specific tool, including inputs and outputs.
*   **Run Tools:** Run a tool in Galaxy with specified inputs.
*   **Manage Histories:** Get a list of user histories.
*   **Upload Files:** Upload a local file to Galaxy.
*   **Workflow Invocations:** View workflow invocations in Galaxy.
*   **IWC Integration:** Search and import workflows from the Interactive Workflow Composer (IWC).

## Requirements

*   Python 3.6+
*   BioBlend
*   Requests
*   MCP SDK

## Required Variables

1.  Clone the repository:

    ```bash
    git clone <repository_url>
    cd galaxy-mcp
    ```

2.  Install the dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3.  Set the Galaxy URL and API key as environment variables:

    ```bash
    export GALAXY_URL=<galaxy_url>
    export GALAXY_API_KEY=<galaxy_api_key>
    ```

    Alternatively, you can create a `.env` file with the following content:

    ```
    GALAXY_URL=<galaxy_url>
    GALAXY_API_KEY=<galaxy_api_key>
    ```

    jj

## Usage

Run the server:

```bash
mcp run main.py
```

Once the server is running, you can use the MCP client to interact with the Galaxy instance.


Or, you can use a development server to explore available tools, resources, prompts, etc.

```bash
mcp dev main.py
```

## MCP Tools

The following tools are available:

*   `connect(url: str | None = None, api_key: str | None = None) -> dict[str, Any]`: Connect to Galaxy server.
*   `search_tools(query: str) -> dict[str, Any]`: Search for tools in Galaxy.
*   `get_tool_details(tool_id: str, io_details: bool = False) -> dict[str, Any]`: Get detailed information about a specific tool.
*   `run_tool(history_id: str, tool_id: str, inputs: dict[str, Any]) -> dict[str, Any]`: Run a tool in Galaxy.
*   `get_tool_panel() -> dict[str, Any]`: Get the tool panel structure (toolbox).
*   `get_user() -> dict[str, Any]`: Get current user information.
*   `get_histories() -> dict[str, Any]`: Get list of user histories.
*   `upload_file(path: str, history_id: str | None = None) -> dict[str, Any]`: Upload a local file to Galaxy.
*   `get_invocations(invocation_id: str | None = None, workflow_id: str | None = None, history_id: str | None = None, limit: int | None = None, view: str = "collection", step_details: bool = False) -> dict[str, Any]`: View workflow invocations in Galaxy.
*   `get_iwc_workflows() -> dict[str, Any]`: Fetch all workflows from the IWC (Interactive Workflow Composer).
*   `search_iwc_workflows(query: str) -> dict[str, Any]`: Search for workflows in the IWC manifest.
*   `import_workflow_from_iwc(workflow_id: str) -> dict[str, Any]`: Import a workflow from IWC to the user's Galaxy instance.

## License

[MIT](LICENSE)
