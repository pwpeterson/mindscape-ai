import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
	// Allow overriding the backend target without changing code.
	// Example: VITE_API_PROXY_TARGET=http://127.0.0.1:8000
	const env = loadEnv(mode, process.cwd(), '');
	const target = (env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8091').trim();

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
