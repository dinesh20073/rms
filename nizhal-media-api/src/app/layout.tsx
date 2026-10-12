import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Nizhal Community | Media API Backend',
  description: 'Production Media API backend for Nizhal Community Scrapbook & Memories',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
