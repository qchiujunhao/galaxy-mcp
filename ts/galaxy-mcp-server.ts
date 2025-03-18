// galaxy-mcp-server.ts
// Message Command Protocol Server for Galaxy Bioinformatics Platform

import { createServer } from 'http';
import { parse } from 'url';
import createClient from 'openapi-fetch';
import axios from 'axios';

interface MCPCommand {
  command: string;
  args: Record<string, any>;
}

interface MCPResponse {
  status: 'success' | 'error';
  data?: any;
  error?: string;
}

class GalaxyMCPServer {
  private apiKey: string | null = null;
  private galaxyUrl: string | null = null;
  private client: any = null;

  constructor(port: number = 3000) {
    const server = createServer((req, res) => {
      res.setHeader('Content-Type', 'application/json');
      res.setHeader('Access-Control-Allow-Origin', '*');
      res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
      res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

      if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
      }

      if (req.method === 'POST') {
        let body = '';
        req.on('data', (chunk) => {
          body += chunk.toString();
        });

        req.on('end', async () => {
          try {
            const command = JSON.parse(body) as MCPCommand;
            const response = await this.processCommand(command);
            res.writeHead(200);
            res.end(JSON.stringify(response));
          } catch (error) {
            res.writeHead(400);
            res.end(JSON.stringify({
              status: 'error',
              error: `Failed to parse command: ${error}`
            }));
          }
        });
      } else {
        res.writeHead(404);
        res.end(JSON.stringify({
          status: 'error',
          error: 'Not found'
        }));
      }
    });

