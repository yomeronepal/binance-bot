/**
 * Theme store for system-wide light/dark mode
 * Persists theme preference to localStorage
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Helper function to apply theme to document
const applyTheme = (theme) => {
    if (typeof document !== 'undefined') {
        if (theme === 'dark') {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
    }
};

const useThemeStore = create(
    persist(
        (set, get) => ({
            theme: 'dark', // 'light' or 'dark'

            toggleTheme: () => {
                const newTheme = get().theme === 'dark' ? 'light' : 'dark';
                set({ theme: newTheme });
                applyTheme(newTheme);
            },

            setTheme: (theme) => {
                set({ theme });
                applyTheme(theme);
            },

            // Initialize theme on app load
            initTheme: () => {
                const theme = get().theme;
                applyTheme(theme);
            },
        }),
        {
            name: 'theme-storage',
            // Called when the persisted state is rehydrated from localStorage
            onRehydrateStorage: () => (state) => {
                // Apply theme after state is restored
                if (state) {
                    applyTheme(state.theme);
                }
            },
        }
    )
);

export default useThemeStore;

