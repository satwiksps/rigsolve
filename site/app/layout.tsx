import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import "./globals.css";
import { getSiteUrl, repositoryUrl, siteDescription } from "./site-config";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: getSiteUrl(),
  title: {
    default: "rigsolve — GPU compatibility resolver",
    template: "%s | rigsolve",
  },
  description: siteDescription,
  applicationName: "rigsolve",
  authors: [{ name: "rigsolve contributors", url: repositoryUrl }],
  creator: "rigsolve contributors",
  keywords: [
    "CUDA",
    "PyTorch",
    "GPU compatibility",
    "flash-attention",
    "MLOps",
    "dependency resolver",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: "/",
    siteName: "rigsolve",
    title: "Resolve the GPU stack before you install it.",
    description: siteDescription,
    images: [
      {
        url: "/og.png",
        width: 1731,
        height: 909,
        alt: "rigsolve — GPU compatibility resolver",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Resolve the GPU stack before you install it.",
    description: siteDescription,
    images: ["/og.png"],
  },
  category: "technology",
};

export const viewport: Viewport = {
  colorScheme: "dark",
  themeColor: "#080a0d",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
