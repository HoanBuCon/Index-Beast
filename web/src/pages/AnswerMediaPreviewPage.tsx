// TV4 · Trang thử độc lập: không gửi API, không thay lịch sử hay chế độ chat thật.
import { useState } from "react";
import MessageList from "../components/chat/MessageList";
import { illustrationKindLabels } from "../components/chat/answerMedia";
import { illustrationFixtureMessages, illustrationFixtures } from "../fixtures/answerIllustrations";

type Scenario = "success" | "loading" | "error" | "none" | "answering" | "stopped";
export default function AnswerMediaPreviewPage() {
  const [kind, setKind] = useState<keyof typeof illustrationFixtures | "all">("character");
  const [scenario, setScenario] = useState<Scenario>("success");
  const images =
    scenario === "none" ? [] : kind === "all" ? Object.values(illustrationFixtures) : [illustrationFixtures[kind]];
  const messages = illustrationFixtureMessages.map((message) =>
    message.role === "assistant"
      ? { ...message, incomplete: scenario === "answering" || scenario === "stopped" }
      : message,
  );
  return (
    <main id="main" className="answer-media-preview">
      <h1>Thử ảnh trong câu trả lời</h1>
      <p>Dữ liệu minh họa — chỉ frontend. Chọn ảnh thủ công để thử giao diện, không gửi câu hỏi hoặc gọi API.</p>
      <div className="answer-media-preview__controls">
        <label htmlFor="illustration-kind">
          Loại đối tượng
          <select id="illustration-kind" value={kind} onChange={(event) => setKind(event.target.value as typeof kind)}>
            {(Object.keys(illustrationFixtures) as (keyof typeof illustrationFixtures)[]).map((value) => (
              <option value={value} key={value}>
                {illustrationKindLabels[value]}
              </option>
            ))}
            <option value="all">Cả ba loại</option>
          </select>
        </label>
        <label htmlFor="illustration-scenario">
          Tình huống thử
          <select
            id="illustration-scenario"
            value={scenario}
            onChange={(event) => setScenario(event.target.value as Scenario)}
          >
            <option value="success">Thành công</option>
            <option value="loading">Ảnh đang tải (mô phỏng)</option>
            <option value="error">Ảnh lỗi lần đầu — bấm Thử lại</option>
            <option value="none">Không có ảnh</option>
            <option value="answering">Câu trả lời chưa hoàn tất</option>
            <option value="stopped">Đã dừng câu trả lời</option>
          </select>
        </label>
      </div>
      <MessageList
        key={`${kind}:${scenario}`}
        messages={messages}
        busy={scenario === "answering"}
        demo
        illustrationsByMessage={{ "preview-answer": images }}
        illustrationPreviewState={scenario === "loading" || scenario === "error" ? scenario : undefined}
      />
    </main>
  );
}
