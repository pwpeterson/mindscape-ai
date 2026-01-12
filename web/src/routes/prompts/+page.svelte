<script lang="ts">
    import { page } from "$app/stores";

    const appId = $derived($page.url.searchParams.get("app_id"));
</script>

<svelte:head>
    <title>Prompts</title>
</svelte:head>

<main class="page-container">
    <header class="page-header">
        <div>
            <h1 class="page-title">Prompts</h1>
            <p class="page-subtitle">
                Placeholder. This section will show prompt templates filtered by
                the selected <code>app_id</code>.
            </p>
        </div>
    </header>

    <section class="card">
        <h2 class="card-title">Current scope</h2>
        <div class="mt-2 text-sm text-gray-200">
            app_id:
            <code
                class="rounded bg-white/5 px-1.5 py-0.5 text-xs text-gray-300"
            >
                {appId ?? "(local/default)"}
            </code>
        </div>

        <p class="mt-3 text-sm text-gray-300">Next steps:</p>
        <ul class="mt-2 list-disc pl-5 text-sm text-gray-200">
            <li>
                Backend: add Supabase prompt store endpoints scoped by <code
                    >app_id</code
                >
            </li>
            <li>UI: list/create/edit prompts in a library view</li>
        </ul>
    </section>
</main>
