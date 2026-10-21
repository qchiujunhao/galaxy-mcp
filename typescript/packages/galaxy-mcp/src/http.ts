/**
 * The Streamable HTTP transport's configuration and guards, after the Python server's.
 *
 * Over stdio the caller is whoever launched the process. Over HTTP it is anything that can
 * reach the socket -- other hosts on the network, and any web page open in a browser on the
 * same machine. This file closes the part of that gap the server can close on its own, the
 * same way and under the same settings as `python/src/galaxy_mcp/http_security.py`: which
 * Host and Origin headers it answers, and whether it will start on a routable address at all.
 * There is no OAuth on this side yet, so the unauthenticated rules are the only rules.
 */
import { BlockList, isIP } from "node:net";
import { ALLOW_LOCAL_FILES_ENV } from "./server.js";

export const DEFAULT_HTTP_HOST = "127.0.0.1";
export const DEFAULT_HTTP_PORT = 8000;
export const DEFAULT_HTTP_PATH = "/";

export const ALLOW_UNAUTHENTICATED_ENV = "GALAXY_MCP_ALLOW_UNAUTHENTICATED";
export const ALLOWED_HOSTS_ENV = "GALAXY_MCP_ALLOWED_HOSTS";
export const ALLOWED_ORIGINS_ENV = "GALAXY_MCP_ALLOWED_ORIGINS";

/** The requested HTTP configuration is not safe to serve. */
export class HttpStartupError extends Error {}

const loopback = new BlockList();
loopback.addSubnet("127.0.0.0", 8, "ipv4");
loopback.addAddress("::1", "ipv6");

export function isLoopbackHost(host: string): boolean {
  const candidate = host.trim().replace(/^\[|\]$/g, "").replace(/\.$/, "").toLowerCase();
  if (candidate === "localhost") return true;
  const family = isIP(candidate);
  return family !== 0 && loopback.check(candidate, family === 4 ? "ipv4" : "ipv6");
}

/** A comma-separated setting as a lower-cased set, the way the Python server reads it. */
function envList(value: string | undefined): Set<string> {
  return new Set((value ?? "").split(",").map((item) => item.trim().toLowerCase()).filter(Boolean));
}

function envFlag(value: string | undefined): boolean {
  return ["1", "true", "yes", "on"].includes((value ?? "").trim().toLowerCase());
}

export function checkHttpStartup(host: string, allowUnauthenticated: boolean): void {
  if (allowUnauthenticated || isLoopbackHost(host)) return;
  throw new HttpStartupError(
    `Refusing to serve HTTP on '${host}' without authentication: anyone who can reach that ` +
      "address could use every tool, with the Galaxy API key configured in this environment. " +
      `Bind to 127.0.0.1, or pass --allow-unauthenticated (${ALLOW_UNAUTHENTICATED_ENV}=1) if ` +
      "something else controls access to the listener. Clients that reach it by a non-loopback " +
      `name also need ${ALLOWED_HOSTS_ENV}.`,
  );
}

/** Command-line flags; each one wins over its environment variable. */
export interface HttpFlags {
  host?: string;
  port?: string;
  path?: string;
  allowUnauthenticated?: boolean;
}

export interface HttpConfig extends HttpGuards {
  host: string;
  port: number;
  path: string;
  allowLocalFiles: boolean;
}

/**
 * Resolves flags and environment into a configuration, with the Python server's names and
 * defaults, or throws HttpStartupError for one that should not be served.
 */
export function httpConfig(flags: HttpFlags, env: NodeJS.ProcessEnv): HttpConfig {
  const host = flags.host ?? env.GALAXY_MCP_HOST ?? DEFAULT_HTTP_HOST;
  const rawPort = flags.port ?? env.GALAXY_MCP_PORT;
  const port = rawPort === undefined ? DEFAULT_HTTP_PORT : Number(rawPort);
  if (!Number.isInteger(port) || port < 0 || port > 65535) throw new HttpStartupError(`invalid port: ${rawPort}`);
  const path = flags.path ?? env.GALAXY_MCP_HTTP_PATH ?? DEFAULT_HTTP_PATH;
  checkHttpStartup(host, flags.allowUnauthenticated === true || envFlag(env[ALLOW_UNAUTHENTICATED_ENV]));
  return {
    host,
    port,
    path: path.startsWith("/") ? path : `/${path}`,
    allowedHosts: envList(env[ALLOWED_HOSTS_ENV]),
    allowedOrigins: new Set([...envList(env[ALLOWED_ORIGINS_ENV])].map((origin) => origin.replace(/\/+$/, ""))),
    allowLocalFiles: envFlag(env[ALLOW_LOCAL_FILES_ENV]),
  };
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^\[|\]$/g, "").toLowerCase();
  } catch {
    return "";
  }
}

export interface HttpGuards {
  allowedHosts: Set<string>;
  allowedOrigins: Set<string>;
}

/** A loopback Host, or one the operator named; defeats DNS rebinding. */
export function hostAllowed(hostHeader: string, { allowedHosts }: HttpGuards): boolean {
  if (allowedHosts.has("*")) return true;
  const name = hostname(`http://${hostHeader}`);
  return isLoopbackHost(name) || allowedHosts.has(name);
}

/** Pages served from this machine (MCP Inspector and friends) are the user's own. */
export function originAllowed(origin: string, { allowedOrigins }: HttpGuards): boolean {
  const normalized = origin.toLowerCase().replace(/\/+$/, "");
  if (allowedOrigins.has("*") || allowedOrigins.has(normalized)) return true;
  return isLoopbackHost(hostname(normalized));
}
