// TV4 · Dữ liệu trình bày phía UI; không mở rộng DTO/API hoặc lưu vào lịch sử hội thoại.
export type IllustrationKind = "character" | "weapon" | "item";
export type IllustrationPreviewState = "loading" | "error";

export interface AnswerIllustration {
  id: string;
  kind: IllustrationKind;
  name: string;
  src: string;
  alt: string;
  source: { label: string; url: string; credit: string };
}

export const illustrationKindLabels: Record<IllustrationKind, string> = {
  character: "Nhân vật",
  weapon: "Vũ khí",
  item: "Vật phẩm",
};

// Chỉ ảnh/link HTTP(S) hoặc đường dẫn cùng origin; không nhận javascript:, data: hay //host.
export function isIllustrationUrl(value: string): boolean {
  if (!value || value !== value.trim() || /[\\\s\u0000-\u001f]/u.test(value)) return false;
  if (value.startsWith("/") && !value.startsWith("//")) return true;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password;
  } catch {
    return false;
  }
}

export function canShowIllustrations(
  message: { role: string; content: string; incomplete?: boolean },
  pending: boolean,
) {
  return message.role === "assistant" && !!message.content.trim() && !message.incomplete && !pending;
}
