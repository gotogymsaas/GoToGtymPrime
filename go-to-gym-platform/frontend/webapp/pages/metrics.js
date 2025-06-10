import { useEffect, useState } from 'react';

export default function Metrics() {
  const [metrics, setMetrics] = useState([]);

  useEffect(() => {
    async function fetchMetrics() {
      try {
        const token = localStorage.getItem('jwtToken');
        if (!token) return;
        const res = await fetch('http://localhost:8001/api/metrics/', {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setMetrics(data);
        }
      } catch (err) {
        console.error(err);
      }
    }
    fetchMetrics();
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center p-4">
      <h1 className="text-xl mb-4">Métricas de Salud</h1>
      <ul className="w-full max-w-md">
        {metrics.map((m) => (
          <li key={m.id} className="border-b py-2">
            <span className="font-semibold">{m.metric_type}</span>: {m.value} ({new Date(m.timestamp).toLocaleString()})
          </li>
        ))}
      </ul>
    </main>
  );
}
