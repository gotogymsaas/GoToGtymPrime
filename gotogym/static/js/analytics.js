/* Medicion de uso del sitio.
 *
 * Las plantillas ya marcaban sus llamadas a la accion con `data-track`,
 * pero nada leia esos atributos: los eventos existian en el HTML y no
 * llegaban a ninguna parte, asi que no habia forma de saber si el Home
 * lleva a producto o si el buscador se usa. Este archivo es el que los
 * recoge.
 *
 * Como se declara un evento en una plantilla:
 *
 *   data-track="product_click"          nombre del evento (obligatorio)
 *   data-track-producto="12"            propiedad `producto`
 *   data-track-posicion="3"             propiedad `posicion`
 *   data-track-impression               ademas, mide la impresion
 *
 * El nombre debe existir en EVENTOS_PERMITIDOS (analitica/views.py) o el
 * servidor lo descarta.
 *
 * Los eventos se acumulan y se envian por lotes con sendBeacon, que sigue
 * entregando aunque la pestana se cierre a continuacion: sin eso, el clic
 * que lleva a otra pagina seria justo el que nunca se registra.
 */
(function () {
  'use strict';

  var configuracion = document.getElementById('gtg-analytics-config');
  if (!configuracion) return;

  // Preferencia de no ser seguido: aunque esta medicion no sale del sitio
  // ni construye perfiles publicitarios, respetarla cuesta poco y es
  // coherente con no usar patrones oscuros en el resto de la tienda.
  var noSeguir = navigator.doNotTrack === '1' || window.doNotTrack === '1';
  if (noSeguir) return;

  var ajustes;
  try {
    ajustes = JSON.parse(configuracion.textContent);
  } catch (error) {
    return;
  }
  if (!ajustes || !ajustes.endpoint) return;

  var TAMANO_LOTE = 8;
  var ESPERA_MS = 5000;
  var cola = [];
  var temporizador = null;

  function encolar(nombre, propiedades) {
    if (!nombre) return;
    cola.push({
      nombre: nombre,
      ruta: window.location.pathname,
      propiedades: propiedades || {}
    });
    if (cola.length >= TAMANO_LOTE) {
      enviar();
      return;
    }
    if (temporizador) clearTimeout(temporizador);
    temporizador = setTimeout(enviar, ESPERA_MS);
  }

  function enviar() {
    if (temporizador) {
      clearTimeout(temporizador);
      temporizador = null;
    }
    if (!cola.length) return;

    var lote = cola;
    cola = [];

    // FormData y no JSON: sendBeacon no permite fijar cabeceras, asi que
    // el token CSRF tiene que viajar como campo del formulario.
    var cuerpo = new FormData();
    cuerpo.append('csrfmiddlewaretoken', ajustes.csrf || '');
    cuerpo.append('eventos', JSON.stringify(lote));

    if (navigator.sendBeacon && navigator.sendBeacon(ajustes.endpoint, cuerpo)) return;

    if (window.fetch) {
      fetch(ajustes.endpoint, {
        method: 'POST',
        body: cuerpo,
        credentials: 'same-origin',
        keepalive: true
      }).catch(function () { /* medir nunca debe romper la pagina */ });
    }
  }

  /* Lee las propiedades declaradas como data-track-* en el elemento. */
  function propiedadesDe(elemento) {
    var propiedades = {};
    var atributos = elemento.attributes;
    for (var i = 0; i < atributos.length; i++) {
      var nombre = atributos[i].name;
      if (nombre.indexOf('data-track-') !== 0) continue;
      var clave = nombre.slice('data-track-'.length);
      if (!clave || clave === 'impression') continue;
      propiedades[clave] = atributos[i].value;
    }
    return propiedades;
  }

  // --- Vista de pagina ---------------------------------------------------
  encolar('page_view', {
    ancho: window.innerWidth,
    autenticado: document.body.classList.contains('gtg-autenticado') ? 1 : 0
  });

  // --- Clics -------------------------------------------------------------
  document.addEventListener('click', function (evento) {
    var objetivo = evento.target.closest ? evento.target.closest('[data-track]') : null;
    if (!objetivo) return;
    encolar(objetivo.getAttribute('data-track'), propiedadesDe(objetivo));
    // El clic suele navegar: se entrega ya, sin esperar al lote.
    enviar();
  }, true);

  // --- Impresiones de producto -------------------------------------------
  /* Una tarjeta cuenta como vista si al menos la mitad estuvo en pantalla
   * medio segundo. Sin el retardo, un scroll rapido registraria todo el
   * catalogo como visto y la tasa de clic por impresion no diria nada. */
  var candidatas = document.querySelectorAll('[data-track-impression]');
  if (candidatas.length && 'IntersectionObserver' in window) {
    var pendientes = new WeakMap();

    var observador = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (entrada) {
        var elemento = entrada.target;

        if (!entrada.isIntersecting) {
          clearTimeout(pendientes.get(elemento));
          pendientes.delete(elemento);
          return;
        }

        if (pendientes.has(elemento)) return;
        pendientes.set(elemento, setTimeout(function () {
          observador.unobserve(elemento);
          encolar('product_impression', propiedadesDe(elemento));
        }, 500));
      });
    }, { threshold: 0.5 });

    Array.prototype.forEach.call(candidatas, function (elemento) {
      observador.observe(elemento);
    });
  }

  // --- Busqueda ----------------------------------------------------------
  Array.prototype.forEach.call(
    document.querySelectorAll('form[role="search"]'),
    function (formulario) {
      formulario.addEventListener('submit', function () {
        var campo = formulario.querySelector('input[name="filtro"]');
        var texto = campo ? campo.value.trim() : '';
        encolar('search_submit', {
          origen: formulario.className.indexOf('mobile') >= 0 ? 'movil' : 'barra',
          termino: texto,
          vacia: texto ? 0 : 1
        });
        enviar();
      });
    }
  );

  // --- Carrito -----------------------------------------------------------
  // commerce_header.js avisa cuando la respuesta del servidor confirma la
  // unidad agregada, de modo que solo se miden altas reales.
  document.addEventListener('gtg:add-to-cart', function (evento) {
    encolar('add_to_cart', (evento.detail || {}));
  });

  // --- Entrega final -----------------------------------------------------
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') enviar();
  });
  window.addEventListener('pagehide', enviar);
})();
