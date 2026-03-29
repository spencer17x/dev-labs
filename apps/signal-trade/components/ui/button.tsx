import * as React from 'react';

import { cn } from '@/lib/utils';

type ButtonVariant = 'default' | 'secondary' | 'ghost' | 'outline';
type ButtonSize = 'default' | 'sm' | 'lg' | 'icon';

const variantClasses: Record<ButtonVariant, string> = {
  default:
    'bg-[color:var(--color-accent)] text-[color:var(--color-accent-foreground)] shadow-[0_12px_30px_rgba(220,88,42,0.24)] hover:bg-[color:var(--color-accent-strong)]',
  secondary:
    'bg-[color:var(--color-panel-muted)] text-foreground hover:bg-[color:var(--color-panel-strong)]',
  ghost:
    'bg-transparent text-muted-foreground hover:bg-[color:var(--color-panel-soft)] hover:text-foreground',
  outline:
    'border border-border bg-transparent text-foreground hover:bg-[color:var(--color-panel-soft)]',
};

const sizeClasses: Record<ButtonSize, string> = {
  default: 'h-10 px-4 py-2',
  sm: 'h-8 rounded-full px-3 text-xs',
  lg: 'h-12 px-5 text-sm',
  icon: 'h-10 w-10',
};

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, size = 'default', variant = 'default', ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-2xl text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--color-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-background',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    />
  ),
);

Button.displayName = 'Button';
