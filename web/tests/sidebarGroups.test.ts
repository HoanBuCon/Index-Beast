// Sidebar nhóm hội thoại theo CHỦ SỞ HỮU (không theo nơi lưu): mở một mục không làm nó nhảy sang mục khác.
// Phụ trách: TV1 · [S5] Sửa sidebar "Của tài khoản"
import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { createServer } from "vite";
import { groupSidebarConversations } from "../src/lib/accountData.ts";
import type { Conversation } from "../src/api/types.ts";

const S1 = "3f2b8c1e-9a4d-4c7e-8b1a-2d5e6f7a8b91";
const S2 = "3f2b8c1e-9a4d-4c7e-8b1a-2d5e6f7a8b92";
const S3 = "3f2b8c1e-9a4d-4c7e-8b1a-2d5e6f7a8b93";

function local(id: string, title: string, updatedAt: string, extra: Partial<Conversation> = {}): Conversation {
  return { id, title, mode: "api-stream", serverId: null, updatedAt, messages: [], ...extra };
}
const remote = (id: string, title: string, created_at: string) => ({ id, title, created_at });

test("account list merges local copies with server-only rows, deduped by server id, newest first", () => {
  const copy = local("l1", "Bản cục bộ", "2026-11-22T10:00:00Z", { serverId: S1, ownerUserId: "u1" });
  const groups = groupSidebarConversations(
    [copy],
    [remote(S1, "Tên server", "2026-11-20T00:00:00Z"), remote(S2, "Chỉ server", "2026-11-23T00:00:00Z")],
    "u1",
  );
  assert.deepEqual(
    groups.account.map((i) => [i.serverId, i.title, i.local?.id ?? null]),
    [
      [S2, "Chỉ server", null], // created_at 23/11 mới hơn
      [S1, "Bản cục bộ", "l1"], // dùng updatedAt cục bộ, chỉ một dòng
    ],
  );
  assert.deepEqual(groups.browser, []);
});

test("an item stays in the account list before and after it gets a local copy", () => {
  const rows = [remote(S1, "A", "2026-11-22T00:00:00Z")];
  const before = groupSidebarConversations([], rows, "u1");
  const after = groupSidebarConversations(
    [local("l1", "A", "2026-11-22T00:00:00Z", { serverId: S1, ownerUserId: "u1" })],
    rows,
    "u1",
  );
  assert.equal(before.account.length, 1);
  assert.equal(after.account.length, 1);
  assert.equal(after.browser.length, 0);
  assert.equal(before.account[0].key, after.account[0].key); // cùng key: không nhảy mục
});

test("owned local conversations show immediately, even before /me/conversations lists them", () => {
  const fresh = local("l2", "Mới tạo", "2026-11-23T09:00:00Z", { ownerUserId: "u1" }); // chưa có serverId
  const synced = local("l3", "Đã có server", "2026-11-23T10:00:00Z", { ownerUserId: "u1", serverId: S3 });
  const { account, browser } = groupSidebarConversations([fresh, synced], [], "u1");
  assert.deepEqual(
    account.map((i) => i.local?.id),
    ["l3", "l2"],
  );
  assert.deepEqual(browser, []);
});

test("local copy whose server id belongs to the account counts as owned even without ownerUserId", () => {
  const copy = local("l1", "Cũ", "2026-11-22T00:00:00Z", { serverId: S1 });
  const { account, browser } = groupSidebarConversations([copy], [remote(S1, "Cũ", "2026-11-21T00:00:00Z")], "u1");
  assert.equal(account.length, 1);
  assert.deepEqual(browser, []);
});

test("signed in: unowned guest conversations go to the browser list, other owners are never listed", () => {
  const guest = local("g", "Khách", "2026-11-22T00:00:00Z");
  const bob = local("b", "Của Bob", "2026-11-22T00:00:00Z", { ownerUserId: "bob", serverId: S2 });
  const { account, browser } = groupSidebarConversations([guest, bob], [], "u1");
  assert.deepEqual(account, []);
  assert.deepEqual(
    browser.map((c) => c.id),
    ["g"],
  );
});

