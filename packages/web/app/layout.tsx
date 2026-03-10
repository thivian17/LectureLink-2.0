import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import { PHProvider } from "./providers";
import { AnalyticsProvider } from "@/components/providers/AnalyticsProvider";
import "./globals.css";

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "LectureLink",
  description: "AI-powered study planning for university students",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${dmSans.variable} font-sans antialiased`}>
        <PHProvider>
          <AnalyticsProvider>
            {children}
          </AnalyticsProvider>
        </PHProvider>
        <Toaster richColors position="top-right" />
      </body>
    </html>
  );
}
