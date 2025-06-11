/** @type {import('next-i18next').UserConfig} */
const config = {
  i18n: {
    defaultLocale: 'es-CO',
    locales: ['es-CO', 'pt-BR', 'en-US', 'en-GB'],
    localeDetection: true
  },
  localePath: './public/locales',
  reloadOnPrerender: process.env.NODE_ENV === 'development'
};
module.exports = config;
