// Lịch sử local chỉ hiện cho khách hoặc đúng chủ; clarification hỏng bị bỏ khi khôi phục.
// Phụ trách: TV4 · [S5] sửa review TV2 (#1, #13)
import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { createServer } from "vite";
import { viewerConversations } from "../src/lib/accountData.ts";
import { readConversations } from "../src/lib/storage.ts";
import type { Conversation } from "../src/api/types.ts";

const clarification = {
  id: "33333333-3333-4333-8333-333333333333",
  status: "pending",
  question: "PvE or PvP?",
  expires_at: "2099-01-01T00:00:00Z",
  fields: [{ key: "goal", label: "Goal", input_type: "choice", options: ["PvE", "PvP"] }],
};

function conversation(id: string, title: string, ownerUserId?: string, extra: object = {}): Conversation {
  return {
    id,
    title,
    mode: "api",
    serverId: null,
    updatedAt: "2026-11-20T00:00:00Z",
    messages: [{ id: `${id}-m`, role: "assistant", content: "x", sources: [] }],
    ...(ownerUserId ? { ownerUserId } : {}),
    ...extra,
  } as Conversation;
}

const guest = conversation("g", "Khach");
const alice = conversation("a", "Cua Alice", "alice");
const bob = conversation("b", "Cua Bob", "bob");
const all = [guest, alice, bob];

test("viewerConversations: guest sees guest only, user sees guest + own, loading hides owned data", () => {
  assert.deepEqual(viewerConversations(all, { loading: false, userId: null }), [guest]); // hết phiên
  assert.deepEqual(viewerConversations(all, { loading: false, userId: "alice" }), [guest, alice]);
  assert.deepEqual(viewerConversations(all, { loading: false, userId: "bob" }), [guest, bob]); // đổi tài khoản
  assert.deepEqual(viewerConversations(all, { loading: true, userId: null }), [guest]); // chưa biết auth
});

async function withStorage(value: string, run: () => void | Promise<void>) {
  const original = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: { getItem: () => value, setItem() {} },
  });
  try {
    await run();
  } finally {
    if (original) Object.defineProperty(globalThis, "localStorage", original);
    else Reflect.deleteProperty(globalThis, "localStorage");
  }
}

test("ChatPage sidebar never lists another owner's conversations (expired session, account switch, loading)", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: ChatPage } = await server.ssrLoadModule("/src/pages/ChatPage.tsx");
    const { AuthContext, guestAuth } = await server.ssrLoadModule("/src/hooks/AuthContext.ts");
    const render = (auth: object) =>
      renderToStaticMarkup(
        createElement(
          MemoryRouter,
          { initialEntries: ["/chat"] },
          createElement(AuthContext.Provider, { value: { ...guestAuth, ...auth } }, createElement(ChatPage)),
        ),
      );
    await withStorage(JSON.stringify(all), () => {
      const expired = render({ user: null });
      assert.match(expired, /Khach/);
      assert.doesNotMatch(expired, /Cua Alice|Cua Bob/);
      const loading = render({ loading: true, user: null });
      assert.match(loading, /Khach/);
      assert.doesNotMatch(loading, /Cua Alice|Cua Bob/);
      const asBob = render({ user: { id: "bob", display_name: "Bob" }, authAvailable: true });
      assert.match(asBob, /Cua Bob/);
      assert.doesNotMatch(asBob, /Cua Alice/);
    });
  } finally {
    await server.close();
  }
});

test("storage restore drops invalid clarification but keeps the message", async () => {
  const withClarification = (value: unknown) =>
    conversation("c", "C", undefined, {
      messages: [
        { id: "m1", role: "assistant", content: "keep me", sources: [], clarification: value },
        { id: "m2", role: "assistant", content: "ok", sources: [], clarification },
      ],
    });
  for (const broken of [{ id: "x" }, { ...clarification, question: 5 }, "oops", { ...clarification, fields: [] }]) {
    await withStorage(JSON.stringify([withClarification(broken)]), () => {
      const [restored] = readConversations();
      assert.equal(restored.messages.length, 2);
      assert.equal(restored.messages[0].content, "keep me");
      assert.equal(restored.messages[0].clarification, undefined);
      assert.deepEqual(restored.messages[1].clarification, clarification);
    });
  }
});
