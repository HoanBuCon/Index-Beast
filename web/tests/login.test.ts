// TV4: bản UI không tạo phiên giả hoặc trỏ tới endpoint OAuth chưa được nối.
import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { createServer } from "vite";

test("login preview offers clickable providers without pretending to authenticate and preserves guest navigation", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: LoginPage } = await server.ssrLoadModule("/src/pages/LoginPage.tsx");
    const { default: App } = await server.ssrLoadModule("/src/App.tsx");
    const html = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(LoginPage)));
    assert.equal((html.match(/<button\b/g) ?? []).length, 2);
    assert.doesNotMatch(html, /<button\b[^>]*disabled/);
    assert.match(html, /Đăng nhập bằng Google/);
    assert.match(html, /Đăng nhập bằng Discord/);
    assert.match(html, /Đăng nhập hiện chưa khả dụng/);
    assert.match(html, /href="\/chat"[^>]*>[\s\S]*?<span>Dùng thử/);
    assert.doesNotMatch(html, /login-footer|login-guest-note|class="login-availability"/);
    assert.doesNotMatch(html, /<form|<input|login-divider|Tiếp tục bằng email|\/auth\/|access_token|service_token/);
    for (const path of ["/", "/login"]) {
      const entry = renderToStaticMarkup(createElement(MemoryRouter, { initialEntries: [path] }, createElement(App)));
      assert.match(entry, /aria-label="Đăng nhập INDEX BEAST"/);
      assert.doesNotMatch(entry, /conversation-sidebar|class="composer"/);
    }
    const chat = renderToStaticMarkup(createElement(MemoryRouter, { initialEntries: ["/chat"] }, createElement(App)));
    assert.match(chat, /conversation-sidebar/);
    assert.match(chat, /class="composer"/);
    assert.doesNotMatch(chat, /aria-label="ĐĂNG NHẬP"/);
  } finally {
    await server.close();
  }
});
