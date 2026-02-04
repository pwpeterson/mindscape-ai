<script lang="ts">
    import { page } from "$app/stores";

    type Tab = {
        href: string;
        label: string;
        isActive: (pathname: string) => boolean;
    };

    const tabs: Tab[] = [
        {
            href: "/context-metrics/summary",
            label: "Summary",
            isActive: (p) =>
                p === "/context-metrics" ||
                p === "/context-metrics/" ||
                p.startsWith("/context-metrics/summary"),
        },
        {
            href: "/context-metrics/trends",
            label: "Trends",
            isActive: (p) => p.startsWith("/context-metrics/trends"),
        },
    ];
</script>

<main class="page-container">
    <header class="page-header">
        <div>
            <h1 class="page-title">Context Metrics</h1>
            <p class="page-subtitle">
                Condensation effectiveness metrics derived from model-proxy
                request logs.
            </p>
        </div>

        <nav class="mt-4 flex flex-wrap items-center gap-2">
            {#each tabs as t (t.href)}
                <a
                    class="btn {t.isActive($page.url.pathname)
                        ? 'btn-primary'
                        : ''}"
                    href={t.href}
                >
                    {t.label}
                </a>
            {/each}
        </nav>
    </header>

    <slot />
</main>
