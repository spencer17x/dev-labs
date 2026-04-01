import * as React from 'react';

import { cn } from '@/lib/utils';

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      'flex min-h-[108px] w-full rounded-xl border border-border bg-[rgba(9,11,17,0.92)] px-3.5 py-3 text-sm text-foreground outline-none transition-colors shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]',
      'placeholder:text-muted-foreground focus:border-[color:var(--color-accent)] focus:bg-[rgba(13,16,24,0.98)] focus:shadow-[0_0_0_3px_rgba(91,132,255,0.12)]',
      className,
    )}
    {...props}
  />
));

Textarea.displayName = 'Textarea';
