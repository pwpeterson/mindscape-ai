<script lang="ts">
    import { page } from "$app/stores";

    let { children } = $props();

    type HeaderDef = { title: string; subtitle?: string };

    function headerFor(pathname: string): HeaderDef {
        switch (pathname) {
            case "/conport/dashboard":
                return {
                    title: "ConPort — Dashboard",
                    subtitle: "High-level rollups for Workbench mode.",
                };
            case "/conport/now":
                return {
                    title: "ConPort — Now",
                    subtitle:
                        "Workbench snapshot from your local ConPort SQLite DB.",
                };
            case "/conport/search":
                return {
                    title: "ConPort — Search",
                    subtitle:
                        "Search decisions and custom data (FTS when available).",
                };
            case "/conport/decisions":
                return {
                    title: "ConPort — Decisions",
                    subtitle:
                        "Recent decisions from Workbench mode (newest first).",
                };
            case "/conport/custom-data":
                return {
                    title: "ConPort — Custom Data",
                    subtitle: "Browse custom key/value entries (newest first).",
                };
            case "/conport/system-patterns":
                return {
                    title: "ConPort — System Patterns",
                    subtitle: "Browse system/coding patterns (newest first).",
                };
            case "/conport/progress":
                return {
                    title: "ConPort — Progress",
                    subtitle: "Browse progress entries (newest first).",
                };
            case "/conport/views":
                return {
                    title: "ConPort — Views",
                    subtitle:
                        "Saved Workbench views (custom_data category: workbench_views).",
                };
            case "/conport/links":
                return {
                    title: "ConPort — Links",
                    subtitle:
                        "Workbench view of context links (knowledge graph edges).",
                };
            case "/conport/item":
                return {
                    title: "ConPort — Item",
                    subtitle: "Generic item detail view (?type=decision&id=1).",
                };
            default:
                return { title: "ConPort" };
        }
    }

    let header = $derived(headerFor($page.url.pathname));

    function withScope(path: string): string {
        const app_id = $page.url.searchParams.get("app_id");
        const db = $page.url.searchParams.get("db");

        const url = new URL(path, "http://local");

        if (app_id) {
            url.searchParams.set("app_id", app_id);
            url.searchParams.delete("db");
        } else if (db) {
            url.searchParams.set("db", db);
        }

        return url.pathname + url.search;
    }

    function isActive(pathname: string): boolean {
        return $page.url.pathname === pathname;
    }
</script>

<div class="module-shell mx-auto max-w-7xl px-6 py-6">
    <header class="page-header">
        <div class="flex items-start gap-6">
            <div class="w-64 shrink-0">
                <h1 class="page-title">{header.title}</h1>
            </div>

            <div class="min-w-0 flex-1">
                {#if header.subtitle}
                    <div class="text-lg font-medium text-gray-200/90">
                        {header.subtitle}
                    </div>
                {/if}
            </div>
        </div>
    </header>

    <div class="flex gap-6">
        <aside class="w-64 shrink-0">
            <div class="card h-full">
                <div
                    class="text-xs font-semibold uppercase tracking-wide text-gray-300/80"
                >
                    Conport
                </div>

                <nav class="mt-3 flex flex-col gap-1">
                    <a
                        href={withScope("/conport/now")}
                        class="text-sm px-3 py-2 rounded-md transition-colors duration-150 hover:bg-white/5"
                        class:bg-sidebar-selected={isActive("/conport/now")}
                        class:text-white={isActive("/conport/now")}
                    >
                        Now
                    </a>

                    <a
                        href={withScope("/conport/dashboard")}
                        class="text-sm px-3 py-2 rounded-md transition-colors duration-150 hover:bg-white/5"
                        class:bg-sidebar-selected={isActive(
                            "/conport/dashboard",
                        )}
                        class:text-white={isActive("/conport/dashboard")}
                    >
                        Dashboard
                    </a>

                    <a
                        href={withScope("/conport/search")}
                        class="text-sm px-3 py-2 rounded-md transition-colors duration-150 hover:bg-white/5"
                        class:bg-sidebar-selected={isActive("/conport/search")}
                        class:text-white={isActive("/conport/search")}
                    >
                        Search
                    </a>

                    <a
                        href={withScope("/conport/decisions")}
                        class="text-sm px-3 py-2 rounded-md transition-colors duration-150 hover:bg-white/5"
                        class:bg-sidebar-selected={isActive(
                            "/conport/decisions",
                        )}
                        class:text-white={isActive("/conport/decisions")}
                    >
                        Decisions
                    </a>

                    <a
                        href={withScope("/conport/custom-data")}
                        class="text-sm px-3 py-2 rounded-md transition-colors duration-150 hover:bg-white/5"
                        class:bg-sidebar-selected={isActive(
                            "/conport/custom-data",
                        )}
                        class:text-white={isActive("/conport/custom-data")}
                    >
                        Custom Data
                    </a>

                    <a
                        href={withScope("/conport/system-patterns")}
                        class="text-sm px-3 py-2 rounded-md transition-colors duration-150 hover:bg-white/5"
                        class:bg-sidebar-selected={isActive(
                            "/conport/system-patterns",
                        )}
                        class:text-white={isActive("/conport/system-patterns")}
                    >
                        System Patterns
                    </a>

                    <a
                        href={withScope("/conport/progress")}
                        class="text-sm px-3 py-2 rounded-md transition-colors duration-150 hover:bg-white/5"
                        class:bg-sidebar-selected={isActive(
                            "/conport/progress",
                        )}
                        class:text-white={isActive("/conport/progress")}
                    >
                        Progress
                    </a>

                    <a
                        href={withScope("/conport/views")}
                        class="text-sm px-3 py-2 rounded-md transition-colors duration-150 hover:bg-white/5"
                        class:bg-sidebar-selected={isActive("/conport/views")}
                        class:text-white={isActive("/conport/views")}
                    >
                        Views
                    </a>

                    <a
                        href={withScope("/conport/links")}
                        class="text-sm px-3 py-2 rounded-md transition-colors duration-150 hover:bg-white/5"
                        class:bg-sidebar-selected={isActive("/conport/links")}
                        class:text-white={isActive("/conport/links")}
                    >
                        Links
                    </a>
                </nav>
            </div>
        </aside>

        <section class="min-w-0 flex-1">
            {@render children()}
        </section>
    </div>
</div>
