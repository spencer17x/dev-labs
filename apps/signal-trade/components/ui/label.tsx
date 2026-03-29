import * as React from 'react';

import { cn } from '@/lib/utils';

export function Label({
  className,
  ...props
}: React.LabelHTMLAttributes<HTMLLabelElement>): React.JSX.Element {
  return (
    <label
      className={cn(
        'text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground',
        className,
      )}
      {...props}
    />
  );
}
