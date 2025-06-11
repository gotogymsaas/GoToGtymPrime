const withPWA = require('next-pwa')({
  dest: 'public',
  disable: process.env.NODE_ENV === 'development',
});
const { i18n } = require('./next-i18next.config.js');

module.exports = withPWA({
  reactStrictMode: true,
  i18n,
});
