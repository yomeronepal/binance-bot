/**
 * Authentication service
 */
import api from './api';

export const authService = {
  /**
   * Register a new user
   */
  async register(userData) {
    const response = await api.post('/users/register/', userData);
    return response.data;
  },

  /**
   * Login user
   */
  async login(credentials) {
    const response = await api.post('/users/login/', credentials);
    const { access, refresh } = response.data;

    // Store tokens in localStorage
    localStorage.setItem('accessToken', access);
    localStorage.setItem('refreshToken', refresh);

    return response.data;
  },

  /**
   * Logout user
   */
  logout() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('user');
  },

  /**
   * Get current user profile
   */
  async getProfile() {
    const response = await api.get('/users/profile/');
    return response.data;
  },

  /**
   * Update user profile
   */
  async updateProfile(userData) {
    const response = await api.put('/users/profile/update/', userData);
    return response.data;
  },

  /**
   * Change password
   */
  async changePassword(passwordData) {
    const response = await api.post('/users/change-password/', passwordData);
    return response.data;
  },

  /**
   * Check if user is authenticated
   */
  isAuthenticated() {
    return !!localStorage.getItem('accessToken');
  },

  /**
   * Get access token
   */
  getAccessToken() {
    return localStorage.getItem('accessToken');
  },
};

export default authService;
