import type { MetadataRoute } from "next";

import { getSiteUrl } from "./site-config";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: getSiteUrl().toString(),
      changeFrequency: "weekly",
      priority: 1,
    },
  ];
}
