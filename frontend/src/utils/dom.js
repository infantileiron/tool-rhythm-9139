export function saveDownload(blob, name) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.download = name;
  link.href = url;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function scrollTop() {
  window.scrollTo({top: 0, behavior: 'instant'});
}
