import { describe, it, expect } from "vitest";
import {
  GalaxyAuthError,
  GalaxyNotFoundError,
  GalaxyConnectionError,
  GalaxyVersionError,
  ToolRequestRejectedError,
  JobFailedError,
  classifyHttp,
} from "../src/errors";

describe("error classification", () => {
  it("maps 401/403 -> auth, 404 -> not found", () => {
    expect(classifyHttp(401, undefined)).toBeInstanceOf(GalaxyAuthError);
    expect(classifyHttp(403, undefined)).toBeInstanceOf(GalaxyAuthError);
    expect(classifyHttp(404, undefined)).toBeInstanceOf(GalaxyNotFoundError);
  });
  it("maps other non-2xx to a generic connection error carrying status", () => {
    const e = classifyHttp(500, { err_msg: "boom" });
    expect(e).toBeInstanceOf(GalaxyConnectionError);
    expect((e as GalaxyConnectionError).status).toBe(500);
  });
  it("keeps Galaxy's err_msg and err_code on a 403", () => {
    // Galaxy's fetch allowlist refuses a private address with a 403 -- not a key problem.
    const e = classifyHttp(403, {
      err_msg: "Access to this address in not permitted by server configuration",
      err_code: 403004,
    });
    expect(e).toBeInstanceOf(GalaxyAuthError);
    expect(e.message).toBe("Access to this address in not permitted by server configuration");
    expect(e.errCode).toBe(403004);
  });
  it("falls back to an auth sentence for a 401 with no body", () => {
    const e = classifyHttp(401, undefined);
    expect(e).toBeInstanceOf(GalaxyAuthError);
    expect(e.message).toBe("Unauthorized (401)");
    expect(e.errCode).toBeUndefined();
  });
  it("keeps Galaxy's err_msg on a 404", () => {
    const e = classifyHttp(404, { err_msg: "History not found", err_code: 404001 });
    expect(e).toBeInstanceOf(GalaxyNotFoundError);
    expect(e.message).toBe("History not found");
    expect(e.errCode).toBe(404001);
    expect(classifyHttp(404, {}).message).toBe("Not found (404)");
  });
  it("ToolRequestRejectedError carries toolId + err_msg", () => {
    const e = new ToolRequestRejectedError("fastqc/0.74", "could not expand");
    expect(e.toolId).toBe("fastqc/0.74");
    expect(e.message).toContain("could not expand");
  });
  it("JobFailedError carries job id + terminal state + stderr", () => {
    const e = new JobFailedError("job1", "error", "traceback");
    expect(e.jobId).toBe("job1");
    expect(e.state).toBe("error");
    expect(e.stderr).toBe("traceback");
  });
});

describe("GalaxyError.kind", () => {
  it("each subclass carries a stable machine-readable kind", () => {
    expect(new GalaxyAuthError("x").kind).toBe("auth");
    expect(new GalaxyNotFoundError("x").kind).toBe("not_found");
    expect(new GalaxyConnectionError("x", 500).kind).toBe("connection");
    expect(new GalaxyVersionError("x").kind).toBe("version");
    expect(new ToolRequestRejectedError("t", "m").kind).toBe("tool_request_rejected");
    expect(new JobFailedError("j", "error").kind).toBe("job_failed");
  });
  it("does not classify any HTTP status as a version problem", () => {
    // The version kind is only ever raised before a request; no status maps to it.
    for (const status of [400, 401, 403, 404, 409, 422, 500, 502, 503]) {
      expect(classifyHttp(status, null).kind).not.toBe("version");
    }
  });
  it("classifyHttp returns subclasses whose kind matches the status", () => {
    expect(classifyHttp(401, null).kind).toBe("auth");
    expect(classifyHttp(404, null).kind).toBe("not_found");
    expect(classifyHttp(500, { err_msg: "boom" }).kind).toBe("connection");
  });
});
