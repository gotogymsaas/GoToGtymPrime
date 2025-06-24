import WelcomeMessage from '../components/Welcome';
import LanguageSwitcher from '../components/LanguageSwitcher';

export default function Welcome() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4">
      <WelcomeMessage />
      <LanguageSwitcher />
    </main>
  );
}
