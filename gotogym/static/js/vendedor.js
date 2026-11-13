/* Panel de Quantum Coach, la IA de GoToGym.
 *
 * Mejora progresiva: los botones que lo abren nacen ocultos y este archivo los
 * muestra. Sin JavaScript no hay control muerto y el resto del sitio funciona
 * igual.
 *
 * Reglas que este archivo no debe romper:
 *
 *  - Nada de lo que escribe el modelo se inserta como HTML. Todo se pinta con
 *    textContent o con elementos creados aqui; nunca innerHTML.
 *  - Las direcciones (enlaces, imagenes, destino de "agregar al carrito")
 *    llegan del servidor, que las construye con reverse(), y aun asi se
 *    comprueban aqui contra una lista de rutas internas. El modelo no decide
 *    ninguna URL.
 *  - El navegador solo habla con la propia tienda, nunca con el Coach.
 *  - Si la tienda dice que no hay IA (`disponible: false`), el panel responde
 *    desde aqui que no esta disponible y no llama al servidor.
 *  - Los textos visibles viven en el panel (ya traducidos); aqui no hay
 *    cadenas en un idioma concreto.
 *  - Al medir se envian categorias y numeros, nunca el texto de los mensajes.
 *
 * El historial se guarda en sessionStorage (solo en esta pestana) para que no
 * se pierda al cambiar de pagina. Vence con la misma inactividad con la que el
 * servidor da por terminada la conversacion (`vigenciaHistorial`): una
 * pestana que el navegador restaura dias despues no muestra una charla que el
 * Coach ya no recuerda. Si el almacenamiento falla, el panel funciona igual.
 */
