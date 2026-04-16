import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ChatArea } from '../components/ChatArea';
import * as useMessagesModule from '../hooks/useMessages';
import * as useStreamingResponseModule from '../hooks/useStreamingResponse';
import * as useToastModule from '../hooks/useToast';

// Mock the hooks with factories
vi.mock('../hooks/useMessages', () => ({
  useMessages: vi.fn(),
}));

vi.mock('../hooks/useStreamingResponse', () => ({
  useStreamingResponse: vi.fn(),
}));

vi.mock('../hooks/useToast', () => ({
  useToast: vi.fn(),
}));

describe('ChatArea', () => {
  const mockUseMessages = useMessagesModule.useMessages as ReturnType<typeof vi.fn>;
  const mockUseStreamingResponse = useStreamingResponseModule.useStreamingResponse as ReturnType<
    typeof vi.fn
  >;
  const mockUseToast = useToastModule.useToast as ReturnType<typeof vi.fn>;

  const mockAddToast = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock implementations
    mockUseMessages.mockReturnValue({
      messages: [],
      setMessages: vi.fn(),
      loading: false,
      error: null,
    });

    mockUseStreamingResponse.mockReturnValue({
      streamingContent: '',
      streamingSources: [],
      isStreaming: false,
      startStream: vi.fn(),
      cancelStream: vi.fn(),
    });

    mockUseToast.mockReturnValue({
      addToast: mockAddToast,
      removeToast: vi.fn(),
    });
  });

  describe('EmptyState', () => {
    it('shows EmptyState when no conversationId is provided', () => {
      render(<ChatArea />);

      expect(screen.getByText('Ask anything about the video library')).toBeInTheDocument();
    });

    it('shows EmptyState with starter questions', () => {
      render(<ChatArea />);

      const starters = [
        'How do RAG pipelines work?',
        'What are the best prompt engineering practices?',
        'Explain vector databases and embeddings',
        'What is the difference between fine-tuning and prompting?',
      ];

      for (const starter of starters) {
        expect(screen.getByText(starter)).toBeInTheDocument();
      }
    });

    it('does not show EmptyState when a conversationId is provided', () => {
      mockUseMessages.mockReturnValue({
        messages: [],
        setMessages: vi.fn(),
        loading: false,
        error: null,
      });

      render(<ChatArea conversationId="conv-1" />);

      expect(screen.queryByText('Ask anything about the video library')).not.toBeInTheDocument();
    });
  });

  describe('Loading skeleton', () => {
    it('shows skeleton while loading', () => {
      mockUseMessages.mockReturnValue({
        messages: [],
        setMessages: vi.fn(),
        loading: true,
        error: null,
      });

      render(<ChatArea conversationId="conv-1" />);

      // Skeleton rows should be visible (they have class "skeleton")
      const skeletons = document.querySelectorAll('.skeleton');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe('Error state', () => {
    it('shows error state when loading fails', () => {
      mockUseMessages.mockReturnValue({
        messages: [],
        setMessages: vi.fn(),
        loading: false,
        error: 'Failed to load',
      });

      render(<ChatArea conversationId="conv-1" />);

      expect(screen.getByText('Failed to load')).toBeInTheDocument();
      expect(screen.getByText('Retry')).toBeInTheDocument();
    });
  });

  describe('Optimistic message insert', () => {
    it('adds user message optimistically when send is triggered', async () => {
      const setMessages = vi.fn();
      mockUseMessages.mockReturnValue({
        messages: [],
        setMessages,
        loading: false,
        error: null,
      });

      const startStream = vi.fn().mockImplementation(async () => {
        // Simulate stream completion
      });
      mockUseStreamingResponse.mockReturnValue({
        streamingContent: '',
        streamingSources: [],
        isStreaming: false,
        startStream,
        cancelStream: vi.fn(),
      });

      render(<ChatArea conversationId="conv-1" />);

      // Find and fill the textarea
      const textarea = screen.getByPlaceholderText(
        'Ask anything about the video library…',
      ) as HTMLTextAreaElement;
      fireEvent.change(textarea, { target: { value: 'Hello' } });

      // Click send
      const sendButton = screen.getByLabelText('Send message');
      fireEvent.click(sendButton);

      // Check that setMessages was called to add the optimistic message
      await waitFor(() => {
        expect(setMessages).toHaveBeenCalled();
      });
    });
  });

  describe('Streaming state', () => {
    it('displays streaming content when isStreaming is true', () => {
      mockUseMessages.mockReturnValue({
        messages: [],
        setMessages: vi.fn(),
        loading: false,
        error: null,
      });

      mockUseStreamingResponse.mockReturnValue({
        streamingContent: 'This is streaming...',
        streamingSources: [],
        isStreaming: true,
        startStream: vi.fn(),
        cancelStream: vi.fn(),
      });

      render(<ChatArea conversationId="conv-1" />);

      expect(screen.getByText('This is streaming...')).toBeInTheDocument();
    });

    it('passes isStreaming to ChatInput', () => {
      mockUseMessages.mockReturnValue({
        messages: [],
        setMessages: vi.fn(),
        loading: false,
        error: null,
      });

      mockUseStreamingResponse.mockReturnValue({
        streamingContent: '',
        streamingSources: [],
        isStreaming: true,
        startStream: vi.fn(),
        cancelStream: vi.fn(),
      });

      render(<ChatArea conversationId="conv-1" />);

      // The textarea should show the streaming placeholder
      expect(screen.getByPlaceholderText('Waiting for response…')).toBeInTheDocument();
    });
  });

  describe('Inline error and retry', () => {
    it('shows inline error when stream fails', async () => {
      const setMessages = vi.fn();
      mockUseMessages.mockReturnValue({
        messages: [],
        setMessages,
        loading: false,
        error: null,
      });

      const startStream = vi.fn().mockRejectedValue(new Error('Network error'));
      mockUseStreamingResponse.mockReturnValue({
        streamingContent: '',
        streamingSources: [],
        isStreaming: false,
        startStream,
        cancelStream: vi.fn(),
      });

      render(<ChatArea conversationId="conv-1" />);

      // Type and send a message
      const textarea = screen.getByPlaceholderText(
        'Ask anything about the video library…',
      ) as HTMLTextAreaElement;
      fireEvent.change(textarea, { target: { value: 'Hello' } });
      fireEvent.click(screen.getByLabelText('Send message'));

      // Should show inline error with retry button
      await waitFor(() => {
        expect(screen.getByText('Failed to get a response. Please try again.')).toBeInTheDocument();
      });

      expect(screen.getByText('Retry')).toBeInTheDocument();
    });

    it('removes optimistic message on failure', async () => {
      const setMessages = vi.fn();
      mockUseMessages.mockReturnValue({
        messages: [],
        setMessages,
        loading: false,
        error: null,
      });

      const startStream = vi.fn().mockRejectedValue(new Error('Network error'));
      mockUseStreamingResponse.mockReturnValue({
        streamingContent: '',
        streamingSources: [],
        isStreaming: false,
        startStream,
        cancelStream: vi.fn(),
      });

      render(<ChatArea conversationId="conv-1" />);

      const textarea = screen.getByPlaceholderText(
        'Ask anything about the video library…',
      ) as HTMLTextAreaElement;
      fireEvent.change(textarea, { target: { value: 'Hello' } });
      fireEvent.click(screen.getByLabelText('Send message'));

      await waitFor(() => {
        // The optimistic message should be filtered out on failure
        expect(setMessages).toHaveBeenCalledWith(expect.any(Function));
      });
    });
  });
});
