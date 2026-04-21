import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { me } from '../lib/authApi';

describe('me() dedup', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function deferredJson(body: unknown, status = 200) {
    let resolveFn!: () => void;
    const gate = new Promise<void>((resolve) => {
      resolveFn = resolve;
    });
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementationOnce(async () => {
      await gate;
      return {
        ok: status >= 200 && status < 300,
        status,
        statusText: 'OK',
        json: async () => body,
        text: async () => JSON.stringify(body),
      };
    });
    return { release: resolveFn };
  }

  it('coalesces concurrent callers into a single fetch (regression for issue #115)', async () => {
    const { release } = deferredJson({
      id: 'u1',
      email: 'a@b.com',
      is_admin: false,
      messages_used_today: 0,
      messages_remaining_today: 25,
      rate_window_resets_at: null,
    });

    const callers = [me(), me(), me(), me(), me(), me(), me()];

    // Every caller shares the same promise while the fetch is in flight.
    expect(callers.every((p) => p === callers[0])).toBe(true);

    release();
    await Promise.all(callers);

    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('re-fetches after the previous call settles', async () => {
    const first = deferredJson({
      id: 'u1',
      email: 'a@b.com',
      is_admin: false,
      messages_used_today: 0,
      messages_remaining_today: 25,
      rate_window_resets_at: null,
    });
    first.release();
    await me();
    expect(fetch).toHaveBeenCalledTimes(1);

    const second = deferredJson({
      id: 'u1',
      email: 'a@b.com',
      is_admin: false,
      messages_used_today: 1,
      messages_remaining_today: 24,
      rate_window_resets_at: null,
    });
    second.release();
    await me();
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
