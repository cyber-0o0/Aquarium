import type { Metadata } from "next";
import Script from "next/script";
import { Space_Grotesk, Manrope, Space_Mono } from "next/font/google";
import "./globals.css";
import { TelegramProvider } from "@/components/TelegramProvider";
import { TonProvider } from "@/providers/TonProvider";
import { QueryProvider } from "@/providers/QueryProvider";
import { TabBar } from "@/components/layout/TabBar";
import { ThemeProvider } from "@/providers/ThemeProvider";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-heading",
  subsets: ["latin"],
  display: 'swap',
});

const manrope = Manrope({
  variable: "--font-body",
  subsets: ["latin"],
  display: 'swap',
});

const spaceMono = Space_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "700"],
  display: 'swap',
});

export const metadata: Metadata = {
  title: "Aquarium AI",
  description: "Next-gen AI Agent Platform for Ton",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover" />
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
      </head>
      <body className={`${spaceGrotesk.variable} ${manrope.variable} ${spaceMono.variable}`}>
        <QueryProvider>
          <TonProvider>
            <TelegramProvider>
              <ThemeProvider>
                <div className="app-container">
                  <div className="content-scroll">
                    <main className="page-wrapper">
                      {children}
                    </main>
                  </div>
                  <TabBar />
                </div>
              </ThemeProvider>
            </TelegramProvider>
          </TonProvider>
        </QueryProvider>
      </body>
    </html>
  );
}


