import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PakHook — Webhook Inspector",
  description: "Real-time webhook inspection for local payment gateways.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
