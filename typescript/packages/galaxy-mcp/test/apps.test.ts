import { describe, expect, it } from "vitest";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { createGalaxyContext } from "@galaxyproject/galaxy-ops";
import { cardPage } from "../src/apps/card-page";
import { HISTORIES_CARD_URI, HISTORY_CARD_URI, historiesCard, historyCard } from "../src/apps/cards";
import { buildServer, toolNames } from "../src/server";
import { runCard } from "./card-host";

const histories = [
  { id: "h1", name: "RNA-seq", count: 4, update_time: "2026-10-21T12:00:00.000000" },
  { id: "h2", name: "ChIP-seq", count: 9, update_time: "2026-10-20T12:00:00.000000" },
];
const contents = [
  { id: "d1", hid: 1, name: "reads.fastq", history_content_type: "dataset", extension: "fastqsanger", state: "ok" },
  { id: "c1", hid: 2, name: "samples", history_content_type: "dataset_collection", collection_type: "list", element_count: 3 },
];
// A Galaxy that only knows its history list and one history's contents.
const ctx = createGalaxyContext({
  baseUrl: "http://galaxy.invalid",
  apiKey: "k",
  fetchImpl: async (request) => {
    const url = new URL(request instanceof Request ? request.url : String(request));
    if (url.pathname === "/api/histories") return Response.json(histories);
    if (url.pathname === "/api/histories/h1/contents") return Response.json({ contents, stats: { total_matches: contents.length } });
    return new Response("not found", { status: 404 });
  },
});

async function connect(apps: boolean): Promise<Client> {
  const [clientSide, serverSide] = InMemoryTransport.createLinkedPair();
  await buildServer(ctx, { apps }).connect(serverSide);
  const client = new Client({ name: "apps-test", version: "0" });
  await client.connect(clientSide);
  return client;
}

describe("MCP Apps cards", () => {
  it("are off by default, so the tools are the operations and nothing else", async () => {
    const client = await connect(false);
    const { tools } = await client.listTools();
    expect(tools.map((t) => t.name).sort()).toEqual(toolNames().sort());
    expect(tools.some((t) => t._meta)).toBe(false);
    expect(client.getServerCapabilities()?.resources).toBeUndefined();
  });

  it("add a show_* tool beside each read, pointing at its card, and change nothing else", async () => {
    const off = (await (await connect(false)).listTools()).tools;
    const { tools } = await (await connect(true)).listTools();
    expect(tools.map((t) => t.name).sort()).toEqual([...toolNames(), "show_histories", "show_history"].sort());
    expect(tools.filter((t) => !t.name.startsWith("show_"))).toEqual(off);
    for (const [show, read, uri] of [
      ["show_histories", "get_histories", HISTORIES_CARD_URI],
      ["show_history", "get_history_contents", HISTORY_CARD_URI],
    ] as const) {
      const shown = tools.find((t) => t.name === show)!;
      const plain = tools.find((t) => t.name === read)!;
      expect(shown._meta).toEqual({ ui: { resourceUri: uri } });
      expect(shown.inputSchema).toEqual(plain.inputSchema);
      expect(shown.annotations).toEqual(plain.annotations);
      expect(shown.description).toContain(`use ${read}, which shows nothing`);
      expect(shown.description).toContain(plain.description!);
    }
  });

  it("serve each card as an MCP App", async () => {
    const client = await connect(true);
    for (const card of [historiesCard, historyCard]) {
      const { contents: served } = await client.readResource({ uri: card.uri });
      expect(served).toEqual([expect.objectContaining({ uri: card.uri, mimeType: "text/html;profile=mcp-app", text: cardPage(card) })]);
    }
  });

  it("answer each show_* call exactly as its read", async () => {
    const client = await connect(true);
    for (const [show, read, args] of [
      ["show_histories", "get_histories", { limit: 1, offset: 0 }],
      ["show_history", "get_history_contents", { history_id: "h1", limit: 5 }],
    ] as const) {
      const shown = await client.callTool({ name: show, arguments: args });
      expect(shown.isError).toBeFalsy();
      expect(shown).toEqual(await client.callTool({ name: read, arguments: args }));
    }
  });

  it("each carry a script that parses", () => {
    for (const card of [historiesCard, historyCard]) {
      const script = cardPage(card).match(/<script>([\s\S]*)<\/script>/)![1]!;
      expect(() => new Function(script)).not.toThrow();
    }
  });
});

describe("the history card", () => {
  it("names its scope from the arguments it was opened with", async () => {
    const card = runCard(cardPage(historyCard));
    await card.initialize();
    await card.open({ history_id: "h1", visible: false, order: "create_time-dsc" }, { history_id: "h1", contents }, { total_items: 2, has_next: false, next_offset: null });
    expect(card.scope()).toBe("Browsing history, without deleted items, sorted by create_time-dsc · Showing 2 of 2");
  });

  it("opens datasets, and names a collection's type without opening it", async () => {
    const card = runCard(cardPage(historyCard));
    await card.initialize();
    await card.open({ history_id: "h1" }, { history_id: "h1", contents }, { total_items: 2, has_next: false, next_offset: null });
    expect(card.scope()).toBe("Browsing history, without deleted or hidden items · Showing 2 of 2");
    expect(card.rows()).toEqual(["1: reads.fastq", "2: samples"]);
    expect(card.root.text).toContain("list, 3 elements");
    const openable = card.root.all((n) => n.tag === "button" && n.className === "row");
    expect(openable).toHaveLength(1);
    await openable[0]!.listeners.click!();
    expect(card.root.text).toContain("fastqsanger");
  });

  it("pages within the same history and filters", async () => {
    const card = runCard(cardPage(historyCard));
    await card.initialize();
    await card.open({ history_id: "h1", deleted: true, visible: false, order: "name-asc", limit: 2 }, { history_id: "h1", contents }, { total_items: 9, has_next: true, next_offset: 2 });
    void card.click("Show more");
    expect(card.sent.at(-1)!.params).toEqual({
      name: "get_history_contents",
      arguments: { history_id: "h1", deleted: true, visible: false, order: "name-asc", limit: 20, offset: 2 },
    });
  });
});

describe("the histories card", () => {
  it("shows each history's size and keeps a name filter across pages", async () => {
    const card = runCard(cardPage(historiesCard));
    await card.initialize();
    await card.open({ name: "RNA-seq", limit: 1 }, [histories[0]], { total_items: 3, has_next: true, next_offset: 1 });
    expect(card.scope()).toBe("Named “RNA-seq” · Showing 1 of 3");
    expect(card.root.text).toContain("4 items");
    const unnamed = runCard(cardPage(historiesCard));
    await unnamed.initialize();
    await unnamed.open({ name: "" }, [], { total_items: 0, has_next: false, next_offset: null });
    expect(unnamed.scope()).toBe("Named \u201c\u201d · Showing 0 of 0");
    void card.click("Show more");
    expect(card.sent.at(-1)!.params.arguments).toEqual({ name: "RNA-seq", limit: 20, offset: 1 });
  });
});
