=======================================================
  SGO-IMBIO · GUÍA DE ACCESO REMOTO (24/7 DESDE CELULAR)
=======================================================

REQUISITOS
----------
1. PC con Windows encendida (debe quedar encendida las 24h)
2. ngrok instalado (https://ngrok.com/download)
3. Cuenta gratuita en ngrok.com (para obtener el authtoken)

PASO 1 — INSTALAR NGROK (solo la primera vez)
----------------------------------------------
a) Ve a https://ngrok.com y crea una cuenta gratuita
b) Descarga ngrok.exe y ponlo en la carpeta sgo-imbio-python
c) En la carpeta, abre CMD y ejecuta:
       ngrok config add-authtoken TU_TOKEN_AQUI
   (El token lo encuentras en https://dashboard.ngrok.com/get-started/your-authtoken)

PASO 2 — ARRANCAR CON ACCESO REMOTO
-------------------------------------
Doble clic en:  start_ngrok.bat

Verás una pantalla como esta:
  Session Status: online
  Forwarding: https://abc123.ngrok-free.app -> http://localhost:8080

PASO 3 — COMPARTIR LA URL
--------------------------
Copia la URL https://abc123.ngrok-free.app y compártela:

  PANEL ADMIN:     https://abc123.ngrok-free.app
  APP INSPECTOR:   https://abc123.ngrok-free.app/inspector
  APP CIUDADANO:   https://abc123.ngrok-free.app/app

IMPORTANTE:
- La URL cambia cada vez que reinicias ngrok (plan gratis)
- Para URL fija, suscríbete al plan pago de ngrok
- Con plan gratis la URL cambia al reiniciar ngrok

PASO 4 — USO DESDE CELULAR
---------------------------
1. Abre el navegador en el celular (Chrome recomendado)
2. Escribe la URL: https://abc123.ngrok-free.app/inspector
3. Para instalar como app: Menu > Agregar a pantalla de inicio
4. Con datos móviles o WiFi — funciona igual

PARA MANTENER EL SERVICIO 24/7
--------------------------------
1. En Windows: Configurar → Sistema → Inicio/apagado
   → "Nunca" apagar por inactividad
2. En Panel de control → Opciones de energía
   → Plan de alto rendimiento
   → "Nunca" en suspensión
3. Desactiva el protector de pantalla

SOLUCIÓN DE PROBLEMAS
----------------------
- Si ngrok da error 403 en el navegador: 
  Añade al final de la URL ?ngrok-skip-browser-warning=true
  O en ngrok.com > Endpoints > desmarca "Browser Warning"
- Si la PC se suspende: ve a Opciones de energía y desactiva suspensión
- Si el servidor se cierra: doble clic en start_ngrok.bat

ALTERNATIVA: URL FIJA SIN PAGAR (DuckDNS + servicio local)
-----------------------------------------------------------
Si quieres una URL fija gratis, puedes usar:
  - Cloudflare Tunnel (gratis, URL fija)
  - Instala con: winget install Cloudflare.cloudflared
  - Ejecuta:  cloudflared tunnel --url http://localhost:8080
  - Te da una URL https://xxx.trycloudflare.com permanente
