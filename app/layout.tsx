import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";
import "./globals.css";

const display = localFont({
  src: "./fonts/dm-serif-display-400.ttf",
  variable: "--font-display",
  weight: "400",
  display: "swap"
});

const body = localFont({
  src: [
    { path: "./fonts/jost-400.ttf", weight: "400" },
    { path: "./fonts/jost-500.ttf", weight: "500" },
    { path: "./fonts/jost-600.ttf", weight: "600" },
    { path: "./fonts/jost-700.ttf", weight: "700" }
  ],
  variable: "--font-body",
  display: "swap"
});

const mono = localFont({
  src: [
    { path: "./fonts/jetbrains-mono-500.ttf", weight: "500" },
    { path: "./fonts/jetbrains-mono-700.ttf", weight: "700" }
  ],
  variable: "--font-mono",
  display: "swap"
});

export const metadata: Metadata = {
  title: "Travel Companion Agent",
  description: "A budget-aware travel research companion that can use local-language sources."
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
