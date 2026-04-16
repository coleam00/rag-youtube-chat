import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Message } from '../components/Message';

describe('Message', () => {
  describe('TypingIndicator', () => {
    it('renders typing indicator when isStreaming is true and content is empty', () => {
      render(<Message role="assistant" content="" isStreaming={true} />);

      // The typing indicator has 3 dots with class "typing-dot"
      const dots = document.querySelectorAll('.typing-dot');
      expect(dots).toHaveLength(3);
    });

    it('does not render typing indicator when isStreaming is false', () => {
      render(<Message role="assistant" content="Hello" isStreaming={false} />);

      const dots = document.querySelectorAll('.typing-dot');
      expect(dots).toHaveLength(0);
    });

    it('does not render typing indicator when content is non-empty even if isStreaming is true', () => {
      render(<Message role="assistant" content="Hello world" isStreaming={true} />);

      // When content is non-empty, TypingIndicator doesn't render
      // instead MarkdownRenderer shows the content
      expect(screen.getByText('Hello world')).toBeInTheDocument();
    });
  });

  describe('SourceCitations', () => {
    it('renders source count button when sources are provided', () => {
      render(<Message role="assistant" content="Hello" sources={['Video 1', 'Video 2']} />);

      expect(screen.getByText('Sources (2)')).toBeInTheDocument();
    });

    it('does not render sources section when sources is empty array', () => {
      render(<Message role="assistant" content="Hello" sources={[]} />);

      expect(screen.queryByText(/Sources/)).not.toBeInTheDocument();
    });

    it('does not render sources section when sources is undefined', () => {
      render(<Message role="assistant" content="Hello" sources={undefined} />);

      expect(screen.queryByText(/Sources/)).not.toBeInTheDocument();
    });

    it('expands to show source chips when clicked', () => {
      render(<Message role="assistant" content="Hello" sources={['Video 1', 'Video 2']} />);

      const sourcesButton = screen.getByText('Sources (2)');
      fireEvent.click(sourcesButton);

      expect(screen.getByText('Video 1')).toBeInTheDocument();
      expect(screen.getByText('Video 2')).toBeInTheDocument();
    });

    it('collapses sources when clicked again', () => {
      render(<Message role="assistant" content="Hello" sources={['Video 1']} />);

      const sourcesButton = screen.getByText('Sources (1)');
      fireEvent.click(sourcesButton);
      expect(screen.getByText('Video 1')).toBeInTheDocument();

      fireEvent.click(sourcesButton);
      // After collapse, the video title should not be visible (chips are hidden)
      expect(screen.queryByText('Video 1')).not.toBeInTheDocument();
    });

    it('renders source chips with correct styling', () => {
      render(<Message role="assistant" content="Hello" sources={['Test Video']} />);

      const sourcesButton = screen.getByText('Sources (1)');
      fireEvent.click(sourcesButton);

      const chip = screen.getByText('Test Video');
      expect(chip).toBeInTheDocument();
    });
  });

  describe('user messages', () => {
    it('renders user message with plain text', () => {
      render(<Message role="user" content="Hello assistant" />);

      expect(screen.getByText('Hello assistant')).toBeInTheDocument();
    });

    it('does not show sources for user messages', () => {
      render(<Message role="user" content="Hello" sources={['Video 1']} />);

      expect(screen.queryByText(/Sources/)).not.toBeInTheDocument();
    });

    it('does not show typing indicator for user messages', () => {
      render(<Message role="user" content="" isStreaming={true} />);

      const dots = document.querySelectorAll('.typing-dot');
      expect(dots).toHaveLength(0);
    });
  });

  describe('assistant messages', () => {
    it('renders assistant message content', () => {
      render(<Message role="assistant" content="Hello user" />);

      expect(screen.getByText('Hello user')).toBeInTheDocument();
    });
  });
});
