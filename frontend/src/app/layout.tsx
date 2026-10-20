import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ORIGIN — Autonomous Scientific Intelligence Platform for Software Systems",
  description:
    "Give software the ability to understand itself. Living System Intelligence Engine, OpenTelemetry Ingestion, and Provenance-Verified Topology.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased selection:bg-[#0F1E36] selection:text-[#FAF8F5]">
        {children}
      </body>
    </html>
  );
}
