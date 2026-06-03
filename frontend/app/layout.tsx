import "./globals.css";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Bili Knowledge Asset",
  description: "A local-first platform for turning Bilibili videos into reusable knowledge assets.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="topbar">
            <div>
              <p className="eyebrow">Visual Learning Workspace</p>
              <Link href="/" className="brand">
                Bili Knowledge Asset
              </Link>
              <p className="topbar-copy">Public Bilibili videos become reusable study assets with evidence, memory, and generation tools.</p>
            </div>
            <nav className="nav">
              <Link href="/">Home</Link>
              <Link href="/generate">Generate</Link>
            </nav>
          </header>
          <main className="page">{children}</main>
        </div>
      </body>
    </html>
  );
}
