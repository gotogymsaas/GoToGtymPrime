import axios from 'axios';

export async function registerDeviceToken(token, authToken) {
  return axios.post('/api/device-token/', { token }, {
    headers: { Authorization: `Bearer ${authToken}` },
  });
}

export async function fetchNotifications(authToken) {
  const res = await axios.get('/api/notifications/', {
    headers: { Authorization: `Bearer ${authToken}` },
  });
  return res.data;
}
