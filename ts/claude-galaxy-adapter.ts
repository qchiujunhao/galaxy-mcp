// claude-galaxy-adapter.ts
// Adapter for Claude to interact with Galaxy via MCP

import GalaxyMCPClient from './galaxy-mcp-client';

/**
 * Claude Galaxy Adapter provides a high-level interface for Claude to interact with Galaxy
 */
class ClaudeGalaxyAdapter {
  private client: GalaxyMCPClient;
  private connected: boolean = false;
  private currentHistory: string | null = null;

  /**
   * Create a new Claude Galaxy Adapter
   * @param mcpServerUrl URL of the MCP server
   */
  constructor(mcpServerUrl: string) {
    this.client = new GalaxyMCPClient(mcpServerUrl);
  }

  /**
   * Connect to a Galaxy server
   * @param galaxyUrl Galaxy server URL
   * @param apiKey Galaxy API key
   */
  async connect(galaxyUrl: string, apiKey: string): Promise<string> {
    const response = await this.client.connect(galaxyUrl, apiKey);
    
    if (response.status === 'error') {
      return `Failed to connect to Galaxy: ${response.error}`;
    }
    
    this.connected = true;
    return `Successfully connected to Galaxy as ${response.data.user.username || 'anonymous'}`;
  }

  /**
   * Get information about the current user
   */
  async whoAmI(): Promise<string> {
    this.ensureConnected();
    
    const response = await this.client.getUser();
    
    if (response.status === 'error') {
      return `Failed to get user information: ${response.error}`;
    }
    
    const user = response.data;
    return `You are connected as ${user.username || 'anonymous'} (${user.email || 'no email'})${user.is_admin ? ' with admin privileges' : ''}`;
  }

  /**
   * List all histories
   */
  async listHistories(): Promise<string> {
    this.ensureConnected();
    
    const response = await this.client.listHistories();
    
    if (response.status === 'error') {
      return `Failed to list histories: ${response.error}`;
    }
    
    const histories = response.data;
    
    if (histories.length === 0) {
      return 'No histories found';
    }
    
    return `Found ${histories.length} histories:\n\n` + 
      histories.map((h: any, i: number) => 
        `${i+1}. "${h.name}" (ID: ${h.id}) - ${h.tags?.length ? `Tags: ${h.tags.join(', ')} - ` : ''}${h.deleted ? 'Deleted' : 'Active'}`
      ).join('\n');
  }

  /**
   * Set the current working history
   * @param historyId History ID
   */
  async useHistory(historyId: string): Promise<string> {
    this.ensureConnected();
    
    const response = await this.client.getHistory(historyId);
    
    if (response.status === 'error') {
      return `Failed to set current history: ${response.error}`;
    }
    
    this.currentHistory = historyId;
    const history = response.data;
    
    return `Now using history "${history.name}" (ID: ${history.id})`;
  }

  /**
   * List datasets in the current history
   */
  async listDatasets(): Promise<string> {
    this.ensureConnected();
    this.ensureHistorySelected();
    
    const response = await this.client.listDatasets(this.currentHistory!);
    
    if (response.status === 'error') {
      return `Failed to list datasets: ${response.error}`;
    }
    
    const datasets = response.data;
    
    if (datasets.length === 0) {
      return 'No datasets found in the current history';
    }
    
    return `Found ${datasets.length} datasets in the current history:\n\n` + 
      datasets.map((d: any, i: number) => 
        `${i+1}. "${d.name}" (ID: ${d.id}) - Type: ${d.history_content_type}, Status: ${d.state}`
      ).join('\n');
  }

  /**
   * Get details about a dataset
   * @param datasetId Dataset ID
   */
  async getDataset(datasetId: string): Promise<string> {
    this.ensureConnected();
    
    const response = await this.client.getDataset(datasetId);
    
    if (response.status === 'error') {
      return `Failed to get dataset: ${response.error}`;
    }
    
    const dataset = response.data;
    return `Dataset "${dataset.name}" (ID: ${dataset.id})\n` +
      `Type: ${dataset.history_content_type}\n` +
      `Data Type: ${dataset.data_type}\n` +
      `State: ${dataset.state}\n` +
      `Created: ${dataset.create_time}\n` +
      `Size: ${dataset.file_size || 'Unknown'}\n` +
      (dataset.peek ? `Peek: ${dataset.peek.substring(0, 200)}${dataset.peek.length > 200 ? '...' : ''}` : '');
  }

