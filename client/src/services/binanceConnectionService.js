/**
 * Per-user Binance API key connection — slice 1 (read-only validation).
 *
 * Backend endpoints:
 *   GET    /binance/server-ip/         (public)
 *   GET    /binance/connection/        (auth) -> 404 if not connected
 *   POST   /binance/connect/           (auth) -> body { api_key, api_secret }
 *   POST   /binance/revalidate/        (auth)
 *   DELETE /binance/disconnect/        (auth)
 */
import { api } from './api';

export async function getServerIp() {
  const { data } = await api.get('/binance/server-ip/');
  return data.ip;
}

export async function getConnection() {
  try {
    const { data } = await api.get('/binance/connection/');
    return data;
  } catch (err) {
    if (err?.response?.status === 404) return null;
    throw err;
  }
}

export async function connect({ apiKey, apiSecret }) {
  // 200 on success, 400 with body.validation on a clean validation failure
  try {
    const { data } = await api.post('/binance/connect/', {
      api_key: apiKey,
      api_secret: apiSecret,
    });
    return { ok: true, ...data };
  } catch (err) {
    const data = err?.response?.data;
    if (data?.validation) {
      return { ok: false, ...data };
    }
    throw err;
  }
}

export async function revalidate() {
  const { data } = await api.post('/binance/revalidate/');
  return data;
}

export async function disconnect() {
  await api.delete('/binance/disconnect/');
}
