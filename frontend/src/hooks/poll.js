export function pollWhile(container, callback, delay = 850) {
  const step = async () => {
    if (!container.isConnected) return;
    try {
      if (await callback() && container.isConnected) setTimeout(step, delay);
    } catch (error) {
      container.querySelector('[data-poll-error]').textContent = error.message;
      setTimeout(step, 2500);
    }
  };
  setTimeout(step, delay);
}
