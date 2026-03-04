import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSSE } from "@/hooks/useSSE";

// Helper: create a ReadableStream from SSE text
function sseStream(text: string): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text));
      controller.close();
    },
  });
}

function mockFetchSSE(sseText: string) {
  vi.spyOn(global, "fetch").mockResolvedValueOnce({
    ok: true,
    body: sseStream(sseText),
  } as unknown as Response);
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("useSSE", () => {
  it("parses planner event", async () => {
    const sse =
      'event: planner\ndata: {"needs_search":true,"reasoning":"temporal","search_queries":["test"],"query_type":"temporal"}\n\nevent: done\ndata: {}\n\n';
    mockFetchSSE(sse);

    const onPlanner = vi.fn();
    const onDone = vi.fn();
    const { result } = renderHook(() => useSSE());

    await act(async () => {
      await result.current.sendMessage("test", [], { onPlanner, onDone });
    });

    expect(onPlanner).toHaveBeenCalledWith({
      needs_search: true,
      reasoning: "temporal",
      search_queries: ["test"],
      query_type: "temporal",
    });
    expect(onDone).toHaveBeenCalledOnce();
  });

  it("parses chunk events and accumulates content", async () => {
    const sse =
      'event: chunk\ndata: {"content":"Hello "}\n\nevent: chunk\ndata: {"content":"world"}\n\nevent: done\ndata: {}\n\n';
    mockFetchSSE(sse);

    const chunks: string[] = [];
    const { result } = renderHook(() => useSSE());

    await act(async () => {
      await result.current.sendMessage("test", [], {
        onChunk: (data) => chunks.push(data.content),
      });
    });

    expect(chunks).toEqual(["Hello ", "world"]);
  });

  it("parses citations event", async () => {
    const sse =
      'event: citations\ndata: {"citations":[{"index":1,"title":"Test","url":"https://example.com","snippet":"..."}]}\n\nevent: done\ndata: {}\n\n';
    mockFetchSSE(sse);

    const onCitations = vi.fn();
    const { result } = renderHook(() => useSSE());

    await act(async () => {
      await result.current.sendMessage("test", [], { onCitations });
    });

    expect(onCitations).toHaveBeenCalledWith({
      citations: [
        { index: 1, title: "Test", url: "https://example.com", snippet: "..." },
      ],
    });
  });

  it("skips malformed JSON without crashing", async () => {
    const sse =
      'event: chunk\ndata: {INVALID JSON}\n\nevent: chunk\ndata: {"content":"ok"}\n\nevent: done\ndata: {}\n\n';
    mockFetchSSE(sse);

    const chunks: string[] = [];
    const { result } = renderHook(() => useSSE());

    await act(async () => {
      await result.current.sendMessage("test", [], {
        onChunk: (data) => chunks.push(data.content),
      });
    });

    expect(chunks).toEqual(["ok"]);
  });

  it("calls onError for non-abort fetch failures", async () => {
    vi.spyOn(global, "fetch").mockRejectedValueOnce(new Error("Network error"));

    const onError = vi.fn();
    const { result } = renderHook(() => useSSE());

    await act(async () => {
      await result.current.sendMessage("test", [], { onError });
    });

    expect(onError).toHaveBeenCalledWith("Network error");
  });
});
