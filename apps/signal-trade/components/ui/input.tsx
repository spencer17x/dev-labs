import * as React from 'react';

import { cn } from '@/lib/utils';

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'flex h-11 w-full rounded-2xl border border-border bg-[color:var(--color-panel-soft)] px-4 py-2 text-sm text-foreground outline-none transition-colors',
        'placeholder:text-muted-foreground focus:border-[color:var(--color-accent)] focus:bg-white',
        className,
      )}
      {...props}
    />
  ),
);

Input.displayName = 'Input';
