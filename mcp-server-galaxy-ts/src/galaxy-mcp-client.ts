// galaxy-mcp-client.ts
// Message Command Protocol Client for Galaxy Bioinformatics Platform

import fetch from 'node-fetch';

interface MCPCommand {
  command: string;
  args: Record<string, any>;
}

interface MCPResponse {
  status: 'success' | 'error';
  data?: any;
  error?: string;
}

class GalaxyMCPClient {
  private serverUrl: string;

  /**
   * Create a new Galaxy MCP client
   * @param serverUrl URL of the MCP server
   */
  constructor(serverUrl: string) {
    this.serverUrl = serverUrl.endsWith('/') ? serverUrl : `${serverUrl}/`;
  }

  /**
   * Send a command to the MCP server
   * @param command Command name
   * @param args Command arguments
   * @returns Promise with the response
   */
  async sendCommand(command: string, args: Record<string, any> = {}): Promise<MCPResponse> {
    try {
      const response = await fetch(this.serverUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          command,
          args
        } as MCPCommand)
      });

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status} ${response.statusText}`);
      }

      return await response.json() as MCPResponse;
    } catch (error) {
      return {
        status: 'error',
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  /**
   * Connect to a Galaxy server
   * @param url Galaxy server URL
   * @param apiKey Galaxy API key
   */
  async connect(url: string, apiKey: string): Promise<MCPResponse> {
    return this.sendCommand('connect', { url, apiKey });
  }

  /**
   * Get the current user
   */
  async getUser(): Promise<MCPResponse> {
    return this.sendCommand('getUser');
  }

  /**
   * List all histories
   */
  async listHistories(): Promise<MCPResponse> {
    return this.sendCommand('listHistories');
  }

  /**
   * Get a specific history by ID
   * @param id History ID
   */
  async getHistory(id: string): Promise<MCPResponse> {
    return this.sendCommand('getHistory', { id });
  }

  /**
   * List datasets in a history
   * @param historyId History ID
   */
  async listDatasets(historyId: string): Promise<MCPResponse> {
    return this.sendCommand('listDatasets', { historyId });
  }

  /**
   * Get a specific dataset by ID
   * @param id Dataset ID
   */
  async getDataset(id: string): Promise<MCPResponse> {
    return this.sendCommand('getDataset', { id });
  }

  /**
   * Run a workflow
   * @param workflowId Workflow ID
   * @param inputs Workflow inputs
   */
  async runWorkflow(workflowId: string, inputs: Record<string, any>): Promise<MCPResponse> {
    return this.sendCommand('runWorkflow', { workflowId, inputs });
  }

  /**
   * Search for tools
   * @param query Search query
   */
  async searchTools(query: string): Promise<MCPResponse> {
    return this.sendCommand('searchTools', { query });
  }

  /**
   * Run a tool
   * @param toolId Tool ID
   * @param inputs Tool inputs
   * @param historyId History ID to store results
   */
  async runTool(toolId: string, inputs: Record<string, any>, historyId: string): Promise<MCPResponse> {
    return this.sendCommand('runTool', { toolId, inputs, historyId });
  }

  /**
   * Upload a file to Galaxy
   * @param file File object with name and content
   * @param historyId History ID to store the file
   */
  async uploadFile(file: { name: string, content: string }, historyId: string): Promise<MCPResponse> {
    return this.sendCommand('uploadFile', { file, historyId });
  }
}

export default GalaxyMCPClient;