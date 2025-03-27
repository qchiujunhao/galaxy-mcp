import { McpServer, ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import axios, { AxiosInstance } from 'axios';

// Create an MCP server for Galaxy
const server = new McpServer({
  name: "Galaxy",
  version: "1.0.0"
});

// Store Galaxy connection details
let galaxyState = {
  url: process.env.GALAXY_URL || null,
  apiKey: process.env.GALAXY_API_KEY || null,
  client: null as AxiosInstance | null,
  connected: false
};

// Initialize Galaxy client if environment variables are set
if (galaxyState.url && galaxyState.apiKey) {
  const galaxyUrl = galaxyState.url.endsWith('/') ? galaxyState.url : `${galaxyState.url}/`;
  galaxyState.url = galaxyUrl;
  galaxyState.client = axios.create({
    baseURL: galaxyUrl,
    headers: {
      'x-api-key': galaxyState.apiKey
    }
  });
  galaxyState.connected = true;
  console.error(`Galaxy client initialized from environment variables (URL: ${galaxyUrl})`);
}

// Schema definitions
const ConnectSchema = z.object({
  url: z.string().url(),
  apiKey: z.string()
});

const HistoryIdSchema = z.object({
  id: z.string()
});

const DatasetIdSchema = z.object({
  id: z.string()
});

const SearchToolsSchema = z.object({
  query: z.string()
});

const RunToolSchema = z.object({
  toolId: z.string(),
  inputs: z.record(z.any()),
  historyId: z.string()
});

const RunWorkflowSchema = z.object({
  workflowId: z.string(),
  inputs: z.record(z.any())
});

const UploadFileSchema = z.object({
  file: z.object({
    name: z.string(),
    content: z.string()
  }),
  historyId: z.string()
});

// Helper function to ensure connection
function ensureConnected() {
  if (!galaxyState.connected || !galaxyState.url || !galaxyState.apiKey) {
    throw new Error('Not connected to Galaxy. Use connect command first.');
  }
}

// Register all tools
server.tool("connect",
  ConnectSchema,
  async ({ url, apiKey }) => {
    try {
      const galaxyUrl = url.endsWith('/') ? url : `${url}/`;
      
      // Test the connection by fetching user info
      const response = await axios.get(`${galaxyUrl}api/users/current`, {
        headers: {
          'x-api-key': apiKey
        }
      });
      
      galaxyState = {
        url: galaxyUrl,
        apiKey,
        client: axios.create({ // type is now AxiosInstance
          baseURL: galaxyUrl,
          headers: {
            'x-api-key': apiKey
          }
        }),
        connected: true
      };

      return {
        content: [{ 
          type: "text", 
          text: JSON.stringify({
            connected: true,
            user: response.data
          })
        }]
      };
    } catch (error) {
      galaxyState = {
        url: null,
        apiKey: null,
        client: null,
        connected: false
      };
      
      throw new Error(`Failed to connect to Galaxy: ${error.message}`);
    }
  }
);

server.tool("listHistories",
  z.object({}),
  async () => {
    ensureConnected();
    
    try {
      const response = await galaxyState.client.get('/api/histories', {
        params: {
          view: 'summary',
          keys: 'size,contents_active,user_id'
        }
      });

      return {
        content: [{ 
          type: "text", 
          text: JSON.stringify(response.data)
        }]
      };
    } catch (error) {
      throw new Error(`Failed to list histories: ${error.message}`);
    }
  }
);

server.tool("getHistory",
  HistoryIdSchema,
  async ({ id }) => {
    ensureConnected();
    
    try {
      const response = await galaxyState.client.get(`/api/histories/${id}`, {
        params: {
          view: 'detailed'
        }
      });

      return {
        content: [{ 
          type: "text", 
          text: JSON.stringify(response.data)
        }]
      };
    } catch (error) {
      throw new Error(`Failed to get history: ${error.message}`);
    }
  }
);

server.tool("listDatasets",
  HistoryIdSchema,
  async ({ id }) => {
    ensureConnected();
    
    try {
      const response = await galaxyState.client.get(`/api/histories/${id}/contents`);

      return {
        content: [{ 
          type: "text", 
          text: JSON.stringify(response.data)
        }]
      };
    } catch (error) {
      throw new Error(`Failed to list datasets: ${error.message}`);
    }
  }
);

server.tool("getDataset",
  DatasetIdSchema,
  async ({ id }) => {
    ensureConnected();
    
    try {
      const response = await galaxyState.client.get(`/api/datasets/${id}`, {
        params: {
          view: 'detailed'
        }
      });

      return {
        content: [{ 
          type: "text", 
          text: JSON.stringify(response.data)
        }]
      };
    } catch (error) {
      throw new Error(`Failed to get dataset: ${error.message}`);
    }
  }
);

server.tool("searchTools",
  SearchToolsSchema,
  async ({ query }) => {
    ensureConnected();
    
    try {
      const response = await galaxyState.client.get('/api/tools', {
        params: {
          q: query
        }
      });

      return {
        content: [{ 
          type: "text", 
          text: JSON.stringify(response.data)
        }]
      };
    } catch (error) {
      throw new Error(`Failed to search tools: ${error.message}`);
    }
  }
);

server.tool("runTool",
  RunToolSchema,
  async ({ toolId, inputs, historyId }) => {
    ensureConnected();
    
    try {
      const response = await galaxyState.client.post('/api/tools', {
        tool_id: toolId,
        inputs,
        history_id: historyId
      });

      return {
        content: [{ 
          type: "text", 
          text: JSON.stringify(response.data)
        }]
      };
    } catch (error) {
      throw new Error(`Failed to run tool: ${error.message}`);
    }
  }
);

server.tool("runWorkflow",
  RunWorkflowSchema,
  async ({ workflowId, inputs }) => {
    ensureConnected();
    
    try {
      const response = await galaxyState.client.post(`/api/workflows/${workflowId}/invocations`, {
        inputs
      });

      return {
        content: [{ 
          type: "text", 
          text: JSON.stringify(response.data)
        }]
      };
    } catch (error) {
      throw new Error(`Failed to run workflow: ${error.message}`);
    }
  }
);

server.tool("uploadFile",
  UploadFileSchema,
  async ({ file, historyId }) => {
    ensureConnected();
    
    try {
      // Create FormData
      const formData = new FormData();
      formData.append('file', new Blob([file.content]), file.name);
      formData.append('history_id', historyId);
      
      const response = await galaxyState.client.post('/api/tools/fetch', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      return {
        content: [{ 
          type: "text", 
          text: JSON.stringify(response.data)
        }]
      };
    } catch (error) {
      throw new Error(`Failed to upload file: ${error.message}`);
    }
  }
);

server.tool("getUser",
  z.object({}),
  async () => {
    ensureConnected();
    
    try {
      const response = await galaxyState.client.get('/api/users/current');

      return {
        content: [{ 
          type: "text", 
          text: JSON.stringify(response.data)
        }]
      };
    } catch (error) {
      throw new Error(`Failed to get user: ${error.message}`);
    }
  }
);

// Add resources for histories and datasets
server.resource(
  "history",
  new ResourceTemplate("galaxy://history/{id}", { list: "galaxy://histories" }),
  async (uri, { id }) => {
    ensureConnected();
    
    try {
      const response = await galaxyState.client.get(`/api/histories/${id}`, {
        params: {
          view: 'detailed'
        }
      });

      return {
        contents: [{
          uri: uri.href,
          text: JSON.stringify(response.data)
        }]
      };
    } catch (error) {
      throw new Error(`Failed to get history: ${error.message}`);
    }
  }
);

server.resource(
  "histories",
  new ResourceTemplate("galaxy://histories", { list: undefined }),
  async (uri) => {
    ensureConnected();
    
    try {
      const response = await galaxyState.client.get('/api/histories', {
        params: {
          view: 'summary'
        }
      });
      
      const histories = response.data.map(history => ({
        uri: `galaxy://history/${history.id}`,
        text: history.name
      }));

      return {
        contents: histories
      };
    } catch (error) {
      throw new Error(`Failed to list histories: ${error.message}`);
    }
  }
);

server.resource(
  "dataset",
  new ResourceTemplate("galaxy://dataset/{id}", { list: "galaxy://datasets/{historyId}" }),
  async (uri, { id }) => {
    ensureConnected();
    
    try {
      const response = await galaxyState.client.get(`/api/datasets/${id}`, {
        params: {
          view: 'detailed'
        }
      });

      return {
        contents: [{
          uri: uri.href,
          text: JSON.stringify(response.data)
        }]
      };
    } catch (error) {
      throw new Error(`Failed to get dataset: ${error.message}`);
    }
  }
);

server.resource(
  "datasets",
  new ResourceTemplate("galaxy://datasets/{historyId}", { list: undefined }),
  async (uri, { historyId }) => {
    ensureConnected();
    
    try {
      const response = await galaxyState.client.get(`/api/histories/${historyId}/contents`);
      
      const datasets = response.data.map(dataset => ({
        uri: `galaxy://dataset/${dataset.id}`,
        text: dataset.name
      }));

      return {
        contents: datasets
      };
    } catch (error) {
      throw new Error(`Failed to list datasets: ${error.message}`);
    }
  }
);

// Start the server using stdin/stdout
async function runServer() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Galaxy MCP Server running on stdio");
}

runServer().catch((error) => {
  console.error("Fatal error running server:", error);
  process.exit(1);
});
