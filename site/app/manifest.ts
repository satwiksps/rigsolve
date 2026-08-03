import type { MetadataRoute } from "next";

import { siteDescription } from "./site-config";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "rigsolve — GPU compatibility resolver",
    short_name: "rigsolve",
    description: siteDescription,
    start_url: "/",
    display: "standalone",
    background_color: "#080a0d",
    theme_color: "#080a0d",
    icons: [
      {
        src: "/icon",
        sizes: "64x64",
        type: "image/png",
      },
    ],
  };
}
