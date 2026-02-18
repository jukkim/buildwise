import { describe, it, expect, vi, afterEach } from "vitest";
import timeAgo from "@/utils/timeAgo";

describe("timeAgo", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns 'just now' for very recent timestamps", () => {
    const now = new Date().toISOString();
    expect(timeAgo(now)).toBe("just now");
  });

  it("returns 'just now' for future timestamps", () => {
    const future = new Date(Date.now() + 60_000).toISOString();
    expect(timeAgo(future)).toBe("just now");
  });

  it("returns minutes ago", () => {
    vi.useFakeTimers();
    const base = new Date("2026-01-15T12:00:00Z");
    vi.setSystemTime(base);

    const fiveMinAgo = new Date("2026-01-15T11:55:00Z").toISOString();
    expect(timeAgo(fiveMinAgo)).toBe("5m ago");

    const oneMinAgo = new Date("2026-01-15T11:59:00Z").toISOString();
    expect(timeAgo(oneMinAgo)).toBe("1m ago");
  });

  it("returns hours ago", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-15T12:00:00Z"));

    expect(timeAgo("2026-01-15T09:00:00Z")).toBe("3h ago");
    expect(timeAgo("2026-01-15T11:00:00Z")).toBe("1h ago");
  });

  it("returns days ago", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-15T12:00:00Z"));

    expect(timeAgo("2026-01-14T12:00:00Z")).toBe("1d ago");
    expect(timeAgo("2026-01-08T12:00:00Z")).toBe("7d ago");
  });

  it("returns localized date for older than 30 days", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-01T12:00:00Z"));

    const result = timeAgo("2026-01-15T12:00:00Z");
    // Should be a date string, not "Xd ago"
    expect(result).not.toContain("d ago");
    expect(result).not.toContain("h ago");
  });
});