(function () {
  'use strict';

  var panel = document.querySelector('[data-vendedor-panel]');
  if (!panel) return;

  var configuracion = {};
  try {
    configuracion = JSON.parse(document.getElementById('vendedor-config').textContent);
  } catch (error) {
    return;
  }
  if (!configuracion.endpoint || !window.fetch) return;

  var CLAVE_HISTORIAL = 'gtg_vendedor_historial';
  var CLAVE_AVISO = 'gtg_vendedor_aviso';
  var MAX_ENTRADAS = 24;
  var ESPERA_POR_DEFECTO = 10;
  var VIGENCIA_MS = (configuracion.vigenciaHistorial > 0 ? configuracion.vigenciaHistorial : 1800) * 1000;
  // Rutas internas a las que puede apuntar un enlace del panel.
  var RUTA_ENLACE = /^\/[a-z]{2}\/(tienda|carrito|pedidos-tienda|contacto)\/[A-Za-z0-9\-_\/.%]*$/;
  var RUTA_IMAGEN = /^\/(media|static)\/[A-Za-z0-9\-_\/.%]+$/;
  var RUTA_AGREGAR = /^\/[a-z]{2}\/carrito\/add\/\d+\/$/;
  var RUTA_RECORDAR = /^\/[a-z]{2}\/vendedor\/personalizacion\/recordar\/$/;
  var SIN_REINTENTO = { limite_turnos: true, limite_diario: true, mensaje_invalido: true };

  var botones = document.querySelectorAll('[data-vendedor-toggle]');
  var registro = panel.querySelector('[data-vendedor-log]');
  var bienvenida = panel.querySelector('[data-vendedor-bienvenida]');
  var sugerencias = panel.querySelector('[data-vendedor-sugerencias]');
  var atajos = panel.querySelector('[data-vendedor-atajos]');
  var estado = panel.querySelector('[data-vendedor-status]');
  var cajaError = panel.querySelector('[data-vendedor-error]');
  var textoError = panel.querySelector('[data-vendedor-error-texto]');
  var botonReintentar = panel.querySelector('[data-vendedor-reintentar]');
  var enlaceContacto = panel.querySelector('[data-vendedor-contacto]');
  var formulario = panel.querySelector('[data-vendedor-form]');
  var campo = panel.querySelector('[data-vendedor-mensaje]');
  var botonEnviar = panel.querySelector('[data-vendedor-enviar]');
  var aviso = panel.querySelector('[data-vendedor-notice]');
  var botonAviso = panel.querySelector('[data-vendedor-notice-ok]');
  var botonCerrar = panel.querySelector('[data-vendedor-close]');
  var botonNueva = panel.querySelector('[data-vendedor-nueva]');
  var velo = document.querySelector('[data-vendedor-scrim]');

  var abierto = false;
  var enviando = false;
  var disparador = null;
  var ultimoMensaje = '';
  var nuevaConversacion = false;
  var temporizadorEspera = null;
  var historial = [];

  // --- Utilidades --------------------------------------------------------

  function texto(clave) {
    var nodo = panel.querySelector('[data-texto="' + clave + '"]');
    return nodo ? nodo.textContent : '';
  }

  function crear(etiqueta, clase, contenido) {
    var nodo = document.createElement(etiqueta);
    if (clase) nodo.className = clase;
    if (contenido !== undefined && contenido !== null) nodo.textContent = contenido;
    return nodo;
  }

  function medir(nombre, propiedades) {
    try {
      document.dispatchEvent(new CustomEvent('gtg:track', {
        detail: { nombre: nombre, propiedades: propiedades || {} }
      }));
    } catch (error) { /* medir nunca debe romper el panel */ }
  }

  function guardado(clave) {
    try { return window.sessionStorage.getItem(clave); } catch (error) { return null; }
  }

  function guardar(clave, valor) {
    try { window.sessionStorage.setItem(clave, valor); } catch (error) { /* sin almacenamiento */ }
  }

  function esVisible(nodo) {
    return !!nodo && !nodo.hidden && nodo.getClientRects().length > 0;
  }

  function desplazarAlFinal() {
    registro.scrollTop = registro.scrollHeight;
  }

  // --- Historial ---------------------------------------------------------

  // Se guarda con la hora del ultimo cambio: { ts, e: [entradas] }.
  function guardarHistorial() {
    guardar(CLAVE_HISTORIAL, JSON.stringify({ ts: Date.now(), e: historial.slice(-MAX_ENTRADAS) }));
  }

  // Un historial vencido, sin hora (formato anterior) o ilegible se descarta.
  function leerHistorial() {
    var crudo = guardado(CLAVE_HISTORIAL);
    if (!crudo) return [];
    try {
      var datos = JSON.parse(crudo);
      var vigente = datos && typeof datos.ts === 'number' && Date.now() - datos.ts <= VIGENCIA_MS;
      return vigente && Array.isArray(datos.e) ? datos.e.slice(-MAX_ENTRADAS) : [];
    } catch (error) {
      return [];
    }
  }

  // --- Pintado de mensajes ----------------------------------------------

  function pintarUsuario(contenido) {
    var caja = crear('div', 'gtg-vendedor__msg gtg-vendedor__msg--user');
    caja.appendChild(crear('span', 'sr-only', texto('tu') + ': '));
    caja.appendChild(crear('p', null, contenido));
    registro.appendChild(caja);
    desplazarAlFinal();
  }

  function pintarTarjeta(tarjeta) {
    if (!tarjeta || typeof tarjeta.name !== 'string' || !RUTA_ENLACE.test(tarjeta.url || '')) return null;
    var item = crear('li', 'gtg-vendedor__card');
    if (RUTA_IMAGEN.test(tarjeta.image_url || '')) {
      var imagen = crear('img', 'gtg-vendedor__card-img');
      imagen.src = tarjeta.image_url;
      imagen.alt = '';
      imagen.width = 64;
      imagen.height = 80;
      imagen.loading = 'lazy';
      item.appendChild(imagen);
    }
    var cuerpo = crear('div', 'gtg-vendedor__card-body');
    cuerpo.appendChild(crear('strong', null, tarjeta.name));
    var precio = crear('p', 'gtg-vendedor__card-price', String(tarjeta.price || ''));
    if (tarjeta.compare_price) {
      precio.appendChild(document.createTextNode(' '));
      precio.appendChild(crear('s', null, String(tarjeta.compare_price)));
    }
    cuerpo.appendChild(precio);
    if (tarjeta.reason) cuerpo.appendChild(crear('p', 'gtg-vendedor__card-reason', String(tarjeta.reason)));
    var enlace = crear('a', 'gtg-vendedor__link', texto('ver_producto'));
    enlace.href = tarjeta.url;
    enlace.addEventListener('click', function () {
      medir('vendedor_product_click', { origen: 'tarjeta', producto: tarjeta.product_id || 0 });
    });
    cuerpo.appendChild(enlace);
    item.appendChild(cuerpo);
    return item;
  }

  function actualizarContador(total) {
    var contador = document.getElementById('cart-count');
    if (!contador || typeof total !== 'number') return;
    contador.textContent = total;
    contador.hidden = !total;
  }

  function avisoDeAccion(caja, mensaje, conEnlaceAlCarrito) {
    var linea = crear('p', 'gtg-vendedor__action-note', mensaje);
    linea.setAttribute('role', 'status');
    if (conEnlaceAlCarrito && RUTA_ENLACE.test(configuracion.cartUrl || '')) {
      linea.appendChild(document.createTextNode(' '));
      var enlace = crear('a', 'gtg-vendedor__link', texto('ver_carrito'));
      enlace.href = configuracion.cartUrl;
      linea.appendChild(enlace);
    }
    var anterior = caja.querySelector('.gtg-vendedor__action-note');
    if (anterior) caja.removeChild(anterior);
    caja.appendChild(linea);
    desplazarAlFinal();
  }

  function agregarAlCarrito(accion, boton, caja) {
    if (!RUTA_AGREGAR.test(accion.endpoint || '')) return;
    boton.disabled = true;
    fetch(accion.endpoint, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': configuracion.csrf || '',
        'Accept': 'application/json'
      }
    }).then(function (respuesta) {
      return respuesta.json().then(function (cuerpo) {
        return { ok: respuesta.ok, cuerpo: cuerpo };
      });
    }).then(function (resultado) {
      if (!resultado.ok || !resultado.cuerpo || !resultado.cuerpo.success) {
        boton.disabled = false;
        // El servidor ya explica el motivo (sin stock, compras en pausa...).
        var motivo = resultado.cuerpo && typeof resultado.cuerpo.error === 'string' ? resultado.cuerpo.error : '';
        avisoDeAccion(caja, (texto('no_se_pudo_agregar') + ' ' + motivo).trim(), false);
        return;
      }
      actualizarContador(resultado.cuerpo.cart_count);
      boton.textContent = texto('agregado');
      avisoDeAccion(caja, texto('agregado_aviso'), true);
      // Mismo aviso que usa la ficha de producto: alimenta el embudo de compra.
      document.dispatchEvent(new CustomEvent('gtg:add-to-cart', {
        detail: {
          producto: accion.product_name || '',
          variante: accion.variant_label || '',
          unidades: resultado.cuerpo.cart_count,
          producto_id: accion.product_id || ''
        }
      }));
      medir('vendedor_add_to_cart', { variante: accion.variant_id || 0 });
      ofrecerRecordar(accion, caja);
    }).catch(function () {
      boton.disabled = false;
      avisoDeAccion(caja, texto('no_se_pudo_agregar'), false);
    });
  }

  // Memoria comercial: solo si el cliente la activo en Mi cuenta y solo
  // cuando el pulsa "Recordar". El servidor deduce la talla de la variante.
  function ofrecerRecordar(accion, caja) {
    if (!configuracion.puedeRecordar || !RUTA_RECORDAR.test(configuracion.recordarUrl || '')) return;
    if (typeof accion.variant_id !== 'number') return;
    var boton = crear('button', 'gtg-vendedor__button gtg-vendedor__button--quiet', texto('recordar_talla'));
    boton.type = 'button';
    boton.addEventListener('click', function () {
      boton.disabled = true;
      fetch(configuracion.recordarUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': configuracion.csrf || '', 'Accept': 'application/json' },
        body: JSON.stringify({ variant_id: accion.variant_id })
      }).then(function (respuesta) {
        return respuesta.json().then(function (cuerpo) { return { ok: respuesta.ok, cuerpo: cuerpo }; });
      }).then(function (resultado) {
        if (!resultado.ok || !resultado.cuerpo || typeof resultado.cuerpo.value !== 'string') {
          boton.disabled = false;
          avisoDeAccion(caja, texto('no_se_pudo_recordar'), false);
          return;
        }
        boton.remove();
        avisoDeAccion(caja, texto('recordado') + ' ' + resultado.cuerpo.value, false);
      }).catch(function () {
        boton.disabled = false;
        avisoDeAccion(caja, texto('no_se_pudo_recordar'), false);
      });
    });
    caja.appendChild(boton);
    desplazarAlFinal();
  }

  function pintarAccion(accion, caja) {
    if (!accion || typeof accion.label !== 'string') return null;
    if (accion.type === 'add_to_cart') {
      // Sin un destino valido no se pinta el boton: seria un control muerto.
      if (!RUTA_AGREGAR.test(accion.endpoint || '')) return null;
      var boton = crear('button', 'gtg-vendedor__button', accion.label);
      boton.type = 'button';
      boton.addEventListener('click', function () { agregarAlCarrito(accion, boton, caja); });
      return boton;
    }
    if (accion.type === 'open_solution') {
      // Otra solucion de GoToGym: solo direcciones que la tienda declaro.
      var permitidas = Array.isArray(configuracion.soluciones) ? configuracion.soluciones : [];
      if (permitidas.indexOf(accion.url) === -1) return null;
      var externo = crear('a', 'gtg-vendedor__button gtg-vendedor__button--quiet', accion.label);
      externo.href = accion.url;
      externo.target = '_blank';
      externo.rel = 'noopener noreferrer';
      externo.addEventListener('click', function () {
        medir('vendedor_solution_click', { solucion: String(accion.solution || '') });
      });
      return externo;
    }
    if (!RUTA_ENLACE.test(accion.url || '')) return null;
    var enlace = crear('a', 'gtg-vendedor__button gtg-vendedor__button--quiet', accion.label);
    enlace.href = accion.url;
    enlace.addEventListener('click', function (evento) {
      if (accion.type === 'open_contact') {
        medir('vendedor_handoff', { origen: 'accion' });
        if (abrirAtencion()) evento.preventDefault();
      } else if (accion.type === 'open_product') medir('vendedor_product_click', { origen: 'accion', producto: accion.product_id || 0 });
    });
    return enlace;
  }

  function pintarAsistente(entrada) {
    var fila = crear('div', 'gtg-vendedor__row');
    fila.appendChild(crear('span', 'coach-orb coach-orb--sm')).setAttribute('aria-hidden', 'true');
    var caja = crear('div', 'gtg-vendedor__msg gtg-vendedor__msg--bot');
    fila.appendChild(caja);
    caja.appendChild(crear('span', 'sr-only', texto('coach') + ': '));
    caja.appendChild(crear('p', null, String(entrada.t || '')));

    var tarjetas = Array.isArray(entrada.c) ? entrada.c : [];
    if (tarjetas.length) {
      var lista = crear('ul', 'gtg-vendedor__cards');
      tarjetas.forEach(function (tarjeta) {
        var item = pintarTarjeta(tarjeta);
        if (item) lista.appendChild(item);
      });
      if (lista.children.length) caja.appendChild(lista);
    }

    var acciones = Array.isArray(entrada.a) ? entrada.a : [];
    if (acciones.length) {
      var contenedor = crear('div', 'gtg-vendedor__actions');
      acciones.forEach(function (accion) {
        var control = pintarAccion(accion, contenedor);
        if (control) contenedor.appendChild(control);
      });
      if (contenedor.children.length) caja.appendChild(contenedor);
    }
    registro.appendChild(fila);
    desplazarAlFinal();
  }

  function ocultarBienvenida() {
    if (sugerencias) bienvenida.hidden = true;
  }

  // Al abrir sobre una conversacion reciente, las sugerencias quedan a mano
  // encima del campo; desaparecen en cuanto la persona escribe.
  function mostrarAtajos(visible) {
    if (atajos) atajos.hidden = !(visible && bienvenida && bienvenida.hidden);
  }

  function restaurarHistorial() {
    historial = leerHistorial();
    if (historial.length) ocultarBienvenida();
    historial.forEach(function (entrada) {
      if (!entrada || typeof entrada.t !== 'string') return;
      if (entrada.r === 'u') pintarUsuario(entrada.t);
      else if (entrada.r === 'b') pintarAsistente(entrada);
    });
  }

  // --- Errores y estados -------------------------------------------------

  function mostrarEstado(visible) {
    estado.hidden = !visible;
    registro.setAttribute('aria-busy', visible ? 'true' : 'false');
    // La linea de estado le quita alto a la conversacion: sin volver al final,
    // el ultimo mensaje quedaria cortado por abajo.
    desplazarAlFinal();
  }

  function ocultarError() {
    cajaError.hidden = true;
  }

  function actualizarControles() {
    var ocupado = enviando || temporizadorEspera !== null;
    botonEnviar.disabled = ocupado;
    botonNueva.disabled = enviando;
    botonReintentar.disabled = ocupado;
  }

  function mostrarError(codigo, esperaSegundos, urlContacto, diagnostico) {
    var mensaje = texto('error_' + codigo) || texto('error_error');
    // `diagnostic` solo llega para el personal del sitio: el motivo tecnico
    // del fallo, para saber que paso sin acceso a los logs del servidor.
    if (typeof diagnostico === 'string' && diagnostico) mensaje += ' [' + diagnostico + ']';
    textoError.textContent = mensaje;
    botonReintentar.hidden = !!SIN_REINTENTO[codigo];
    if (RUTA_ENLACE.test(urlContacto || '')) enlaceContacto.href = urlContacto;
    cajaError.hidden = false;
    medir('vendedor_error', { codigo: codigo });

    // El limitador de uso responde 429 sin cuerpo: sin una espera propia se
    // podria insistir una y otra vez.
    if (codigo === 'espera' && !(esperaSegundos > 0)) esperaSegundos = ESPERA_POR_DEFECTO;

    if (esperaSegundos > 0) {
      if (temporizadorEspera) window.clearTimeout(temporizadorEspera);
      temporizadorEspera = window.setTimeout(function () {
        temporizadorEspera = null;
        actualizarControles();
      }, esperaSegundos * 1000);
    }
    actualizarControles();
  }

  function codigoSegunEstado(estadoHttp) {
    if (estadoHttp === 429) return 'espera';
    if (estadoHttp === 403) return 'sesion';
    if (estadoHttp === 404) return 'no_disponible';
    if (estadoHttp === 409) return 'limite_turnos';
    if (estadoHttp === 400 || estadoHttp === 413 || estadoHttp === 415) return 'mensaje_invalido';
    return 'error';
  }

  // --- Envio ---------------------------------------------------------------

  function enviar(mensaje) {
    if (enviando || temporizadorEspera !== null) return;
    ocultarError();
    enviando = true;
    mostrarEstado(true);
    actualizarControles();

    var cuerpo = { message: mensaje };
    if (nuevaConversacion) cuerpo['new'] = true;

    fetch(configuracion.endpoint, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-CSRFToken': configuracion.csrf || '',
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: JSON.stringify(cuerpo)
    }).then(function (respuesta) {
      // Un 429 del limitador o un 403 de CSRF pueden no traer JSON.
      return respuesta.text().then(function (crudo) {
        var datos = null;
        try { datos = JSON.parse(crudo); } catch (error) { datos = null; }
        return { estado: respuesta.status, datos: datos };
      });
    }).then(function (resultado) {
      var datos = resultado.datos;
      if (datos && datos.ok === true && typeof datos.reply === 'string') {
        nuevaConversacion = false;
        var entrada = {
          r: 'b',
          t: datos.reply,
          c: Array.isArray(datos.cards) ? datos.cards : [],
          a: Array.isArray(datos.actions) ? datos.actions : []
        };
        historial.push(entrada);
        guardarHistorial();
        pintarAsistente(entrada);
        medir('vendedor_message', {
          turno: datos.conversation && datos.conversation.turns || 0,
          tarjetas: entrada.c.length,
          acciones: entrada.a.length
        });
        return;
      }
      var codigo = datos && typeof datos.error === 'string' ? datos.error : codigoSegunEstado(resultado.estado);
      mostrarError(codigo, datos && datos.retry_after, datos && datos.contact_url, datos && datos.diagnostic);
    }).catch(function () {
      mostrarError('red', 0, null);
    }).then(function () {
      enviando = false;
      mostrarEstado(false);
      actualizarControles();
    });
  }

  // Sin IA configurada no hay a quien preguntar: se responde aqui mismo, como
  // un mensaje del Coach, con el aviso y el camino a una persona.
  function responderQueNoHayIA() {
    var entrada = { r: 'b', t: texto('no_disponible_ia'), c: [], a: [] };
    if (RUTA_ENLACE.test(configuracion.contactUrl || '')) {
      entrada.a.push({ type: 'open_contact', label: texto('hablar_con_persona'), url: configuracion.contactUrl });
    }
    historial.push(entrada);
    guardarHistorial();
    pintarAsistente(entrada);
    medir('vendedor_error', { codigo: 'no_disponible' });
  }

  function enviarDesdeElCampo() {
    // Enter no pasa por el boton deshabilitado: sin esto el mensaje se
    // pintaria sin llegar a enviarse.
    if (enviando || temporizadorEspera !== null) return;
    var mensaje = campo.value.trim();
    if (!mensaje || mensaje.length > (configuracion.maxLength || 600)) return;
    campo.value = '';
    ultimoMensaje = mensaje;
    ocultarBienvenida();
    mostrarAtajos(false);
    historial.push({ r: 'u', t: mensaje });
    guardarHistorial();
    pintarUsuario(mensaje);
    if (configuracion.disponible === false) {
      responderQueNoHayIA();
      return;
    }
    enviar(mensaje);
  }

  function empezarDeNuevo() {
    historial = [];
    guardarHistorial();
    Array.prototype.slice.call(registro.children).forEach(function (nodo) {
      if (nodo !== bienvenida) registro.removeChild(nodo);
    });
    bienvenida.hidden = false;
    mostrarAtajos(false);
    nuevaConversacion = true;
    ultimoMensaje = '';
    ocultarError();
    registro.focus();
  }

  // --- Abrir y cerrar --------------------------------------------------------

  function cerrarMenuMovil() {
    var menu = document.getElementById('mobile-menu');
    if (!menu || menu.hidden) return;
    menu.hidden = true;
    var alternador = document.querySelector('[data-menu-toggle]');
    if (alternador) alternador.setAttribute('aria-expanded', 'false');
  }

  function marcarBotones(expandido) {
    Array.prototype.forEach.call(botones, function (boton) {
      boton.setAttribute('aria-expanded', expandido ? 'true' : 'false');
    });
  }

  // En escritorio el panel va junto a la pagina, que sigue en uso: no es modal ni
  // atrapa el foco. En movil ocupa toda la pantalla y si lo es. Debe coincidir
  // con el corte de vendedor.css.
  var consultaEscritorio = window.matchMedia ? window.matchMedia('(min-width: 901px)') : null;

  function esModal() {
    return !(consultaEscritorio && consultaEscritorio.matches);
  }

  function abrir(origen) {
    if (abierto) return;
    disparador = origen || null;
    cerrarMenuMovil();
    panel.setAttribute('aria-modal', esModal() ? 'true' : 'false');
    panel.hidden = false;
    if (velo) velo.hidden = false;
    document.documentElement.classList.add('gtg-vendedor-abierto');
    marcarBotones(true);
    abierto = true;
    if (aviso) aviso.hidden = guardado(CLAVE_AVISO) === '1';
    // Si la conversacion vencio mientras la pestana seguia abierta, se empieza
    // de nuevo con la bienvenida en vez de mostrar lo que el Coach ya olvido.
    if (historial.length && !leerHistorial().length) empezarDeNuevo();
    mostrarAtajos(historial.length > 0);
    desplazarAlFinal();
    panel.focus();
  }

  function devolverElFoco() {
    var destino = esVisible(disparador) ? disparador : null;
    if (!destino) {
      Array.prototype.some.call(botones, function (boton) {
        if (esVisible(boton)) { destino = boton; return true; }
        return false;
      });
    }
    if (!destino) destino = document.querySelector('[data-menu-toggle]');
    if (destino) destino.focus();
  }

  function cerrar() {
    if (!abierto) return;
    panel.hidden = true;
    if (velo) velo.hidden = true;
    document.documentElement.classList.remove('gtg-vendedor-abierto');
    marcarBotones(false);
    abierto = false;
    devolverElFoco();
    disparador = null;
  }

  function enfocables() {
    var candidatos = panel.querySelectorAll(
      'a[href], button:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    return Array.prototype.filter.call(candidatos, function (nodo) {
      return nodo.getClientRects().length > 0 && !nodo.closest('[hidden]');
    });
  }

  function atraparElFoco(evento) {
    if (evento.key !== 'Tab' || !esModal()) return;
    var lista = enfocables();
    if (!lista.length) { evento.preventDefault(); return; }
    var primero = lista[0];
    var ultimo = lista[lista.length - 1];
    if (evento.shiftKey && (document.activeElement === primero || document.activeElement === panel)) {
      evento.preventDefault();
      ultimo.focus();
    } else if (!evento.shiftKey && document.activeElement === ultimo) {
      evento.preventDefault();
      primero.focus();
    }
  }

  // --- Eventos ---------------------------------------------------------------

  Array.prototype.forEach.call(botones, function (boton) {
    boton.hidden = false;
    boton.addEventListener('click', function (evento) {
      evento.stopPropagation();
      if (abierto) cerrar(); else abrir(boton);
    });
  });

  botonCerrar.addEventListener('click', cerrar);
  if (velo) velo.addEventListener('click', cerrar);
  botonNueva.addEventListener('click', empezarDeNuevo);

  // Una sugerencia es un mensaje como cualquier otro: se escribe en el campo
  // y sigue el mismo camino, con los mismos limites.
  function alElegirSugerencia(evento) {
    var chip = evento.target.closest ? evento.target.closest('[data-sugerencia]') : null;
    if (!chip || enviando || temporizadorEspera !== null) return;
    registro.focus();
    campo.value = chip.textContent.trim();
    enviarDesdeElCampo();
  }
  if (sugerencias) sugerencias.addEventListener('click', alElegirSugerencia);
  if (atajos) atajos.addEventListener('click', alElegirSugerencia);

  if (botonAviso) {
    botonAviso.addEventListener('click', function () {
      guardar(CLAVE_AVISO, '1');
      aviso.hidden = true;
      campo.focus();
    });
  }

  formulario.addEventListener('submit', function (evento) {
    evento.preventDefault();
    enviarDesdeElCampo();
  });

  campo.addEventListener('keydown', function (evento) {
    if (evento.key === 'Enter' && !evento.shiftKey && !evento.isComposing) {
      evento.preventDefault();
      enviarDesdeElCampo();
    }
  });

  botonReintentar.addEventListener('click', function () {
    if (ultimoMensaje) enviar(ultimoMensaje);
  });

  enlaceContacto.addEventListener('click', function (evento) {
    medir('vendedor_handoff', { origen: 'error' });
    if (abrirAtencion()) evento.preventDefault();
  });

  // --- Atencion humana con radicado (agente 7) ---------------------------
  // El enlace a Contacto sigue siendo el respaldo: sin formulario o sin
  // JavaScript, se navega a la pagina de contacto como antes.

  var formAtencion = panel.querySelector('[data-vendedor-atencion]');
  var errorAtencion = panel.querySelector('[data-vendedor-atencion-error]');
  var RUTA_ATENCION = /^\/[a-z]{2}\/vendedor\/atencion\/$/;

  function abrirAtencion() {
    if (!formAtencion || !RUTA_ATENCION.test(configuracion.atencionUrl || '')) return false;
    formAtencion.hidden = false;
    errorAtencion.hidden = true;
    var primero = formAtencion.querySelector('#atencion-nombre');
    if (primero && primero.value) primero = formAtencion.querySelector('#atencion-mensaje');
    if (primero) primero.focus();
    return true;
  }

  function cerrarAtencion() {
    if (!formAtencion) return;
    formAtencion.hidden = true;
    if (campo) campo.focus();
  }

  function errorDeAtencion(clave) {
    errorAtencion.textContent = texto(clave);
    errorAtencion.hidden = false;
  }

  if (formAtencion) {
    panel.querySelectorAll('[data-vendedor-abrir-atencion]').forEach(function (enlace) {
      enlace.addEventListener('click', function (evento) {
        medir('vendedor_handoff', { origen: 'bienvenida' });
        if (abrirAtencion()) evento.preventDefault();
      });
    });
    formAtencion.querySelector('[data-vendedor-atencion-cancelar]').addEventListener('click', cerrarAtencion);
    formAtencion.addEventListener('submit', function (evento) {
      evento.preventDefault();
      var boton = formAtencion.querySelector('[data-vendedor-atencion-enviar]');
      var datos = {
        nombre: formAtencion.elements.nombre.value.trim(),
        email: formAtencion.elements.email.value.trim(),
        motivo: formAtencion.elements.motivo.value,
        mensaje: formAtencion.elements.mensaje.value.trim(),
        acepta_contacto: formAtencion.elements.acepta_contacto.checked
      };
      if (!datos.nombre || !datos.email || datos.mensaje.length < 5 || !datos.acepta_contacto) {
        errorDeAtencion('atencion_campos');
        return;
      }
      boton.disabled = true;
      fetch(configuracion.atencionUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': configuracion.csrf || '', 'Accept': 'application/json' },
        body: JSON.stringify(datos)
      }).then(function (respuesta) {
        return respuesta.json().then(function (cuerpo) { return { estado: respuesta.status, cuerpo: cuerpo }; },
          function () { return { estado: respuesta.status, cuerpo: null }; });
      }).then(function (resultado) {
        boton.disabled = false;
        var cuerpo = resultado.cuerpo || {};
        // Solo un 201 con radicado cuenta como solicitud creada.
        if (resultado.estado !== 201 || typeof cuerpo.radicado !== 'string' || !/^GTG-\d{4}-\d{6}$/.test(cuerpo.radicado)) {
          errorDeAtencion(resultado.estado === 429 ? 'atencion_espera' : resultado.estado === 400 ? 'atencion_campos' : 'atencion_error');
          return;
        }
        var mensaje = texto('atencion_creada') + ' ' + cuerpo.radicado + '. ' +
          (cuerpo.correo_enviado ? texto('atencion_correo') + ' ' + String(cuerpo.email || '') + '.' : texto('atencion_sin_correo'));
        var entrada = { r: 'b', t: mensaje };
        historial.push(entrada);
        guardarHistorial();
        pintarAsistente(entrada);
        formAtencion.elements.mensaje.value = '';
        formAtencion.elements.acepta_contacto.checked = false;
        cerrarAtencion();
        desplazarAlFinal();
        medir('vendedor_handoff_creado', { motivo: datos.motivo });
      }).catch(function () {
        boton.disabled = false;
        errorDeAtencion('atencion_error');
      });
    });
  }

  panel.addEventListener('keydown', atraparElFoco);
  document.addEventListener('keydown', function (evento) {
    if (evento.key === 'Escape' && abierto) cerrar();
  });

  restaurarHistorial();
})();
