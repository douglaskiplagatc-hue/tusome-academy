// Dark mode toggle
const toggleDark = () => {
  const html = document.documentElement;
  const current = html.getAttribute('data-bs-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-bs-theme', next);
  localStorage.setItem('theme', next);
  // Update icons
  document.querySelectorAll('.dark-toggle-icon').forEach(el => {
      el.className = next === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
  });
};
document.querySelectorAll('#darkModeToggle, #darkModeToggleTop').forEach(btn => {
  btn?.addEventListener('click', toggleDark);
});
// Restore theme
const savedTheme = localStorage.getItem('theme') || 'light';
document.documentElement.setAttribute('data-bs-theme', savedTheme);

// Command Palette (Ctrl+K)
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      const palette = document.getElementById('commandPalette');
      palette.style.display = palette.style.display === 'none' ? 'flex' : 'none';
      if (palette.style.display !== 'none') {
          document.getElementById('commandInput').focus();
      }
  }
  if (e.key === 'Escape') {
      document.getElementById('commandPalette').style.display = 'none';
  }
});
// Search logic (simplified)
document.getElementById('commandInput')?.addEventListener('input', function() {
  const query = this.value.toLowerCase();
  const items = [
      { label: 'Dashboard', url: '/' },
      { label: 'Bulk Import', url: '/bulk/' },
      // ... populate from server or static
  ];
  const results = items.filter(i => i.label.toLowerCase().includes(query));
  const ul = document.getElementById('commandResults');
  ul.innerHTML = results.map(i => `<li class="list-group-item"><a href="${i.url}">${i.label}</a></li>`).join('');
});

// Skeleton loading (example)
document.addEventListener('DOMContentLoaded', () => {
  // Replace .skeleton with actual content after data loads
  // or use a loading state
});
