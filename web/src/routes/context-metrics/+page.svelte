<script lang="ts">
    import { goto } from "$app/navigation";
    import { page } from "$app/stores";
    import { onMount } from "svelte";

    onMount(() => {
        const qs = $page.url.searchParams.toString();
        void goto(`/context-metrics/summary${qs ? `?${qs}` : ""}`, {
            replaceState: true,
        });
    });
</script>

<svelte:head>
    <title>Context Metrics</title>
</svelte:head>

<div class="card">
    <h2 class="card-title">Redirecting…</h2>
    <div class="mt-2 text-sm text-gray-200">
        Taking you to <code>/context-metrics/summary</code>.
    </div>
</div>
