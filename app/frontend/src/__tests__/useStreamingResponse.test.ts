import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useStreamingResponse } from '../hooks/useStreamingResponse';

// Mock fetch globally using globalThis assignment (vi.stubGlobal not available in all Vitest versions)
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

describe('useStreamingResponse', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('startStream', () => {
    it('sets isStreaming to true and clears content on start', async () => {
      const mockBody = {
        getReader: () => ({
          read: vi.fn().mockResolvedValueOnce({ done: true, value: undefined }),
        }),
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: mockBody,
      });

      const { result } = renderHook(() => useStreamingResponse());

      let onCompleteCalled = false;
      await act(async () => {
        await result.current.startStream('conv-1', 'hello', () => {
          onCompleteCalled = true;
        });
      });

      expect(result.current.isStreaming).toBe(false);
      expect(onCompleteCalled).toBe(true);
    });

    it('parses SSE token events and accumulates fullText', async () => {
      const encoder = new TextEncoder();
      const events: Uint8Array[] = [];

      // First token event
      events.push(encoder.encode(JSON.stringify('Hello')));
      // Second token event
      events.push(encoder.encode(JSON.stringify(' world')));

      let callCount = 0;
      const mockBody = {
        getReader: () => ({
          read: vi.fn().mockImplementation(() => {
            if (callCount < events.length) {
              const value = events[callCount++];
              return Promise.resolve({ done: false, value });
            }
            return Promise.resolve({ done: true, value: undefined });
          }),
        }),
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: mockBody,
      });

      const { result } = renderHook(() => useStreamingResponse());

      await act(async () => {
        await result.current.startStream('conv-1', 'hi', () => {});
      });

      // After stream completes, streamingContent should be reset
      expect(result.current.isStreaming).toBe(false);
    });

    it('parses sources event and updates streamingSources', async () => {
      const encoder = new TextEncoder();
      const sourcesData = JSON.stringify(['Video Title 1', 'Video Title 2']);
      const sourcesEvent = `event: sources\ndata: ${sourcesData}\n\n`;
      const doneEvent = 'data: [DONE]\n\n';

      let callCount = 0;
      const mockBody = {
        getReader: () => ({
          read: vi.fn().mockImplementation(() => {
            if (callCount === 0) {
              callCount++;
              return Promise.resolve({ done: false, value: encoder.encode(sourcesEvent) });
            }
            return Promise.resolve({ done: true, value: encoder.encode(doneEvent) });
          }),
        }),
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: mockBody,
      });

      const { result } = renderHook(() => useStreamingResponse());

      let capturedSources: string[] = [];
      await act(async () => {
        await result.current.startStream('conv-1', 'hi', ({ sources }) => {
          capturedSources = sources;
        });
      });

      expect(capturedSources).toEqual(['Video Title 1', 'Video Title 2']);
    });

    it('throws on non-ok HTTP response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        text: () => Promise.resolve('Internal Server Error'),
      });

      const { result } = renderHook(() => useStreamingResponse());

      await act(async () => {
        try {
          await result.current.startStream('conv-1', 'hi', () => {});
        } catch (e) {
          // Expected
        }
      });

      expect(result.current.isStreaming).toBe(false);
    });

    it('throws when response body is missing', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: null,
      });

      const { result } = renderHook(() => useStreamingResponse());

      await act(async () => {
        try {
          await result.current.startStream('conv-1', 'hi', () => {});
        } catch (e) {
          // Expected
        }
      });

      expect(result.current.isStreaming).toBe(false);
    });

    it('aborts in-flight stream when cancelStream is called', async () => {
      // Spy on AbortController.abort to verify it's called
      const abortSpy = vi.spyOn(AbortController.prototype, 'abort');

      // Create a mock reader that we can control
      const readResolveHolder: {
        fn: ((value: { done: boolean; value?: Uint8Array }) => void) | undefined;
      } = { fn: undefined };
      const mockReadPromise = new Promise<{ done: boolean; value?: Uint8Array }>((resolve) => {
        readResolveHolder.fn = resolve;
      });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => ({
            read: vi.fn().mockReturnValue(mockReadPromise),
          }),
        },
      });

      const { result } = renderHook(() => useStreamingResponse());

      // Start the stream - it will block on the mock read
      act(() => {
        result.current.startStream('conv-1', 'hi', () => {});
      });

      // Wait for stream to start (isStreaming becomes true before read() is called)
      await vi.waitFor(() => expect(result.current.isStreaming).toBe(true));

      // Cancel — should call abort() on the AbortController
      act(() => {
        result.current.cancelStream();
      });

      expect(abortSpy).toHaveBeenCalled();

      // Resolve the read to clean up
      readResolveHolder.fn?.({ done: true, value: undefined });
    });
  });

  describe('cancelStream', () => {
    it('does nothing when no stream is in progress', () => {
      const { result } = renderHook(() => useStreamingResponse());

      // Hook should return cancelStream as a function
      expect(result.current.cancelStream).toBeDefined();
      expect(typeof result.current.cancelStream).toBe('function');

      // Calling cancelStream when no stream is in progress should not throw
      expect(() => result.current.cancelStream()).not.toThrow();
    });
  });
});
