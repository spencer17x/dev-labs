import * as React from 'react';

import { cn } from '@/lib/utils';

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      'flex min-h-[108px] w-full rounded-2xl border border-border bg-[color:var(--color-panel-soft)] px-4 py-3 text-sm text-foreground outline-none transition-colors',
      'placeholder:text-muted-foreground focus:border-[color:var(--color-accent)] focus:bg-white',
      className,
    )}
    {...props}
  />
));

Textarea.displayName = 'Textarea';
