import { describe, it, expect } from "vitest";
import { getToolCitationsOp, getToolCitations } from "../../src/operations/get-tool-citations";
import { runWithEnvelope } from "../../src/operations/registry";
import { mockClient } from "../util/mock-client";
import { DEFAULT_POLL } from "../../src/context";
import type { GalaxyContext } from "../../src/context";

const ctxWith = (client: any): GalaxyContext => ({ client, poll: DEFAULT_POLL });

describe("get_tool_citations", () => {
  it("reads name/version from the show payload and citations from their own endpoint", async () => {
    const bibtex = { format: "bibtex", content: "@article{fastqc,\n  title = {FastQC}\n}" };
    const seen: string[] = [];
    const client = mockClient({
      GET: (path, init) => {
        seen.push(path);
        expect(init.params.path.tool_id).toBe("fastqc");
        if (path === "/api/tools/{tool_id}") {
          expect(init.params.query.io_details).toBe(false);
          expect(init.params.query.link_details).toBe(false);
          // The show payload never carries citations, so a stray key here must be ignored.
          return {
            data: { id: "fastqc", name: "FastQC", version: "0.74", citations: false },
            response: { status: 200 },
          };
        }
        expect(path).toBe("/api/tools/{tool_id}/citations");
        return { data: [bibtex], response: { status: 200 } };
      },
    });
    const out = await getToolCitations({ toolId: "fastqc" }, ctxWith(client));
    expect(seen).toEqual(["/api/tools/{tool_id}", "/api/tools/{tool_id}/citations"]);
    expect(out.tool_name).toBe("FastQC");
    expect(out.tool_version).toBe("0.74");
    expect(out.citations).toEqual([bibtex]);
  });

  it("answers [] when the citations endpoint has none", async () => {
    const client = mockClient({
      GET: (path) =>
        path === "/api/tools/{tool_id}"
          ? { data: { id: "cat1", name: "Concatenate" }, response: { status: 200 } }
          : { data: [], response: { status: 200 } },
    });
    const out = await getToolCitations({ toolId: "cat1" }, ctxWith(client));
    expect(out.citations).toEqual([]);
  });

  it("fails with Galaxy's own words when the citations endpoint answers an error entry", async () => {
    // A race: the show resolved the id, then a toolbox reload or another worker did not.
    const said = "Tool 'cat1' not found. Citations for this tool may be missing.";
    const client = mockClient({
      GET: (path) =>
        path === "/api/tools/{tool_id}"
          ? { data: { id: "cat1", name: "Concatenate", version: "1.0.0" }, response: { status: 200 } }
          : { data: [{ format: "error", error: said, tool_id: "cat1" }], response: { status: 200 } },
    });
    const out = await runWithEnvelope(
      getToolCitationsOp as never,
      { toolId: "cat1" } as never,
      ctxWith(client),
    );
    expect(out.success).toBe(false);
    expect(out.errorKind).toBe("not_found");
    // Galaxy's own full stop goes, so the context clause doesn't double it.
    expect(out.message).toBe(
      "Get tool citations failed: Tool 'cat1' not found. Citations for this tool may be missing. Context: tool_id=cat1",
    );
  });

  it("fails, rather than throwing a TypeError, when the citations reply is not a list", async () => {
    const client = mockClient({
      GET: (path) =>
        path === "/api/tools/{tool_id}"
          ? { data: { id: "cat1", name: "Concatenate", version: "1.0.0" }, response: { status: 200 } }
          : { data: { id: "cat1", name: "Concatenate" }, response: { status: 200 } },
    });
    const out = await runWithEnvelope(
      getToolCitationsOp as never,
      { toolId: "cat1" } as never,
      ctxWith(client),
    );
    expect(out.success).toBe(false);
    expect(out.errorKind).toBe("connection");
    expect(out.message).toBe(
      "Get tool citations failed: the citations reply was not a list. Context: tool_id=cat1",
    );
  });

  it("project message counts the citations and names the tool that was asked for", () => {
    // Not the name Galaxy answered with, which is in data: the other server's
    // sentence quotes the id, so a caller reading it knows what to ask again with.
    const result = { tool_name: "FastQC", tool_version: "0.74", citations: [{}] };
    const msg = getToolCitationsOp.project!(result as any, { toolId: "fastqc" });
    expect(msg.message).toBe("Retrieved 1 citations for tool 'fastqc'");
  });

  it("writes the plural for one citation, as the other server does", () => {
    const result = { tool_name: "FastQC", citations: [{}] };
    expect(getToolCitationsOp.project!(result as any, { toolId: "cat1" }).message).toBe(
      "Retrieved 1 citations for tool 'cat1'",
    );
  });
});
