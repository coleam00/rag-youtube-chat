import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import App from '../App'

// Mock heavy child components that make API calls or are out of scope
vi.mock('../components/Sidebar', () => ({
  Sidebar: ({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) => (
    <div data-testid="sidebar" data-open={isOpen}>
      <button aria-label="Close sidebar" onClick={onClose}>
        Close
      </button>
    </div>
  ),
}))

vi.mock('../components/ChatArea', () => ({
  ChatArea: () => <div data-testid="chat-area" />,
}))

vi.mock('../components/ToastProvider', () => ({
  ToastProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

describe('AppLayout — hamburger button visibility', () => {
  it('renders hamburger button when sidebar is closed (initial state)', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument()
  })

  it('hides hamburger button after clicking it (sidebar opens)', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /open sidebar/i }))

    expect(screen.queryByRole('button', { name: /open sidebar/i })).not.toBeInTheDocument()
  })

  it('shows hamburger button again after sidebar closes via overlay', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /open sidebar/i }))
    // Overlay is rendered by AppLayout when sidebarOpen === true
    const overlay = document.querySelector('.sidebar-overlay') as HTMLElement
    expect(overlay).not.toBeNull()
    await user.click(overlay)

    expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument()
  })

  it('shows hamburger button again after sidebar closes via Sidebar onClose prop', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /open sidebar/i }))
    await user.click(screen.getByRole('button', { name: /close sidebar/i }))

    expect(screen.getByRole('button', { name: /open sidebar/i })).toBeInTheDocument()
  })

  it('hamburger button has correct aria-label', () => {
    render(<App />)
    expect(screen.getByRole('button', { name: /open sidebar/i })).toHaveAttribute(
      'aria-label',
      'Open sidebar'
    )
  })

  it('overlay is not rendered when sidebar is closed', () => {
    render(<App />)
    expect(document.querySelector('.sidebar-overlay')).toBeNull()
  })

  it('overlay is rendered when sidebar is open', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /open sidebar/i }))

    expect(document.querySelector('.sidebar-overlay')).not.toBeNull()
  })
})
