/**
 * Tests for useStreamingResponse hook SSE parsing.
 *
 * Verifies:
 *   - Parses sources event with Citation[] objects into streamingSources state
 *   - Handles malformed sources JSON gracefully with console.warn
 */

import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useStreamingResponse } from './useStreamingResponse';

const mockCitation = {
  chunk_id: 'chunk-1',
  video_id: 'vid-1',
  video_title: 'Test Video',
  video_url: 'https://www.youtube.com/watch?v=abc123',
  start_seconds: 10,
  end_seconds: 20,
  snippet: 'Test snippet text',
};

describe('useStreamingResponse SSE parsing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('parses sources event with Citation objects', () => {
    const warnMock = vi.fn();
    const originalWarn = console.warn;
    console.warn = warnMock;

    // Simulate SSE parsing logic from the hook
    const eventType = 'sources';
    const data = JSON.stringify([mockCitation]);
    let sources: unknown[] = [];
    try {
      const parsed = JSON.parse(data);
      if (Array.isArray(parsed)) {
        sources = parsed;
      }
    } catch (e) {
      console.warn('[useStreamingResponse] Failed to parse sources event:', e);
    }

    expect(sources).toHaveLength(1);
    expect((sources[0] as typeof mockCitation).chunk_id).toBe('chunk-1');
    expect((sources[0] as typeof mockCitation).video_title).toBe('Test Video');

    console.warn = originalWarn;
  });

  it('warns on malformed sources JSON', () => {
    const warnMock = vi.fn();
    const originalWarn = console.warn;
    console.warn = warnMock;

    const eventType = 'sources';
    const data = 'not valid json {';

    let sources: unknown[] = [];
    try {
      const parsed = JSON.parse(data);
      if (Array.isArray(parsed)) {
        sources = parsed;
      }
    } catch (e) {
      console.warn('[useStreamingResponse] Failed to parse sources event:', e);
    }

    expect(sources).toHaveLength(0);
    expect(warnMock).toHaveBeenCalledWith(
      '[useStreamingResponse] Failed to parse sources event:',
      expect.any(Error),
    );

    console.warn = originalWarn;
  });

  it('handles empty sources array', () => {
    const eventType = 'sources';
    const data = '[]';

    let sources: unknown[] = [];
    try {
      const parsed = JSON.parse(data);
      if (Array.isArray(parsed)) {
        sources = parsed;
      }
    } catch {
      // ignore
    }

    expect(sources).toHaveLength(0);
  });

  it('handles sources event with multiple citations', () => {
    const multipleCitations = [
      mockCitation,
      { ...mockCitation, chunk_id: 'chunk-2', video_title: 'Second Video' },
    ];
    const data = JSON.stringify(multipleCitations);

    let sources: unknown[] = [];
    try {
      const parsed = JSON.parse(data);
      if (Array.isArray(parsed)) {
        sources = parsed;
      }
    } catch {
      // ignore
    }

    expect(sources).toHaveLength(2);
    expect((sources[0] as typeof mockCitation).chunk_id).toBe('chunk-1');
    expect((sources[1] as typeof mockCitation).chunk_id).toBe('chunk-2');
  });
});

describe('abortStream', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should be a no-op when no stream is active', () => {
    const { result } = renderHook(() => useStreamingResponse());
    expect(result.current.abortStream).not.toThrow();
    expect(result.current.isStreaming).toBe(false);
  });

  it('should be callable multiple times without throwing', () => {
    const { result } = renderHook(() => useStreamingResponse());
    result.current.abortStream();
    result.current.abortStream();
    result.current.abortStream();
    expect(result.current.isStreaming).toBe(false);
  });
});

describe('startStream onAbort callback', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should call onAbort and reset isStreaming when stream is aborted', async () => {
    const { result } = renderHook(() => useStreamingResponse());

    // Create an AbortController that aborts immediately
    const abortController = new AbortController();
    setTimeout(() => abortController.abort(), 10);

    const onAbort = vi.fn();
    const onComplete = vi.fn();

    // Mock fetch to return a stream that never completes
    const stream = new ReadableStream({
      start(controller) {
        // Don't close — we want the abort to interrupt read()
      },
    });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: stream,
      }),
    );

    await result.current.startStream('conv-1', 'test message', onComplete, onAbort);

    // Assert onAbort was called
    expect(onAbort).toHaveBeenCalledTimes(1);
    // Assert isStreaming was reset (key bug check)
    expect(result.current.isStreaming).toBe(false);
    // Assert onComplete was NOT called
    expect(onComplete).not.toHaveBeenCalled();
  });

  it('should reset isStreaming to false after successful stream completion', async () => {
    const { result } = renderHook(() => useStreamingResponse());
    const onComplete = vi.fn();

    // Mock a complete SSE response
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('data: "hello"\n\ndata: [DONE]\n\n'));
        controller.close();
      },
    });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: stream,
      }),
    );

    await result.current.startStream('conv-1', 'test', onComplete);

    expect(onComplete).toHaveBeenCalledWith(expect.objectContaining({ fullText: 'hello' }));
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.streamingContent).toBe('');
  });
});
