import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

import ts from "typescript";

function loadGetSiteUrl(env) {
  const moduleUrl = new URL("../site-config.ts", import.meta.url);
  const source = readFileSync(moduleUrl, "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  const loaded = { exports: {} };
  const context = vm.createContext({
    Error,
    URL,
    exports: loaded.exports,
    module: loaded,
    process: { env },
  });
  vm.runInContext(output, context, { filename: moduleUrl.pathname });
  return loaded.exports.getSiteUrl;
}

test("site URL defaults to the local development origin", () => {
  const getSiteUrl = loadGetSiteUrl({});

  assert.equal(getSiteUrl().toString(), "http://localhost:3000/");
});

test("NEXT_PUBLIC_SITE_URL accepts only an HTTPS origin", () => {
  const valid = loadGetSiteUrl({
    NEXT_PUBLIC_SITE_URL: "https://docs.example.com",
  });
  assert.equal(valid().toString(), "https://docs.example.com/");

  for (const value of [
    "http://docs.example.com",
    "https://user@docs.example.com",
    "https://docs.example.com/release",
    "https://docs.example.com?preview=1",
    "https://docs.example.com#release",
  ]) {
    const getSiteUrl = loadGetSiteUrl({ NEXT_PUBLIC_SITE_URL: value });
    assert.throws(
      getSiteUrl,
      /NEXT_PUBLIC_SITE_URL must be an HTTPS origin with no credentials, path, query, or fragment/,
    );
  }
});

test("VERCEL_PROJECT_PRODUCTION_URL accepts only an origin hostname", () => {
  const valid = loadGetSiteUrl({
    VERCEL_PROJECT_PRODUCTION_URL: "rigsolve.vercel.app",
  });
  assert.equal(valid().toString(), "https://rigsolve.vercel.app/");

  for (const value of [
    "https://rigsolve.vercel.app",
    "user@rigsolve.vercel.app",
    "rigsolve.vercel.app/release",
    "rigsolve.vercel.app?preview=1",
    "rigsolve.vercel.app#release",
  ]) {
    const getSiteUrl = loadGetSiteUrl({
      VERCEL_PROJECT_PRODUCTION_URL: value,
    });
    assert.throws(
      getSiteUrl,
      /VERCEL_PROJECT_PRODUCTION_URL must be an HTTPS origin with no credentials, path, query, or fragment/,
    );
  }
});
