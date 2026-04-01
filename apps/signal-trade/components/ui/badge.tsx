import * as React from 'react';

import { cn } from '@/lib/utils';

type BadgeVariant = 'default' | 'secondary' | 'outline' | 'success';

const variantClasses: Record<BadgeVariant, string> = {
  default:
    'border border-[rgba(91,132,255,0.22)] bg-[rgba(91,132,255,0.16)] text-[#9ab4ff]',
  secondary:
    'border border-white/[0.08] bg-[rgba(15,18,27,0.92)] text-muted-foreground',
  outline: 'border border-border bg-[rgba(9,11,17,0.75)] text-foreground',
  success: 'border border-emerald-500/20 bg-emerald-500/12 text-emerald-300',
};

export function Badge({
  className,
  variant = 'default',
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: BadgeVariant }): React.JSX.Element {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em]',
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  );
}
