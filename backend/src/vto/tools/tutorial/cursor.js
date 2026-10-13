// Faux curseur pour le tournage : Playwright ne filme pas la souris du système.
(() => {
  if (window.top !== window) return
  const install = () => {
    if (document.getElementById('tutorial-cursor')) return
    const cursor = document.createElement('div')
    cursor.id = 'tutorial-cursor'
    cursor.innerHTML =
      '<svg width="28" height="28" viewBox="0 0 24 24"><path d="M4 2l16 9.5-7 1.6-3.6 6.9z"' +
      ' fill="#2e1f2b" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>'
    Object.assign(cursor.style, {
      position: 'fixed', left: '0', top: '0', zIndex: '2147483647', pointerEvents: 'none',
      transform: 'translate(640px, 400px)', filter: 'drop-shadow(0 2px 3px rgba(0,0,0,.25))',
    })
    document.documentElement.appendChild(cursor)

    document.addEventListener('mousemove', (e) => {
      cursor.style.transform = `translate(${e.clientX - 3}px, ${e.clientY - 2}px)`
    }, true)
    document.addEventListener('mousedown', (e) => {
      const halo = document.createElement('div')
      Object.assign(halo.style, {
        position: 'fixed', left: `${e.clientX - 22}px`, top: `${e.clientY - 22}px`,
        width: '44px', height: '44px', borderRadius: '50%', pointerEvents: 'none',
        background: 'rgba(232, 119, 74, .35)', border: '2px solid rgba(232, 119, 74, .9)',
        zIndex: '2147483646', transition: 'transform .45s ease-out, opacity .45s ease-out',
      })
      document.documentElement.appendChild(halo)
      requestAnimationFrame(() => {
        halo.style.transform = 'scale(1.6)'
        halo.style.opacity = '0'
      })
      setTimeout(() => halo.remove(), 500)
    }, true)
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install)
  else install()
})()
