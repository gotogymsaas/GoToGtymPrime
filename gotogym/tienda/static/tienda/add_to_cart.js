document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.add-to-cart-btn').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      const productId = this.getAttribute('data-product-id');
      fetch(`/carrito/add/${productId}/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCookie('csrftoken'),
          'X-Requested-With': 'XMLHttpRequest',
        },
      })
      .then(res => res.json())
      .then(data => {
        // Opcional: mostrar feedback visual
        this.classList.add('bg-green-500');
        setTimeout(() => this.classList.remove('bg-green-500'), 800);
        // Opcional: actualizar contador de carrito en navbar
        if (data.cart_count !== undefined) {
          const cartCount = document.getElementById('cart-count');
          if (cartCount) cartCount.textContent = data.cart_count;
        }
      });
    });
  });
});

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}
