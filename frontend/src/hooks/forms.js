export function bindForm(form, onSubmit) {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = event.submitter || form.querySelector('button[type=submit]');
    const message = form.querySelector('[role=alert]');
    button.disabled = true;
    if (message) message.textContent = '';
    try {
      await onSubmit(Object.fromEntries(new FormData(form)));
    } catch (error) {
      if (message) message.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
}
