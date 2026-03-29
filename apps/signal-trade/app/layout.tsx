import type { Metadata } from 'next';
import { IBM_Plex_Mono, Space_Grotesk } from 'next/font/google';
import type { ReactNode } from 'react';

import './globals.css';

const displayFont = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-display',
});

const monoFont = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-mono',
});

export const metadata: Metadata = {
  title: 'Signal Trade Control Room',
  description:
    'Signal Trade full-stack dashboard for reviewing notifications and adjusting frontend filter presets.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html
      className={`${displayFont.variable} ${monoFont.variable}`}
      lang="zh-CN"
      suppressHydrationWarning
    >
      <body>{children}</body>
    </html>
  );
}
