import type { Metadata, Viewport } from "next";

import "./globals.css";
import {
  getSiteUrl,
  repositoryUrl,
  siteDescription,
  socialImageUrl,
} from "./site-config";

export const metadata: Metadata = {
  metadataBase: getSiteUrl(),
  title: "rigsolve",
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
    title: "rigsolve",
    description: siteDescription,
    images: [
      {
        url: socialImageUrl,
        width: 1774,
        height: 887,
        alt: "rigsolve social card",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "rigsolve",
    description: siteDescription,
    images: [socialImageUrl],
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
      <body>{children}</body>
    </html>
  );
}