test("guest viewer: everything unowned is in the browser list, account list is empty", () => {
  const guest = local("g", "Khách", "2026-11-22T00:00:00Z");
  const alice = local("a", "Của Alice", "2026-11-22T00:00:00Z", { ownerUserId: "alice" });
  const groups = groupSidebarConversations([guest, alice], [remote(S1, "x", "2026-11-22T00:00:00Z")], null);
  assert.deepEqual(groups.account, []);
  assert.deepEqual(
    groups.browser.map((c) => c.id),
    ["g"],
  );
});

test("duplicate local copies of one server conversation collapse to the newest", () => {
  const older = local("l1", "Cũ", "2026-11-20T00:00:00Z", { serverId: S1, ownerUserId: "u1" });
  const newer = local("l2", "Mới", "2026-11-22T00:00:00Z", { serverId: S1, ownerUserId: "u1" });
  const { account } = groupSidebarConversations([older, newer], [], "u1");
  assert.deepEqual(
    account.map((i) => i.local?.id),
    ["l2"],
  );
});

async function renderSidebar(auth: object, stored: Conversation[]) {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  const original = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: { getItem: () => JSON.stringify(stored), setItem() {} },
  });
  try {
    const { default: ChatPage } = await server.ssrLoadModule("/src/pages/ChatPage.tsx");
    const { AuthContext, guestAuth } = await server.ssrLoadModule("/src/hooks/AuthContext.ts");
    return renderToStaticMarkup(
      createElement(
        MemoryRouter,
        { initialEntries: ["/chat"] },
        createElement(AuthContext.Provider, { value: { ...guestAuth, ...auth } }, createElement(ChatPage)),
      ),
    );
  } finally {
    if (original) Object.defineProperty(globalThis, "localStorage", original);
    else Reflect.deleteProperty(globalThis, "localStorage");
    await server.close();
  }
}

// Phần HTML của một mục sidebar (từ <h2> của nó đến <h2> kế tiếp hoặc hết sidebar).
function section(html: string, heading: string): string {
  const start = html.indexOf(`>${heading}</h2>`);
  if (start < 0) return "";
  const rest = html.slice(start + heading.length);
  const end = rest.search(/<h2|<\/aside>/);
  return rest.slice(0, end < 0 ? undefined : end);
}

test("sidebar: one item appears in exactly one section before and after it has a local copy", async () => {
  const signedIn = {
    authAvailable: true,
    user: { id: "u1", display_name: "Tarnished", is_admin: false },
    myConversations: [remote(S1, "Boss cuối là ai?", "2026-11-22T12:00:00Z")],
  };
  const guestChat = local("g", "Cuộc trò chuyện khách", "2026-11-21T00:00:00Z");
  const copy = local("l1", "Boss cuối là ai?", "2026-11-22T12:00:00Z", { serverId: S1, ownerUserId: "u1" });
  for (const stored of [[guestChat], [guestChat, copy]]) {
    const html = await renderSidebar(signedIn, stored);
    assert.equal(html.match(/Boss cuối là ai\?<\/span>/g)?.length, 1, "chỉ một dòng");
    assert.match(section(html, "Của tài khoản"), /Boss cuối là ai\?/);
    assert.doesNotMatch(section(html, "Trên trình duyệt này"), /Boss cuối là ai\?/);
    assert.match(section(html, "Trên trình duyệt này"), /Cuộc trò chuyện khách/);
    assert.doesNotMatch(section(html, "Của tài khoản"), /Cuộc trò chuyện khách/);
    assert.match(html, /aria-label="Xóa Boss cuối là ai\?"/);
  }
});

test("sidebar: owned local copy lists under the account; guests keep the 'Tất cả' list", async () => {
  const copy = local("l1", "Đang mở", "2026-11-22T12:00:00Z", { serverId: S1, ownerUserId: "u1" });
  const guestChat = local("g", "Khách", "2026-11-21T00:00:00Z");
  const html = await renderSidebar(
    { authAvailable: true, user: { id: "u1", display_name: "T", is_admin: false }, myConversations: [] },
    [copy],
  );
  assert.match(section(html, "Của tài khoản"), /Đang mở/);
  assert.doesNotMatch(html, />Trên trình duyệt này</); // rỗng thì ẩn
  const guestHtml = await renderSidebar({ user: null }, [guestChat]);
  assert.match(section(guestHtml, "Tất cả"), /Khách/);
  assert.doesNotMatch(guestHtml, /Của tài khoản/);
});
