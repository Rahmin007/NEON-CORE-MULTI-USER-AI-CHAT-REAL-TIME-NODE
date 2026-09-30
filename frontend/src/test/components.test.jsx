import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import ChatMessage from '../components/ChatMessage';
import Composer from '../components/Composer';
import { errorMessage } from '../lib/api';

describe('Composer', () => {
  it('sends on Enter and clears the box', async () => {
    const onSend = vi.fn(() => true);
    render(<Composer onSend={onSend} mutedSeconds={0} />);
    const box = screen.getByLabelText('Message');
    await userEvent.type(box, 'hello{Enter}');
    expect(onSend).toHaveBeenCalledWith('hello');
    expect(box).toHaveValue('');
  });

  it('adds a new line with Shift+Enter instead of sending', async () => {
    const onSend = vi.fn(() => true);
    render(<Composer onSend={onSend} mutedSeconds={0} />);
    await userEvent.type(screen.getByLabelText('Message'), 'line one{Shift>}{Enter}{/Shift}line two');
    expect(onSend).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Message')).toHaveValue('line one\nline two');
  });

  it('keeps the draft when sending fails (old bug: message was lost offline)', async () => {
    const onSend = vi.fn(() => false);
    render(<Composer onSend={onSend} mutedSeconds={0} />);
    await userEvent.type(screen.getByLabelText('Message'), 'important{Enter}');
    expect(screen.getByLabelText('Message')).toHaveValue('important');
  });

  it('is disabled with a countdown while muted', () => {
    render(<Composer onSend={() => true} mutedSeconds={125} />);
    expect(screen.getByLabelText('Message')).toBeDisabled();
    expect(screen.getByText('You are muted for 2m 05s.')).toBeInTheDocument();
  });
});

describe('ChatMessage', () => {
  const base = { id: '1', user_id: 'u1', username: 'alice', created_at: new Date().toISOString() };

  it('renders AI answers as Markdown', () => {
    render(<ChatMessage message={{ ...base, sender_role: 'AI', message: '**bold** and `code`' }} isOwn={false} canDelete={false} />);
    expect(screen.getByText('bold').tagName).toBe('STRONG');
    expect(screen.getByText('code').tagName).toBe('CODE');
  });

  it('shows user messages as plain text (no HTML injection)', () => {
    const { container } = render(
      <ChatMessage message={{ ...base, sender_role: 'USER', message: '<img src=x onerror=alert(1)>' }} isOwn={false} canDelete={false} />,
    );
    expect(container.querySelector('img')).toBeNull();
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
  });

  it('only shows the delete button to staff', () => {
    const { rerender } = render(<ChatMessage message={{ ...base, sender_role: 'USER', message: 'hi' }} isOwn={false} canDelete={false} />);
    expect(screen.queryByRole('button', { name: /delete/i })).toBeNull();
    rerender(<ChatMessage message={{ ...base, sender_role: 'USER', message: 'hi' }} isOwn={false} canDelete onDelete={() => {}} />);
    expect(screen.getByRole('button', { name: /delete message from alice/i })).toBeInTheDocument();
  });
});

describe('errorMessage', () => {
  it('reads FastAPI string and validation errors', () => {
    expect(errorMessage({ detail: 'Nope' }, 400)).toBe('Nope');
    expect(errorMessage({ detail: [{ loc: ['body', 'password'], msg: 'String should have at least 8 characters' }] }, 422)).toBe(
      'password: String should have at least 8 characters',
    );
    expect(errorMessage(null, 502)).toMatch(/server had a problem/);
  });
});
