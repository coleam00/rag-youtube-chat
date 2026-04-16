// Vitest setup — runs before each test file.
//
// Adds `@testing-library/jest-dom` matchers (`toBeInTheDocument`, etc.)
// to Vitest's `expect`. See CLAUDE.md §Testing for frontend test conventions.

import { vi } from 'vitest';
import '@testing-library/jest-dom/vitest';

// jsdom does not implement scrollIntoView — mock it so components that call
// bottomRef.current?.scrollIntoView() can be tested in jsdom without errors.
Object.defineProperty(Element.prototype, 'scrollIntoView', {
  writable: true,
  value: vi.fn(),
});
