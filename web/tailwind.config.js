/** @type {import('tailwindcss').Config} */
export default {
    content: ['./src/**/*.{html,js,svelte,ts}'],
    theme: {
        extend: {
            colors: {
                sidebar: {
                    DEFAULT: '#1e1e1e',
                    hover: '#2a2d2e',
                    selected: '#094771',
                    border: '#3c3c3c'
                },
                accent: {
                    DEFAULT: '#007acc',
                    hover: '#1c8ae0',
                    light: '#4fc1ff'
                },
                status: {
                    gray: '#6b7280',
                    blue: '#3b82f6',
                    yellow: '#f59e0b',
                    green: '#10b981',
                    purple: '#8b5cf6',
                    red: '#ef4444'
                }
            },
            spacing: {
                'tree-indent': '18px'
            },
            transitionDuration: {
                '150': '150ms'
            }
        }
    },
    plugins: []
};
