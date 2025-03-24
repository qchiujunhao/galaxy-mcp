// integration.test.ts
// Basic integration tests for Galaxy MCP

import { describe, test, expect, beforeAll, afterAll } from '@jest/globals';
import GalaxyMCPServer from './galaxy-mcp-server';
import GalaxyMCPClient from './galaxy-mcp-client';
import { createServer } from 'http';

describe('Galaxy MCP Integration Tests', () => {
  let server: GalaxyMCPServer;
  let client: GalaxyMCPClient;
  const PORT = 3001;
  
  beforeAll(() => {
    // Start a test server
    server = new GalaxyMCPServer(PORT);
    client = new GalaxyMCPClient(`http://localhost:${PORT}`);
  });
  
  afterAll(() => {
    // Clean up resources
    if (server) {
      // Ideally, the server should have a close method
      // This is just a placeholder
    }
  });
  
  test('Client can send a command to the server', async () => {
    // This test doesn't actually connect to a Galaxy server
    // It just tests that the MCP protocol itself works
    const response = await client.sendCommand('test', { test: true });
    
    // The server should return an error for unknown commands
    expect(response.status).toBe('error');
    expect(response.error).toContain('Unknown command');
  });
  
  test('Client properly formats connection request', async () => {
    // This doesn't test actual Galaxy connection, just the request format
    const mockUrl = 'https://test-galaxy.org';
    const mockApiKey = 'test-api-key';
    
    // Mock the sendCommand method
    const originalSendCommand = client.sendCommand;
    let capturedCommand: string;
    let capturedArgs: any;
    
    client.sendCommand = async (command, args) => {
      capturedCommand = command;
      capturedArgs = args;
      return { status: 'error', error: 'Mock connection' };
    };
    
    await client.connect(mockUrl, mockApiKey);
    
    // Restore original method
    client.sendCommand = originalSendCommand;
    
    // Check that the command was properly formatted
    expect(capturedCommand).toBe('connect');
    expect(capturedArgs).toEqual({ url: mockUrl, apiKey: mockApiKey });
  });
});
