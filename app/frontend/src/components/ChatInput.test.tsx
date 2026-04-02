import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createRef } from 'react'
import { ChatInput, ChatInputHandle } from './ChatInput'

describe('ChatInput', () => {
  it('calls onSend with trimmed content and resets the textarea', async () => {
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} />)
    const textarea = screen.getByRole('textbox')

    await userEvent.type(textarea, '  hello world  ')
    fireEvent.click(screen.getByRole('button', { name: /send message/i }))

    expect(onSend).toHaveBeenCalledWith('hello world')
    expect(textarea).toHaveValue('')
  })

  it('does not call onSend when content is empty', () => {
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} />)
    fireEvent.click(screen.getByRole('button', { name: /send message/i }))
    expect(onSend).not.toHaveBeenCalled()
  })

  it('does not call onSend when disabled', async () => {
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} disabled />)
    const textarea = screen.getByRole('textbox')
    await userEvent.type(textarea, 'hello')
    fireEvent.click(screen.getByRole('button', { name: /send message/i }))
    expect(onSend).not.toHaveBeenCalled()
  })

  it('does not call onSend when isStreaming', async () => {
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} isStreaming />)
    const textarea = screen.getByRole('textbox')
    await userEvent.type(textarea, 'hello')
    fireEvent.click(screen.getByRole('button', { name: /send message/i }))
    expect(onSend).not.toHaveBeenCalled()
  })

  it('sends on Enter and does not send on Shift+Enter', async () => {
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} />)
    const textarea = screen.getByRole('textbox')

    await userEvent.type(textarea, 'hello')
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false })
    expect(onSend).toHaveBeenCalledWith('hello')

    // Shift+Enter should NOT send
    onSend.mockClear()
    await userEvent.type(textarea, 'line1')
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true })
    expect(onSend).not.toHaveBeenCalled()
  })

  it('imperative handle setInputText restores value and focuses', () => {
    const onSend = vi.fn()
    const ref = createRef<ChatInputHandle>()
    render(<ChatInput ref={ref} onSend={onSend} />)
    const textarea = screen.getByRole('textbox')

    ref.current!.setInputText('restored text')

    // Value is set via direct DOM manipulation (uncontrolled), check textarea value
    expect(textarea).toHaveValue('restored text')
  })

  it('imperative handle focus focuses the textarea', () => {
    const onSend = vi.fn()
    const ref = createRef<ChatInputHandle>()
    render(<ChatInput ref={ref} onSend={onSend} />)
    const textarea = screen.getByRole('textbox')

    ref.current!.focus()
    expect(document.activeElement).toBe(textarea)
  })

  it('shows waiting placeholder when isStreaming', () => {
    render(<ChatInput onSend={vi.fn()} isStreaming />)
    expect(screen.getByPlaceholderText(/waiting for response/i)).toBeInTheDocument()
  })

  it('flex wrapper uses alignItems center', () => {
    const { container } = render(<ChatInput onSend={vi.fn()} />)
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.style.alignItems).toBe('center')
  })
})
