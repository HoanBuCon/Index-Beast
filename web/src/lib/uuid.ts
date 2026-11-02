// randomUUID needs a secure context; HTTP LAN/VPN still supports getRandomValues.
export function createUuid(source: Crypto = globalThis.crypto): string {
  if (typeof source?.randomUUID === "function") return source.randomUUID();
  if (typeof source?.getRandomValues !== "function") {
    throw new Error("Trình duyệt không hỗ trợ tạo ID an toàn. Hãy dùng trình duyệt mới hoặc HTTPS.");
  }
  const bytes = source.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
