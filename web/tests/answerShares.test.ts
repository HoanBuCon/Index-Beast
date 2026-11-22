import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { readSharedAnswer } from "../src/api/answerShares.ts";

const token = "s".repeat(43);
const snapshot = {
  question: "Câu hỏi",
  answer: "Đầy đủ [1].",
  sources: [{ index: 1, title: "Nguồn", url: "https://example.test/source" }],
  grounded: true,
  expires_at: "2099-01-01T00:00:00Z",
};

test("share reader keeps capability out of URL and validates expiry/metadata without fetching for invalid links", async (t) => {
  let calls = 0;
  t.mock.method(globalThis, "fetch", async (url: string, init: RequestInit) => {
    calls++;
    assert.equal(url, "/api/v1/answer-shares");
    assert.equal(new Headers(init.headers).get("X-Answer-Share-Token"), token);
    assert.equal(new Headers(init.headers).get("X-Service-Token"), null);
    assert.equal(init.cache, "no-store");
    return Response.json(snapshot);
  });
  assert.deepEqual(await readSharedAnswer(token), snapshot);
  await assert.rejects(readSharedAnswer("bad"));
  assert.equal(calls, 1);
});

test("expired/unavailable/malformed shares fail without a demo fallback", async (t) => {
  for (const response of [
    new Response(null, { status: 404 }),
    new Response(null, { status: 503 }),
    Response.json({ ...snapshot, sources: [null] }),
    Response.json({ ...snapshot, expires_at: "bad" }),
  ]) {
    t.mock.method(globalThis, "fetch", async () => response);
    await assert.rejects(readSharedAnswer(token));
  }
});

test("source block opens excerpts without duplicate links; only the popover links safe source URLs", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: SourceList } = await server.ssrLoadModule("/src/components/chat/SourceList.tsx");
    const { default: CitationPopover } = await server.ssrLoadModule("/src/components/chat/CitationPopover.tsx");
    const html = renderToStaticMarkup(
      createElement(SourceList, {
        sources: [
          ...snapshot.sources,
          { index: 2, title: "Unsafe", url: "javascript:alert(1)" },
          { index: 3, title: "Credentials", url: "https://user:pass@example.test" },
        ],
        onSelect() {},
      }),
    );
    assert.match(html, /\[1\]/);
    assert.doesNotMatch(html, /<a\b/);
    assert.match(html, /Xem trích đoạn/);
    assert.doesNotMatch(html, /href="javascript:|href="https:\/\/user:pass/);
    assert.equal(renderToStaticMarkup(createElement(SourceList, { sources: [], onSelect() {} })), "");
    const popover = (url: string) =>
      renderToStaticMarkup(createElement(CitationPopover, { source: { ...snapshot.sources[0], url }, onClose() {} }));
    assert.match(popover(snapshot.sources[0].url), /href="https:\/\/example.test\/source"/);
    assert.doesNotMatch(popover("javascript:alert(1)"), /<a\b/);
    assert.doesNotMatch(popover("https://user:pass@example.test"), /<a\b/);
  } finally {
    await server.close();
  }
});
