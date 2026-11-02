// Media is optional: invalid media never destroys an otherwise valid text answer.
import type { ChatImage, Source } from "./types";

function isSourceUrl(value: unknown): value is string {
  if (typeof value !== "string" || /[\\\s\u0000-\u001f]/u.test(value)) return false;
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password;
  } catch {
    return false;
  }
}

export function readChatImages(value: unknown, sources: readonly Source[]): ChatImage[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const images: ChatImage[] = [];
  for (const entry of value) {
    if (!entry || typeof entry !== "object") continue;
    const item = entry as Record<string, unknown>;
    if (
      typeof item.id !== "string" ||
      !/^[0-9a-f]{64}$/.test(item.id) ||
      seen.has(item.id) ||
      item.url !== `/api/v1/images/${item.id}` ||
      !isSourceUrl(item.source_url) ||
      !Array.isArray(item.source_indices) ||
      !item.source_indices.length ||
      item.source_indices.length > 5 ||
      !item.source_indices.every((index) => Number.isInteger(index) && sources.some((source) => source.index === index))
    )
      continue;
    const fields = [
      "caption",
      "alt",
      "attribution",
      "license",
      "license_status",
      "file_page_url",
      "game_scope",
      "release_scope",
    ] as const;
    if (fields.some((field) => item[field] != null && typeof item[field] !== "string")) continue;
    if (item.file_page_url != null && !isSourceUrl(item.file_page_url)) continue;
    const image: ChatImage = {
      id: item.id,
      url: item.url as string,
      source_url: item.source_url,
      source_indices: [...new Set(item.source_indices as number[])],
    };
    for (const field of fields) if (item[field] !== undefined) image[field] = item[field] as string | null;
    images.push(image);
    seen.add(image.id);
    if (images.length === 3) break;
  }
  return images;
}
