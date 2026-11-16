// Phụ thuộc dùng chung của các lệnh/handler cần backend theo server: client API và cache kênh /setup.
// Khởi tạo lười để import registry (ví dụ trong test) không đọc cấu hình môi trường.

import { createApiClient } from "./api/client.ts";
import type { ApiClient } from "./api/client.ts";
import { createGuildChannelCache } from "./utils/guildChannelCache.ts";
import type { GuildChannelCache } from "./utils/guildChannelCache.ts";

// Mỗi lệnh dùng một client mới để có X-Request-ID riêng; client không giữ trạng thái.
export const defaultApi = (): ApiClient => createApiClient();

let cache: GuildChannelCache | undefined;
export function defaultChannelCache(): GuildChannelCache {
  cache ??= createGuildChannelCache((guildId) => defaultApi().listGuildChannels(guildId));
  return cache;
}
