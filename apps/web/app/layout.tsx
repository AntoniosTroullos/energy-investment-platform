import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import AppNav from "../components/AppNav";
import { ScenarioConfigProvider } from "../lib/scenario/ScenarioConfigContext";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Energy Investment Platform",
  description: "Map-based infrastructure intelligence",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-screen flex flex-col">
        <AppNav />
        <ScenarioConfigProvider>{children}</ScenarioConfigProvider>
      </body>
    </html>
  );
}
