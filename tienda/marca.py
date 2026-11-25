"""Marca de Taruma: el logo B (Hoja de taruma) y el favicon, del diseno de T2.

El logo va en linea en la cabecera (aria-hidden: el nombre lo da el texto del enlace) y solo
con atributos de presentacion, porque la CSP (style-src 'self') bloquea el atributo style.
El favicon lo sirve la tienda en /tienda/favicon.svg: Caddy solo sirve .glb, .webp, .js y .css
de estaticos/, asi que un .svg ahi daria 404 en produccion.
"""

LOGO = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" aria-hidden="true" focusable="false"><path d="M24 25 Q24.8 34 22 43" fill="none" stroke="#7a3e12" stroke-width="2.6" stroke-linecap="round"/><path d="M22.42 24.72 C20.37 23.42 17.96 19.99 15.15 20.06 C13.17 20.54 12.3 25.49 14 26.62 C16.61 27.64 20.05 25.24 22.42 24.72 Z M22.97 23.77 C21.45 20.29 21.48 14.97 18.58 12.52 C16.21 11.17 11.73 14.93 12.65 17.49 C14.56 20.78 19.8 21.67 22.97 23.77 Z M24 23.4 C25.18 18.88 28.94 14.15 28.23 9.78 C27.2 6.8 20.8 6.8 19.77 9.78 C19.06 14.15 22.82 18.88 24 23.4 Z M25.03 23.77 C28.2 21.67 33.44 20.78 35.35 17.49 C36.27 14.93 31.79 11.17 29.42 12.52 C26.52 14.97 26.55 20.29 25.03 23.77 Z M25.58 24.72 C27.95 25.24 31.39 27.64 34 26.62 C35.7 25.49 34.83 20.54 32.85 20.06 C30.04 19.99 27.63 23.42 25.58 24.72 Z" fill="#4f6b3a"/><circle cx="32.5" cy="39" r="3.6" fill="#5a2d52"/><circle cx="38.5" cy="35.5" r="2.8" fill="#5a2d52"/></svg>'
)

FAVICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32"><rect width="32" height="32" rx="7" fill="#7a3e12"/><path d="M16 18 Q16.5 24 14.5 28" fill="none" stroke="#faf8f4" stroke-width="2" stroke-linecap="round"/><path d="M14.87 17.8 C13.39 16.86 11.65 14.39 9.63 14.44 C8.2 14.79 7.57 18.35 8.8 19.16 C10.68 19.9 13.15 18.17 14.87 17.8 Z M15.26 17.12 C14.16 14.61 14.19 10.78 12.09 9.01 C10.39 8.04 7.17 10.75 7.83 12.59 C9.21 14.96 12.98 15.6 15.26 17.12 Z M16 16.85 C16.85 13.59 19.55 10.19 19.05 7.04 C18.3 4.9 13.7 4.9 12.95 7.04 C12.45 10.19 15.15 13.59 16 16.85 Z M16.74 17.12 C19.02 15.6 22.79 14.96 24.17 12.59 C24.83 10.75 21.61 8.04 19.91 9.01 C17.81 10.78 17.84 14.61 16.74 17.12 Z M17.13 17.8 C18.85 18.17 21.32 19.9 23.2 19.16 C24.43 18.35 23.8 14.79 22.37 14.44 C20.35 14.39 18.61 16.86 17.13 17.8 Z" fill="#faf8f4"/><circle cx="22.5" cy="25.5" r="2.6" fill="#e8b77a"/></svg>'
).encode("ascii")
