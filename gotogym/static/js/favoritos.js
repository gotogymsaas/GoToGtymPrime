/* Corazon de favoritos (tienda/partials/_favorito_boton.html).
 *
 * El formulario funciona solo (POST y vuelta a la pagina); esto lo envia en
 * segundo plano para no perder el scroll ni recargar el grid. Se delega en
 * `document` para cubrir todas las tarjetas sin un listener por cada una.
 *
 * El formulario envia el estado deseado, no "alternar": tras cada respuesta
 * se reescribe con el estado que confirmo el servidor.
 *
 * En la pagina de favoritos (contenedor con data-favoritos-lista), quitar
 * un favorito retira la tarjeta; si la lista queda vacia se muestra el aviso vacio.
 */
(function () {
  'use strict';

  function pintar(form, esFavorito) {
    var boton = form.querySelector('.gtg-favorito__boton');
    var valor = form.querySelector('[data-favorito-valor]');
    if (!boton || !valor) return;
    var texto = esFavorito ? boton.getAttribute('data-texto-quitar') : boton.getAttribute('data-texto-agregar');
    boton.classList.toggle('is-favorito', esFavorito);
    boton.setAttribute('aria-pressed', esFavorito ? 'true' : 'false');
    boton.setAttribute('aria-label', texto);
    boton.setAttribute('data-favorito-tooltip', texto);
    valor.value = esFavorito ? '0' : '1';
  }

  // Un mismo producto puede tener varios corazones en la pagina (por
  // ejemplo, la galeria de la ficha y un relacionado): todos deben coincidir.
  function pintarTodos(accion, esFavorito) {
    var formularios = document.querySelectorAll('[data-favorito-form]');
    Array.prototype.forEach.call(formularios, function (otro) {
      if (otro.getAttribute('action') === accion) pintar(otro, esFavorito);
    });
  }

  function retirarDeLaLista(form) {
    var lista = form.closest('[data-favoritos-lista]');
    if (!lista) return;
    var tarjeta = form.closest('.gtg-product-card');
    if (tarjeta) tarjeta.remove();
    if (!lista.querySelector('.gtg-product-card')) {
      lista.hidden = true;
      var vacio = document.querySelector('[data-favoritos-vacio]');
      if (vacio) vacio.hidden = false;
    }
  }

  /* En la ficha la foto se ajusta sin recortar (object-fit: contain) dentro
   * de un recuadro 4:5: una foto con otra proporcion deja franjas, y el
   * corazon anclado al recuadro quedaria sobre la franja y no sobre la
   * foto. Se calcula el rectangulo que de verdad ocupa la imagen visible y
   * se coloca el corazon en su esquina inferior derecha. Sin JS queda la
   * posicion del CSS, que coincide con la esquina en las fotos 4:5. */
  // Lo que separa el boton (area de toque) de la esquina; el circulo visible
  // queda unos 6px mas adentro.
  var MARGEN_GALERIA = 4;

  function ubicarEnGaleria() {
    var formularios = document.querySelectorAll('.gtg-favorito--galeria');
    Array.prototype.forEach.call(formularios, function (form) {
      var recuadro = form.closest('.pdp-gallery__viewport');
      var imagen = recuadro && recuadro.querySelector('[data-gallery-slide].is-active img');
      if (!imagen || !imagen.naturalWidth || !imagen.naturalHeight) return;
      var caja = imagen.getBoundingClientRect();
      var marco = recuadro.getBoundingClientRect();
      if (!caja.width || !caja.height) return;
      var escala = Math.min(caja.width / imagen.naturalWidth, caja.height / imagen.naturalHeight);
      var franjaX = (caja.width - imagen.naturalWidth * escala) / 2;
      var franjaY = (caja.height - imagen.naturalHeight * escala) / 2;
      form.style.right = Math.round(marco.right - (caja.right - franjaX) + MARGEN_GALERIA) + 'px';
      form.style.bottom = Math.round(marco.bottom - (caja.bottom - franjaY) + MARGEN_GALERIA) + 'px';
    });
  }

  function vigilarGaleria() {
    var galeria = document.querySelector('[data-gallery]');
    if (!galeria || !document.querySelector('.gtg-favorito--galeria')) return;
    Array.prototype.forEach.call(galeria.querySelectorAll('[data-gallery-slide] img'), function (imagen) {
      if (!imagen.complete) imagen.addEventListener('load', ubicarEnGaleria);
    });
    // Cambiar de foto solo mueve la clase is-active entre diapositivas.
    if ('MutationObserver' in window) {
      new MutationObserver(ubicarEnGaleria).observe(galeria, {
        subtree: true, attributes: true, attributeFilter: ['class']
      });
    }
    window.addEventListener('resize', ubicarEnGaleria);
    ubicarEnGaleria();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', vigilarGaleria);
  } else {
    vigilarGaleria();
  }

  document.addEventListener('submit', function (evento) {
    var form = evento.target;
    if (!form.matches || !form.matches('[data-favorito-form]') || !window.fetch) return;
    evento.preventDefault();

    var boton = form.querySelector('.gtg-favorito__boton');
    if (!boton || boton.getAttribute('aria-busy') === 'true') return;
    boton.setAttribute('aria-busy', 'true');

    fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
    })
      .then(function (respuesta) {
        return respuesta.json().catch(function () { return {}; }).then(function (datos) {
          return { estado: respuesta.status, datos: datos };
        });
      })
      .then(function (resultado) {
        if (resultado.estado === 401 && resultado.datos.login_url) {
          window.location.href = resultado.datos.login_url;
          return;
        }
        if (!resultado.datos.ok) return;
        pintarTodos(form.getAttribute('action'), resultado.datos.favorito);
        if (!resultado.datos.favorito) retirarDeLaLista(form);
      })
      .catch(function () { /* sin red: el corazon queda como estaba */ })
      .then(function () {
        boton.removeAttribute('aria-busy');
      });
  });
})();
