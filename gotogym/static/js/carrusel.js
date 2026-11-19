/* Carrusel horizontal de tarjetas ([data-carrusel]).
 *
 * El desplazamiento lo hace el navegador (overflow-x + scroll-snap en
 * commerce_editorial.css): funciona con el dedo, la rueda y el teclado sin
 * este archivo. Aqui solo se conectan las flechas, que avanzan una "pagina"
 * (el ancho visible), y se desactivan en los extremos. Si todo cabe sin
 * desplazar, las flechas se ocultan.
 */
(function () {
  'use strict';

  function iniciar(carrusel) {
    var pista = carrusel.querySelector('[data-carrusel-pista]');
    var anterior = carrusel.querySelector('[data-carrusel-anterior]');
    var siguiente = carrusel.querySelector('[data-carrusel-siguiente]');
    if (!pista || !anterior || !siguiente) return;
    var controles = anterior.parentElement;

    function actualizar() {
      var maximo = pista.scrollWidth - pista.clientWidth;
      // Tolerancia de 2px: con zoom el scroll final puede quedar en decimales.
      controles.hidden = maximo <= 2;
      anterior.disabled = pista.scrollLeft <= 2;
      siguiente.disabled = pista.scrollLeft >= maximo - 2;
    }

    function mover(sentido) {
      var sinAnimacion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      pista.scrollBy({ left: sentido * pista.clientWidth * 0.9, behavior: sinAnimacion ? 'auto' : 'smooth' });
    }

    anterior.addEventListener('click', function () { mover(-1); });
    siguiente.addEventListener('click', function () { mover(1); });
    pista.addEventListener('scroll', actualizar, { passive: true });
    window.addEventListener('resize', actualizar);
    actualizar();
  }

  function iniciarTodos() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-carrusel]'), iniciar);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciarTodos);
  } else {
    iniciarTodos();
  }
})();
