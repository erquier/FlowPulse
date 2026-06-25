# FlowPulse

**FlowPulse** es una herramienta ligera de system tray para Windows que simula actividad de input humano realista (mouse, teclado y rotación de ventanas) en entornos de **testing de seguridad** autorizados.

Diseñada para investigadores de seguridad y equipos de blue team que necesitan mantener sesiones activas o simular comportamiento de usuario en máquinas de prueba sin levantar sospechas en sistemas de detección automatizados.

---

## Características

- **Simulación de mouse realista** — Movimientos con curvas bezier, aceleración variable, pausas naturales, clics contextuales.
- **Simulación de teclado** — Escritura con velocidad variable y errores tipográficos simulados, atajos comunes (Alt+Tab, Ctrl+C, Win+D).
- **Rotación de ventanas** — Cambio periódico entre ventanas abiertas simulando multitarea humana.
- **Anti-detección** — Patrones no repetitivos, variación de timing, jitter en coordenadas, amplitud y frecuencia aleatorias.
- **System tray** — Icono en bandeja con menú contextual para pausar, reanudar, configurar y salir.
- **Configurable** — Intervalo mínimo/máximo, tipo de actividad, pausas nocturnas opcionales.
- **Sin dependencias externas pesadas** — Solo `math` y `random` del stdlib para generación de números; nada de `numpy`.

---

## Requisitos

- **Sistema operativo:** Windows 10 / Windows 11 (64-bit)
- **Python:** 3.11 o superior
- **Permisos:** No requiere administrador (funciona en user space)

---

## Instalación

```bash
git clone https://github.com/tu-organizacion/flowpulse.git
cd flowpulse
pip install -r requirements.txt
```

### Uso directo con Python

```bash
python flowpulse.py
```

El icono aparecerá en la bandeja del sistema. Haz clic derecho para ver las opciones.

---

## Build con Nuitka

Para generar un ejecutable independiente (`FlowPulse.exe`) sin necesidad de Python instalado:

```bash
pip install nuitka
python build/build_nuitka.py
```

El ejecutable se generará en `dist/FlowPulse.exe`.

### Flags incluidas

- `--standalone --onefile` — ejecutable único autocontenido
- `--windows-disable-console` — sin ventana de terminal
- `--windows-icon-from-ico` — icono personalizado
- Metadatos legítimos (Erqlabs, FlowPulse v1.1.0)

### Firma digital (opcional)

```powershell
powershell -ExecutionPolicy Bypass -File build/sign.ps1
```

Esto crea un certificado autofirmado y firma `dist/FlowPulse.exe`. Ideal para pruebas en entornos controlados donde se requiere firma Authenticode.

---

## Uso

1. Ejecuta `FlowPulse.exe` (o `python flowpulse.py`).
2. Aparece el icono en la bandeja del sistema.
3. **Click derecho** sobre el icono:
   - ▶️ **Reanudar** — Inicia la simulación
   - ⏸️ **Pausar** — Detiene la simulación
   - ⚙️ **Configurar** — Ajusta intervalos y tipos de actividad
   - ❌ **Salir** — Cierra la aplicación
4. La simulación se ejecuta en segundo plano sin interferir con tu trabajo.

---

## Build con GitHub Actions

El repositorio incluye un workflow de GitHub Actions en `.github/workflows/build.yml`.

### Cómo usarlo

1. Haz push a la rama `main` o crea un tag con formato `v*` (ej: `v1.0.0`).
2. El workflow compila automáticamente `FlowPulse.exe` con Nuitka en un runner Windows.
3. El artifact `flowpulse-build.zip` estará disponible en la página del workflow.
4. Si usaste un tag, se creará automáticamente un **GitHub Release** con el ejecutable adjunto.

### Descargar el artifact

1. Ve a la pestaña **Actions** de tu repositorio en GitHub.
2. Selecciona el workflow run correspondiente.
3. Descarga **flowpulse-build.zip** desde la sección de artifacts.

---

## Legal

> FlowPulse está diseñado exclusivamente para **entornos autorizados** de testing de seguridad, demostraciones controladas y laboratorios de investigación. El usuario es el único responsable de cumplir con las políticas de seguridad de su organización y las leyes aplicables. No utilizar en sistemas sin consentimiento explícito por escrito.

---

*FlowPulse — Input simulation for authorized security testing.*
