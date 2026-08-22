import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

import ts from "typescript";

function loadCopyText(document) {
  const component = new URL("./TerminalDemo.tsx", import.meta.url);
  const source = `${readFileSync(component, "utf8")}\nexport { copyText as copyTextForTest };`;
  const output = ts.transpileModule(source, {
    compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX,
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  const loaded = { exports: {} };
  const context = vm.createContext({
    document,
    exports: loaded.exports,
    module: loaded,
    navigator: {},
    require: () => ({}),
  });
  vm.runInContext(output, context, { filename: component.pathname });
  return loaded.exports.copyTextForTest;
}

test("legacy clipboard fallback rejects a reported copy failure", async () => {
  let removed = false;
  const input = {
    remove() {
      removed = true;
    },
    select() {},
    setAttribute() {},
    style: {},
    value: "",
  };
  const document = {
    body: { append() {} },
    createElement() {
      return input;
    },
    execCommand(command) {
      assert.equal(command, "copy");
      return false;
    },
  };
  const copyText = loadCopyText(document);

  await assert.rejects(copyText("rigsolve detect"), /clipboard copy failed/i);
  assert.equal(removed, true);
});