    server.listen(port, () => {
      console.log(`Galaxy MCP Server running on port ${port}`);
    });
  }

  private async processCommand(command: MCPCommand): Promise<MCPResponse> {
    try {
      console.log(`Processing command: ${command.command}`, command.args);

      switch (command.command) {
        case 'connect':
          return await this.connectToGalaxy(command.args.url, command.args.apiKey);
        case 'listHistories':
          return await this.listHistories();
        case 'getHistory':
          return await this.getHistory(command.args.id);
        case 'listDatasets':
          return await this.listDatasets(command.args.historyId);
        case 'getDataset':
          return await this.getDataset(command.args.id);
        case 'runWorkflow':
          return await this.runWorkflow(command.args.workflowId, command.args.inputs);
        case 'searchTools':
          return await this.searchTools(command.args.query);
        case 'runTool':
          return await this.runTool(command.args.toolId, command.args.inputs, command.args.historyId);
        case 'uploadFile':
          return await this.uploadFile(command.args.file, command.args.historyId);
        case 'getUser':
          return await this.getUser();
        default:
          return {
            status: 'error',
            error: `Unknown command: ${command.command}`
          };
      }
    } catch (error) {
      console.error(`Error processing command ${command.command}:`, error);
      return {
        status: 'error',
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  private async connectToGalaxy(url: string, apiKey: string): Promise<MCPResponse> {
    try {
      this.galaxyUrl = url.endsWith('/') ? url : `${url}/`;
      this.apiKey = apiKey;
      
      // Create a client with the API key
      this.client = createClient({
        baseUrl: this.galaxyUrl,
        headers: {
          'x-api-key': this.apiKey
        }
      });

      // Test the connection by fetching user info
      const { data, error } = await this.client.GET('/api/users/current');
      
      if (error) {
        throw new Error(`Failed to connect to Galaxy: ${JSON.stringify(error)}`);
      }

      return {
        status: 'success',
        data: { 
          connected: true,
          user: data
        }
      };
    } catch (error) {
      this.galaxyUrl = null;
      this.apiKey = null;
      this.client = null;
      
      return {
        status: 'error',
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  private async listHistories(): Promise<MCPResponse> {
    this.ensureConnected();
    
    const { data, error } = await this.client.GET('/api/histories', {
      params: {
        query: {
          view: 'summary',
          keys: 'size,contents_active,user_id'
        }
      }
    });

    if (error) {
      throw new Error(`Failed to list histories: ${JSON.stringify(error)}`);
    }

    return {
      status: 'success',
      data
    };
  }

  private async getHistory(id: string): Promise<MCPResponse> {
    this.ensureConnected();
    
    const { data, error } = await this.client.GET('/api/histories/{history_id}', {
      params: {
        path: {
          history_id: id
        },
        query: {
          view: 'detailed'
        }
      }
    });

    if (error) {
      throw new Error(`Failed to get history: ${JSON.stringify(error)}`);
    }

    return {
      status: 'success',
      data
    };
  }

  private async listDatasets(historyId: string): Promise<MCPResponse> {
    this.ensureConnected();
    
    const { data, error } = await this.client.GET('/api/histories/{history_id}/contents', {
      params: {
        path: {
          history_id: historyId
        }
      }
    });

    if (error) {
      throw new Error(`Failed to list datasets: ${JSON.stringify(error)}`);
    }

    return {
      status: 'success',
      data
    };
  }

  private async getDataset(id: string): Promise<MCPResponse> {
    this.ensureConnected();
    
    const { data, error } = await this.client.GET('/api/datasets/{dataset_id}', {
      params: {
        path: {
          dataset_id: id
        },
        query: {
          view: 'detailed'
        }
      }
    });

    if (error) {
      throw new Error(`Failed to get dataset: ${JSON.stringify(error)}`);
    }

    return {
      status: 'success',
      data
    };
  }

  private async runWorkflow(workflowId: string, inputs: Record<string, any>): Promise<MCPResponse> {
    this.ensureConnected();
    
    const { data, error } = await this.client.POST('/api/workflows/{workflow_id}/invocations', {
      params: {
        path: {
          workflow_id: workflowId
        }
      },
      body: {
        inputs
      }
    });

    if (error) {
      throw new Error(`Failed to run workflow: ${JSON.stringify(error)}`);
    }

    return {
      status: 'success',
      data
    };
  }

  private async searchTools(query: string): Promise<MCPResponse> {
    this.ensureConnected();
    
    const { data, error } = await this.client.GET('/api/tools', {
      params: {
        query: {
          q: query
        }
      }
    });

    if (error) {
      throw new Error(`Failed to search tools: ${JSON.stringify(error)}`);
    }

    return {
      status: 'success',
      data
    };
  }

  private async runTool(toolId: string, inputs: Record<string, any>, historyId: string): Promise<MCPResponse> {
    this.ensureConnected();
    
    const { data, error } = await this.client.POST('/api/tools', {
      body: {
        tool_id: toolId,
        inputs,
        history_id: historyId
      }
    });

    if (error) {
      throw new Error(`Failed to run tool: ${JSON.stringify(error)}`);
    }

    return {
      status: 'success',
      data
    };
  }

  private async uploadFile(file: { name: string, content: string }, historyId: string): Promise<MCPResponse> {
    this.ensureConnected();
    
    // Galaxy API uses FormData for file uploads
    const formData = new FormData();
    formData.append('file', new Blob([file.content]), file.name);
    formData.append('history_id', historyId);
    
    const response = await axios.post(`${this.galaxyUrl}api/tools/fetch`, formData, {
      headers: {
        'x-api-key': this.apiKey,
        'Content-Type': 'multipart/form-data'
      }
    });

    return {
      status: 'success',
      data: response.data
    };
  }

  private async getUser(): Promise<MCPResponse> {
    this.ensureConnected();
    
    const { data, error } = await this.client.GET('/api/users/current');

    if (error) {
      throw new Error(`Failed to get user: ${JSON.stringify(error)}`);
    }

    return {
      status: 'success',
      data
    };
  }

  private ensureConnected() {
    if (!this.client || !this.galaxyUrl || !this.apiKey) {
      throw new Error('Not connected to Galaxy. Use connect command first.');
    }
  }
}

// Start the server
const port = process.env.PORT ? parseInt(process.env.PORT) : 3000;
new GalaxyMCPServer(port);

export default GalaxyMCPServer;