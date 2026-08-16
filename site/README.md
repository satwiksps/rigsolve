# rigsolve website

The public [rigsolve](https://github.com/satwiksps/rigsolve) site. It uses Next.js App Router and deploys to Vercel.

## Local development

Use Node.js 24:

```bash
npm ci
npm run dev
```

Open `http://localhost:3000`.

Run the complete website gate before committing:

```bash
npm test
```

This checks formatting, lint, types, and the production build.

## Deploy to Vercel

1. Import `https://github.com/satwiksps/rigsolve` in Vercel.
2. Set **Root Directory** to `site`.
3. Leave the framework, install, build, and output settings at their auto-detected Next.js defaults.
4. Deploy.

`vercel.json` enables Git deployments only for `main`. Pull requests do not create preview deployments.

Vercel supplies `VERCEL_PROJECT_PRODUCTION_URL`, which the site uses for canonical metadata, `robots.txt`, and `sitemap.xml`. For a custom production domain, set:

```text
NEXT_PUBLIC_SITE_URL=https://your-domain.example
```

The value must include `https://` and should not end with a path.

No database, server-side secret, or external service is required.

## Structure

- `app/page.tsx`: landing page and structured data
- `app/globals.css`: Tailwind entry point and global styles
- `app/components/TerminalDemo.tsx`: command examples
- `app/layout.tsx`: canonical and social metadata
- `app/manifest.ts`, `app/robots.ts`, `app/sitemap.ts`: deployment metadata
- `../docs/assets/social-card.png`: Open Graph and wide post image
- `../docs/assets/social-card-square.png`: square post image
- `../docs/assets/github-social-preview.jpg`: GitHub repository preview image
