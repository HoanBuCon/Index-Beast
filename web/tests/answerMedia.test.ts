// TV4 · Ảnh là dữ liệu UI tách rời API; kiểm tra chặn trước khi hoàn tất và Markdown an toàn.
import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { canShowIllustrations, isIllustrationUrl } from "../src/components/chat/answerMedia.ts";

test("only completed nonempty assistant answers can show supplied illustrations", () => {
  const answer = { role: "assistant", content: "Câu trả lời" };
  assert.equal(canShowIllustrations(answer, false), true);
  assert.equal(canShowIllustrations(answer, true), false);
  assert.equal(canShowIllustrations({ ...answer, incomplete: true }, false), false);
  assert.equal(canShowIllustrations({ ...answer, role: "user" }, false), false);
  assert.equal(canShowIllustrations({ ...answer, content: "  " }, false), false);
});

test("illustrations allow only local-root and HTTP(S) URLs, without credentials", () => {
  for (const url of ["/assets/image.png", "https://example.com/a.png", "http://localhost:15173/asset.jpg"])
    assert.equal(isIllustrationUrl(url), true, url);
  for (const url of [
    "",
    "//tracker.example/x",
    "/\\tracker.example/x",
    "javascript:alert(1)",
    "data:image/svg+xml,test",
    "file:///x",
    "https://user:secret@example.com/x",
    " /x",
    "/x\n",
  ])
    assert.equal(isIllustrationUrl(url), false, url);
});

test("rendering preserves safe Markdown and sources, requires opt-in media, and provides honest states", async () => {
  const server = await createServer({ server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
  try {
    const { default: MessageList } = await server.ssrLoadModule("/src/components/chat/MessageList.tsx");
    const { default: AnswerIllustrations } = await server.ssrLoadModule("/src/components/chat/AnswerIllustrations.tsx");
    const { illustrationFixtures } = await server.ssrLoadModule("/src/fixtures/answerIllustrations.ts");
    const source = { index: 1, title: "Nguồn văn bản", url: "https://example.com/lore", text: "Đoạn nguồn" };
    const message = {
      id: "answer",
      role: "assistant",
      serverId: "11111111-1111-4111-8111-111111111111",
      content: "**Trả lời** [1]\n\n![unsafe](https://tracker.example/x)\n\n<script>alert(1)</script>",
      sources: [source],
    };
    const map = { answer: Object.values(illustrationFixtures) };
    const render = (extra = {}) =>
      renderToStaticMarkup(createElement(MessageList, { messages: [message], busy: false, demo: true, ...extra }));
    assert.doesNotMatch(render(), /answer-illustrations/);
    const markup = render({ illustrationsByMessage: map });
    assert.equal((markup.match(/<figure/g) ?? []).length, 3);
    assert.match(markup, /Nhân vật/);
    assert.match(markup, /Vũ khí/);
    assert.match(markup, /Vật phẩm/);
    assert.match(markup, /Nguồn ảnh: tài nguyên dự án/);
    assert.match(markup, /chưa xác minh tác giả/);
    assert.match(markup, /<strong>Trả lời<\/strong>/);
    assert.match(markup, /citation-link/);
    assert.match(markup, /aria-label="Nguồn tham khảo"/);
    assert.match(markup, /aria-label="Hữu ích"/);
    assert.doesNotMatch(markup, /src="https:\/\/tracker|<script>/);
    for (const extra of [
      { busy: true },
      { messages: [{ ...message, incomplete: true }] },
      { messages: [{ ...message, role: "user" }] },
    ])
      assert.doesNotMatch(render({ illustrationsByMessage: map, ...extra }), /answer-illustrations/);
    assert.match(
      render({
        messages: [message, { ...message, id: "next", incomplete: true }],
        busy: true,
        illustrationsByMessage: map,
      }),
      /answer-illustrations/,
    );
    assert.equal(renderToStaticMarkup(createElement(AnswerIllustrations, { illustrations: [] })), "");
    assert.equal(
      renderToStaticMarkup(
        createElement(AnswerIllustrations, {
          illustrations: [{ ...illustrationFixtures.item, src: "javascript:alert(1)" }],
        }),
      ),
      "",
    );
    const loading = render({ illustrationsByMessage: map, illustrationPreviewState: "loading" });
    assert.match(loading, /Đang tải ảnh/);
    assert.doesNotMatch(loading, /<img[^>]+alt="Tranh/);
    const error = render({ illustrationsByMessage: map, illustrationPreviewState: "error" });
    assert.match(error, /Không tải được ảnh/);
    assert.match(error, /Thử tải lại ảnh/);
  } finally {
    await server.close();
  }
});
