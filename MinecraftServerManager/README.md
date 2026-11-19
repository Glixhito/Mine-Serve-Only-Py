# Minecraft Server Manager

Aplicación de escritorio en Python (PySide6) para crear y administrar servidores de Minecraft Java en Windows 10/11 de 64 bits.

## Antes de empezar

- Instala Python 3.13 (o 3.12) desde python.org.
- Guarda el proyecto fuera de OneDrive, por ejemplo en `C:\Proyectos\MinecraftServerManager`. La sincronización de OneDrive bloquea archivos de la base de datos y de los servidores, y provoca errores como "Acceso denegado" al empaquetar.
- Instala Java compatible con la versión de Minecraft: Java 8 hasta 1.16.5; Java 16 para 1.17; Java 17 de 1.18 a 1.20.4; Java 21 desde 1.20.5. Confirma estos umbrales en la documentación oficial.

## Instalación (PowerShell)

    cd C:\Proyectos\MinecraftServerManager
    py -3.13 -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt

Trabaja siempre con `.venv` activo: así no se mezclan versiones de PySide6 con las de tu Python global.

## Comprobar y ejecutar

    python verificar.py
    python -m pytest
    python main.py

## Crear el ejecutable

    Set-ExecutionPolicy -Scope Process Bypass
    .\build.ps1

El resultado queda en `dist\MinecraftServerManager\MinecraftServerManager.exe`. Los datos (base de datos, servidores, respaldos y registros) se guardan en una carpeta `data` junto al ejecutable.

## Estructura

- `core/`: composición de la aplicación, controlador de ejecución, procesos (QProcess) y bus de eventos.
- `managers/`: servidores, Java, configuración, versiones, cargadores, mods, respaldos, jugadores y monitor.
- `integrations/`: clientes HTTP (Mojang, Fabric, Forge, NeoForge, Modrinth).
- `database/` y `repositories/`: esquema SQLite y acceso a datos.
- `ui/`: ventana, vistas y tareas en segundo plano.
- `utils/`: validaciones, archivos, red e información del sistema.
- `tests/`: pruebas automáticas.

## Estado

- Fase 1 (núcleo): completa.
- Fase 2 (cargadores y mods): base completa en el backend. La vista de mods aún no está conectada.
- Fase 3 (interfaz): servidores, creación, EULA, inicio y parada, consola y respaldos. Falta la vista de ajustes.
- Fase 4 (administración): respaldos completos. La administración de jugadores existe en el backend, sin pantalla.
- Fase 5 (monitoreo): CPU y RAM del proceso; diagnóstico de puertos en el backend.
- Fase 6 (distribución): script de compilación con reintentos y pruebas automáticas.

## Antes de producción

- Confirma en su documentación oficial los endpoints de Mojang, Fabric, Forge, NeoForge y Modrinth, y los umbrales de Java.
- Prueba la creación, instalación, arranque y parada con un servidor real.
- Cambia el `USER_AGENT` de `integrations/http_client.py` por tu contacto.
