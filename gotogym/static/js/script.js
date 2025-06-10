const sidebar = document.getElementById("sidebar");
const collapseButton = document.getElementById("collapseButton");
const sidebarTitle = document.getElementById("sidebarTitle");
const menuLabels = document.querySelectorAll(".menu-label");
const collapseIconPath = document.getElementById("collapseIconPath");

// Definimos las rutas para los iconos de flecha
const iconExpanded = "M19 12H5m7-7l-7 7 7 7"; // Flecha apuntando a la izquierda
const iconCollapsed = "M5 12h14m-7-7l7 7-7 7"; // Flecha apuntando a la derecha

collapseButton.addEventListener("click", () => {
  // Alterna el ancho del sidebar
  sidebar.classList.toggle("w-64");
  sidebar.classList.toggle("w-16");

  // Alterna la visibilidad del título y las etiquetas
  sidebarTitle.classList.toggle("hidden");
  menuLabels.forEach((label) => label.classList.toggle("hidden"));

  // Verifica si el sidebar está colapsado y cambia el icono
  if (sidebar.classList.contains("w-16")) {
    // Sidebar colapsado
    collapseIconPath.setAttribute("d", iconCollapsed);
  } else {
    // Sidebar expandido
    collapseIconPath.setAttribute("d", iconExpanded);
  }
});

// Espera a que el DOM esté cargado
document.addEventListener("DOMContentLoaded", () => {
  const mainElement = document.querySelector("main");
  const sizeDisplay = document.getElementById("mainSize");

  function updateMainSize() {
    const width = mainElement.offsetWidth;
    const height = mainElement.offsetHeight;
    sizeDisplay.textContent = `Tamaño del elemento <main>: Ancho = ${width}px, Alto = ${height}px`;
  }

  // Llama a la función inicialmente
  updateMainSize();

  // Actualiza el tamaño si la ventana cambia de tamaño
  window.addEventListener("resize", updateMainSize);
});
