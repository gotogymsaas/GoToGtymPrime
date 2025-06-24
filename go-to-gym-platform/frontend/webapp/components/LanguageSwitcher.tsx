'use client';
import { useRouter } from 'next/router';

const languages = [
  { code: 'es-CO', label: 'ES' },
  { code: 'pt-BR', label: 'PT' },
  { code: 'en-US', label: 'EN-US' },
  { code: 'en-GB', label: 'EN-GB' }
];

export default function LanguageSwitcher() {
  const router = useRouter();
  const { locale, asPath } = router;

  const changeLanguage = (code: string) => {
    router.push(asPath, asPath, { locale: code });
  };

  return (
    <div>
      {languages.map(({ code, label }) => (
        <button key={code} onClick={() => changeLanguage(code)} disabled={locale === code}>
          {label}
        </button>
      ))}
    </div>
  );
}
