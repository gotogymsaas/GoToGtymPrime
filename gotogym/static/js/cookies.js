/* Preferencias de cookies.
 *
 * La eleccion se guarda en una cookie propia, `gtg_cookies`, durante 12 meses:
 *   analitica   -> acepto las cookies necesarias y la medicion anonima del uso
 *   necesarias  -> solo las necesarias
 * Sin cookie (primera visita) se muestra el banner y no se mide nada: la
 * medicion es opt-in. El servidor lee la misma cookie (analitica/services.py).
 *
 * Al guardar se emite el evento `gtg:cookies` en `document`; analytics.js
 * lo escucha para empezar (o dejar) de medir sin recargar la pagina.
 *
 * Sin JavaScript el banner no aparece y tampoco se mide nada.
 */
(function () {
  'use strict';

  var NOMBRE = 'gtg_cookies';
  var DURACION = 60 * 60 * 24 * 365;

  var banner = document.getElementById('gtg-cookies');
  if (!banner) return;

  var panel = document.getElementById('gtg-cookies-panel');
  var interruptor = banner.querySelector('[data-cookies-analitica]');
  var botonConfigurar = banner.querySelector('[data-cookies-configurar]');
  var botonGuardar = banner.querySelector('[data-cookies-guardar]');
  var botonAceptar = banner.querySelector('[data-cookies-aceptar]');
  var botonRechazar = banner.querySelector('[data-cookies-rechazar]');
  var ultimoFoco = null;

  function leer() {
    var coincidencia = document.cookie.match(/(?:^|;\s*)gtg_cookies=([^;]*)/);
    return coincidencia ? decodeURIComponent(coincidencia[1]) : null;
  }

  function guardar(valor) {
    var seguro = window.location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = NOMBRE + '=' + valor + '; Max-Age=' + DURACION + '; Path=/; SameSite=Lax' + seguro;
    document.dispatchEvent(new CustomEvent('gtg:cookies', { detail: { analitica: valor === 'analitica' } }));
    cerrar();
  }

  function abrirPanel(abierto) {
    panel.hidden = !abierto;
    botonConfigurar.setAttribute('aria-expanded', abierto ? 'true' : 'false');
    botonGuardar.hidden = !abierto;
    botonAceptar.hidden = abierto;
    botonRechazar.hidden = abierto;
  }

  function mostrar(conPanel) {
    interruptor.checked = leer() === 'analitica';
    abrirPanel(!!conPanel);
    banner.hidden = false;
  }

  function cerrar() {
    banner.hidden = true;
    if (ultimoFoco && document.contains(ultimoFoco)) ultimoFoco.focus();
    ultimoFoco = null;
  }

  botonAceptar.addEventListener('click', function () { guardar('analitica'); });
  botonRechazar.addEventListener('click', function () { guardar('necesarias'); });
  botonGuardar.addEventListener('click', function () {
    guardar(interruptor.checked ? 'analitica' : 'necesarias');
  });
  botonConfigurar.addEventListener('click', function () {
    abrirPanel(panel.hidden);
  });

  // Volver a abrir las preferencias desde el pie o desde la politica.
  Array.prototype.forEach.call(document.querySelectorAll('[data-cookies-abrir]'), function (control) {
    control.addEventListener('click', function () {
      ultimoFoco = control;
      mostrar(true);
      botonGuardar.focus();
    });
  });

  // Escape cierra solo cuando ya hay una eleccion guardada (reapertura).
  banner.addEventListener('keydown', function (evento) {
    if (evento.key === 'Escape' && leer()) cerrar();
  });

  if (!leer()) mostrar(false);
})();
