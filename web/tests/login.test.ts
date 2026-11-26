// TV4: provider chỉ bật theo capabilities; điều hướng dùng thử độc lập với OAuth.
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
    // SSR chưa chạy effect, cả hai provider đều chưa khả dụng.
    assert.equal((html.match(/<button\b/g) ?? []).length, 2);
    assert.match(html, /<button\b[^>]*disabled/);
    assert.match(html, /Đăng nhập bằng Google/);
    assert.match(html, /Đăng nhập bằng Google[\s\S]*?\(sắp có\)/);
    assert.match(html, /Đăng nhập bằng Discord/);
    assert.match(html, /Đăng nhập hiện chưa khả dụng/);
    assert.match(html, /href="\/chat"[^>]*>[\s\S]*?<span>Dùng thử/);
    assert.doesNotMatch(html, /login-footer|login-guest-note|class="login-availability"/);
    assert.doesNotMatch(html, /<form|<input|login-divider|Tiếp tục bằng email|access_token|service_token/);
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

test("login enables the Google row only when capabilities announce it", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: LoginPage } = await server.ssrLoadModule("/src/pages/LoginPage.tsx");
    const { AuthContext, guestAuth } = await server.ssrLoadModule("/src/hooks/AuthContext.ts");
    const render = (auth: object) =>
      renderToStaticMarkup(
        createElement(
          AuthContext.Provider,
          { value: { ...guestAuth, ...auth } },
          createElement(MemoryRouter, null, createElement(LoginPage)),
        ),
      );
    const buttons = (html: string) => html.match(/<button[^>]*>[\s\S]*?<\/button>/g) ?? [];
    const google = (html: string) => buttons(html).find((b) => b.includes("Google")) ?? "";
    const on = render({ googleAuthAvailable: true });
    assert.doesNotMatch(google(on), /disabled/);
    assert.doesNotMatch(google(on), /sắp có/);
    assert.match(buttons(on).find((b) => b.includes("Discord")) ?? "", /disabled/);
    assert.match(on, /Đăng nhập để giữ lịch sử/);
    const off = render({ googleAuthAvailable: false, authAvailable: true });
    assert.match(google(off), /disabled/);
    assert.match(google(off), /sắp có/);
    assert.doesNotMatch(buttons(off).find((b) => b.includes("Discord")) ?? "", /disabled/);
  } finally {
    await server.close();
  }
});
