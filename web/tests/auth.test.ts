// S5 · Đăng nhập Discord, nhận hội thoại khách, feedback, admin bằng phiên: dùng fetch giả, không gọi backend thật.
import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { createServer } from "vite";
import {
  claimGuestConversations,
  discordLoginUrl,
  getCapabilities,
  getMe,
  listMyConversations,
  logout,
  toLocalConversation,
} from "../src/api/auth.ts";
import { getAdminStats, sendFeedback } from "../src/api/client.ts";

const ID = "11111111-1111-4111-8111-111111111111";
const ID2 = "22222222-2222-4222-8222-222222222222";
const ID3 = "33333333-3333-4333-8333-333333333333";
const TOKEN = "t".repeat(40);
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
const callArgs = (mock: { mock: { calls: { arguments: unknown[] }[] } }, i: number) =>
  mock.mock.calls[i].arguments as [string, RequestInit];

test("discord login URL is a same-origin path and next stays relative", () => {
  assert.equal(discordLoginUrl("/chat"), "/api/v1/auth/discord/login?next=%2Fchat");
  for (const bad of ["https://evil.example", "//evil.example", "/\\evil.example", ""])
    assert.equal(discordLoginUrl(bad), "/api/v1/auth/discord/login?next=%2Fchat", bad);
});

test("capabilities: auth is off unless the API says so, and failures never throw", async (t) => {
  const fetchMock = t.mock.method(globalThis, "fetch", async () =>
    json({ auth_available: true, trace_available: true }),
  );
  assert.deepEqual(await getCapabilities(), { authAvailable: true, searchAvailable: false, traceAvailable: true });
  fetchMock.mock.mockImplementation(async () => json({ auth_available: "yes" }));
  assert.equal((await getCapabilities()).authAvailable, false);
  fetchMock.mock.mockImplementation(async () => json({}, 500));
  assert.equal((await getCapabilities()).authAvailable, false);
  fetchMock.mock.mockImplementation(async () => {
    throw new TypeError("Failed to fetch");
  });
  assert.equal((await getCapabilities()).authAvailable, false);
});

test("me: parses the user, treats guest/errors as null, and sends the session cookie same-origin", async (t) => {
  const fetchMock = t.mock.method(globalThis, "fetch", async () =>
    json({ authenticated: true, user: { id: "u1", display_name: "Tarnished", is_admin: true } }),
  );
  assert.deepEqual(await getMe(), { id: "u1", display_name: "Tarnished", is_admin: true });
  const [url, init] = callArgs(fetchMock, 0);
  assert.equal(url, "/api/v1/auth/me");
  assert.equal(init.credentials, "same-origin");
  fetchMock.mock.mockImplementation(async () => json({ authenticated: false, user: null }));
  assert.equal(await getMe(), null);
  fetchMock.mock.mockImplementation(async () => json({}, 503));
  assert.equal(await getMe(), null);
});

test("logout POSTs to /auth/logout and reports failure instead of throwing", async (t) => {
  const fetchMock = t.mock.method(globalThis, "fetch", async () => new Response(null, { status: 204 }));
  assert.equal(await logout(), true);
  const [url, init] = callArgs(fetchMock, 0);
  assert.equal(url, "/api/v1/auth/logout");
  assert.equal(init.method, "POST");
  fetchMock.mock.mockImplementation(async () => new Response(null, { status: 403 }));
  assert.equal(await logout(), false);
});

test("my conversations keeps only well-formed rows; 401 means empty", async (t) => {
  const fetchMock = t.mock.method(globalThis, "fetch", async () =>
    json([
      { id: ID, title: "Radahn", created_at: "2026-11-16T00:00:00Z" },
      { id: "bad", title: "x", created_at: "y" },
    ]),
  );
  assert.deepEqual(await listMyConversations(), [{ id: ID, title: "Radahn", created_at: "2026-11-16T00:00:00Z" }]);
  fetchMock.mock.mockImplementation(async () => json({ error: "no" }, 401));
  assert.deepEqual(await listMyConversations(), []);
});

