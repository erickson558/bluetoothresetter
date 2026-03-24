# Changelog

## V0.0.2 - 2026-03-24
- Corrección del renderizado de aceleradores en la barra de menús de Tkinter usando `accelerator=` en lugar de incrustar el atajo en `label`.
- Mejora de accesibilidad con `underline` para mnemonics de menú estilo Windows.
- Refuerzo de atajos globales de teclado con `bind_all` para `Ctrl+R`, `Ctrl+Q` y `F1`.

## V0.0.1 - 2026-03-24
- Bootstrap inicial del proyecto Bluetooth Resetter.
- Script PowerShell para reinicio de audio/Bluetooth sin reiniciar Windows.
- GUI Tkinter no bloqueante con configuración persistente, logging e i18n ES/EN.
- Build a `.exe` con icono local y workflow base para release automático.
