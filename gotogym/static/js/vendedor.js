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
 *  - Una foto adjunta se reduce aqui (maximo 1280 px, JPEG) antes de subirla y
 *    no se guarda en el historial: solo queda el rotulo de que hubo una foto.
 *    De un archivo adjunto solo queda su nombre; el contenido lo lee la tienda.
 *  - Herramientas del boton "+" (las de Quantum Coach): tomar foto, adjuntar
 *    archivo, subir imagen y voz. El microfono dicta con el reconocimiento del
 *    navegador; si no lo hay, graba (WAV de 16 kHz, maximo 30 s) y lo
 *    transcribe el Coach a traves de la tienda. Lo dictado queda en el campo
 *    para revisarlo antes de enviar. "Leer respuestas en voz alta" nace
 *    apagado, usa la voz de GoToGym y se recuerda en localStorage (solo en
 *    este navegador).
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
  var identityEpoch = configuracion.identityEpoch || '';
  var CLAVE_AVISO = 'gtg_vendedor_aviso';
  var MAX_ENTRADAS = 24;
  var ESPERA_POR_DEFECTO = 10;
  var VIGENCIA_MS = (configuracion.vigenciaHistorial > 0 ? configuracion.vigenciaHistorial : 1800) * 1000;
  // Rutas internas a las que puede apuntar un enlace del panel.
  var RUTA_ENLACE = /^\/[a-z]{2}\/(tienda|carrito|pedidos-tienda|contacto|tarjetas-regalo)\/[A-Za-z0-9\-_\/.%]*$/;
  var RUTA_IMAGEN = /^\/(media|static)\/[A-Za-z0-9\-_\/.%]+$/;
  var RUTA_AGREGAR = /^\/[a-z]{2}\/carrito\/add\/\d+\/$/;
  var RUTA_RECORDAR = /^\/[a-z]{2}\/vendedor\/personalizacion\/recordar\/$/;
  var RUTA_IMAGEN_SUBIDA = /^\/[a-z]{2}\/vendedor\/imagen\/$/;
  var RUTA_DOCUMENTO = /^\/[a-z]{2}\/vendedor\/documento\/$/;
  var RUTA_VOZ = /^\/[a-z]{2}\/vendedor\/voz\/$/;
  var LADO_FOTO = 1280;
  var MAX_BYTES_FOTO = 8 * 1024 * 1024;
  var MAX_BYTES_DOCUMENTO = 5 * 1024 * 1024;
  var MAX_LARGO_NOMBRE = 80;
  var CLAVE_VOZ = 'gtg_vendedor_voz';
  var FRECUENCIA_VOZ = 16000;
  var MAX_SEGUNDOS_VOZ = 30;
  var SEGUNDOS_SILENCIO_DICTADO = 5;
  var SIN_REINTENTO = {
    limite_turnos: true, limite_diario: true, mensaje_invalido: true,
    imagen_invalida: true, imagen_grande: true, imagen_no_disponible: true, limite_imagenes: true,
    documento_invalido: true, documento_grande: true, documento_sin_texto: true, documento_protegido: true,
    microfono: true, voz_invalida: true, voz_larga: true, voz_no_disponible: true, limite_voz: true
  };

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
  var botonMas = panel.querySelector('[data-vendedor-mas]');
  var menuHerramientas = panel.querySelector('[data-vendedor-herramientas]');
  var campoCamara = panel.querySelector('[data-vendedor-camara]');
  var campoArchivo = panel.querySelector('[data-vendedor-archivo]');
  var campoDocumento = panel.querySelector('[data-vendedor-documento]');
  var cajaAdjunto = panel.querySelector('[data-vendedor-adjunto]');
  var imagenAdjunto = panel.querySelector('[data-vendedor-adjunto-img]');
  var iconoAdjunto = panel.querySelector('[data-vendedor-adjunto-icono]');
  var nombreAdjunto = panel.querySelector('[data-vendedor-adjunto-nombre]');
  var avisoAdjunto = panel.querySelector('[data-vendedor-adjunto-aviso]');
  var botonQuitarAdjunto = panel.querySelector('[data-vendedor-quitar-adjunto]');
  var botonMicrofono = panel.querySelector('[data-vendedor-microfono]');
  var barraGrabando = panel.querySelector('[data-vendedor-grabando]');
  var compositor = panel.querySelector('[data-vendedor-composer]');
  // Voz de GoToGym: espanol de Colombia, o ingles si el sitio esta en ingles.
  var REGION_GOTOGYM = /^en/i.test(document.documentElement.lang || '') ? 'en-US' : 'es-CO';
  var fotosHabilitadas = !!(campoArchivo && cajaAdjunto && RUTA_IMAGEN_SUBIDA.test(configuracion.imagenUrl || ''));
  var documentosHabilitados = !!(campoDocumento && cajaAdjunto && RUTA_DOCUMENTO.test(configuracion.documentoUrl || ''));
  var sintesis = window.speechSynthesis && window.SpeechSynthesisUtterance ? window.speechSynthesis : null;
  var Reconocimiento = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  var ContextoDeAudio = window.AudioContext || window.webkitAudioContext || null;
  var puedeGrabar = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && ContextoDeAudio &&
    RUTA_VOZ.test(configuracion.vozUrl || ''));

  var abierto = false;
  var enviando = false;
  var disparador = null;
  var ultimoMensaje = '';
  var nuevaConversacion = false;
  var temporizadorEspera = null;
  var historial = [];
  var adjunto = null;        // { tipo: 'foto' | 'documento', blob, url, nombre } listo para enviar
  var ultimoAdjunto = null;  // para reintentar el ultimo envio con foto o archivo
  var reconocimiento = null; // dictado del navegador en curso
  var grabacion = null;      // grabacion de respaldo en curso
  var transcribiendo = false;
  var temporizadorNota = null;

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
    guardar(CLAVE_HISTORIAL, JSON.stringify({ ts: Date.now(), epoch: identityEpoch, e: historial.slice(-MAX_ENTRADAS) }));
  }

  // Un historial vencido, sin hora (formato anterior) o ilegible se descarta.
  function leerHistorial() {
    var crudo = guardado(CLAVE_HISTORIAL);
    if (!crudo) return [];
    try {
      var datos = JSON.parse(crudo);
      var vigente = datos && typeof datos.ts === 'number' && Date.now() - datos.ts <= VIGENCIA_MS &&
        datos.epoch === identityEpoch;
      return vigente && Array.isArray(datos.e) ? datos.e.slice(-MAX_ENTRADAS) : [];
    } catch (error) {
      return [];
    }
  }

  // --- Pintado de mensajes ----------------------------------------------

  function pintarUsuario(contenido, urlFoto, nombreArchivo) {
    var caja = crear('div', 'gtg-vendedor__msg gtg-vendedor__msg--user');
    caja.appendChild(crear('span', 'sr-only', texto('tu') + ': '));
    if (urlFoto) {
      var foto = crear('img', 'gtg-vendedor__msg-foto');
      foto.src = urlFoto;
      foto.alt = texto('foto_enviada');
      caja.appendChild(foto);
    }
    if (nombreArchivo) caja.appendChild(crear('p', 'gtg-vendedor__msg-archivo', texto('archivo_enviado') + ' ' + nombreArchivo));
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
    // Lo que se busco a partir de una foto, con las etiquetas que da la tienda.
    if (Array.isArray(entrada.v) && entrada.v.length) {
      var buscado = entrada.v.filter(function (parte) { return typeof parte === 'string'; }).slice(0, 8);
      caja.appendChild(crear('p', 'gtg-vendedor__busqueda', texto('busque') + ' ' + buscado.join(' · ')));
    }
    caja.appendChild(crear('p', null, String(entrada.t || '')));
    if (typeof entrada.n === 'string' && entrada.n) caja.appendChild(crear('p', 'gtg-vendedor__busqueda', entrada.n));

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
      // Una foto vieja no se vuelve a mostrar; de un archivo queda el nombre.
      if (entrada.r === 'u') pintarUsuario(entrada.t, '', typeof entrada.d === 'string' ? entrada.d : '');
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

  // Sin texto ni adjunto el boton de enviar se ve en reposo.
  function actualizarEnvio() {
    if (compositor) compositor.classList.toggle('gtg-vendedor__composer--vacio', !campo.value.trim() && !adjunto);
  }

  function actualizarControles() {
    var ocupado = enviando || temporizadorEspera !== null;
    botonEnviar.disabled = ocupado;
    actualizarEnvio();
    if (botonMas) botonMas.disabled = ocupado;
    if (botonMicrofono) botonMicrofono.disabled = transcribiendo;
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

  // --- Identidad actual del servidor ------------------------------------------
  // Evita atribuir a una persona el historial visual de otra cuenta o del
  // visitante que inició sesión. El navegador nunca elige el principal.
  function entradaDeUsuario(mensaje, adj) {
    if (adj && adj.tipo === 'foto') return { r: 'u', t: mensaje, f: 1 };
    // Sin texto, el mensaje ya es el rotulo con el nombre del archivo.
    if (adj && adj.tipo === 'documento' && !adj.sinTexto) return { r: 'u', t: mensaje, d: adj.nombre };
    return { r: 'u', t: mensaje };
  }

  function verificarEpoch(mensaje, adj) {
    if (!configuracion.estadoUrl) return Promise.resolve();
    return fetch(configuracion.estadoUrl, {
      method: 'GET',
      credentials: 'same-origin',
      cache: 'no-store',
      headers: { 'Accept': 'application/json' }
    }).then(function (respuesta) {
      if (!respuesta.ok) throw new Error('identity_status_unavailable');
      return respuesta.json();
    }).then(function (datos) {
      if (!datos || !/^[0-9a-f]{32}$/.test(datos.epoch || '')) {
        throw new Error('identity_epoch_invalid');
      }
      if (datos.epoch !== identityEpoch) {
        identityEpoch = datos.epoch;
        empezarDeNuevo();
        // El mensaje recién escrito no se pierde cuando cambia el contexto;
        // todo el historial anterior se descarta antes de reenviarlo.
        ultimoMensaje = mensaje;
        ocultarBienvenida();
        historial.push(entradaDeUsuario(mensaje, adj));
        guardarHistorial();
        pintarUsuario(mensaje, adj && adj.tipo === 'foto' ? adj.url : '',
          adj && adj.tipo === 'documento' && !adj.sinTexto ? adj.nombre : '');
        medir('vendedor_identity_transition', { mode: datos.mode || 'unknown' });
      }
    });
  }

  // --- Envio ---------------------------------------------------------------

  function cabecerasSeguras() {
    return {
      'Accept': 'application/json',
      'X-CSRFToken': configuracion.csrf || '',
      'X-Requested-With': 'XMLHttpRequest'
    };
  }

  // Turno de texto (JSON) o con foto o archivo (multipart, sin Content-Type
  // propio: lo pone el navegador con el separador).
  function peticionDeTurno(mensaje, adj) {
    var cabeceras = cabecerasSeguras();
    if (adj) {
      var formulario = new FormData();
      var esFoto = adj.tipo === 'foto';
      formulario.append(esFoto ? 'imagen' : 'documento', adj.blob, esFoto ? 'foto.jpg' : adj.nombre);
      // El rotulo visible no es un mensaje: sin texto, el servidor pone el suyo.
      if (!adj.sinTexto) formulario.append('message', mensaje);
      if (nuevaConversacion) formulario.append('new', '1');
      var kb = Math.round(adj.blob.size / 1024);
      if (esFoto) medir('vendedor_image_sent', { kb: kb });
      else medir('vendedor_document_sent', { kb: kb });
      return fetch(esFoto ? configuracion.imagenUrl : configuracion.documentoUrl, {
        method: 'POST', credentials: 'same-origin', headers: cabeceras, body: formulario
      });
    }
    var cuerpo = { message: mensaje };
    if (nuevaConversacion) cuerpo['new'] = true;
    cabeceras['Content-Type'] = 'application/json';
    return fetch(configuracion.endpoint, {
      method: 'POST', credentials: 'same-origin', headers: cabeceras, body: JSON.stringify(cuerpo)
    });
  }

  function enviar(mensaje, adj) {
    if (enviando || temporizadorEspera !== null) return;
    ocultarError();
    enviando = true;
    mostrarEstado(true);
    actualizarControles();

    verificarEpoch(mensaje, adj).then(function () {
      return peticionDeTurno(mensaje, adj);
    }).then(function (respuesta) {
      // Un 429 del limitador o un 403 de CSRF pueden no traer JSON.
      return respuesta.text().then(function (crudo) {
        var datos = null;
        try { datos = JSON.parse(crudo); } catch (error) { datos = null; }
        return { estado: respuesta.status, datos: datos };
      });
    }).then(function (resultado) {
      var datos = resultado.datos;
      if (datos && datos.ok === true && datos.notice === 'sin_prenda') {
        var aviso = { r: 'b', t: texto('aviso_sin_prenda'), c: [], a: [] };
        historial.push(aviso);
        guardarHistorial();
        pintarAsistente(aviso);
        ultimoAdjunto = null;
        return;
      }
      if (datos && datos.ok === true && typeof datos.reply === 'string') {
        nuevaConversacion = false;
        ultimoAdjunto = null;
        var entrada = {
          r: 'b',
          t: datos.reply,
          c: Array.isArray(datos.cards) ? datos.cards : [],
          a: Array.isArray(datos.actions) ? datos.actions : []
        };
        if (datos.visual && Array.isArray(datos.visual.summary)) entrada.v = datos.visual.summary;
        if (datos.document && datos.document.truncated === true) entrada.n = texto('documento_recortado');
        historial.push(entrada);
        guardarHistorial();
        pintarAsistente(entrada);
        hablarSiCorresponde(entrada.t);
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
    detenerDictado(false);
    var mensaje = campo.value.trim();
    var adj = null;
    if (adjunto) {
      // Con adjunto el texto es opcional: el rotulo solo se muestra.
      adj = { tipo: adjunto.tipo, blob: adjunto.blob, url: adjunto.url, nombre: adjunto.nombre, sinTexto: !mensaje };
      if (!mensaje) mensaje = adj.tipo === 'foto' ? texto('foto_enviada') : texto('archivo_enviado') + ' ' + adj.nombre;
    }
    if (!mensaje || mensaje.length > (configuracion.maxLength || 600)) return;
    campo.value = '';
    ultimoMensaje = mensaje;
    ultimoAdjunto = adj;
    ocultarBienvenida();
    mostrarAtajos(false);
    historial.push(entradaDeUsuario(mensaje, adj));
    guardarHistorial();
    pintarUsuario(mensaje, adj && adj.tipo === 'foto' ? adj.url : '',
      adj && adj.tipo === 'documento' && !adj.sinTexto ? adj.nombre : '');
    if (adj) soltarAdjunto(false);
    if (configuracion.disponible === false) {
      responderQueNoHayIA();
      return;
    }
    enviar(mensaje, adj);
  }

  // --- Foto o archivo adjunto ----------------------------------------------------

  function limpiarCampos() {
    [campoCamara, campoArchivo, campoDocumento].forEach(function (nodo) { if (nodo) nodo.value = ''; });
  }

  function soltarAdjunto(liberarUrl) {
    // La URL local se conserva mientras la foto se vea en la conversacion.
    if (liberarUrl && adjunto && adjunto.url) URL.revokeObjectURL(adjunto.url);
    adjunto = null;
    if (cajaAdjunto) cajaAdjunto.hidden = true;
    limpiarCampos();
    actualizarEnvio();
  }

  function mostrarAdjunto(nuevo) {
    soltarAdjunto(true);
    adjunto = nuevo;
    var esFoto = nuevo.tipo === 'foto';
    imagenAdjunto.hidden = !esFoto;
    if (esFoto) imagenAdjunto.src = nuevo.url;
    if (iconoAdjunto) iconoAdjunto.hidden = esFoto;
    if (nombreAdjunto) {
      nombreAdjunto.hidden = esFoto;
      nombreAdjunto.textContent = esFoto ? '' : nuevo.nombre;
    }
    if (avisoAdjunto) avisoAdjunto.textContent = texto(esFoto ? 'aviso_foto' : 'aviso_documento');
    cajaAdjunto.hidden = false;
    actualizarEnvio();
    campo.focus();
  }

  function nombreCorto(nombre) {
    var limpio = String(nombre || '').replace(/[\u0000-\u001f]/g, '').trim() || 'archivo';
    return limpio.length > MAX_LARGO_NOMBRE ? limpio.slice(0, MAX_LARGO_NOMBRE - 1) + '\u2026' : limpio;
  }

  // Reduce la foto en el navegador: menos datos por la red movil y sin los
  // metadatos del archivo original (el lienzo no los copia). Si el navegador
  // no puede leerla (HEIC fuera de Safari), se sube tal cual y la reduce la
  // tienda.
  function reducirFoto(archivo) {
    if (!window.createImageBitmap || !document.createElement('canvas').toBlob) {
      return Promise.resolve(archivo);
    }
    return window.createImageBitmap(archivo, { imageOrientation: 'from-image' }).then(function (mapa) {
      var escala = Math.min(1, LADO_FOTO / Math.max(mapa.width, mapa.height));
      var lienzo = document.createElement('canvas');
      lienzo.width = Math.max(1, Math.round(mapa.width * escala));
      lienzo.height = Math.max(1, Math.round(mapa.height * escala));
      var contexto = lienzo.getContext('2d');
      contexto.fillStyle = 'white';
      contexto.fillRect(0, 0, lienzo.width, lienzo.height);
      contexto.drawImage(mapa, 0, 0, lienzo.width, lienzo.height);
      if (mapa.close) mapa.close();
      return new Promise(function (resolver) {
        lienzo.toBlob(function (blob) { resolver(blob || archivo); }, 'image/jpeg', 0.85);
      });
    }).catch(function () { return archivo; });
  }

  function prepararFoto(archivo) {
    if (archivo.size > MAX_BYTES_FOTO) {
      soltarAdjunto(true);
      mostrarError('imagen_grande', 0, null);
      return;
    }
    ocultarError();
    reducirFoto(archivo).then(function (blob) {
      if (blob.size > MAX_BYTES_FOTO) {
        soltarAdjunto(true);
        mostrarError('imagen_grande', 0, null);
        return;
      }
      mostrarAdjunto({ tipo: 'foto', blob: blob, url: URL.createObjectURL(blob), nombre: '' });
    });
  }

  function alElegirFoto(evento) {
    var archivo = evento.target.files && evento.target.files[0];
    if (archivo) prepararFoto(archivo);
  }

  // Un archivo puede ser una imagen (va a la busqueda por foto) o un
  // documento que la tienda lee en memoria.
  function alElegirDocumento() {
    var archivo = campoDocumento.files && campoDocumento.files[0];
    if (!archivo) return;
    if (/^image\//.test(archivo.type || '') && fotosHabilitadas) {
      prepararFoto(archivo);
      return;
    }
    if (archivo.size > MAX_BYTES_DOCUMENTO) {
      soltarAdjunto(true);
      mostrarError('documento_grande', 0, null);
      return;
    }
    ocultarError();
    mostrarAdjunto({ tipo: 'documento', blob: archivo, url: '', nombre: nombreCorto(archivo.name) });
  }

  // --- Menu de herramientas (boton +) ----------------------------------------------

  function itemsDelMenu() {
    if (!menuHerramientas) return [];
    return Array.prototype.filter.call(menuHerramientas.querySelectorAll('[data-herramienta]'), function (item) {
      return !item.hidden;
    });
  }

  function abrirMenu() {
    if (!menuHerramientas || !botonMas) return;
    menuHerramientas.hidden = false;
    botonMas.setAttribute('aria-expanded', 'true');
    var items = itemsDelMenu();
    if (items.length) items[0].focus();
  }

  function cerrarMenu(devolverFoco) {
    if (!menuHerramientas || menuHerramientas.hidden) return false;
    menuHerramientas.hidden = true;
    botonMas.setAttribute('aria-expanded', 'false');
    if (devolverFoco) botonMas.focus();
    return true;
  }

  function moverEnElMenu(evento) {
    var items = itemsDelMenu();
    var posicion = items.indexOf(document.activeElement);
    var destino = null;
    if (evento.key === 'ArrowDown') destino = items[(posicion + 1) % items.length];
    else if (evento.key === 'ArrowUp') destino = items[(posicion - 1 + items.length) % items.length];
    else if (evento.key === 'Home') destino = items[0];
    else if (evento.key === 'End') destino = items[items.length - 1];
    else if (evento.key === 'Tab') cerrarMenu(false);
    if (destino) {
      evento.preventDefault();
      destino.focus();
    }
  }

  function usarHerramienta(nombre) {
    medir('vendedor_tool', { herramienta: nombre });
    // El interruptor de lectura cambia ahi mismo y el menu sigue abierto para verlo.
    if (nombre === 'leer') {
      cambiarLectura();
      return;
    }
    cerrarMenu(false);
    if (nombre === 'camara' && campoCamara) campoCamara.click();
    else if (nombre === 'imagen' && campoArchivo) campoArchivo.click();
    else if (nombre === 'archivo' && campoDocumento) campoDocumento.click();
  }

  // --- Lectura en voz alta (apagada por defecto, voz de GoToGym) ------------------------

  var itemLeer = menuHerramientas ? menuHerramientas.querySelector('[data-herramienta="leer"]') : null;

  function lecturaGuardada() {
    try {
      return JSON.parse(window.localStorage.getItem(CLAVE_VOZ) || '{}').leer === true;
    } catch (error) {
      return false;
    }
  }

  var leerRespuestas = lecturaGuardada();

  function pintarLectura() {
    if (itemLeer) itemLeer.setAttribute('aria-checked', leerRespuestas ? 'true' : 'false');
  }

  function cambiarLectura() {
    leerRespuestas = !leerRespuestas;
    try { window.localStorage.setItem(CLAVE_VOZ, JSON.stringify({ leer: leerRespuestas })); } catch (error) { /* sin almacenamiento */ }
    pintarLectura();
    if (!leerRespuestas) callar();
  }

  function elegirVoz() {
    var voces = sintesis && sintesis.getVoices ? sintesis.getVoices() : [];
    var region = REGION_GOTOGYM.toLowerCase();
    var base = region.split('-')[0];
    var mejor = null;
    var mejorPuntaje = 0;
    Array.prototype.forEach.call(voces || [], function (voz) {
      var idioma = String(voz.lang || '').toLowerCase().replace('_', '-');
      var puntaje = 0;
      if (idioma === region) puntaje += 8;
      if (idioma === base || idioma.indexOf(base + '-') === 0) puntaje += 4;
      if (voz.localService) puntaje += 1;
      if (puntaje > mejorPuntaje) {
        mejor = voz;
        mejorPuntaje = puntaje;
      }
    });
    return mejor;
  }

  function hablar(contenido) {
    var limpio = String(contenido || '').trim();
    if (!sintesis || !limpio) return;
    try {
      sintesis.cancel();
      var locucion = new window.SpeechSynthesisUtterance(limpio);
      locucion.lang = REGION_GOTOGYM;
      var voz = elegirVoz();
      if (voz) {
        locucion.voice = voz;
        locucion.lang = voz.lang || locucion.lang;
      }
      sintesis.speak(locucion);
    } catch (error) { /* la voz nunca debe romper el panel */ }
  }

  function callar() {
    if (!sintesis) return;
    try { sintesis.cancel(); } catch (error) { /* nada que detener */ }
  }

  function hablarSiCorresponde(contenido) {
    if (leerRespuestas) hablar(contenido);
  }

  // --- Microfono: dictado --------------------------------------------------------------

  var notaVoz = null;

  function nota(clave) {
    if (!notaVoz) {
      notaVoz = crear('p', 'gtg-vendedor__nota');
      notaVoz.setAttribute('role', 'status');
      notaVoz.hidden = true;
      compositor.parentNode.insertBefore(notaVoz, compositor);
    }
    if (temporizadorNota) window.clearTimeout(temporizadorNota);
    temporizadorNota = null;
    if (!clave) {
      notaVoz.hidden = true;
      return;
    }
    notaVoz.textContent = texto(clave);
    notaVoz.hidden = false;
    if (clave !== 'transcribiendo') {
      temporizadorNota = window.setTimeout(function () { notaVoz.hidden = true; }, 5000);
    }
  }

  function marcarDictado(activo) {
    if (!botonMicrofono) return;
    botonMicrofono.classList.toggle('is-recording', activo);
    botonMicrofono.setAttribute('aria-pressed', activo ? 'true' : 'false');
    var etiqueta = texto(activo ? 'detener_dictado' : 'dictar');
    botonMicrofono.setAttribute('aria-label', etiqueta);
    botonMicrofono.title = etiqueta;
    if (compositor) compositor.classList.toggle('gtg-vendedor__composer--grabando', activo);
    if (barraGrabando) barraGrabando.textContent = activo ? texto('escuchando') : '';
    if (activo) nota(null);
  }

  function idiomaDeDictado() {
    return REGION_GOTOGYM;
  }

  function ponerEnElCampo(base, dictado) {
    var maximo = configuracion.maxLength || 600;
    campo.value = (base + dictado).slice(0, maximo);
    actualizarEnvio();
  }

  function baseDelCampo() {
    return campo.value.trim() ? campo.value.replace(/\s+$/, '') + ' ' : '';
  }

  function dictarConNavegador() {
    var rec = new Reconocimiento();
    var base = baseDelCampo();
    var definitivo = '';
    var fallo = '';
    // En modo de una sola frase el navegador corta en la primera pausa (~2 s).
    // En modo continuo el corte por silencio lo decide la tienda.
    var silencio = null;
    var limite = null;
    function esperarSilencio() {
      window.clearTimeout(silencio);
      silencio = window.setTimeout(function () { rec.stop(); }, SEGUNDOS_SILENCIO_DICTADO * 1000);
    }
    rec.lang = idiomaDeDictado();
    rec.interimResults = true;
    rec.continuous = true;
    rec.maxAlternatives = 1;
    rec.onresult = function (evento) {
      // Se rearma con todos los resultados: en modo continuo la lista crece
      // y sumar solo desde resultIndex duplica frases en algunos navegadores.
      var finales = '';
      var provisional = '';
      for (var i = 0; i < evento.results.length; i++) {
        var resultado = evento.results[i];
        if (resultado.isFinal) finales += resultado[0].transcript;
        else provisional += resultado[0].transcript;
      }
      definitivo = finales;
      ponerEnElCampo(base, definitivo + provisional);
      esperarSilencio();
    };
    rec.onerror = function (evento) { fallo = evento.error || 'error'; };
    rec.onend = function () {
      window.clearTimeout(silencio);
      window.clearTimeout(limite);
      reconocimiento = null;
      marcarDictado(false);
      if (fallo === 'not-allowed') {
        mostrarError('microfono', 0, null);
        return;
      }
      // El servicio del navegador no responde (sin red o sin dictado del
      // sistema): se graba y lo transcribe la tienda.
      if ((fallo === 'network' || fallo === 'service-not-allowed' || fallo === 'language-not-supported') &&
          puedeGrabar && !definitivo) {
        grabar();
        return;
      }
      if (fallo === 'aborted') return;
      if (!definitivo.trim()) {
        ponerEnElCampo(base, '');
        nota('voz_sin_texto');
        return;
      }
      ponerEnElCampo(base, definitivo.trim());
      campo.focus();
      nota('voz_lista');
      medir('vendedor_voice', { via: 'navegador' });
    };
    try {
      rec.start();
    } catch (error) {
      if (puedeGrabar) grabar();
      return;
    }
    reconocimiento = rec;
    marcarDictado(true);
    esperarSilencio();
    limite = window.setTimeout(function () { rec.stop(); }, MAX_SEGUNDOS_VOZ * 1000);
  }

  function grabar() {
    ocultarError();
    navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } })
      .then(function (flujo) {
        var contexto = new ContextoDeAudio();
        var fuente = contexto.createMediaStreamSource(flujo);
        var procesador = contexto.createScriptProcessor(4096, 1, 1);
        var actual = { flujo: flujo, contexto: contexto, fuente: fuente, procesador: procesador, trozos: [], muestras: 0 };
        procesador.onaudioprocess = function (evento) {
          if (grabacion !== actual) return;
          var datos = evento.inputBuffer.getChannelData(0);
          actual.trozos.push(new Float32Array(datos));
          actual.muestras += datos.length;
          if (actual.muestras >= contexto.sampleRate * MAX_SEGUNDOS_VOZ) terminarGrabacion(true);
        };
        fuente.connect(procesador);
        procesador.connect(contexto.destination);
        actual.limite = window.setTimeout(function () { terminarGrabacion(true); }, (MAX_SEGUNDOS_VOZ + 1) * 1000);
        grabacion = actual;
        marcarDictado(true);
      })
      .catch(function () { mostrarError('microfono', 0, null); });
  }

  function terminarGrabacion(transcribirla) {
    var actual = grabacion;
    if (!actual) return;
    grabacion = null;
    window.clearTimeout(actual.limite);
    try {
      actual.procesador.disconnect();
      actual.fuente.disconnect();
    } catch (error) { /* ya desconectado */ }
    actual.flujo.getTracks().forEach(function (pista) { pista.stop(); });
    if (actual.contexto.close) actual.contexto.close();
    marcarDictado(false);
    if (!transcribirla) return;
    var wav = codificarWav(actual.trozos, actual.contexto.sampleRate);
    if (!wav) {
      nota('voz_sin_texto');
      return;
    }
    transcribir(wav);
  }

  // PCM de 16 bits, un canal, 16 kHz: lo que acepta el reconocimiento de voz
  // sin conversiones. Se reduce la frecuencia promediando muestras.
  function codificarWav(trozos, frecuencia) {
    var total = 0;
    trozos.forEach(function (trozo) { total += trozo.length; });
    var paso = frecuencia / FRECUENCIA_VOZ;
    var cantidad = Math.min(Math.floor(total / paso), FRECUENCIA_VOZ * MAX_SEGUNDOS_VOZ);
    if (cantidad < FRECUENCIA_VOZ * 0.3) return null;
    var origen = new Float32Array(total);
    var desde = 0;
    trozos.forEach(function (trozo) { origen.set(trozo, desde); desde += trozo.length; });
    var buffer = new ArrayBuffer(44 + cantidad * 2);
    var vista = new DataView(buffer);
    function cadena(posicion, valor) {
      for (var i = 0; i < valor.length; i++) vista.setUint8(posicion + i, valor.charCodeAt(i));
    }
    cadena(0, 'RIFF');
    vista.setUint32(4, 36 + cantidad * 2, true);
    cadena(8, 'WAVE');
    cadena(12, 'fmt ');
    vista.setUint32(16, 16, true);
    vista.setUint16(20, 1, true);
    vista.setUint16(22, 1, true);
    vista.setUint32(24, FRECUENCIA_VOZ, true);
    vista.setUint32(28, FRECUENCIA_VOZ * 2, true);
    vista.setUint16(32, 2, true);
    vista.setUint16(34, 16, true);
    cadena(36, 'data');
    vista.setUint32(40, cantidad * 2, true);
    for (var i = 0; i < cantidad; i++) {
      var inicio = Math.floor(i * paso);
      var fin = Math.min(total, Math.max(inicio + 1, Math.floor((i + 1) * paso)));
      var suma = 0;
      for (var j = inicio; j < fin; j++) suma += origen[j];
      var muestra = Math.max(-1, Math.min(1, suma / (fin - inicio)));
      vista.setInt16(44 + i * 2, muestra < 0 ? muestra * 0x8000 : muestra * 0x7fff, true);
    }
    return new Blob([buffer], { type: 'audio/wav' });
  }

  function transcribir(wav) {
    var base = baseDelCampo();
    var formulario = new FormData();
    formulario.append('audio', wav, 'voz.wav');
    formulario.append('region', REGION_GOTOGYM);
    transcribiendo = true;
    actualizarControles();
    nota('transcribiendo');
    fetch(configuracion.vozUrl, {
      method: 'POST', credentials: 'same-origin', headers: cabecerasSeguras(), body: formulario
    }).then(function (respuesta) {
      return respuesta.text().then(function (crudo) {
        var datos = null;
        try { datos = JSON.parse(crudo); } catch (error) { datos = null; }
        return { estado: respuesta.status, datos: datos };
      });
    }).then(function (resultado) {
      var datos = resultado.datos;
      if (datos && datos.ok === true && typeof datos.text === 'string') {
        if (!datos.text.trim()) {
          nota('voz_sin_texto');
          return;
        }
        ponerEnElCampo(base, datos.text.trim());
        campo.focus();
        nota('voz_lista');
        medir('vendedor_voice', { via: 'tienda' });
        return;
      }
      nota(null);
      var codigo = datos && typeof datos.error === 'string' ? datos.error : codigoSegunEstado(resultado.estado);
      mostrarError(codigo, datos && datos.retry_after, datos && datos.contact_url, datos && datos.diagnostic);
    }).catch(function () {
      nota(null);
      mostrarError('red', 0, null);
    }).then(function () {
      transcribiendo = false;
      actualizarControles();
    });
  }

  function dictando() {
    return !!(reconocimiento || grabacion);
  }

  function detenerDictado(conResultado) {
    if (reconocimiento) {
      try {
        if (conResultado) reconocimiento.stop(); else reconocimiento.abort();
      } catch (error) { /* ya termino */ }
    }
    if (grabacion) terminarGrabacion(conResultado);
  }

  function alPulsarMicrofono() {
    if (transcribiendo) return;
    if (dictando()) {
      detenerDictado(true);
      return;
    }
    cerrarMenu(false);
    ocultarError();
    callar();
    if (Reconocimiento) dictarConNavegador();
    else if (puedeGrabar) grabar();
  }

  function empezarDeNuevo() {
    if (adjunto) soltarAdjunto(true);
    detenerDictado(false);
    callar();
    ultimoAdjunto = null;
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

  // --- Movil: pagina quieta y panel encima del teclado -----------------------------
  // overflow: hidden no detiene el arrastre elastico de Safari en iPhone, asi
  // que mientras el panel es modal el body queda fijo donde estaba. Y como
  // 100dvh no cambia al abrir el teclado, el panel toma el alto y la posicion
  // de la parte visible (visualViewport) para que nada de la tienda se asome.

  var vistaVisible = window.visualViewport || null;
  var desplazamientoGuardado = null;

  function fijarPagina() {
    if (desplazamientoGuardado !== null || !esModal()) return;
    desplazamientoGuardado = window.scrollY || window.pageYOffset || 0;
    var cuerpo = document.body.style;
    cuerpo.position = 'fixed';
    cuerpo.top = -desplazamientoGuardado + 'px';
    cuerpo.left = '0';
    cuerpo.right = '0';
    cuerpo.width = '100%';
  }

  function soltarPagina() {
    if (desplazamientoGuardado === null) return;
    var cuerpo = document.body.style;
    cuerpo.position = cuerpo.top = cuerpo.left = cuerpo.right = cuerpo.width = '';
    window.scrollTo(0, desplazamientoGuardado);
    desplazamientoGuardado = null;
  }

  function ajustarALaVista() {
    if (!abierto || !esModal() || !vistaVisible) {
      panel.style.removeProperty('--coach-alto');
      panel.style.removeProperty('--coach-arriba');
      return;
    }
    panel.style.setProperty('--coach-alto', Math.round(vistaVisible.height) + 'px');
    panel.style.setProperty('--coach-arriba', Math.round(vistaVisible.offsetTop) + 'px');
  }

  if (vistaVisible) {
    vistaVisible.addEventListener('resize', ajustarALaVista);
    vistaVisible.addEventListener('scroll', ajustarALaVista);
  }
  if (consultaEscritorio && consultaEscritorio.addEventListener) {
    // Al girar una tablet o cambiar el tamano de la ventana, el panel puede
    // dejar de ser modal (o volver a serlo).
    consultaEscritorio.addEventListener('change', function () {
      if (!abierto) return;
      if (esModal()) fijarPagina(); else soltarPagina();
      ajustarALaVista();
    });
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
    fijarPagina();
    ajustarALaVista();
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
    cerrarMenu(false);
    detenerDictado(false);
    callar();
    panel.hidden = true;
    if (velo) velo.hidden = true;
    document.documentElement.classList.remove('gtg-vendedor-abierto');
    marcarBotones(false);
    abierto = false;
    soltarPagina();
    ajustarALaVista();
    devolverElFoco();
    disparador = null;
  }

  function enfocables() {
    var candidatos = panel.querySelectorAll(
      'a[href], button:not([disabled]), textarea:not([disabled]), select:not([disabled]), ' +
      'input:not([disabled]):not([type="file"]):not([tabindex="-1"]), [tabindex]:not([tabindex="-1"])'
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
    if (ultimoMensaje) enviar(ultimoMensaje, ultimoAdjunto);
  });

  // Herramientas: cada opcion aparece solo si el navegador y el acceso la permiten.
  if (menuHerramientas && botonMas) {
    if (itemLeer) itemLeer.hidden = !sintesis;
    pintarLectura();
    if (!fotosHabilitadas) {
      Array.prototype.forEach.call(menuHerramientas.querySelectorAll('[data-herramienta="camara"], [data-herramienta="imagen"]'),
        function (item) { item.hidden = true; });
    }
    var itemArchivo = menuHerramientas.querySelector('[data-herramienta="archivo"]');
    if (itemArchivo) itemArchivo.hidden = !documentosHabilitados;
    if (itemsDelMenu().length) {
      botonMas.hidden = false;
      botonMas.addEventListener('click', function (evento) {
        evento.stopPropagation();
        if (menuHerramientas.hidden) abrirMenu(); else cerrarMenu(true);
      });
      menuHerramientas.addEventListener('click', function (evento) {
        var item = evento.target.closest ? evento.target.closest('[data-herramienta]') : null;
        if (item) usarHerramienta(item.getAttribute('data-herramienta'));
      });
      menuHerramientas.addEventListener('keydown', moverEnElMenu);
    }
  }
  if (fotosHabilitadas) {
    campoArchivo.addEventListener('change', alElegirFoto);
    if (campoCamara) campoCamara.addEventListener('change', alElegirFoto);
  }
  if (documentosHabilitados) campoDocumento.addEventListener('change', alElegirDocumento);
  if (botonQuitarAdjunto) botonQuitarAdjunto.addEventListener('click', function () { soltarAdjunto(true); campo.focus(); });

  campo.addEventListener('input', actualizarEnvio);
  actualizarEnvio();

  if (botonMicrofono && (Reconocimiento || puedeGrabar)) {
    botonMicrofono.hidden = false;
    botonMicrofono.addEventListener('click', alPulsarMicrofono);
  }

  // Un toque fuera del menu lo cierra.
  document.addEventListener('click', function (evento) {
    var objetivo = evento.target;
    if (!(objetivo instanceof Element)) return;
    if (menuHerramientas && !menuHerramientas.hidden && !menuHerramientas.contains(objetivo) &&
        !(botonMas && botonMas.contains(objetivo))) cerrarMenu(false);
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
    if (evento.key !== 'Escape' || !abierto) return;
    // Escape cierra primero lo que esta encima: el menu o el dictado.
    if (cerrarMenu(true)) return;
    if (dictando()) {
      detenerDictado(false);
      return;
    }
    cerrar();
  });

  restaurarHistorial();
})();
