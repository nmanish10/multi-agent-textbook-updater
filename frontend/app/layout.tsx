import type { Metadata } from "next";
import Link from "next/link";
import { Inter, Outfit } from "next/font/google";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Textbook Update Platform",
  description: "Reader and admin interface for the Multi-Agent Textbook Update System",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${outfit.variable}`}>
      <body>
        <div className="shell">
          <header className="topbar">
            <div>
              <p className="eyebrow">Living Textbooks</p>
              <Link href="/" className="brand">
                Textbook Update Platform
              </Link>
            </div>
            <nav className="nav">
              <Link href="/">Library</Link>
              <Link href="/admin">Admin</Link>
            </nav>
          </header>
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
