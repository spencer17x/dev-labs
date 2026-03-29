import * as React from 'react';

import { cn } from '@/lib/utils';

type BadgeVariant = 'default' | 'secondary' | 'outline' | 'success';

const variantClasses: Record<BadgeVariant, string> = {
  default:
    'bg-[color:var(--color-accent)]/10 text-[color:var(--color-accent-strong)]',
  secondary:
    'bg-[color:var(--color-panel-soft)] text-muted-foreground',
  outline: 'border border-border text-foreground',
  success: 'bg-emerald-500/12 text-emerald-700',
};

export function Badge({
  className,
  variant = 'default',
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: BadgeVariant }): React.JSX.Element {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em]',
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  );
}
