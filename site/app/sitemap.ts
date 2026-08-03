import type { MetadataRoute } from "next";

import { getSiteUrl } from "./site-config";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: getSiteUrl().toString(),
      lastModified: new Date("2026-08-15"),
      changeFrequency: "weekly",
      priority: 1,
    },
  ];
}
