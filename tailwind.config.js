/* Configuracion de Tailwind para las plantillas Django.
 *
 * Sustituye a cdn.tailwindcss.com, que compilaba en el navegador de cada
 * visitante: bloqueaba el render, anadia el compilador al peso de la
 * pagina y provocaba un parpadeo sin estilos mientras generaba las
 * utilidades.
 *
 * `content` incluye los .js porque hay clases que solo aparecen ahi
 * (la ficha de producto marca la talla elegida con classList.toggle);
 * si faltaran, el purgado las eliminaria y la seleccion dejaria de verse.
 */
module.exports = {
  content: [
    './gotogym/**/templates/**/*.html',
    './gotogym/static/js/**/*.js',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
