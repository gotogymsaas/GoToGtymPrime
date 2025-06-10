import { getMessaging, getToken } from 'firebase/messaging';
import app from '../firebase-config';
import { registerDeviceToken } from '../services/notifications';

export async function registerFCM(authToken) {
  try {
    const messaging = getMessaging(app);
    const token = await getToken(messaging, { vapidKey: process.env.NEXT_PUBLIC_FCM_VAPID });
    if (token) {
      await registerDeviceToken(token, authToken);
    }
  } catch (err) {
    console.error('FCM registration failed', err);
  }
}
