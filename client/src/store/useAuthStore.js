/**
 * Authentication state management with Zustand
 */
import { create } from 'zustand';
import { authService } from '../services/authService';

export const useAuthStore = create((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  /**
   * Login user
   */
  login: async (credentials) => {
    set({ isLoading: true, error: null });
    try {
      const data = await authService.login(credentials);

      // Get user profile after login
      const user = await authService.getProfile();

      set({
        user,
        isAuthenticated: true,
        isLoading: false
      });

      return { success: true, data };
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Login failed';
      set({
        error: errorMessage,
        isLoading: false,
        isAuthenticated: false
      });
      return { success: false, error: errorMessage };
    }
  },

  /**
   * Register new user
   */
  register: async (userData) => {
    set({ isLoading: true, error: null });
    try {
      const data = await authService.register(userData);
      set({ isLoading: false });
      return { success: true, data };
    } catch (error) {
      const errorMessage = error.response?.data?.detail || error.response?.data?.username?.[0] || 'Registration failed';
      set({
        error: errorMessage,
        isLoading: false
      });
      return { success: false, error: errorMessage };
    }
  },

  /**
   * Logout user
   */
  logout: () => {
    authService.logout();
    set({
      user: null,
      isAuthenticated: false,
      error: null
    });
  },

  /**
   * Load user profile
   */
  loadUser: async () => {
    if (!authService.isAuthenticated()) {
      set({ isAuthenticated: false, user: null });
      return;
    }

    set({ isLoading: true });
    try {
      const user = await authService.getProfile();
      set({
        user,
        isAuthenticated: true,
        isLoading: false
      });
    } catch (error) {
      set({
        isAuthenticated: false,
        user: null,
        isLoading: false
      });
      authService.logout();
    }
  },

  /**
   * Update user profile
   */
  updateProfile: async (userData) => {
    set({ isLoading: true, error: null });
    try {
      const user = await authService.updateProfile(userData);
      set({ user, isLoading: false });
      return { success: true, data: user };
    } catch (error) {
      const errorMessage = error.response?.data?.detail || 'Update failed';
      set({ error: errorMessage, isLoading: false });
      return { success: false, error: errorMessage };
    }
  },

  /**
   * Clear error
   */
  clearError: () => set({ error: null }),
}));

export default useAuthStore;
