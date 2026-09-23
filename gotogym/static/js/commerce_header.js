/* Comportamiento del header comercial: panel movil, menu de cuenta y
 * confirmacion de carrito.
 *
 * Antes vivia como dos <script> incrustados en base.html. Aqui es un solo
 * archivo cacheable y, sobre todo, el punto donde anadir al carrito deja
 * de expulsar al comprador del catalogo.
 *
 * Todo es mejora progresiva: sin este archivo el panel movil no se abre
 * pero la navegacion persistente sigue visible, y el formulario de la
 * ficha de producto se envia como siempre y la vista redirige al carrito.
 */
(function () {
  'use strict';

  function mostrar(elemento, visible) {
    if (!elemento) return;
    elemento.hidden = !visible;
  }

  function esVisible(elemento) {
    return !!elemento && !elemento.hidden;
  }

  // --- Panel movil ------------------------------------------------------
  var botonMenu = document.querySelector('[data-menu-toggle]');
  var panelMovil = document.getElementById('mobile-menu');

  function alternarPanelMovil(abrir) {
    if (!botonMenu || !panelMovil) return;
    var visible = typeof abrir === 'boolean' ? abrir : !esVisible(panelMovil);
    mostrar(panelMovil, visible);
    botonMenu.setAttribute('aria-expanded', visible ? 'true' : 'false');
  }

  if (botonMenu && panelMovil) {
    botonMenu.addEventListener('click', function (evento) {
      evento.stopPropagation();
      alternarPanelMovil();
    });
  }

  // --- Menu de cuenta ---------------------------------------------------
  var botonCuenta = document.querySelector('[data-user-toggle]');
  var menuCuenta = document.getElementById('userDropdown');

  function alternarMenuCuenta(abrir) {
    if (!botonCuenta || !menuCuenta) return;
    var visible = typeof abrir === 'boolean' ? abrir : !esVisible(menuCuenta);
    mostrar(menuCuenta, visible);
    botonCuenta.setAttribute('aria-expanded', visible ? 'true' : 'false');
  }

  if (botonCuenta && menuCuenta) {
    botonCuenta.addEventListener('click', function (evento) {
      evento.stopPropagation();
      alternarMenuCuenta();
    });
  }

  // --- Confirmacion de carrito -----------------------------------------
  var panelCarrito = document.querySelector('[data-minicart]');
  var contador = document.getElementById('cart-count');
  var ultimoDisparador = null;

  function cerrarPanelCarrito(devolverFoco) {
    if (!esVisible(panelCarrito)) return;
    mostrar(panelCarrito, false);
    if (devolverFoco && ultimoDisparador) ultimoDisparador.focus();
    ultimoDisparador = null;
  }

  function abrirPanelCarrito(datos) {
    if (!panelCarrito) return;
    panelCarrito.classList.toggle('is-error', !!datos.error);
    panelCarrito.querySelector('[data-minicart-icon]').textContent =
      datos.error ? 'error_outline' : 'check_circle';
    panelCarrito.querySelector('[data-minicart-title]').textContent = datos.titulo;
    panelCarrito.querySelector('[data-minicart-product]').textContent = datos.producto || '';
    panelCarrito.querySelector('[data-minicart-variant]').textContent = datos.variante || '';
    mostrar(panelCarrito, true);
  }

  function actualizarContador(total) {
    if (!contador) return;
    contador.textContent = total;
    contador.hidden = !total;
  }

  if (panelCarrito) {
    var botonCerrar = panelCarrito.querySelector('[data-minicart-close]');
    if (botonCerrar) {
      botonCerrar.addEventListener('click', function () {
        cerrarPanelCarrito(true);
      });
    }
  }

  /* La vista de agregar responde JSON solo si la peticion se identifica
   * como XMLHttpRequest; con cualquier otro encabezado redirige al
   * carrito, que es justo el salto que este interceptor evita. */
  var formularioCarrito = document.querySelector('[data-add-to-cart]');

  if (formularioCarrito && window.fetch && window.FormData) {
    formularioCarrito.addEventListener('submit', function (evento) {
      if (!formularioCarrito.action) return;
      evento.preventDefault();
      ultimoDisparador = document.activeElement;

      var boton = formularioCarrito.querySelector('button[type="submit"]');
      if (boton) boton.disabled = true;

      fetch(formularioCarrito.action, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        body: new FormData(formularioCarrito),
        credentials: 'same-origin'
      }).then(function (respuesta) {
        return respuesta.json().then(function (cuerpo) {
          return { ok: respuesta.ok, cuerpo: cuerpo };
        });
      }).then(function (resultado) {
        if (boton) boton.disabled = false;

        if (!resultado.ok || !resultado.cuerpo.success) {
          abrirPanelCarrito({
            error: true,
            titulo: formularioCarrito.dataset.labelError || 'No se pudo agregar',
            producto: resultado.cuerpo.error || ''
          });
          return;
        }

        actualizarContador(resultado.cuerpo.cart_count);

        // Solo se avisa de altas confirmadas por el servidor, para que la
        // medicion no cuente intentos fallidos por falta de stock.
        document.dispatchEvent(new CustomEvent('gtg:add-to-cart', {
          detail: {
            producto: formularioCarrito.dataset.productName || '',
            variante: formularioCarrito.dataset.variantLabel || '',
            unidades: resultado.cuerpo.cart_count
          }
        }));

        abrirPanelCarrito({
          titulo: formularioCarrito.dataset.labelExito || 'Añadido al carrito',
          producto: formularioCarrito.dataset.productName || '',
          variante: formularioCarrito.dataset.variantLabel || ''
        });
      }).catch(function () {
        // Sin red o con una respuesta inesperada, el envio normal deja al
        // usuario en el carrito con el mensaje de siempre.
        if (boton) boton.disabled = false;
        formularioCarrito.submit();
      });
    });
  }

  // --- Cierre compartido ------------------------------------------------
  document.addEventListener('click', function (evento) {
    if (esVisible(panelMovil) && !panelMovil.contains(evento.target) &&
        !(botonMenu && botonMenu.contains(evento.target))) {
      alternarPanelMovil(false);
    }
    if (esVisible(menuCuenta) && !menuCuenta.contains(evento.target) &&
        !(botonCuenta && botonCuenta.contains(evento.target))) {
      alternarMenuCuenta(false);
    }
    if (esVisible(panelCarrito) && !panelCarrito.contains(evento.target)) {
      cerrarPanelCarrito(false);
    }
  });

  document.addEventListener('keydown', function (evento) {
    if (evento.key !== 'Escape') return;
    alternarPanelMovil(false);
    alternarMenuCuenta(false);
    cerrarPanelCarrito(true);
  });
})();
