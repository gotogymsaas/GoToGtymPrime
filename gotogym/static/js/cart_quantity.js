document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('[data-cart-quantity]').forEach(function (input) {
    const form = input.closest('form');
    if (!form) return;

    form.querySelectorAll('[data-quantity-step]').forEach(function (button) {
      button.addEventListener('click', function () {
        const step = Number(button.dataset.quantityStep);
        const current = Number(input.value) || 1;
        input.value = Math.max(1, current + step);
        updateCart(form);
      });
    });

    input.addEventListener('change', function () {
      input.value = Math.max(1, Number(input.value) || 1);
      updateCart(form);
    });
  });
});

function updateCart(form) {
  if (form.dataset.updating === 'true') return;
  form.dataset.updating = 'true';
  const formData = new FormData(form);
  form.querySelectorAll('button, input').forEach(function (control) {
    control.disabled = true;
  });

  const csrfToken = form.querySelector('[name="csrfmiddlewaretoken"]').value;
  fetch(form.action, {
    method: 'POST',
    body: formData,
    headers: {
      'X-CSRFToken': csrfToken,
      'X-Requested-With': 'XMLHttpRequest',
    },
  }).then(function (response) {
    if (!response.ok) throw new Error('No se pudo actualizar el carrito.');
    window.location.reload();
  }).catch(function () {
    form.dataset.updating = 'false';
    form.querySelectorAll('button, input').forEach(function (control) {
      control.disabled = false;
    });
    form.submit();
  });
}
