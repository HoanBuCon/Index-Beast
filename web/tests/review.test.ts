// S5 · Sửa sau review: chủ sở hữu hội thoại cục bộ, đăng xuất có xác minh, hỏi trước khi nhận hội thoại khách,
// capabilities/user dùng chung qua context, hộp xác nhận bằng <dialog>. fetch giả, không gọi backend.
import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { createServer } from "vite";
import { logoutVerified } from "../src/api/auth.ts";
import {
  accountConversationIds,
  claimableGuestConversations,
  claimDeclined,
  markClaimed,
  rememberClaimDeclined,
  stampOwner,
} from "../src/lib/accountData.ts";
import type { Conversation } from "../src/api/types.ts";

const ID = "11111111-1111-4111-8111-111111111111";
const ID2 = "22222222-2222-4222-8222-222222222222";
const TOKEN = "t".repeat(40);
const conv = (over: Partial<Conversation>): Conversation => ({
  id: "c",
  title: "t",
  mode: "api-stream",
  serverId: null,
  messages: [],
  updatedAt: "2026-11-16T00:00:00Z",
  ...over,
});
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });

test("conversations created while logged in get the owner; guest ones with a server id do not", () => {
  assert.equal(stampOwner(undefined, conv({}), "u1").ownerUserId, "u1");
  assert.equal(stampOwner(conv({ serverId: null }), conv({}), "u1").ownerUserId, "u1");
  // đã có chủ thì giữ chủ cũ, kể cả khi bản mới không mang theo
  assert.equal(stampOwner(conv({ ownerUserId: "u1", serverId: ID }), conv({ serverId: ID }), "u2").ownerUserId, "u1");
  // hội thoại khách đã có trên server: gửi tiếp khi đã đăng nhập vẫn là của khách
  assert.equal(
    stampOwner(conv({ serverId: ID, serverToken: TOKEN }), conv({ serverId: ID }), "u1").ownerUserId,
    undefined,
  );
  // không đăng nhập thì không gắn chủ
  assert.equal(stampOwner(undefined, conv({}), undefined).ownerUserId, undefined);
});

test("account conversations to purge: owned ones, claimed ones and ones listed by the server", () => {
  const list = [
    conv({ id: "a", ownerUserId: "u1", serverId: ID, serverToken: TOKEN }), // tạo khi đăng nhập (vẫn có token)
    conv({ id: "b", serverId: ID2 }), // có trong danh sách server của tài khoản
    conv({ id: "c", serverId: "33333333-3333-4333-8333-333333333333", serverToken: TOKEN }), // khách khác
    conv({ id: "d", ownerUserId: "u2" }), // người dùng khác
  ];
  assert.deepEqual(accountConversationIds(list, "u1", [ID2]), ["a", "b"]);
});

test("claimable guest conversations need a valid id+token and no owner; claiming drops the token", () => {
  const list = [
    conv({ id: "a", serverId: ID, serverToken: TOKEN }),
    conv({ id: "b", serverId: ID2, serverToken: TOKEN, ownerUserId: "u1" }),
    conv({ id: "c", serverId: ID2 }),
    conv({ id: "d", serverId: null }),
  ];
  assert.deepEqual(
    claimableGuestConversations(list).map((c) => c.id),
    ["a"],
  );
  const claimed = markClaimed(list[0], "u1");
  assert.equal(claimed.ownerUserId, "u1");
  assert.equal(claimed.serverToken, undefined);
});

test("a declined claim is remembered for the session only", () => {
  const store = new Map<string, string>();
  const storage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
  };
  assert.equal(claimDeclined(storage), false);
  rememberClaimDeclined(storage);
  assert.equal(claimDeclined(storage), true);
  assert.equal(
    claimDeclined({
      getItem: () => {
        throw new Error("blocked");
      },
    }),
    false,
  );
});

test("logout stays logged in when the POST fails and /auth/me still shows the user", async (t) => {
  const user = { authenticated: true, user: { id: "u1", display_name: "Tarnished", is_admin: false } };
  const fetchMock = t.mock.method(globalThis, "fetch", async (url: string) =>
    url.endsWith("/auth/logout") ? new Response(null, { status: 500 }) : json(user),
  );
  assert.equal(await logoutVerified(), false);
  // POST lỗi mạng nhưng phiên đã hết ở server → vẫn coi là đã đăng xuất
  fetchMock.mock.mockImplementation(async (url: string) => {
    if (url.endsWith("/auth/logout")) throw new TypeError("Failed to fetch");
    return json({ authenticated: false, user: null });
  });
  assert.equal(await logoutVerified(), true);
  // POST thành công thì không cần hỏi lại /auth/me
  fetchMock.mock.mockImplementation(async () => new Response(null, { status: 204 }));
  const before = fetchMock.mock.calls.length;
  assert.equal(await logoutVerified(), true);
  assert.equal(fetchMock.mock.calls.length, before + 1);
});

test("claim prompt asks with the count and never claims by itself", async (t) => {
  const fetchMock = t.mock.method(globalThis, "fetch", async () => new Response(null, { status: 204 }));
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: ClaimPrompt } = await server.ssrLoadModule("/src/components/layout/ClaimPrompt.tsx");
    const html = renderToStaticMarkup(createElement(ClaimPrompt, { count: 3, onAccept() {}, onDecline() {} }));
    assert.match(html, /Chuyển 3 hội thoại khách trong trình duyệt này vào tài khoản\?/);
    assert.match(html, />Đồng ý</);
    assert.match(html, />Không</);
    assert.equal(fetchMock.mock.calls.length, 0);
  } finally {
    await server.close();
  }
});

test("confirm uses a native <dialog> and the menu shows a failed-logout error", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: AccountMenu } = await server.ssrLoadModule("/src/components/layout/AccountMenu.tsx");
    const render = (props: object) =>
      renderToStaticMarkup(
        createElement(
          MemoryRouter,
          null,
          createElement(AccountMenu, { name: "T", onLogout() {}, onDeleted() {}, ...props }),
        ),
      );
    assert.doesNotMatch(render({}), /<dialog/);
    assert.match(render({ initialConfirming: true }), /<dialog[^>]*aria-labelledby="account-confirm-title"/);
    assert.match(render({ logoutError: "Chưa đăng xuất được. Vui lòng thử lại." }), /role="alert">Chưa đăng xuất được/);
  } finally {
    await server.close();
  }
});

test("admin page takes the session admin from the shared auth context (no own /auth/me call)", async (t) => {
  const fetchMock = t.mock.method(globalThis, "fetch", async () => json({}));
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: AdminPage } = await server.ssrLoadModule("/src/pages/AdminPage.tsx");
    const { AuthContext, guestAuth } = await server.ssrLoadModule("/src/hooks/AuthContext.ts");
    const render = (user: object | null) =>
      renderToStaticMarkup(
        createElement(
          MemoryRouter,
          null,
          createElement(AuthContext.Provider, { value: { ...guestAuth, user } }, createElement(AdminPage)),
        ),
      );
    assert.match(
      render({ id: "u1", display_name: "Melina", is_admin: true }),
      /quản trị viên: Melina\. Không cần token/,
    );
    assert.doesNotMatch(render({ id: "u2", display_name: "Khách", is_admin: false }), /Không cần token/);
    assert.doesNotMatch(render(null), /Không cần token/);
    assert.equal(fetchMock.mock.calls.length, 0);
  } finally {
    await server.close();
  }
});
