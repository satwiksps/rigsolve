# rigsolve website

The public landing site for [rigsolve](https://github.com/satwiksps/rigsolve). It is a native Next.js App Router project designed to deploy from this repository on Vercel.

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

That command verifies formatting, runs ESLint and strict TypeScript checking, and produces a production Next.js build.

## Deploy to Vercel

1. Import `https://github.com/satwiksps/rigsolve` in Vercel.
2. Set **Root Directory** to `site`.
3. Leave the framework, install, build, and output settings at their auto-detected Next.js defaults.
4. Deploy.

Vercel supplies `VERCEL_PROJECT_PRODUCTION_URL`, which the site uses for canonical metadata, `robots.txt`, and `sitemap.xml`. For a custom production domain, set:

```text
NEXT_PUBLIC_SITE_URL=https://your-domain.example
```

The value must include `https://` and should not end with a path.

No database, server-side secret, or external service is required.

## Structure

- `app/page.tsx` — Tailwind-based landing page and structured data
- `app/globals.css` — Tailwind entry point, font tokens, and global accessibility rules
- `app/components/TerminalDemo.tsx` — keyboard-accessible command examples and copy controls
- `app/layout.tsx` — canonical, Open Graph, and social metadata
- `app/manifest.ts`, `app/robots.ts`, `app/sitemap.ts` — deployment metadata
- `public/og.png` — generated social preview card
