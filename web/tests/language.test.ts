// Kiểm tra giao diện tiếng Việt, kể cả khi còn lựa chọn ngôn ngữ cũ hoặc storage bị chặn.
// Phụ trách: TV4 · Giao diện web
import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { createServer } from "vite";

test("UI renders on HTTP LAN without randomUUID, old English preference or blocked storage", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false }, appType: "custom" });
  const original = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  const originalCrypto = Object.getOwnPropertyDescriptor(globalThis, "crypto");
  const getRandomValues = globalThis.crypto.getRandomValues.bind(globalThis.crypto);
  try {
    const { default: App } = await server.ssrLoadModule("/src/App.tsx");
    const { default: ChatPage } = await server.ssrLoadModule("/src/pages/ChatPage.tsx");
    const { default: MessageList } = await server.ssrLoadModule("/src/components/chat/MessageList.tsx");
    Object.defineProperty(globalThis, "crypto", { configurable: true, value: { getRandomValues } });
    function render(language: string | null, blocked = false, route = "/about") {
      Object.defineProperty(globalThis, "localStorage", {
        configurable: true,
        value: {
          getItem(key: string) {
            if (blocked) throw new Error("blocked");
            return key === "indexbeast.language" ? language : "[]";
          },
        },
      });
      return renderToStaticMarkup(createElement(MemoryRouter, { initialEntries: [route] }, createElement(App)));
    }
    const savedEnglish = render("en");
    assert.match(savedEnglish, /Cuộc trò chuyện mới/);
    assert.match(savedEnglish, /Nguồn &amp; ghi nhận/);
    assert.doesNotMatch(savedEnglish, /Explore lore|Sources &amp; credits/);
    const admin = render("en", false, "/admin");
    assert.match(admin, /Quản trị kho lore/);
    assert.doesNotMatch(admin, /language-switch|Ngôn ngữ giao diện|aria-label="English"/);
    assert.ok(savedEnglish.indexOf("<aside") < savedEnglish.indexOf("<header"));
    const vietnamese = render("vi");
    assert.match(vietnamese, /Cuộc trò chuyện mới/);
    assert.match(vietnamese, /Nguồn &amp; ghi nhận/);
    assert.match(render("invalid"), /Cuộc trò chuyện mới/);
    assert.match(render(null, true), /Cuộc trò chuyện mới/);
    // Trạng thái rỗng chỉ có một ô nhập, nằm trước các gợi ý như bố cục tham khảo.
    const chat = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(ChatPage)));
    assert.equal((chat.match(/<textarea/g) ?? []).length, 1);
    assert.match(chat, /Hôm nay bạn muốn khám phá điều gì/);
    assert.doesNotMatch(chat, /class="welcome-logo"/);
    assert.ok(chat.indexOf("<textarea") < chat.indexOf('class="suggestions"'));
    for (const question of ["Elden Ring là game gì?", "Game thuộc thể loại gì?", "FromSoftware là gì?"]) {
      assert.ok(chat.includes(question));
    }
    assert.match(chat, /aria-label="Gửi câu hỏi"/);
    assert.match(chat, /maxLength="2000"/i);
    assert.doesNotMatch(chat, /class="mode-note"/);
    assert.doesNotMatch(chat, /aria-label="Tra cứu lore"|aria-label="Chế độ trò chuyện"|aria-label="Tình huống thử"/);
    // Chỉ báo chờ phải biến mất khi có nội dung hoặc request kết thúc.
    const waiting = { id: "waiting", role: "assistant", content: "", sources: [], incomplete: true };
    const renderMessages = (busy: boolean, content = "") =>
      renderToStaticMarkup(
        createElement(MessageList, {
          messages: [{ ...waiting, content }],
          busy,
          demo: false,
        }),
      );
    assert.match(renderMessages(true), /class="thinking-bubble"/);
    assert.doesNotMatch(renderMessages(true, "Đã có nội dung"), /class="thinking-bubble"/);
    assert.doesNotMatch(renderMessages(false), /class="thinking-bubble"/);
    assert.match(renderMessages(false), /Câu trả lời chưa hoàn tất/);
  } finally {
    if (originalCrypto) Object.defineProperty(globalThis, "crypto", originalCrypto);
    else Reflect.deleteProperty(globalThis, "crypto");
    if (original) Object.defineProperty(globalThis, "localStorage", original);
    else Reflect.deleteProperty(globalThis, "localStorage");
    await server.close();
  }
});
