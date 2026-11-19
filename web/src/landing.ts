/**
 * RGB ASCII & Retro FX Studio — Landing Page Progressive Enhancements
 * Zero external dependencies. Lean, accessible, client-side helpers.
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Copy snippet buttons with fallback
  const copyButtons = document.querySelectorAll<HTMLButtonElement>('[data-copy]');
  copyButtons.forEach((btn) => {
    btn.addEventListener('click', async () => {
      const textToCopy = btn.getAttribute('data-copy');
      if (!textToCopy) return;

      let success = false;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(textToCopy);
          success = true;
        } catch {
          // Fallback below
        }
      }

      if (!success) {
        try {
          const textarea = document.createElement('textarea');
          textarea.value = textToCopy;
          textarea.style.position = 'fixed';
          textarea.style.opacity = '0';
          document.body.appendChild(textarea);
          textarea.select();
          success = document.execCommand('copy');
          document.body.removeChild(textarea);
        } catch (err) {
          console.warn('Fallback copy failed:', err);
        }
      }

      if (success) {
        const originalText = btn.textContent;
        btn.textContent = 'COPIED';
        btn.classList.add('text-highlight');
        setTimeout(() => {
          btn.textContent = originalText;
          btn.classList.remove('text-highlight');
        }, 1800);
      }
    });
  });

  // 2. Mobile navigation toggle
  const toggleBtn = document.getElementById('mobile-nav-toggle');
  const navMenu = document.getElementById('mobile-nav-menu');
  if (toggleBtn && navMenu) {
    toggleBtn.addEventListener('click', () => {
      const isExpanded = toggleBtn.getAttribute('aria-expanded') === 'true';
      toggleBtn.setAttribute('aria-expanded', String(!isExpanded));
      navMenu.classList.toggle('hidden');
    });

    // Close mobile nav when clicking any link
    const mobileLinks = navMenu.querySelectorAll('a');
    mobileLinks.forEach((link) => {
      link.addEventListener('click', () => {
        navMenu.classList.add('hidden');
        toggleBtn.setAttribute('aria-expanded', 'false');
      });
    });
  }
});
