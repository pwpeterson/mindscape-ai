<script lang="ts">
    import { page } from "$app/stores";

    let { children } = $props();

    function withScope(path: string): string {
        const app_id = $page.url.searchParams.get("app_id");
        const db = $page.url.searchParams.get("db");

        const url = new URL(path, "http://local");

        if (app_id) {
            url.searchParams.set("app_id", app_id);
            url.searchParams.delete("db");
        } else if (db) {
            // Legacy/workbench fallback
            url.searchParams.set("db", db);
        }

        return url.pathname + url.search;
    }

    function isActive(pathname: string): boolean {
        return $page.url.pathname === pathname;
    }
</script>

<div class="module-shell mx-auto max-w-7xl px-6 py-6">
    <div class="flex gap-6">
        <aside class="w-64 shrink-0">
            <div class="card h-full">
                <div
                    class="text-xs font-semibold uppercase tracking-wide text-gray-300/80"
                >
                    Prompts
                </div>

                <nav class="mt-3 flex flex-col gap-1">
                    <a
                        href={withScope("/prompts")}
                        class="text-sm px-3 py-2 rounded-md transition-colors duration-150 hover:bg-white/5"
                        class:bg-sidebar-selected={isActive("/prompts")}
                        class:text-white={isActive("/prompts")}
                    >
                        Overview
                    </a>
                </nav>

                <div class="mt-4 text-xs text-gray-300/80">
                    Coming next: Supabase-backed prompt library filtered by <code
                        >app_id</code
                    >.
                </div>
            </div>
        </aside>

        <section class="min-w-0 flex-1">
            {@render children()}
        </section>
    </div>
</div>
