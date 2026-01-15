import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

/**
 * @param {string} relPath
 */
function readUtf8(relPath) {
    const abs = path.resolve(process.cwd(), relPath);
    return fs.readFileSync(abs, "utf8");
}

test("global layout reload button triggers invalidateAll and forces subtree remount", () => {
    const svelte = readUtf8("src/routes/+layout.svelte");

    // Reload helper exists and calls invalidateAll (SvelteKit load revalidation).
    assert.match(svelte, /\basync function reloadUi\(\)\s*{/);
    assert.match(svelte, /\binvalidateAll\(\)/);

    // Reload helper bumps nonce to force a remount (pages that fetch in onMount()).
    assert.match(svelte, /\breloadNonce\s*\+=\s*1/);

    // Ensure the subtree is keyed so it remounts when scope changes or reload is pressed.
    assert.match(svelte, /\{#key\s+pageRemountKey\(\)\s*\}/);
    assert.match(svelte, /\{\/key\}/);

    // Ensure the button is wired to the global reload helper (not only refreshApps()).
    assert.match(svelte, /onclick=\{\(\)\s*=>\s*void reloadUi\(\)\}/);
});