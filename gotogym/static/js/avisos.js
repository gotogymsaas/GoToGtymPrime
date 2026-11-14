/* Avisos del sitio (partials/_mensajes.html).
 *
 * Las confirmaciones se cierran solas tras unos segundos; los errores y las
 * advertencias esperan a que la persona los cierre. Mientras el puntero o el
 * foco estan sobre un aviso, no se cierra: nadie pierde un mensaje que esta
 * leyendo.
 */
(function () {
  'use strict';

  var SEGUNDOS_VISIBLE = 6;
  var contenedor = document.querySelector('[data-avisos]');
  if (!contenedor) return;

  var sinMovimiento = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function cerrar(aviso) {
    if (!aviso || aviso.dataset.cerrando) return;
    aviso.dataset.cerrando = '1';
    function quitar() {
      aviso.remove();
      if (!contenedor.querySelector('[data-aviso]')) contenedor.remove();
    }
    if (sinMovimiento) {
      quitar();
      return;
    }
    aviso.classList.add('is-saliendo');
    aviso.addEventListener('animationend', quitar, { once: true });
    // Por si la animacion no corre (pestana en segundo plano).
    window.setTimeout(quitar, 400);
  }

  Array.prototype.forEach.call(contenedor.querySelectorAll('[data-aviso]'), function (aviso) {
    var boton = aviso.querySelector('[data-aviso-cerrar]');
    if (boton) boton.addEventListener('click', function () { cerrar(aviso); });
    if (!aviso.hasAttribute('data-aviso-temporal')) return;

    var temporizador = null;
    function programar() {
      temporizador = window.setTimeout(function () { cerrar(aviso); }, SEGUNDOS_VISIBLE * 1000);
    }
    function pausar() {
      if (temporizador) window.clearTimeout(temporizador);
      temporizador = null;
    }
    aviso.addEventListener('mouseenter', pausar);
    aviso.addEventListener('mouseleave', programar);
    aviso.addEventListener('focusin', pausar);
    aviso.addEventListener('focusout', programar);
    programar();
  });
}());
