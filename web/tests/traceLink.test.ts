// TV1 · Liên kết "Xem trace" ở câu trả lời và trang admin nhận sẵn message_id; token không đi theo URL.
import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { createServer } from "vite";

const id = "11111111-1111-4111-8111-111111111111";
const answer = { id: "a", role: "assistant", content: "Trả lời", sources: [], serverId: id };

test("answers show the message id and a trace link only when the API enables admin", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: MessageList } = await server.ssrLoadModule("/src/components/chat/MessageList.tsx");
    const render = (extra = {}, messages = [answer]) =>
      renderToStaticMarkup(
        createElement(MemoryRouter, null, createElement(MessageList, { messages, busy: false, demo: false, ...extra })),
      );
    const on = render({ traceLinks: true });
    assert.match(on, new RegExp(`<code>${id}</code>`));
    assert.match(on, new RegExp(`href="/admin\\?message_id=${id}"`));
    assert.match(on, /Xem trace/);
    assert.doesNotMatch(render(), /message-trace|Xem trace/); // mặc định ẩn
    assert.doesNotMatch(render({ traceLinks: true }, [{ ...answer, serverId: undefined }]), /Xem trace/);
    assert.doesNotMatch(render({ traceLinks: true }, [{ ...answer, incomplete: true }]), /Xem trace/);
    assert.doesNotMatch(render({ traceLinks: true }, [{ ...answer, role: "user" }]), /Xem trace/);
  } finally {
    await server.close();
  }
});

test("the admin page is prefilled from ?message_id and never reads a token from the URL", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: AdminPage } = await server.ssrLoadModule("/src/pages/AdminPage.tsx");
    const render = (route: string) =>
      renderToStaticMarkup(createElement(MemoryRouter, { initialEntries: [route] }, createElement(AdminPage)));
    const withId = render(`/admin?message_id=${id}&token=secret-from-url`);
    assert.match(withId, new RegExp(`id="message-id"[^>]*value="${id}"`));
    assert.match(withId, /Nhập token quản trị rồi bấm Kết nối/);
    assert.doesNotMatch(withId, /secret-from-url/);
    assert.match(withId, /id="admin-token"[^>]*type="password"/);
    const plain = render("/admin");
    assert.doesNotMatch(plain, /Nhập token quản trị rồi bấm Kết nối/);
  } finally {
    await server.close();
  }
});
