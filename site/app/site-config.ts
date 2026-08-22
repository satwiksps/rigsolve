export const repositoryUrl = "https://github.com/satwiksps/rigsolve";
export const documentationUrl = "https://rigsolve.readthedocs.io/en/latest/";
export const socialImageUrl =
  "https://raw.githubusercontent.com/satwiksps/rigsolve/main/docs/assets/social-card.png";

export const siteDescription =
  "Resolve PyTorch, CUDA, and native extension compatibility.";

function parseHttpsOrigin(
  variableName: string,
  value: string,
  hostnameOnly = false,
): URL {
  const expectedShape = hostnameOnly
    ? /^[^/?#]+\/?$/
    : /^https:\/\/[^/?#]+\/?$/i;
  const candidate = hostnameOnly ? `https://${value}` : value;
  let url: URL;

  try {
    url = new URL(candidate);
  } catch {
    throw new Error(
      `${variableName} must be an HTTPS origin with no credentials, path, query, or fragment`,
    );
  }

  if (
    !expectedShape.test(value) ||
    url.protocol !== "https:" ||
    url.username !== "" ||
    url.password !== "" ||
    url.pathname !== "/" ||
    url.search !== "" ||
    url.hash !== ""
  ) {
    throw new Error(
      `${variableName} must be an HTTPS origin with no credentials, path, query, or fragment`,
    );
  }
  return url;
}

export function getSiteUrl(): URL {
  const explicitUrl = process.env.NEXT_PUBLIC_SITE_URL;
  const vercelUrl = process.env.VERCEL_PROJECT_PRODUCTION_URL;

  if (explicitUrl) {
    return parseHttpsOrigin("NEXT_PUBLIC_SITE_URL", explicitUrl);
  }
  if (vercelUrl) {
    return parseHttpsOrigin("VERCEL_PROJECT_PRODUCTION_URL", vercelUrl, true);
  }
  return new URL("http://localhost:3000");
}
