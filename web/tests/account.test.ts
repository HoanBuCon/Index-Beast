// S5 · Xóa tài khoản (xác nhận trước khi gọi API) và mục quyền riêng tư ở trang About; fetch giả, không gọi backend.
import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { createServer } from "vite";
import { deleteAccount } from "../src/api/auth.ts";

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
