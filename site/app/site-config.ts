export const repositoryUrl = "https://github.com/satwiksps/rigsolve";

export const siteDescription =
  "Resolve PyTorch, CUDA, and native-extension compatibility from sourced evidence before you install.";

export function getSiteUrl(): URL {
  const explicitUrl = process.env.NEXT_PUBLIC_SITE_URL;
  const vercelUrl = process.env.VERCEL_PROJECT_PRODUCTION_URL;

  if (explicitUrl) {
    return new URL(explicitUrl);
  }
  if (vercelUrl) {
    return new URL(`https://${vercelUrl}`);
  }
  return new URL("http://localhost:3000");
}