  /**
   * Search for tools
   * @param query Search query
   */
  async searchTools(query: string): Promise<string> {
    this.ensureConnected();
    
    const response = await this.client.searchTools(query);
    
    if (response.status === 'error') {
      return `Failed to search tools: ${response.error}`;
    }
    
    const tools = response.data;
    
    if (tools.length === 0) {
      return `No tools found matching "${query}"`;
    }
    
    return `Found ${tools.length} tools matching "${query}":\n\n` + 
      tools.map((t: any, i: number) => 
        `${i+1}. "${t.name}" (ID: ${t.id})\n   Description: ${t.description || 'No description'}`
      ).join('\n\n');
  }

  /**
   * Run a tool
   * @param toolId Tool ID
   * @param inputs Tool inputs as a JSON string
   */
  async runTool(toolId: string, inputs: string): Promise<string> {
    this.ensureConnected();
    this.ensureHistorySelected();
    
    let parsedInputs: Record<string, any>;
    
    try {
      parsedInputs = JSON.parse(inputs);
    } catch (error) {
      return `Failed to parse inputs: ${error instanceof Error ? error.message : String(error)}`;
    }
    
    const response = await this.client.runTool(toolId, parsedInputs, this.currentHistory!);
    
    if (response.status === 'error') {
      return `Failed to run tool: ${response.error}`;
    }
    
    const result = response.data;
    return `Tool execution started successfully:\n` +
      `Job ID: ${result.jobs?.[0]?.id || 'Unknown'}\n` +
      `Outputs: ${JSON.stringify(result.outputs || {}, null, 2)}`;
  }

  /**
   * Run a workflow
   * @param workflowId Workflow ID
   * @param inputs Workflow inputs as a JSON string
   */
  async runWorkflow(workflowId: string, inputs: string): Promise<string> {
    this.ensureConnected();
    
    let parsedInputs: Record<string, any>;
    
    try {
      parsedInputs = JSON.parse(inputs);
    } catch (error) {
      return `Failed to parse inputs: ${error instanceof Error ? error.message : String(error)}`;
    }
    
    const response = await this.client.runWorkflow(workflowId, parsedInputs);
    
    if (response.status === 'error') {
      return `Failed to run workflow: ${response.error}`;
    }
    
    const result = response.data;
    return `Workflow execution started successfully:\n` +
      `Invocation ID: ${result.id || 'Unknown'}\n` +
      `History ID: ${result.history_id || 'Unknown'}`;
  }

  /**
   * Upload a file to Galaxy
   * @param filename File name
   * @param content File content
   */
  async uploadFile(filename: string, content: string): Promise<string> {
    this.ensureConnected();
    this.ensureHistorySelected();
    
    const response = await this.client.uploadFile({ name: filename, content }, this.currentHistory!);
    
    if (response.status === 'error') {
      return `Failed to upload file: ${response.error}`;
    }
    
    const result = response.data;
    return `File uploaded successfully:\n` +
      `Job ID: ${result.jobs?.[0]?.id || 'Unknown'}\n` +
      `Outputs: ${JSON.stringify(result.outputs || {}, null, 2)}`;
  }

  /**
   * Ensure the client is connected to Galaxy
   */
  private ensureConnected(): void {
    if (!this.connected) {
      throw new Error('Not connected to Galaxy. Use the connect command first.');
    }
  }

  /**
   * Ensure a history is selected
   */
  private ensureHistorySelected(): void {
    if (!this.currentHistory) {
      throw new Error('No history selected. Use the useHistory command first.');
    }
  }
}

export default ClaudeGalaxyAdapter;