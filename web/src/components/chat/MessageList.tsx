// Hiển thị lượt hỏi/đáp, render Markdown.
// Phụ trách: TV4 · [S2] UI chat cơ bản

import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message, Source } from "../../api/types";
import SourceList from "./SourceList";
import CitationPopover from "./CitationPopover";
import FeedbackButtons from "./FeedbackButtons";
import graceIcon from "../../assets/ERN_Map_Icon_Site_of_Grace.png";
export default function MessageList({ messages, busy, demo }: { messages: Message[]; busy: boolean; demo: boolean }) {
  const [selected, setSelected] = useState<Source | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "nearest" });
  }, [messages]);
  return (
    <div className="messages" aria-busy={busy}>
      {messages.map((message) => (
        <article key={message.id} className={`message ${message.role}`}>
          <div className={message.role === "user" ? "sr-only" : "message-label"}>
            {message.role === "assistant" && (
              <img className="message-avatar" src={graceIcon} alt="" width={24} height={24} draggable={false} />
            )}
            {message.role === "user" ? "BẠN" : "INDEX BEAST"}
            {message.role === "assistant" && demo && <small>{"MINH HỌA"}</small>}
          </div>
          <div className="prose">
            {message.role === "user" ? (
              message.content
            ) : (
              <Markdown
                remarkPlugins={[remarkGfm]}
                skipHtml
                components={{
                  img: () => null,
                  a: ({ href, children }) => {
                    const match = /^#source-(\d+)$/.exec(href ?? "");
                    const source = match ? message.sources.find((s) => s.index === Number(match[1])) : undefined;
                    return source ? (
                      <button className="citation-link" onClick={() => setSelected(source)}>
                        {children}
                      </button>
                    ) : (
                      <a href={href} target="_blank" rel="noreferrer">
                        {children}
                      </a>
                    );
                  },
                }}
              >
                {message.content.replace(/\[(\d+)\](?!\()/g, (full, index: string) =>
                  message.sources.some((s) => s.index === Number(index)) ? `[${index}](#source-${index})` : full,
                )}
              </Markdown>
            )}
          </div>
          {message.role === "assistant" && (
            <>
              {!message.content && busy && message.id === messages.at(-1)?.id && (
                <div role="status" className="thinking-bubble">
                  <span className="sr-only">Đang chờ câu trả lời…</span>
                  <span className="thinking-dots" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </span>
                </div>
              )}
              {message.incomplete && !(busy && message === messages.at(-1)) && (
                <p className="muted">{"Câu trả lời chưa hoàn tất."}</p>
              )}
              {message.grounded === false && !demo && (
                <p className="muted">{"Chưa tìm được đủ bằng chứng trong kho nguồn."}</p>
              )}
              <SourceList sources={message.sources} onSelect={setSelected} />
              {!message.incomplete && message.serverId && <FeedbackButtons messageId={message.serverId} demo={demo} />}
            </>
          )}
        </article>
      ))}
      <div ref={bottom} />
      {selected && <CitationPopover source={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
