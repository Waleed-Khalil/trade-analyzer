import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "Trade Analyzer",
  description: "Option play analysis — Go/No-Go, Greeks, risk, and recommendation",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="antialiased">
      <body className="min-h-screen font-sans bg-[#0b0f14] text-slate-200">
        {children}
      </body>
    </html>
  )
}
