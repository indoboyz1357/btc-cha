import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BTCUSD Signal Omega V2 — Trading Terminal",
  description: "Professional-grade BTC/USD trading terminal with Crystal Heikin Ashi analysis, AI-powered signals via OpenRouter, and automated trading engine.",
  keywords: "BTCUSD, trading terminal, Crystal Heikin Ashi, MT5, auto trading, AI signals",
  openGraph: {
    title: "BTCUSD Signal Omega V2",
    description: "Professional BTC/USD trading terminal",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <head>
        <link rel="icon" href="/favicon.ico" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="theme-color" content="#0a0b0d" />
      </head>
      <body>{children}</body>
    </html>
  );
}
