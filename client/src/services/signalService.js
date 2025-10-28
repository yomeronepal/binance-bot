/**
 * Trading signals service
 */
import api from './api';

export const signalService = {
  /**
   * Get all signals
   */
  async getAll(params = {}) {
    const response = await api.get('/signals/', { params });
    return response.data;
  },

  /**
   * Get signal by ID
   */
  async getById(id) {
    const response = await api.get(`/signals/${id}/`);
    return response.data;
  },

  /**
   * Create new signal
   */
  async create(signalData) {
    const response = await api.post('/signals/', signalData);
    return response.data;
  },

  /**
   * Update signal
   */
  async update(id, signalData) {
    const response = await api.put(`/signals/${id}/`, signalData);
    return response.data;
  },

  /**
   * Delete signal
   */
  async delete(id) {
    const response = await api.delete(`/signals/${id}/`);
    return response.data;
  },

  /**
   * Get signal statistics
   */
  async getStatistics() {
    const response = await api.get('/signals/statistics/');
    return response.data;
  },
};

export default signalService;
