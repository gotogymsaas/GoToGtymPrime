export default function Login() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center">
      <h1>Iniciar Sesión</h1>
      <form className="flex flex-col gap-2 mt-4">
        <input type="text" placeholder="Usuario" required />
        <input type="password" placeholder="Contraseña" required />
        <button type="submit">Ingresar</button>
      </form>
    </main>
  );
}
