export type SearchMode = "off" | "auto" | "always";

export const searchModeLabel: Record<SearchMode, string> = {
  off: "OFF",
  auto: "ON",
  always: "ALWAYS",
};

export function nextSearchMode(mode: SearchMode): SearchMode {
  return mode === "off" ? "auto" : mode === "auto" ? "always" : "off";
}
