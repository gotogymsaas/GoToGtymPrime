import { useState, useEffect } from 'react';

export default function NotificationBanner({ message }) {
  const [visible, setVisible] = useState(!!message);

  useEffect(() => {
    setVisible(!!message);
  }, [message]);

  if (!visible || !message) return null;

  const handleClose = () => setVisible(false);

  return (
    <div className="notification-banner">
      <p>{message.body}</p>
      <button onClick={handleClose}>Cerrar</button>
    </div>
  );
}
