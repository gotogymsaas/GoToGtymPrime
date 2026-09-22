/* Campo gravitacional Quantum: desplazamiento suave al mover el puntero y
 * pausa cuando sale del viewport.
 *
 * El movimiento es una mejora progresiva: sin este script el campo ya se
 * anima solo con CSS. Se omite por completo si el sistema pide menos
 * movimiento o si el dispositivo no tiene un puntero preciso (en tactil no
 * hay hover que seguir y el parallax solo costaria bateria).
 */
(function () {
  'use strict';

  var campos = document.querySelectorAll('[data-quantum-field]');
  if (!campos.length) return;

  var sinMovimiento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var punteroPreciso = window.matchMedia('(pointer: fine)').matches;

  Array.prototype.forEach.call(campos, function (campo) {
    var contenedor = campo.parentElement;
    if (!contenedor) return;

    if ('IntersectionObserver' in window) {
      var observador = new IntersectionObserver(function (entradas) {
        campo.classList.toggle('is-paused', !entradas[0].isIntersecting);
      }, { threshold: 0.05 });
      observador.observe(contenedor);
    }

    if (sinMovimiento || !punteroPreciso) return;

    contenedor.addEventListener('pointermove', function (evento) {
      var caja = contenedor.getBoundingClientRect();
      // Maximo 8px de desplazamiento: el campo acompana, no persigue.
      var x = ((evento.clientX - caja.left) / caja.width - 0.5) * 8;
      var y = ((evento.clientY - caja.top) / caja.height - 0.5) * 8;
      campo.style.setProperty('--qf-x', x.toFixed(2) + 'px');
      campo.style.setProperty('--qf-y', y.toFixed(2) + 'px');
    });

    contenedor.addEventListener('pointerleave', function () {
      campo.style.setProperty('--qf-x', '0px');
      campo.style.setProperty('--qf-y', '0px');
    });
  });
})();
