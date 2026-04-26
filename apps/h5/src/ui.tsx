import type { ButtonHTMLAttributes, ReactNode, TextareaHTMLAttributes } from 'react'

function cx(...names: Array<string | false | null | undefined>) {
  return names.filter(Boolean).join(' ')
}

export function UiButton({ variant = 'secondary', className, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'text' }) {
  return <button className={cx('ui-button', variant, className)} {...props}>{children}</button>
}

export function UiCard({ className, children }: { className?: string; children: ReactNode }) {
  return <section className={cx('ui-card', className)}>{children}</section>
}

export function UiBadge({ tone = 'default', className, children }: { tone?: 'default' | 'ai' | 'success' | 'warning' | 'danger'; className?: string; children: ReactNode }) {
  return <span className={cx('ui-badge', tone, className)}>{children}</span>
}

export function UiTextArea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cx('ui-textarea', className)} {...props} />
}
