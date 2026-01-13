import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
	// Allow overriding the backend target without changing code.
	// Examples:
	// - Container (published): VITE_API_PROXY_TARGET=http://127.0.0.1:8011
	// - Local dev (uvicorn): pick a free port (avoid 8000 if supabase-kong is bound)
	//   e.g. VITE_API_PROXY_TARGET=http://127.0.0.1:8091
	const env = loadEnv(mode, process.cwd(), '');
	const target = (env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8011').trim();

	return {
		plugins: [sveltekit()],
		server: {
			proxy: {
				// Local dev: route API calls to FastAPI without CORS.
				'/api': {
					target,
					changeOrigin: true
				}
			}
		}
	};
});
