import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			// Local dev: route API calls to FastAPI without CORS.
			'/api': {
				target: 'http://127.0.0.1:8091',
				changeOrigin: true
			}
		}
	}
});