test("claiming sends only guest conversations with a server id and valid token; 404 is ignored", async (t) => {
  const fetchMock = t.mock.method(globalThis, "fetch", async (_url: string, init: RequestInit) => {
    const body = JSON.parse(String(init.body));
    return new Response(null, { status: body.conversation_id === ID ? 204 : 404 });
  });
  const base = { title: "t", mode: "api-stream" as const, messages: [], updatedAt: "2026-11-16T00:00:00Z" };
  const claimed = await claimGuestConversations([
    { ...base, id: "a", serverId: ID, serverToken: TOKEN },
    { ...base, id: "b", serverId: ID2, serverToken: TOKEN },
    { ...base, id: "c", serverId: null },
    { ...base, id: "d", serverId: ID },
    { ...base, id: "e", serverId: ID, serverToken: "short" },
  ]);
  assert.deepEqual(claimed, [ID]);
  assert.equal(fetchMock.mock.calls.length, 2);
  const [url, init] = callArgs(fetchMock, 0);
  assert.equal(url, "/api/v1/me/conversations/claim");
  assert.deepEqual(JSON.parse(String(init.body)), { conversation_id: ID, conversation_token: TOKEN });
});

test("a conversation opened from the account maps to a local one without a token", () => {
  const local = toLocalConversation(
    {
      id: ID,
      channel: "web",
      created_at: "2026-11-16T00:00:00Z",
      messages: [
        { id: ID2, role: "user", content: "Hỏi", sources: [], created_at: "x" },
        { id: ID3, role: "assistant", content: "Đáp", sources: [], grounded: true, created_at: "x" },
      ],
    },
    "Radahn",
  );
  assert.equal(local.serverId, ID);
  assert.equal(local.serverToken, undefined);
  assert.equal(local.messages[0].serverId, undefined);
  assert.equal(local.messages[1].serverId, ID3);
  assert.equal(local.messages[1].grounded, true);
});

test("feedback sends the conversation token for guests and omits it when logged in", async (t) => {
  const fetchMock = t.mock.method(globalThis, "fetch", async () => new Response(null, { status: 204 }));
  await sendFeedback(ID, -1, "sai", TOKEN);
  const [url, init] = callArgs(fetchMock, 0);
  assert.equal(url, "/api/v1/feedback");
  assert.equal((init.headers as Record<string, string>)["X-Conversation-Token"], TOKEN);
  assert.deepEqual(JSON.parse(String(init.body)), { message_id: ID, rating: -1, reason: "sai" });
  await sendFeedback(ID, 1, "");
  assert.equal((callArgs(fetchMock, 1)[1].headers as Record<string, string>)["X-Conversation-Token"], undefined);
});

test("admin stats works with the session cookie alone (no X-Admin-Token) and with a token", async (t) => {
  const stats = { conversations: [], feedback: [], ingestion_jobs: [], eval_runs: [] };
  const fetchMock = t.mock.method(globalThis, "fetch", async () => json(stats));
  await getAdminStats(null);
  await getAdminStats("secret");
  const headers = (i: number) => callArgs(fetchMock, i)[1].headers as Record<string, string>;
  assert.equal(headers(0)["X-Admin-Token"], undefined);
  assert.equal(headers(1)["X-Admin-Token"], "secret");
});

test("feedback buttons render under a finished real answer only", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: MessageList } = await server.ssrLoadModule("/src/components/chat/MessageList.tsx");
    const answer = { id: "a", role: "assistant", content: "Trả lời", sources: [], serverId: ID };
    const render = (message: object, demo = false) =>
      renderToStaticMarkup(
        createElement(MemoryRouter, null, createElement(MessageList, { messages: [message], busy: false, demo })),
      );
    const done = render(answer);
    assert.match(done, /Câu trả lời có hữu ích\?/);
    assert.match(done, /aria-label="Hữu ích"[^>]*aria-pressed="false"/);
    assert.match(done, /aria-label="Chưa hữu ích"/);
    assert.doesNotMatch(done, /Lý do phản hồi/); // ô lý do chỉ hiện sau khi bấm 👎
    for (const hidden of [
      { ...answer, incomplete: true },
      { ...answer, serverId: undefined },
      { ...answer, content: "  " },
    ])
      assert.doesNotMatch(render(hidden), /Câu trả lời có hữu ích/);
    assert.doesNotMatch(render(answer, true), /Câu trả lời có hữu ích/);
  } finally {
    await server.close();
  }
});

test("chat shell shows no Discord login or user box until the API reports auth", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: App } = await server.ssrLoadModule("/src/App.tsx");
    const html = renderToStaticMarkup(createElement(MemoryRouter, { initialEntries: ["/chat"] }, createElement(App)));
    assert.doesNotMatch(html, /sidebar-account|Đăng nhập Discord|Đăng xuất/);
  } finally {
    await server.close();
  }
});
