// Zero-Cost AI Business — shared JS utilities
// Lightweight, no dependencies.

// Copy text to clipboard with fallback
function copyToClipboard(text, buttonEl) {
  const fallback = () => {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (e) {}
    document.body.removeChild(ta);
  };
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).catch(fallback);
  } else {
    fallback();
  }
  if (buttonEl) {
    const orig = buttonEl.textContent;
    buttonEl.textContent = 'Copied!';
    setTimeout(() => { buttonEl.textContent = orig; }, 1500);
  }
}

// Add copy button to all .output elements
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.output').forEach(el => {
    if (el.dataset.copyable === 'false') return;
    const btn = document.createElement('button');
    btn.className = 'btn';
    btn.textContent = 'Copy';
    btn.style.marginTop = '8px';
    btn.addEventListener('click', () => copyToClipboard(el.textContent, btn));
    el.parentNode.insertBefore(btn, el.nextSibling);
  });
});
