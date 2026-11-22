// TV4 · Bản chia sẻ chỉ đọc; token của đúng một câu trả lời, không phải token hội thoại/service.
import { isSource } from "./types.ts";
import type { Source } from "./types";

export interface SharedAnswer {
  question: string;
  answer: string;
  sources: Source[];
  grounded: boolean;
  expires_at: string;
}

export async function readSharedAnswer(token: string, signal?: AbortSignal): Promise<SharedAnswer> {
  if (!/^[A-Za-z0-9_-]{43}$/.test(token)) throw new Error("Link chia sẻ không hợp lệ hoặc đã hết hạn.");
  const response = await fetch("/api/v1/answer-shares", {
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(10_000)]) : AbortSignal.timeout(10_000),
    cache: "no-store",
    headers: { "X-Answer-Share-Token": token },
  });
  if (!response.ok)
    throw new Error(
      response.status === 404
        ? "Link chia sẻ không hợp lệ hoặc đã hết hạn."
        : "Chưa tải được câu trả lời. Vui lòng thử lại.",
    );
  const data: unknown = await response.json();
  if (!data || typeof data !== "object") throw new Error("Bản chia sẻ không hợp lệ.");
  const value = data as Record<string, unknown>;
  if (
    typeof value.question !== "string" ||
    [...value.question].length > 2000 ||
    typeof value.answer !== "string" ||
    !value.answer.trim() ||
    [...value.answer].length > 100_000 ||
    !Array.isArray(value.sources) ||
    value.sources.length > 100 ||
    !value.sources.every(isSource) ||
    typeof value.grounded !== "boolean" ||
    typeof value.expires_at !== "string" ||
    !Number.isFinite(Date.parse(value.expires_at))
  )
    throw new Error("Bản chia sẻ không hợp lệ.");
  return {
    question: value.question,
    answer: value.answer,
    sources: value.sources,
    grounded: value.grounded,
    expires_at: value.expires_at,
  };
}
