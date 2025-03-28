// claude-galaxy-example.ts
// Example of using Claude with Galaxy MCP

import ClaudeGalaxyAdapter from './claude-galaxy-adapter.js';

// Example of a Claude function to analyze Galaxy data
async function claudeAnalyzeGalaxyData(adapter: ClaudeGalaxyAdapter, message: string): Promise<string> {
  // Parse the user message and execute appropriate Galaxy commands
  const lowerMessage = message.toLowerCase();
  
  try {
    // Connect to Galaxy
    if (lowerMessage.includes('connect') || lowerMessage.includes('login')) {
      // Extract URL and API key from message
      const urlMatch = message.match(/url[:\s]+([^\s]+)/i);
      const apiKeyMatch = message.match(/api.?key[:\s]+([^\s]+)/i);
      
      if (!urlMatch || !apiKeyMatch) {
        return "Please provide both URL and API key in the format: Connect to Galaxy URL: https://usegalaxy.org API Key: your-api-key";
      }
      
      const url = urlMatch[1];
      const apiKey = apiKeyMatch[1];
      
      return await adapter.connect(url, apiKey);
    }
    
    // Check who I am
    if (lowerMessage.includes('who am i') || lowerMessage.includes('my user info')) {
      return await adapter.whoAmI();
    }
    
    // List histories
    if (lowerMessage.includes('list histor')) {
      return await adapter.listHistories();
    }
    
    // Use a specific history
    const historyMatch = message.match(/use history[:\s]+([a-f0-9]+)/i);
    if (historyMatch) {
      const historyId = historyMatch[1];
      return await adapter.useHistory(historyId);
    }
    
    // List datasets
    if (lowerMessage.includes('list dataset')) {
      return await adapter.listDatasets();
    }
    
    // Get dataset details
    const datasetMatch = message.match(/dataset[:\s]+([a-f0-9]+)/i);
    if (datasetMatch) {
      const datasetId = datasetMatch[1];
      return await adapter.getDataset(datasetId);
    }
    
    // Search tools
    const toolSearchMatch = message.match(/search tools?[:\s]+(.+)/i);
    if (toolSearchMatch) {
      const query = toolSearchMatch[1];
      return await adapter.searchTools(query);
    }
    
    // Run a tool
    const runToolMatch = message.match(/run tool[:\s]+([^\s]+)[:\s]+(.+)/i);
    if (runToolMatch) {
      const toolId = runToolMatch[1];
      const inputsJson = runToolMatch[2];
      return await adapter.runTool(toolId, inputsJson);
    }
    
    // Run a workflow
    const runWorkflowMatch = message.match(/run workflow[:\s]+([^\s]+)[:\s]+(.+)/i);
    if (runWorkflowMatch) {
      const workflowId = runWorkflowMatch[1];
      const inputsJson = runWorkflowMatch[2];
      return await adapter.runWorkflow(workflowId, inputsJson);
    }
    
    // Upload a file
    const uploadMatch = message.match(/upload file[:\s]+([^\s]+)[:\s]+(.+)/i);
    if (uploadMatch) {
      const filename = uploadMatch[1];
      const content = uploadMatch[2];
      return await adapter.uploadFile(filename, content);
    }
    
    // If no command matched, provide help
    return `
Galaxy MCP Commands:
- Connect to Galaxy URL: <url> API Key: <api_key>
- Who am I - Display current user info
- List histories - Display all available histories
- Use history: <history_id> - Set the current working history
- List datasets - Display datasets in the current history
- Dataset: <dataset_id> - Display details about a specific dataset
- Search tools: <query> - Search for tools
- Run tool: <tool_id>: <inputs_json> - Run a tool with given inputs
- Run workflow: <workflow_id>: <inputs_json> - Run a workflow with given inputs
- Upload file: <filename>: <content> - Upload a file to the current history
    `;
    
  } catch (error) {
    return `Error: ${error instanceof Error ? error.message : String(error)}`;
  }
}

// Example usage
async function main() {
  const adapter = new ClaudeGalaxyAdapter('http://localhost:3000');
  
  // Example commands
  const commands = [
    "Connect to Galaxy URL: https://usegalaxy.org API Key: your-api-key-here",
    "Who am I",
    "List histories",
    "Use history: f2db41e1fa331b3e",
    "List datasets",
    "Dataset: f2db41e1fa331b3e",
    "Search tools: FASTQ",
    "Run tool: toolshed.g2.bx.psu.edu/repos/devteam/fastqc/fastqc/0.73+galaxy0: {\"input_file\": \"f2db41e1fa331b3e\"}",
    "Upload file: test.txt: This is a test file content"
  ];
  
  // Process each command
  for (const command of commands) {
    console.log(`\n> ${command}`);
    const response = await claudeAnalyzeGalaxyData(adapter, command);
    console.log(response);
  }
}

// Run the example if this script is executed directly
if (require.main === module) {
  main().catch(console.error);
}

export { claudeAnalyzeGalaxyData, ClaudeGalaxyAdapter };
