// S5 · Xóa tài khoản (xác nhận trước khi gọi API) và mục quyền riêng tư ở trang About; fetch giả, không gọi backend.
import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { createServer } from "vite";
import { deleteAccount, deleteMyConversation } from "../src/api/auth.ts";

const callArgs = (mock: { mock: { calls: { arguments: unknown[] }[] } }, i: number) =>
  mock.mock.calls[i].arguments as [string, RequestInit];

test("delete account calls DELETE /me with the session cookie and is true only on 204", async (t) => {
  const fetchMock = t.mock.method(globalThis, "fetch", async () => new Response(null, { status: 204 }));
  assert.equal(await deleteAccount(), true);
  const [url, init] = callArgs(fetchMock, 0);
  assert.equal(url, "/api/v1/me");
  assert.equal(init.method, "DELETE");
  assert.equal(init.credentials, "same-origin");
  for (const status of [401, 403, 500]) {
    fetchMock.mock.mockImplementation(async () => new Response(null, { status }));
    assert.equal(await deleteAccount(), false, String(status));
  }
  fetchMock.mock.mockImplementation(async () => {
    throw new TypeError("Failed to fetch");
  });
  assert.equal(await deleteAccount(), false);
});

test("account menu warns about permanent deletion before anything is sent, and opens only on request", async (t) => {
  const fetchMock = t.mock.method(globalThis, "fetch", async () => new Response(null, { status: 204 }));
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: AccountMenu } = await server.ssrLoadModule("/src/components/layout/AccountMenu.tsx");
    const render = (initialConfirming: boolean) =>
      renderToStaticMarkup(
        createElement(
          MemoryRouter,
          null,
          createElement(AccountMenu, { name: "Tarnished", onLogout() {}, onDeleted() {}, initialConfirming }),
        ),
      );
    const closed = render(false);
    assert.match(closed, /Tarnished/);
    assert.match(closed, /Đăng xuất/);
    assert.match(closed, /Xóa tài khoản/);
    assert.doesNotMatch(closed, /alertdialog/);
    const open = render(true);
    assert.match(open, /role="alertdialog"[^>]*aria-labelledby="account-confirm-title"/);
    assert.match(open, /xóa vĩnh viễn/);
    assert.match(open, />Hủy</);
    assert.match(open, />Xóa vĩnh viễn</);
    assert.equal(fetchMock.mock.calls.length, 0); // chưa xác nhận thì chưa gọi API
  } finally {
    await server.close();
  }
});

test("about page summarises privacy: hashed Discord IDs, 90 days, deletion paths", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: AboutPage } = await server.ssrLoadModule("/src/pages/AboutPage.tsx");
    const html = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(AboutPage)));
    assert.match(html, /Quyền riêng tư/);
    assert.match(html, /mã Discord đã băm/);
    assert.match(html, /90 ngày/);
    assert.match(html, /Xóa tài khoản/);
    assert.match(html, /<code>\/clear<\/code>/);
  } finally {
    await server.close();
  }
});

const ID = "3f2b8c1e-9a4d-4c7e-8b1a-2d5e6f7a8b9c";

test("delete one account conversation calls DELETE /me/conversations/{id}; 404 counts as already gone", async (t) => {
  const fetchMock = t.mock.method(globalThis, "fetch", async () => new Response(null, { status: 204 }));
  assert.equal(await deleteMyConversation(ID), true);
  const [url, init] = callArgs(fetchMock, 0);
  assert.equal(url, `/api/v1/me/conversations/${ID}`);
  assert.equal(init.method, "DELETE");
  assert.equal(init.credentials, "same-origin");
  fetchMock.mock.mockImplementation(async () => new Response(null, { status: 404 }));
  assert.equal(await deleteMyConversation(ID), true);
  for (const status of [401, 403, 500, 503]) {
    fetchMock.mock.mockImplementation(async () => new Response(null, { status }));
    assert.equal(await deleteMyConversation(ID), false, String(status));
  }
  fetchMock.mock.mockImplementation(async () => {
    throw new TypeError("Failed to fetch");
  });
  assert.equal(await deleteMyConversation(ID), false);
  const calls = fetchMock.mock.callCount();
  assert.equal(await deleteMyConversation("../me"), false); // không phải UUID: không gửi gì
  assert.equal(fetchMock.mock.callCount(), calls);
});

test("account-only conversations in the sidebar can be deleted", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: ChatPage } = await server.ssrLoadModule("/src/pages/ChatPage.tsx");
    const { AuthContext, guestAuth } = await server.ssrLoadModule("/src/hooks/AuthContext.ts");
    const html = renderToStaticMarkup(
      createElement(
        MemoryRouter,
        { initialEntries: ["/chat"] },
        createElement(
          AuthContext.Provider,
          {
            value: {
              ...guestAuth,
              authAvailable: true,
              user: { id: "u1", display_name: "Tarnished", is_admin: false },
              myConversations: [{ id: ID, title: "Elden Ring là gì?", created_at: "2026-11-22T12:00:00Z" }],
            },
          },
          createElement(ChatPage),
        ),
      ),
    );
    assert.match(html, /Của tài khoản/);
    assert.match(html, /aria-label="Xóa Elden Ring là gì\?"/);
  } finally {
    await server.close();
  }
});
