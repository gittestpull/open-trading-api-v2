import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Deep Dive - Investment Platform",
  description: "AI-Powered Korean Stock Trading Platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" className="dark">
      <body className="bg-dark-900 text-gray-300 min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}
