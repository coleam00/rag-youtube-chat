import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Conversation, Message } from './api';

vi.mock('file-saver', () => ({ saveAs: vi.fn() }));

import { saveAs } from 'file-saver';
import {
  exportConversationAsMarkdown,
  formatCitation,
  formatSources,
  formatTimestamp,
} from './exportMarkdown';

describe('exportConversationAsMarkdown', () => {
  beforeEach(() => {
    // biome-ignore lint/suspicious/noExplicitAny: vi.mocked() not available in this environment
    (saveAs as any).mockClear();
  });

  it('should format header with title and ISO timestamp', async () => {
    const conv: Conversation = { id: '1', title: 'Test Chat', created_at: '', updated_at: '' };
    const messages: Message[] = [];

    exportConversationAsMarkdown(conv, messages);

    // biome-ignore lint/suspicious/noExplicitAny: vi.mocked() not available in this environment
    const blob = (saveAs as any).mock.calls[0][0] as Blob;
    const text = await blob.text();
    expect(text).toMatch(/^# Test Chat\n\n\d{4}-\d{2}-\d{2}T/);
  });

  it('should map user role to **You:** and assistant to **Assistant:**', async () => {
    const conv: Conversation = { id: '1', title: 'Chat', created_at: '', updated_at: '' };
    const messages: Message[] = [
      { id: '1', conversation_id: '1', role: 'user', content: 'Hello', created_at: '' },
      { id: '2', conversation_id: '1', role: 'assistant', content: 'Hi there', created_at: '' },
    ];

    exportConversationAsMarkdown(conv, messages);

    // biome-ignore lint/suspicious/noExplicitAny: vi.mocked() not available in this environment
    const blob = (saveAs as any).mock.calls[0][0] as Blob;
    const text = await blob.text();
    expect(text).toContain('**You:** Hello');
    expect(text).toContain('**Assistant:** Hi there');
  });

  it('should generate valid filename slug', () => {
    const conv: Conversation = {
      id: '1',
      title: '  My Video: Episode 1  ',
      created_at: '',
      updated_at: '',
    };
    const messages: Message[] = [];

    exportConversationAsMarkdown(conv, messages);

    // biome-ignore lint/suspicious/noExplicitAny: vi.mocked() not available in this environment
    const filename = (saveAs as any).mock.calls[0][1];
    expect(filename).toMatch(/^conversation-my-video-episode-1-\d{4}-\d{2}-\d{2}\.md$/);
  });

  it('should handle empty messages array', async () => {
    const conv: Conversation = { id: '1', title: 'Empty Chat', created_at: '', updated_at: '' };

    exportConversationAsMarkdown(conv, []);

    // biome-ignore lint/suspicious/noExplicitAny: vi.mocked() not available in this environment
    const blob = (saveAs as any).mock.calls[0][0] as Blob;
    const text = await blob.text();
    expect(text).toContain('# Empty Chat');
    expect(text).toContain('---');
  });

  it('should handle special markdown characters in content', async () => {
    const conv: Conversation = { id: '1', title: 'Chat', created_at: '', updated_at: '' };
    const messages: Message[] = [
      { id: '1', conversation_id: '1', role: 'user', content: '# Warning', created_at: '' },
    ];

    exportConversationAsMarkdown(conv, messages);

    // biome-ignore lint/suspicious/noExplicitAny: vi.mocked() not available in this environment
    const blob = (saveAs as any).mock.calls[0][0] as Blob;
    const text = await blob.text();
    expect(text).toContain('**You:** # Warning');
  });

  it('should include formatted sources for assistant messages with sources', async () => {
    const conv: Conversation = { id: '1', title: 'Chat', created_at: '', updated_at: '' };
    const messages: Message[] = [
      {
        id: '1',
        conversation_id: '1',
        role: 'assistant',
        content: 'Here is the answer.',
        created_at: '',
        sources: [
          {
            chunk_id: 'chunk-1',
            video_id: 'vid-1',
            video_title: 'Source Video',
            video_url: 'https://www.youtube.com/watch?v=abc123',
            start_seconds: 30,
            end_seconds: 45,
            snippet: 'Relevant text',
          },
        ],
      },
    ];

    exportConversationAsMarkdown(conv, messages);

    // biome-ignore lint/suspicious/noExplicitAny: vi.mocked() not available in this environment
    const blob = (saveAs as any).mock.calls[0][0] as Blob;
    const text = await blob.text();
    expect(text).toContain('**Assistant:** Here is the answer.');
    expect(text).toContain('**Sources:**');
    expect(text).toContain('[Source Video](https://www.youtube.com/watch?v=abc123&t=30s)');
    expect(text).toContain('0:30–0:45');
    expect(text).toContain('> "Relevant text"');
  });

  it('should not include Sources header when message has empty sources array', async () => {
    const conv: Conversation = { id: '1', title: 'Chat', created_at: '', updated_at: '' };
    const messages: Message[] = [
      {
        id: '1',
        conversation_id: '1',
        role: 'assistant',
        content: 'Answer.',
        created_at: '',
        sources: [],
      },
    ];

    exportConversationAsMarkdown(conv, messages);

    // biome-ignore lint/suspicious/noExplicitAny: vi.mocked() not available in this environment
    const blob = (saveAs as any).mock.calls[0][0] as Blob;
    const text = await blob.text();
    expect(text).not.toContain('**Sources:**');
  });

  it('should not include Sources section when message has no sources property', async () => {
    const conv: Conversation = { id: '1', title: 'Chat', created_at: '', updated_at: '' };
    const messages: Message[] = [
      { id: '1', conversation_id: '1', role: 'assistant', content: 'Answer.', created_at: '' },
    ];

    exportConversationAsMarkdown(conv, messages);

    // biome-ignore lint/suspicious/noExplicitAny: vi.mocked() not available in this environment
    const blob = (saveAs as any).mock.calls[0][0] as Blob;
    const text = await blob.text();
    expect(text).not.toContain('**Sources:**');
  });
});

describe('formatTimestamp', () => {
  it('should format 0 seconds as 0:00', () => {
    expect(formatTimestamp(0)).toBe('0:00');
  });

  it('should format 59 seconds as 0:59', () => {
    expect(formatTimestamp(59)).toBe('0:59');
  });

  it('should format 60 seconds as 1:00', () => {
    expect(formatTimestamp(60)).toBe('1:00');
  });

  it('should format 65 seconds as 1:05', () => {
    expect(formatTimestamp(65)).toBe('1:05');
  });

  it('should format 3600 seconds as 60:00', () => {
    expect(formatTimestamp(3600)).toBe('60:00');
  });

  it('should floor fractional seconds', () => {
    expect(formatTimestamp(5.9)).toBe('0:05');
  });

  it('should handle large values correctly', () => {
    expect(formatTimestamp(3661)).toBe('61:01');
  });
});

describe('formatCitation', () => {
  const baseCitation = {
    chunk_id: 'chunk-1',
    video_id: 'vid-1',
    video_title: 'Test Video Title',
    video_url: 'https://www.youtube.com/watch?v=abc123',
    start_seconds: 10,
    end_seconds: 20,
    snippet: 'Test snippet text',
  };

  it('should return empty string for empty snippet', () => {
    expect(formatCitation({ ...baseCitation, snippet: '' })).toBe('');
    expect(formatCitation({ ...baseCitation, snippet: '   ' })).toBe('');
    expect(formatCitation({ ...baseCitation, snippet: undefined as unknown as string })).toBe('');
  });

  it('should format citation with full video URL', () => {
    const result = formatCitation(baseCitation);
    expect(result).toContain('[Test Video Title](https://www.youtube.com/watch?v=abc123&t=10s)');
    expect(result).toContain('0:10–0:20');
    expect(result).toContain('> "Test snippet text"');
  });

  it('should fall back to title-only with unavailable text when URL is invalid', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const citation = { ...baseCitation, video_url: 'not-a-url' };
    const result = formatCitation(citation);
    expect(result).toContain('Test Video Title');
    expect(result).not.toContain('[Test Video Title](');
    expect(result).toContain('(timestamp link unavailable)');
    expect(result).toContain('0:10–0:20');
    expect(warnSpy).toHaveBeenCalledWith(
      '[exportMarkdown] Skipping timestamp link — invalid video_url: "not-a-url"',
    );
    warnSpy.mockRestore();
  });

  it('should fall back when video_url has no v param', () => {
    const citation = { ...baseCitation, video_url: 'https://www.youtube.com/' };
    const result = formatCitation(citation);
    expect(result).not.toContain('[Test Video Title](https://www.youtube.com/watch?v=');
    expect(result).toContain('Test Video Title');
    expect(result).toContain('(timestamp link unavailable)');
  });

  it('should format with empty video_title', () => {
    const citation = { ...baseCitation, video_title: '' };
    const result = formatCitation(citation);
    expect(result).toContain('— 0:10–0:20');
  });
});

describe('formatSources', () => {
  const mockCitation = {
    chunk_id: 'chunk-1',
    video_id: 'vid-1',
    video_title: 'Test Video',
    video_url: 'https://www.youtube.com/watch?v=abc123',
    start_seconds: 10,
    end_seconds: 20,
    snippet: 'Test snippet',
  };

  it('should return empty string for empty array', () => {
    expect(formatSources([])).toBe('');
  });

  it('should return empty string for null', () => {
    // biome-ignore lint/suspicious/noExplicitAny: testing null guard
    expect(formatSources(null as any)).toBe('');
  });

  it('should return empty string for undefined', () => {
    // biome-ignore lint/suspicious/noExplicitAny: testing undefined guard
    expect(formatSources(undefined as any)).toBe('');
  });

  it('should format single citation with header', () => {
    const result = formatSources([mockCitation]);
    expect(result).toContain('**Sources:**');
    expect(result).toContain('- [Test Video]');
  });

  it('should join multiple citations with newline', () => {
    const result = formatSources([mockCitation, { ...mockCitation, chunk_id: 'chunk-2' }]);
    expect(result.split('- [Test Video]').length).toBe(3);
  });
});
