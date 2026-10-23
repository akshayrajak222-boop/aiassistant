import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Axy — 24/7 Personal AI Agent Platform",
  description: "Always-on personal AI assistant platform running 24/7 with text and natural voice.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="font-sans bg-slate-950 text-slate-100 min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}
