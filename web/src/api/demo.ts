// Dữ liệu minh họa cố định cho TV4 thử UI; không phải kết quả RAG hoặc API thật.
// Phụ trách: TV4 · [S2–S4] UI chat và streaming
import type { ChatRequest, ChatResponse, StreamEvent } from "./types";

export type DemoScenario = "success" | "error" | "slow";
// Mock chỉ trong frontend để thử UI S2; không tạo endpoint hoặc thay backend của TV1.
export async function demoChat(
  body: ChatRequest,
  signal: AbortSignal,
  scenario: DemoScenario = "success",
): Promise<ChatResponse> {
  signal.throwIfAborted();
  await new Promise<void>((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer);
      reject(signal.reason);
    };
    const timer = setTimeout(
      () => {
        signal.removeEventListener("abort", abort);
        resolve();
      },
      scenario === "slow" ? 6000 : 600,
    );
    signal.addEventListener("abort", abort, { once: true });
  });
  signal.throwIfAborted();
  if (scenario === "error") throw new Error("Lỗi minh họa. Chọn Thành công rồi bấm Thử lại để kiểm tra.");
  return {
    conversation_id: body.conversation_id ?? crypto.randomUUID(),
    message_id: crypto.randomUUID(),
    grounded: false,
    answer:
      "Đây là **phản hồi JSON minh họa của frontend**, không phải kết quả RAG hay API của TV1.\n\nBạn vừa gửi một câu hỏi. Giao diện đã đi qua trạng thái chờ và nhận một câu trả lời hoàn chỉnh. Nguồn [1] chỉ dùng để thử hiển thị.\n\n- Chọn **Kết nối API (JSON)** để gửi tới `/api/v1/chat`.\n- Chọn tình huống **Lỗi** hoặc **Phản hồi chậm** để kiểm tra lỗi, thử lại và hủy.",
    sources: [
      {
        index: 1,
        title: "Elden Ring — nguồn minh họa",
        url: "https://en.wikipedia.org/wiki/Elden_Ring",
        text: "Liên kết minh họa, không phải bằng chứng cho câu trả lời.",
        origin: "corpus",
      },
    ],
  };
}
export async function* demoStream(body: ChatRequest, signal: AbortSignal): AsyncGenerator<StreamEvent> {
  const answer =
    "Đây là **câu trả lời minh họa giao diện**, chưa được truy xuất từ kho lore.\n\nKhi API RAG sẵn sàng, Index Beast sẽ tìm các đoạn liên quan, trả lời bằng ngôn ngữ của bạn và đánh số nguồn như [1]. Bạn có thể bấm số nguồn để xem chi tiết.\n\nChọn **Kết nối API** để gửi câu hỏi tới backend của dự án.";
  for (const token of answer.match(/\S+\s*/g) ?? []) {
    signal.throwIfAborted();
    await new Promise<void>((resolve, reject) => {
      const abort = () => {
        clearTimeout(timer);
        reject(new DOMException("Stopped", "AbortError"));
      };
      const timer = setTimeout(() => {
        signal.removeEventListener("abort", abort);
        resolve();
      }, 25);
      signal.addEventListener("abort", abort, { once: true });
    });
    yield { type: "token", token };
  }
  yield {
    type: "sources",
    sources: [
      {
        index: 1,
        title: "Elden Ring — nguồn minh họa",
        section: "Tổng quan",
        url: "https://en.wikipedia.org/wiki/Elden_Ring",
        text: "Liên kết để minh họa cách hiển thị nguồn. Không phải bằng chứng cho câu trả lời RAG.",
        origin: "corpus",
      },
    ],
  };
  yield {
    type: "done",
    data: {
      conversation_id: body.conversation_id ?? crypto.randomUUID(),
      message_id: crypto.randomUUID(),
      grounded: false,
    },
  };
}
