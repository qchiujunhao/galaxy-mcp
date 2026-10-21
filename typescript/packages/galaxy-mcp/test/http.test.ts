import { describe, expect, it } from "vitest";
import {
  checkHttpStartup,
  hostAllowed,
  httpConfig,
  HttpStartupError,
  isLoopbackHost,
  originAllowed,
} from "../src/http";

describe("loopback hosts", () => {
  it.each(["127.0.0.1", "127.8.9.10", "localhost", "LOCALHOST.", "::1", "[::1]", "0:0:0:0:0:0:0:1"])(
    "treats %s as loopback",
    (host) => expect(isLoopbackHost(host)).toBe(true),
  );
  it.each(["0.0.0.0", "::", "10.0.0.1", "example.org", "localhost.example.org", ""])(
    "does not treat %s as loopback",
    (host) => expect(isLoopbackHost(host)).toBe(false),
  );
});

describe("HTTP startup", () => {
  it("serves on loopback without being asked", () => {
    expect(() => checkHttpStartup("127.0.0.1", false)).not.toThrow();
  });
  it("refuses a routable address unless told something else controls access", () => {
    expect(() => checkHttpStartup("0.0.0.0", false)).toThrow(HttpStartupError);
    expect(() => checkHttpStartup("0.0.0.0", false)).toThrow(/--allow-unauthenticated/);
    expect(() => checkHttpStartup("0.0.0.0", true)).not.toThrow();
  });
});

describe("HTTP configuration", () => {
  it("uses the Python server's defaults", () => {
    expect(httpConfig({}, {})).toEqual({
      host: "127.0.0.1",
      port: 8000,
      path: "/",
      allowedHosts: new Set(),
      allowedOrigins: new Set(),
      allowLocalFiles: false,
    });
  });

  it("reads the environment, and lets a flag win over it", () => {
    const env = {
      GALAXY_MCP_HOST: "0.0.0.0",
      GALAXY_MCP_PORT: "9000",
      GALAXY_MCP_HTTP_PATH: "mcp",
      GALAXY_MCP_ALLOW_UNAUTHENTICATED: "true",
      GALAXY_MCP_ALLOWED_HOSTS: "MCP.example.org, other.example.org",
      GALAXY_MCP_ALLOWED_ORIGINS: "https://Client.example.org/",
      GALAXY_MCP_ALLOW_LOCAL_FILES: "1",
    };
    expect(httpConfig({}, env)).toMatchObject({
      host: "0.0.0.0",
      port: 9000,
      path: "/mcp",
      allowedHosts: new Set(["mcp.example.org", "other.example.org"]),
      allowedOrigins: new Set(["https://client.example.org"]),
      allowLocalFiles: true,
    });
    expect(httpConfig({ host: "127.0.0.1", port: "8123", path: "/x" }, env)).toMatchObject({
      host: "127.0.0.1",
      port: 8123,
      path: "/x",
    });
  });

  it("refuses a port that is not one, and an unauthenticated routable address", () => {
    expect(() => httpConfig({ port: "80a" }, {})).toThrow("invalid port: 80a");
    expect(() => httpConfig({ host: "0.0.0.0" }, {})).toThrow(HttpStartupError);
    expect(httpConfig({ host: "0.0.0.0", allowUnauthenticated: true }, {}).host).toBe("0.0.0.0");
  });
});

describe("Host and Origin", () => {
  const guards = { allowedHosts: new Set(["mcp.example.org"]), allowedOrigins: new Set(["https://client.example.org"]) };

  it("answers a loopback Host or one it was told about", () => {
    expect(hostAllowed("127.0.0.1:8000", guards)).toBe(true);
    expect(hostAllowed("[::1]:8000", guards)).toBe(true);
    expect(hostAllowed("MCP.example.org", guards)).toBe(true);
    expect(hostAllowed("attacker.example", guards)).toBe(false);
    expect(hostAllowed("anything", { ...guards, allowedHosts: new Set(["*"]) })).toBe(true);
  });

  it("answers pages from this machine or the allowlist", () => {
    expect(originAllowed("http://localhost:6274", guards)).toBe(true);
    expect(originAllowed("https://client.example.org/", guards)).toBe(true);
    expect(originAllowed("https://evil.example", guards)).toBe(false);
    expect(originAllowed("https://evil.example", { ...guards, allowedOrigins: new Set(["*"]) })).toBe(true);
  });
});
