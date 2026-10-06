// Filas dinamicas de redes sociales del afiliado (postulacion y edicion del
// perfil): agregar y quitar filas, pedir el nombre cuando la red es "Otra" y
// mostrar los seguidores con punto de mil.
(function () {
  const lista = document.getElementById('redes-lista');
  const plantilla = document.getElementById('red-vacia');
  const total = document.getElementById('id_redes-TOTAL_FORMS');
  const agregar = document.getElementById('agregar-red');
  if (!lista || !plantilla || !total || !agregar) return;
  const maximo = parseInt(document.getElementById('id_redes-MAX_NUM_FORMS').value, 10);

  function filas() { return lista.querySelectorAll('[data-social-row]'); }

  // El formset exige indices consecutivos: tras quitar una fila se renumeran.
  function renumerar() {
    filas().forEach(function (fila, i) {
      fila.querySelectorAll('[name], [id], [for]').forEach(function (el) {
        ['name', 'id', 'for'].forEach(function (atributo) {
          const valor = el.getAttribute(atributo);
          if (valor) el.setAttribute(atributo, valor.replace(/(id_)?redes-\d+-/, '$1redes-' + i + '-'));
        });
      });
    });
    total.value = filas().length;
    agregar.disabled = filas().length >= maximo;
  }

  agregar.addEventListener('click', function () {
    if (filas().length >= maximo) return;
    const indice = filas().length;
    lista.insertAdjacentHTML('beforeend', plantilla.innerHTML.replace(/__prefix__/g, indice));
    renumerar();
    const nueva = filas()[indice];
    const campo = nueva && nueva.querySelector('select');
    if (campo) campo.focus();
  });

  lista.addEventListener('click', function (event) {
    const boton = event.target.closest('[data-remove-social]');
    if (!boton) return;
    boton.closest('[data-social-row]').remove();
    renumerar();
  });

  // El nombre de la red solo se pide cuando se elige "Otra".
  lista.addEventListener('change', function (event) {
    if (!event.target.matches('select[name$="-platform"]')) return;
    const otra = event.target.closest('[data-social-row]').querySelector('.social-row__other');
    const esOtra = event.target.value === 'other';
    otra.hidden = !esOtra;
    if (!esOtra) otra.querySelector('input').value = '';
  });

  // Seguidores con punto de mil mientras se escribe (1.000.000). El
  // servidor acepta la cifra con o sin puntos.
  function conPuntos(digitos) { return digitos.replace(/\B(?=(\d{3})+(?!\d))/g, '.'); }
  function formatear(campo, conservarCursor) {
    const cursor = campo.selectionStart || 0;
    const digitosAntes = campo.value.slice(0, cursor).replace(/\D/g, '').length;
    campo.value = conPuntos(campo.value.replace(/\D/g, '').replace(/^0+(?=\d)/, ''));
    if (!conservarCursor) return;
    let posicion = 0;
    let vistos = 0;
    while (posicion < campo.value.length && vistos < digitosAntes) {
      if (/\d/.test(campo.value[posicion])) vistos++;
      posicion++;
    }
    campo.setSelectionRange(posicion, posicion);
  }
  lista.addEventListener('input', function (event) {
    if (event.target.matches('[data-miles]')) formatear(event.target, true);
  });
  lista.querySelectorAll('[data-miles]').forEach(function (campo) { formatear(campo, false); });

  renumerar();
})();
