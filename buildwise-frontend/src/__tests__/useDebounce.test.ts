import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import useDebounce from "@/hooks/useDebounce";

describe("useDebounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns initial value immediately", () => {
    const { result } = renderHook(() => useDebounce("hello", 300));
    expect(result.current).toBe("hello");
  });

  it("debounces value changes", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: "a" } },
    );

    expect(result.current).toBe("a");

    rerender({ value: "ab" });
    expect(result.current).toBe("a"); // not yet updated

    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toBe("ab"); // now updated
  });

  it("resets timer on rapid changes", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: "" } },
    );

    rerender({ value: "a" });
    act(() => vi.advanceTimersByTime(100));

    rerender({ value: "ab" });
    act(() => vi.advanceTimersByTime(100));

    rerender({ value: "abc" });
    act(() => vi.advanceTimersByTime(100));

    // Only 100ms since last change — still debouncing
    expect(result.current).toBe("");

    act(() => vi.advanceTimersByTime(200));
    // Now 300ms since last change
    expect(result.current).toBe("abc");
  });

  it("works with custom delay", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 500),
      { initialProps: { value: "x" } },
    );

    rerender({ value: "y" });
    act(() => vi.advanceTimersByTime(300));
    expect(result.current).toBe("x");

    act(() => vi.advanceTimersByTime(200));
    expect(result.current).toBe("y");
  });
});
