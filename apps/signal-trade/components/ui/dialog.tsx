'use client';

import type { JSX, ReactNode } from 'react';
import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

import { cn } from '@/lib/utils';

type DialogProps = {
  children: ReactNode;
  className?: string;
  onClose: () => void;
  open: boolean;
  title?: string;
};

export function Dialog({ children, className, onClose, open, title }: DialogProps): JSX.Element | null {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 px-4 py-10 backdrop-blur-sm"
      onClick={e => {
        if (e.target === overlayRef.current) onClose();
      }}
    >
      <div
        className={cn(
          'relative my-auto w-full max-w-lg rounded-[20px] border border-border bg-[rgba(13,16,24,0.98)] shadow-[0_24px_64px_rgba(0,0,0,0.5)]',
          className,
        )}
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <p className="text-sm font-semibold text-foreground">{title ?? ''}</p>
          <button
            type="button"
            aria-label="关闭"
            className="rounded-full p-1 text-muted-foreground transition-colors hover:text-foreground"
            onClick={onClose}
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}
