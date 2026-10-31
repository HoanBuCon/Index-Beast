// TV4 presentation + TV3 adapter for citation-associated backend media.
import type { ChatImage, Source } from "../../api/types";
import { readChatImages } from "../../api/images.ts";
export type IllustrationKind = "character" | "weapon" | "item" | "related";
export type IllustrationPreviewState = "loading" | "error";

export interface AnswerIllustration {
  id: string;
  kind: IllustrationKind;
  name: string;
  src: string;
  alt: string;
  description?: string;
  source: { label: string; url: string; credit: string };
}

export const illustrationKindLabels: Record<IllustrationKind, string> = {
  character: "Nhân vật",
  weapon: "Vũ khí",
  item: "Vật phẩm",
  related: "Ảnh từ nguồn trích dẫn",
};

export function backendIllustrations(
  images: readonly ChatImage[] | undefined,
  sources: readonly Source[],
): AnswerIllustration[] {
  return readChatImages(images, sources).map((image) => {
    const source = sources.find((source) => image.source_indices.includes(source.index))!;
    const credit = [
      image.attribution,
      image.license ? `Giấy phép: ${image.license}` : "Chưa có thông tin giấy phép.",
      image.license_status !== "approved" ? "Quyền sử dụng ảnh chưa được xác minh." : null,
    ]
      .filter(Boolean)
      .join(" · ");
    return {
      id: image.id,
      kind: "related",
      name: source.title,
      src: image.url,
      alt: image.alt?.trim() || image.caption?.trim() || `Ảnh từ nguồn ${source.title}`,
      description: image.caption?.trim() || undefined,
      source: { label: `Nguồn ảnh [${image.source_indices.join(", ")}]`, url: image.source_url, credit },
    };
  });
}

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
