// TV1 · [S5] Trang admin: danh sách cuộn được, nút Xem trace theo dòng, khung JSON chọn/sao chép được.
import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const convId = "11111111-1111-4111-8111-111111111111";
const msgId = "22222222-2222-4222-8222-222222222222";
const fbId = "33333333-3333-4333-8333-333333333333";

async function withModules<T>(run: (m: Record<string, any>) => Promise<T> | T): Promise<T> {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const lists = await server.ssrLoadModule("/src/components/admin/AdminLists.tsx");
    const helpers = await server.ssrLoadModule("/src/lib/adminTrace.ts");
    return await run({ ...lists, ...helpers });
  } finally {
    await server.close();
  }
}

test("conversation list is a focusable fixed-height scroll box showing the latest message id and a Xem trace button", async () => {
  await withModules(({ ConversationList }) => {
    const html = renderToStaticMarkup(
      createElement(ConversationList, {
        conversations: [
          { id: convId, title: "Marika là ai?", created_at: "2026-11-08T03:00:00Z", last_message_id: msgId },
          { id: fbId, title: "Chưa đáp", created_at: "2026-11-08T03:00:00Z" },
        ],
        canView: true,
        onViewTrace: () => {},
      }),
    );
    assert.match(html, /class="admin-scroll"[^>]*tabindex="0"|tabindex="0"[^>]*class="admin-scroll"/);
    assert.match(html, /aria-label="Danh sách hội thoại gần đây"/);
    assert.match(html, new RegExp(`<code>${msgId}</code>`));
    assert.equal((html.match(/>Xem trace</g) ?? []).length, 2);
    assert.match(html, new RegExp(`aria-label="Xem trace của hội thoại Marika là ai\\?"`));
    assert.doesNotMatch(
      renderToStaticMarkup(createElement(ConversationList, { conversations: [], canView: true, onViewTrace() {} })),
      /Xem trace/,
    );
    assert.match(
      renderToStaticMarkup(
        createElement(ConversationList, {
          conversations: [{ id: convId, title: "x", created_at: "2026-11-08T03:00:00Z" }],
          canView: false,
          onViewTrace() {},
        }),
      ),
      /<button[^>]*disabled/,
    );
  });
});

test("trace button uses the latest message id, falling back to the conversation id", async () => {
  await withModules(({ traceTargetOf }) => {
    assert.equal(traceTargetOf({ id: convId, last_message_id: msgId }), msgId);
    assert.equal(traceTargetOf({ id: convId }), convId);
  });
});

test("feedback list is a focusable scroll box with a Xem trace button per row", async () => {
  await withModules(({ FeedbackList }) => {
    const html = renderToStaticMarkup(
      createElement(FeedbackList, {
        feedback: [
          { message_id: fbId, rating: -1, reason: "sai" },
          { message_id: msgId, rating: 1 },
        ],
        canView: true,
        onViewTrace: () => {},
      }),
    );
    assert.match(html, /aria-label="Danh sách phản hồi chưa hữu ích"/);
    assert.match(html, /tabindex="0"/);
    assert.match(html, new RegExp(`<code>${fbId}</code>`));
    assert.equal((html.match(/>Xem trace</g) ?? []).length, 1); // chỉ phản hồi 👎
    assert.doesNotMatch(html, new RegExp(msgId));
  });
});

test("trace viewer is a focusable labelled region with a copy button", async () => {
  await withModules(({ TraceViewer }) => {
    const html = renderToStaticMarkup(createElement(TraceViewer, { value: { a: 1 } }));
    assert.match(html, /<pre[^>]*tabindex="0"/);
    assert.match(html, /<pre[^>]*role="region"/);
    assert.match(html, /<pre[^>]*aria-label="Kết quả trace dạng JSON/);
    assert.match(html, />Sao chép</);
    assert.match(html, /&quot;a&quot;: 1/);
  });
});

test("isSelectAllKey matches only Ctrl+A / Cmd+A", async () => {
  await withModules(({ isSelectAllKey }) => {
    const key = (o: object) => ({ key: "a", ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, ...o });
    assert.equal(isSelectAllKey(key({ ctrlKey: true })), true);
    assert.equal(isSelectAllKey(key({ metaKey: true })), true);
    assert.equal(isSelectAllKey(key({ ctrlKey: true, key: "A" })), true);
    assert.equal(isSelectAllKey(key({})), false);
    assert.equal(isSelectAllKey(key({ ctrlKey: true, key: "c" })), false);
    assert.equal(isSelectAllKey(key({ ctrlKey: true, shiftKey: true })), false);
    assert.equal(isSelectAllKey(key({ ctrlKey: true, altKey: true })), false);
  });
});

test("selectOnly selects just the element contents and prevents the default select-all", async () => {
  await withModules(({ selectOnly }) => {
    const calls: string[] = [];
    const range = { selectNodeContents: (n: unknown) => calls.push(`range:${(n as { id: string }).id}`) };
    const selection = {
      removeAllRanges: () => calls.push("clear"),
      addRange: (r: unknown) => calls.push(r === range ? "add" : "add?"),
    };
    const element = { id: "pre", ownerDocument: { createRange: () => range, getSelection: () => selection } };
    let prevented = false;
    selectOnly({ preventDefault: () => (prevented = true) }, element);
    assert.equal(prevented, true);
    assert.deepEqual(calls, ["range:pre", "clear", "add"]);
  });
});

test("copyText writes to the clipboard and reports failure instead of throwing", async () => {
  await withModules(async ({ copyText }) => {
    const written: string[] = [];
    assert.equal(await copyText("{}", { writeText: async (t: string) => void written.push(t) }), "copied");
    assert.deepEqual(written, ["{}"]);
    assert.equal(
      await copyText("{}", {
        writeText: async () => {
          throw new Error("denied");
        },
      }),
      "failed",
    );
    assert.equal(await copyText("{}", undefined), "failed");
  });
});
