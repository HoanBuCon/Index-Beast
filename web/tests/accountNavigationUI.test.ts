import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { createServer } from "vite";

test("account actions follow guest/member/admin state and are grouped in a closed menu", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: AccountMenu } = await server.ssrLoadModule("/src/components/layout/AccountMenu.tsx");
    const render = (props: object) =>
      renderToStaticMarkup(
        createElement(
          MemoryRouter,
          { initialEntries: ["/about"] },
          createElement(AccountMenu, { onLogout() {}, onDeleted() {}, ...props }),
        ),
      );
    const guest = render({});
    assert.match(guest, /aria-haspopup="menu" aria-expanded="false"/);
    assert.match(guest, /role="menu"[^>]*hidden/);
    assert.match(guest, /href="\/login\?next=%2Fabout"/);
    assert.doesNotMatch(guest, /Đăng xuất|Xóa tài khoản|href="\/admin"/);
    const member = render({ name: "Tarnished", canAdmin: false });
    assert.match(member, /Đăng xuất/);
    assert.match(member, /Xóa tài khoản/);
    assert.doesNotMatch(member, /href="\/admin"/);
    assert.match(render({ name: "Tarnished", canAdmin: true }), /role="menuitem" href="\/admin"/);
    assert.match(render({ name: "" }), /Đăng xuất/);
  } finally {
    await server.close();
  }
});

test("login preserves the return route and gates each OAuth provider independently", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: LoginPage } = await server.ssrLoadModule("/src/pages/LoginPage.tsx");
    const { AuthContext, guestAuth } = await server.ssrLoadModule("/src/hooks/AuthContext.ts");
    const render = (state: object, path = "/login?next=%2Fadmin") =>
      renderToStaticMarkup(
        createElement(
          MemoryRouter,
          { initialEntries: [path] },
          createElement(AuthContext.Provider, { value: { ...guestAuth, ...state } }, createElement(LoginPage)),
        ),
      );
    const discord = render({ authAvailable: true });
    assert.equal((discord.match(/<button\b[^>]*disabled/g) ?? []).length, 1);
    const both = render({ authAvailable: true, googleAuthAvailable: true });
    assert.doesNotMatch(both, /<button\b[^>]*disabled/);
    const signedIn = render({ user: { id: "u", display_name: "Tarnished", is_admin: true } });
    assert.match(signedIn, /href="\/admin"/);
    assert.match(signedIn, /Tiếp tục với tư cách Tarnished/);
    assert.doesNotMatch(signedIn, /Đăng nhập bằng Google/);
    assert.match(render({}, "/login?login=__proto__"), /LANG THANG ELDEN RING/);
  } finally {
    await server.close();
  }
});
