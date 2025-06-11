/* ========= scripts.js ========= */

/* 
 * Para cambios de aspecto en enlaces (.enlace)
 */
document.addEventListener("DOMContentLoaded", function() {
    let enlaces = document.querySelectorAll('.enlace');
    enlaces.forEach(function(enlace) {
      enlace.addEventListener('mouseenter', function() {
        enlace.classList.add('hovered');
      });
      enlace.addEventListener('mouseleave', function() {
        enlace.classList.remove('hovered');
      });
    });
  });
  
  /*
   * Para cambios de aspecto en los enlaces de usuario (.enlaceuser)
   */
  document.addEventListener("DOMContentLoaded", function() {
    let enlaceuser = document.querySelectorAll('.enlaceuser');
    enlaceuser.forEach(function(eu) {
      eu.addEventListener('mouseenter', function() {
        eu.classList.add('hovered');
      });
      eu.addEventListener('mouseleave', function() {
        eu.classList.remove('hovered');
      });
    });
  });
  
  /*
   * Para funciones de mouseenter y mouseleave para avisito de Usuario (id="usuario")
   * Nota: En el HTML actual no existe un elemento con id="usuario".
   * Si llegas a crearlo o ajustarlo, esta lógica mostrará y ocultará #avisuser
   */
  const usuario = document.getElementById('usuario');
  const avisuser = document.getElementById('avisuser');
  if (usuario && avisuser) {
    usuario.addEventListener('mouseenter', () => {
      avisuser.style.display = 'block';
    });
    usuario.addEventListener('mouseleave', () => {
      avisuser.style.display = 'none';
    });
  }
  
  /*
   * Para avisito de Store (Bolsito)
   */
  const compras = document.getElementById('compras');
  const bolsito = document.getElementById('bolsito');
  if (compras && bolsito) {
    compras.addEventListener('mouseenter', () => {
      bolsito.style.display = 'block';
    });
    compras.addEventListener('mouseleave', () => {
      bolsito.style.display = 'none';
    });
  }
  
  /*
   * Para avisito de Buscar (Lupita)
   */
  const lupita = document.getElementById('lupita');
  const buscar = document.getElementById('buscar');
  if (lupita && buscar) {
    lupita.addEventListener('mouseenter', () => {
      buscar.style.display = 'block';
    });
    lupita.addEventListener('mouseleave', () => {
      // Ojo: Esto ocultaría el input, si no deseas eso, comenta estas líneas
      buscar.style.display = 'none';
    });
  }
  
  /*
   * Para avisito de Felicidad (Corazoncito)
   */
  const felicidad = document.getElementById('felicidad');
  const corazon = document.getElementById('corazon');
  if (corazon && felicidad) {
    corazon.addEventListener('mouseenter', () => {
      felicidad.style.display = 'block';
    });
    corazon.addEventListener('mouseleave', () => {
      felicidad.style.display = 'none';
    });
  }
  
  /*
   * Manejo del selector de banderas (monedas) 
   */
  document.addEventListener('DOMContentLoaded', function () {
    const customSelect = document.getElementById('custom-select');
    if (!customSelect) return;
  
    const selectedOption = customSelect.querySelector('.selected-option');
    const optionsContainer = customSelect.querySelector('.options-container');
    const hiddenInput = customSelect.querySelector('input[type="hidden"]');
    const optionsList = optionsContainer.querySelectorAll('.option');
    const mostrar = document.getElementById('mostrar');
    const esconder = document.getElementById('esconder');
  
    selectedOption.addEventListener('click', () => {
      customSelect.classList.toggle('open');
      if (esconder.style.display === "none") {
        mostrar.style.display = "none";
        esconder.style.display = "flex";
      } else {
        esconder.style.display = "none";
        mostrar.style.display = "flex";
      }
    });
  
    optionsList.forEach(o => {
      o.addEventListener('click', () => {
        const imgSrc = o.querySelector('img').getAttribute('src');
        const imgAlt = o.querySelector('img').getAttribute('alt');
        const text = o.querySelector('span').textContent;
        const value = o.getAttribute('data-value');
  
        selectedOption.querySelector('img').setAttribute('src', imgSrc);
        selectedOption.querySelector('img').setAttribute('alt', imgAlt);
        selectedOption.querySelector('span').textContent = text;
        hiddenInput.value = value;
        customSelect.classList.remove('open');
      });
    });
  
    document.addEventListener('click', (e) => {
      // Si hiciera falta cerrar el select al hacer click fuera.
    });
  });
  
  /*
   * Carrusel automático
   */
  const imagenes = document.getElementById('imagenes');
  const carrusel = document.getElementById('carrusel');
  if (imagenes && carrusel) {
    const totalImagenes = document.querySelectorAll('.imagen').length;
    let counter = 0;
    let interval;
  
    function mostrarImagen() {
      counter++;
      if (counter >= totalImagenes) {
        counter = 0;
      }
      imagenes.style.transform = `translateX(-${counter * 100}%)`;
    }
  
    function iniciarCarrusel() {
      interval = setInterval(mostrarImagen, 3000);
    }
  
    function detenerCarrusel() {
      clearInterval(interval);
    }
  
    carrusel.addEventListener('mouseenter', detenerCarrusel);
    carrusel.addEventListener('mouseleave', iniciarCarrusel);
    iniciarCarrusel();
  }
  
  /*
   * Efecto hover en el botón "Más Información"
   */
  document.addEventListener("DOMContentLoaded", function() {
    let botoninf = document.querySelectorAll('.botoninf');
    botoninf.forEach(function(boton) {
      boton.addEventListener('mouseenter', function() {
        boton.classList.add('hovered');
      });
      boton.addEventListener('mouseleave', function() {
        boton.classList.remove('hovered');
      });
    });
  });
  
  /*
   * Efecto hover en los <a> class="ampliar"
   */
  document.addEventListener("DOMContentLoaded", function() {
    let ampliar = document.querySelectorAll('.ampliar');
    ampliar.forEach(function(link) {
      link.addEventListener('mouseenter', function() {
        link.classList.add('hovered');
      });
      link.addEventListener('mouseleave', function() {
        link.classList.remove('hovered');
      });
    });
  });
  
  /*
   * Mostrar/ocultar bloques de texto expandible (texto1, texto2, etc.)
   */
  function mostrartapar1() {
    const texto1 = document.getElementById('texto1');
    const flechita = document.getElementById('arribajo1');
    if (texto1.style.display === "none") {
      texto1.style.display = "flex";
      flechita.src = 'Recursos/volver arriba.png';
    } else {
      texto1.style.display = "none";
      flechita.src = 'Recursos/desglosar abajo.png';
    }
  }
  function mostrartapar2() {
    const texto2 = document.getElementById('texto2');
    const flechita = document.getElementById('arribajo2');
    if (texto2.style.display === "none") {
      texto2.style.display = "flex";
      flechita.src = 'Recursos/volver arriba.png';
    } else {
      texto2.style.display = "none";
      flechita.src = 'Recursos/desglosar abajo.png';
    }
  }
  function mostrartapar3() {
    const texto3 = document.getElementById('texto3');
    const flechita = document.getElementById('arribajo3');
    if (texto3.style.display === "none") {
      texto3.style.display = "flex";
      flechita.src = 'Recursos/volver arriba.png';
    } else {
      texto3.style.display = "none";
      flechita.src = 'Recursos/desglosar abajo.png';
    }
  }
  function mostrartapar4() {
    const texto4 = document.getElementById('texto4');
    const flechita = document.getElementById('arribajo4');
    if (texto4.style.display === "none") {
      texto4.style.display = "flex";
      flechita.src = 'Recursos/volver arriba.png';
    } else {
      texto4.style.display = "none";
      flechita.src = 'Recursos/desglosar abajo.png';
    }
  }
  function mostrartapar5() {
    const texto5 = document.getElementById('texto5');
    const flechita = document.getElementById('arribajo5');
    if (texto5.style.display === "none") {
      texto5.style.display = "flex";
      flechita.src = 'Recursos/volver arriba.png';
    } else {
      texto5.style.display = "none";
      flechita.src = 'Recursos/desglosar abajo.png';
    }
  }
  
  /* 
   * Las siguientes funciones (redirectToHome, redirectToStore, etc.)
   * no están definidas en tu código original, pero se llaman desde los onclick. 
   * Aquí puedes definirlas si lo deseas:
   */
  function RedirecToUser() {
    // Ejemplo: window.location.href = "AccesoUsuario.html";
  }
  function redirectToHome() {
    // ...
  }
  function redirectToStore() {
    // ...
  }
  function redirectToTablaTallas() {
    // ...
  }
  function redirectToBlog() {
    // ...
  }
  function redirectToIamOK() {
    // ...
  }
  function redirectToInformation() {
    // ...
  }
  function redirectToReturnPolicies() {
    // ...
  }
  function redirectToPrivacityPolicies() {
    // ...
  }
  function redirectToServiceConditions() {
    // ...
  }
  function redirectContactus() {
    // ...
  }
  function redirectToTechnology() {
    // ...
  }
  