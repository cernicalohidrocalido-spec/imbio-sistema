#!/usr/bin/env python3
"""
SGO-IMBIO – Sistema de Gestión Operativa
Servidor Python puro (stdlib) con API REST + Frontend HTML embebido
"""

import json, hashlib, base64, os, re, uuid, pathlib, threading, sqlite3
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ── Config ─────────────────────────────────────────────────────────────────
PORT       = int(os.environ.get("PORT", 8080))
BASE_DIR   = pathlib.Path(__file__).parent
DB_FILE    = BASE_DIR / "data" / "db.json"   # legacy (used for initial seed)
DB_SQLITE  = pathlib.Path(os.environ.get("DB_PATH", str(BASE_DIR / "data" / "imbio.db")))
UPLOAD_EV  = BASE_DIR / "uploads" / "evidence"
UPLOAD_SIG = BASE_DIR / "uploads" / "signatures"
JWT_SECRET = "sgo-imbio-secret-2026"

# ── App Ciudadano (embebida) ─────────────────────────────────────────────────
import pathlib as _pl
_STATIC_DIR = _pl.Path(__file__).parent / 'static'

def _load(name):
    return (_STATIC_DIR / name).read_text(encoding='utf-8')

APP_HTML       = _load('app.html')
INSPECTOR_HTML = _load('inspector.html')
HTML           = _load('panel.html')

APP_SW       = "// SGO-IMBIO Ciudadano – Service Worker\nconst CACHE = 'imbio-ciudadano-v1';\nconst OFFLINE_URLS = ['/app'];\n\nself.addEventListener('install', e => {\n  e.waitUntil(\n    caches.open(CACHE).then(c => c.addAll(OFFLINE_URLS))\n  );\n  self.skipWaiting();\n});\n\nself.addEventListener('activate', e => {\n  e.waitUntil(\n    caches.keys().then(keys =>\n      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))\n    )\n  );\n  self.clients.claim();\n});\n\nself.addEventListener('fetch', e => {\n  // API calls: network first, no cache\n  if (e.request.url.includes('/api/')) return;\n  e.respondWith(\n    fetch(e.request)\n      .catch(() => caches.match(e.request).then(r => r || caches.match('/app')))\n  );\n});\n"
APP_MANIFEST = '{\n  "name": "IMBIO Ciudadano",\n  "short_name": "IMBIO",\n  "description": "Reporta incidencias ambientales al Instituto Municipal de Biodiversidad y Protección Ambiental de Pabellón de Arteaga",\n  "start_url": "/app",\n  "display": "standalone",\n  "background_color": "#002A5C",\n  "theme_color": "#003B7A",\n  "orientation": "portrait",\n  "icons": [\n    { "src": "/app/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable" },\n    { "src": "/app/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable" }\n  ],\n  "categories": ["utilities", "government"],\n  "lang": "es-MX"\n}\n'
APP_ICON_192 = base64.b64decode('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')
APP_ICON_512 = base64.b64decode('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')



# ── App Ciudadano (embebida) ─────────────────────────────────────────────────
'<!DOCTYPE html>\n<html lang="es">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">\n<meta name="theme-color" content="#003B7A">\n<meta name="apple-mobile-web-app-capable" content="yes">\n<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n<meta name="apple-mobile-web-app-title" content="IMBIO">\n<meta name="mobile-web-app-capable" content="yes">\n<title>IMBIO Ciudadano</title>\n<link rel="manifest" href="/app/manifest.json">\n<link rel="apple-touch-icon" href="/app/icon-192.png">\n<link rel="stylesheet" href="/static/leaflet.css"/>\n<script src="/static/leaflet.js"></script>\n<style>\n/* ═══════════════════════════════════════════════\n   IMBIO CIUDADANO — Mobile-First Design\n   Paleta institucional azul municipal\n═══════════════════════════════════════════════ */\n:root {\n  --azul:       #003B7A;\n  --azul-medio: #0057B8;\n  --azul-claro: #1976D2;\n  --azul-bg:    #E8F1FB;\n  --azul-borde: #B3CFF0;\n  --oscuro:     #002A5C;\n  --texto:      #1a202c;\n  --muted:      #64748b;\n  --gris:       #f0f4fa;\n  --borde:      #e2e8f0;\n  --blanco:     #ffffff;\n  --rojo:       #dc2626;\n  --verde:      #16a34a;\n  --naranja:    #ea580c;\n  --amarillo:   #ca8a04;\n  --safe-top:   env(safe-area-inset-top, 0px);\n  --safe-bot:   env(safe-area-inset-bottom, 0px);\n}\n\n* { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }\nhtml, body { height: 100%; overflow: hidden; background: var(--azul); }\nbody { font-family: \'Segoe UI\', system-ui, -apple-system, sans-serif; color: var(--texto); }\n\n/* ── SPLASH / INTRO ── */\n#splash {\n  position: fixed; inset: 0; z-index: 9999;\n  background: linear-gradient(160deg, #002A5C 0%, #003B7A 50%, #0057B8 100%);\n  display: flex; flex-direction: column; align-items: center; justify-content: center;\n  transition: opacity .5s ease;\n}\n#splash.hide { opacity: 0; pointer-events: none; }\n.splash-logo { width: 90px; height: 90px; background: rgba(255,255,255,.12);\n  border-radius: 24px; display: flex; align-items: center; justify-content: center;\n  font-size: 3rem; margin-bottom: 20px;\n  box-shadow: 0 0 0 1px rgba(255,255,255,.15), 0 20px 60px rgba(0,0,0,.3); }\n.splash-title { color: #fff; font-size: 1.8rem; font-weight: 800; letter-spacing: -.5px; }\n.splash-sub { color: rgba(255,255,255,.65); font-size: .85rem; margin-top: 6px; text-align: center; line-height: 1.4; }\n.splash-loader { margin-top: 48px; width: 40px; height: 4px; background: rgba(255,255,255,.2); border-radius: 99px; overflow: hidden; }\n.splash-loader::after { content: \'\'; display: block; height: 100%; width: 40%; background: #fff; border-radius: 99px; animation: load 1.2s ease-in-out infinite; }\n@keyframes load { 0%{transform:translateX(-100%)} 100%{transform:translateX(350%)} }\n\n/* ── APP SHELL ── */\n#app {\n  position: fixed; inset: 0;\n  display: flex; flex-direction: column;\n  background: var(--gris);\n  padding-top: var(--safe-top);\n  padding-bottom: var(--safe-bot);\n}\n\n/* ── HEADER ── */\n.app-header {\n  background: linear-gradient(135deg, var(--oscuro), var(--azul));\n  padding: 14px 20px 12px;\n  display: flex; align-items: center; gap: 12px;\n  box-shadow: 0 2px 12px rgba(0,0,0,.25);\n  flex-shrink: 0;\n}\n.header-icon { font-size: 1.6rem; }\n.header-text h1 { color: #fff; font-size: 1.05rem; font-weight: 800; letter-spacing: -.3px; }\n.header-text p  { color: rgba(255,255,255,.6); font-size: .72rem; margin-top: 1px; }\n.header-right { margin-left: auto; display: flex; align-items: center; gap: 8px; }\n.conn-dot { width: 8px; height: 8px; border-radius: 50%; background: #4ade80; box-shadow: 0 0 0 2px rgba(74,222,128,.3); }\n.conn-dot.off { background: #f87171; box-shadow: 0 0 0 2px rgba(248,113,113,.3); }\n\n/* ── TABS ── */\n.tabs {\n  display: flex; background: var(--azul); flex-shrink: 0;\n  border-bottom: 1px solid rgba(255,255,255,.1);\n}\n.tab {\n  flex: 1; padding: 10px 4px; display: flex; flex-direction: column;\n  align-items: center; gap: 3px; cursor: pointer; transition: .2s;\n  color: rgba(255,255,255,.5); font-size: .65rem; font-weight: 600; text-transform: uppercase; letter-spacing: .04em;\n  border-bottom: 2px solid transparent;\n}\n.tab .tab-ic { font-size: 1.25rem; }\n.tab.active { color: #fff; border-bottom-color: #60a5fa; }\n.tab:active { background: rgba(255,255,255,.08); }\n\n/* ── CONTENT AREA ── */\n.content { flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch; }\n.screen { display: none; min-height: 100%; }\n.screen.active { display: block; }\n\n/* ── NUEVO REPORTE ── */\n.screen-pad { padding: 16px; }\n\n.form-card {\n  background: var(--blanco); border-radius: 16px;\n  box-shadow: 0 1px 3px rgba(0,0,0,.08), 0 4px 16px rgba(0,59,122,.06);\n  overflow: hidden; margin-bottom: 12px;\n}\n.form-card-header {\n  background: var(--azul-bg); padding: 12px 16px;\n  border-bottom: 1px solid var(--azul-borde);\n  display: flex; align-items: center; gap: 8px;\n}\n.form-card-header .ic { font-size: 1.1rem; }\n.form-card-header span { font-size: .8rem; font-weight: 700; color: var(--oscuro); text-transform: uppercase; letter-spacing: .05em; }\n.form-card-body { padding: 14px 16px; display: flex; flex-direction: column; gap: 12px; }\n\n.fgroup label {\n  display: block; font-size: .78rem; font-weight: 700;\n  color: var(--muted); text-transform: uppercase; letter-spacing: .04em; margin-bottom: 6px;\n}\n.fgroup input, .fgroup select, .fgroup textarea {\n  width: 100%; padding: 12px 14px; border: 1.5px solid var(--borde);\n  border-radius: 10px; font-size: .95rem; font-family: inherit;\n  background: #fff; color: var(--texto); outline: none;\n  transition: border-color .15s, box-shadow .15s; appearance: none;\n}\n.fgroup input:focus, .fgroup select:focus, .fgroup textarea:focus {\n  border-color: var(--azul-claro); box-shadow: 0 0 0 3px rgba(25,118,210,.12);\n}\n.fgroup textarea { resize: none; min-height: 80px; }\n.fgroup select { background-image: url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'12\' height=\'8\' viewBox=\'0 0 12 8\'%3E%3Cpath d=\'M1 1l5 5 5-5\' stroke=\'%23666\' stroke-width=\'1.5\' fill=\'none\' stroke-linecap=\'round\'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 14px center; padding-right: 36px; }\n\n/* Tipo chips */\n.tipo-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }\n.tipo-chip {\n  padding: 10px 8px; border: 2px solid var(--borde); border-radius: 10px;\n  background: #fff; cursor: pointer; text-align: center; transition: .15s;\n  display: flex; flex-direction: column; align-items: center; gap: 4px;\n}\n.tipo-chip .chip-ic { font-size: 1.4rem; }\n.tipo-chip .chip-lbl { font-size: .7rem; font-weight: 700; color: var(--muted); line-height: 1.2; }\n.tipo-chip.sel {\n  border-color: var(--azul-claro); background: var(--azul-bg);\n  box-shadow: 0 0 0 3px rgba(25,118,210,.12);\n}\n.tipo-chip.sel .chip-lbl { color: var(--oscuro); }\n.tipo-chip:active { transform: scale(.97); }\n\n/* Mapa picker */\n#map-app { height: 220px; border-radius: 10px; overflow: hidden; border: 1.5px solid var(--borde); }\n.map-addr {\n  margin-top: 8px; padding: 10px 12px; background: var(--azul-bg);\n  border-radius: 8px; border: 1px solid var(--azul-borde);\n  font-size: .82rem; color: var(--oscuro); line-height: 1.4;\n  min-height: 38px;\n}\n.map-btns { display: flex; gap: 8px; margin-top: 8px; }\n.map-btn {\n  flex: 1; padding: 9px; border: 1.5px solid var(--borde); border-radius: 8px;\n  background: #fff; font-size: .78rem; font-weight: 700; color: var(--azul);\n  cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 5px;\n  transition: .15s;\n}\n.map-btn:active { background: var(--azul-bg); }\n\n/* Firma */\n#sig-app {\n  width: 100%; height: 120px; border: 2px dashed var(--azul-borde);\n  border-radius: 10px; cursor: crosshair; touch-action: none; background: #fafcff; display: block;\n}\n\n/* Dirección autocompletada */\n.addr-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }\n.addr-grid .fgroup.full { grid-column: 1/-1; }\n.addr-filled input { border-color: var(--azul-claro); background: var(--azul-bg); }\n\n/* ── BOTÓN ENVIAR ── */\n.btn-enviar {\n  width: 100%; padding: 16px; background: var(--azul);\n  color: #fff; border: none; border-radius: 14px; font-size: 1rem;\n  font-weight: 800; cursor: pointer; letter-spacing: .02em;\n  box-shadow: 0 4px 20px rgba(0,59,122,.35);\n  display: flex; align-items: center; justify-content: center; gap: 8px;\n  transition: .15s; margin-top: 4px;\n}\n.btn-enviar:active { transform: scale(.98); background: var(--oscuro); }\n.btn-enviar:disabled { background: #94a3b8; box-shadow: none; cursor: not-allowed; }\n.btn-sec {\n  width: 100%; padding: 12px; background: var(--gris);\n  color: var(--muted); border: 1.5px solid var(--borde); border-radius: 12px;\n  font-size: .88rem; font-weight: 700; cursor: pointer; margin-top: 8px;\n  transition: .15s;\n}\n.btn-sec:active { background: var(--borde); }\n\n/* ── ALERTS ── */\n.alert {\n  padding: 12px 14px; border-radius: 10px; font-size: .85rem;\n  margin-bottom: 12px; line-height: 1.4;\n}\n.alert-ok  { background: #dcfce7; color: #166534; border: 1px solid #86efac; }\n.alert-err { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }\n.alert-inf { background: var(--azul-bg); color: var(--oscuro); border: 1px solid var(--azul-borde); }\n\n/* ── MIS REPORTES ── */\n.reporte-card {\n  background: var(--blanco); border-radius: 14px; margin-bottom: 10px;\n  box-shadow: 0 1px 3px rgba(0,0,0,.07); overflow: hidden;\n  border-left: 4px solid var(--azul);\n}\n.reporte-card.est-reportado   { border-left-color: #f59e0b; }\n.reporte-card.est-asignado    { border-left-color: #3b82f6; }\n.reporte-card.est-en_proceso  { border-left-color: #ec4899; }\n.reporte-card.est-cerrado     { border-left-color: #22c55e; }\n.reporte-card-head { padding: 12px 14px 8px; display: flex; justify-content: space-between; align-items: flex-start; }\n.reporte-folio { font-size: .75rem; font-weight: 800; color: var(--azul); font-family: monospace; }\n.reporte-estado { font-size: .68rem; font-weight: 800; padding: 3px 8px; border-radius: 99px; text-transform: uppercase; }\n.est-badge-reportado  { background: #fef3c7; color: #92400e; }\n.est-badge-asignado   { background: #dbeafe; color: #1e40af; }\n.est-badge-en_proceso { background: #fce7f3; color: #9d174d; }\n.est-badge-cerrado    { background: #dcfce7; color: #166534; }\n.reporte-tipo { font-size: .82rem; font-weight: 700; color: var(--texto); padding: 0 14px; }\n.reporte-desc { font-size: .8rem; color: var(--muted); padding: 4px 14px 10px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }\n.reporte-foot { padding: 8px 14px; background: var(--gris); border-top: 1px solid var(--borde); display: flex; justify-content: space-between; align-items: center; }\n.reporte-fecha { font-size: .72rem; color: var(--muted); }\n.reporte-colonia { font-size: .72rem; color: var(--muted); font-weight: 600; }\n\n/* ── ACERCA ── */\n.about-card { background: var(--blanco); border-radius: 16px; padding: 20px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,.07); }\n.about-logo { text-align: center; padding: 20px 0; }\n.about-logo .big-ic { font-size: 3.5rem; }\n.about-logo h2 { font-size: 1.3rem; font-weight: 800; color: var(--azul); margin-top: 8px; }\n.about-logo p { font-size: .82rem; color: var(--muted); margin-top: 4px; line-height: 1.4; }\n.about-row { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid var(--borde); }\n.about-row:last-child { border-bottom: none; }\n.about-row .row-ic { font-size: 1.3rem; width: 36px; text-align: center; }\n.about-row .row-info label { font-size: .72rem; color: var(--muted); font-weight: 700; text-transform: uppercase; }\n.about-row .row-info span { display: block; font-size: .88rem; color: var(--texto); font-weight: 600; margin-top: 1px; }\n.server-input { display: flex; gap: 8px; }\n.server-input input { flex: 1; padding: 10px 12px; border: 1.5px solid var(--borde); border-radius: 8px; font-size: .85rem; outline: none; }\n.server-input input:focus { border-color: var(--azul-claro); }\n.server-input button { padding: 10px 14px; background: var(--azul); color: #fff; border: none; border-radius: 8px; font-size: .82rem; font-weight: 700; cursor: pointer; }\n\n/* ── ÉXITO SCREEN ── */\n#screen-exito {\n  position: fixed; inset: 0; z-index: 500;\n  background: linear-gradient(160deg, #002A5C, #0057B8);\n  display: none; flex-direction: column; align-items: center; justify-content: center;\n  padding: 32px;\n}\n#screen-exito.show { display: flex; }\n.exito-ic { font-size: 5rem; margin-bottom: 20px; animation: pop .4s cubic-bezier(.34,1.56,.64,1); }\n@keyframes pop { from{transform:scale(0)} to{transform:scale(1)} }\n.exito-title { color: #fff; font-size: 1.6rem; font-weight: 800; text-align: center; }\n.exito-folio { color: rgba(255,255,255,.8); font-size: 1rem; margin-top: 8px; font-family: monospace; text-align: center; }\n.exito-msg { color: rgba(255,255,255,.65); font-size: .88rem; margin-top: 12px; text-align: center; line-height: 1.5; }\n.exito-btn { margin-top: 32px; padding: 14px 32px; background: rgba(255,255,255,.15); color: #fff; border: 2px solid rgba(255,255,255,.4); border-radius: 12px; font-size: .95rem; font-weight: 700; cursor: pointer; transition: .15s; }\n.exito-btn:active { background: rgba(255,255,255,.25); }\n\n/* Loading overlay */\n#loading-overlay { position: fixed; inset: 0; background: rgba(0,43,92,.6); z-index: 400; display: none; align-items: center; justify-content: center; }\n#loading-overlay.show { display: flex; }\n.spinner { width: 44px; height: 44px; border: 4px solid rgba(255,255,255,.2); border-top-color: #fff; border-radius: 50%; animation: spin .8s linear infinite; }\n@keyframes spin { to { transform: rotate(360deg); } }\n\n/* ── FORMULARIO ANIMAL AGRESIVO ── */\n#panel-animal-agresivo { display:none }\n.body-map-wrap { position:relative; width:200px; margin:12px auto; user-select:none }\n.body-map-wrap svg { width:100%; height:auto }\n.bzone { cursor:pointer; transition:.15s; }\n.bzone:hover rect,.bzone:hover ellipse,.bzone:hover path { opacity:.7 }\n.bzone.sel rect,.bzone.sel ellipse,.bzone.sel path { fill:#003B7A !important }\n.bzone.sel text { fill:#fff !important }\n.gravedad-btns { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:6px }\n.grav-btn { padding:12px 8px; border:2px solid var(--borde); border-radius:10px; background:#fff; cursor:pointer; text-align:center; font-size:.82rem; font-weight:700; color:var(--muted); transition:.15s }\n.grav-btn.sel-sup { border-color:#1976D2; background:var(--azul-bg); color:var(--inspector) }\n.grav-btn.sel-pro { border-color:#dc2626; background:#fee2e2; color:#991b1b }\n.animal-check { display:flex; align-items:center; gap:10px; padding:12px 14px; border:1.5px solid var(--borde); border-radius:10px; background:#fff; cursor:pointer; font-size:.88rem; font-weight:600 }\n.animal-check input { width:18px; height:18px; accent-color:var(--azul) }\n\n.empty-state { text-align: center; padding: 48px 20px; color: var(--muted); }\n.empty-state .em-ic { font-size: 3rem; margin-bottom: 12px; }\n.empty-state p { font-size: .88rem; line-height: 1.5; }\n</style>\n</head>\n<body>\n\n<!-- SPLASH -->\n<div id="splash">\n  <div class="splash-logo">🌿</div>\n  <div class="splash-title">IMBIO</div>\n  <div class="splash-sub">Reporte Ciudadano<br>Pabellón de Arteaga, Ags.</div>\n  <div class="splash-loader"></div>\n</div>\n\n<!-- ÉXITO -->\n<div id="screen-exito">\n  <div class="exito-ic">✅</div>\n  <div class="exito-title">¡Reporte Enviado!</div>\n  <div class="exito-folio" id="exito-folio"></div>\n  <div class="exito-msg">Tu reporte fue registrado en el sistema municipal.<br>Puedes darle seguimiento en "Mis Reportes".</div>\n  <button class="exito-btn" onclick="cerrarExito()">Hacer otro reporte</button>\n</div>\n\n<!-- LOADING -->\n<div id="loading-overlay"><div class="spinner"></div></div>\n\n<!-- APP -->\n<div id="app">\n\n  <!-- HEADER -->\n  <div class="app-header">\n    <div class="header-icon">🌿</div>\n    <div class="header-text">\n      <h1>IMBIO Ciudadano</h1>\n      <p style="font-size:.65rem;line-height:1.3">IMBIO · Pabellón de Arteaga, Ags.</p>\n    </div>\n    <div class="header-right">\n      <div class="conn-dot" id="conn-dot" title="Conexión"></div>\n    </div>\n  </div>\n\n  <!-- TABS -->\n  <div class="tabs">\n    <div class="tab active" onclick="setTab(\'nuevo\')" id="tab-nuevo">\n      <span class="tab-ic">📝</span><span>Nuevo</span>\n    </div>\n    <div class="tab" onclick="setTab(\'mis\')" id="tab-mis">\n      <span class="tab-ic">📋</span><span>Mis Reportes</span>\n    </div>\n    <div class="tab" onclick="setTab(\'acerca\')" id="tab-acerca">\n      <span class="tab-ic">ℹ️</span><span>Acerca</span>\n    </div>\n  </div>\n\n  <!-- CONTENT -->\n  <div class="content">\n\n    <!-- ══════════ NUEVO REPORTE ══════════ -->\n    <div id="screen-nuevo" class="screen active">\n      <div class="screen-pad">\n        <div id="form-alert"></div>\n\n        <!-- TIPO -->\n        <div class="form-card">\n          <div class="form-card-header"><span class="ic">🏷️</span><span>Tipo de incidencia *</span></div>\n          <div class="form-card-body">\n            <div class="tipo-grid" id="tipo-grid">\n              <div class="tipo-chip" onclick="selTipo(\'emergencia\')" data-tipo="emergencia">\n                <span class="chip-ic">🚨</span><span class="chip-lbl">Emergencia</span>\n              </div>\n              <div class="tipo-chip" onclick="selTipo(\'denuncia_ambiental\')" data-tipo="denuncia_ambiental">\n                <span class="chip-ic">🌱</span><span class="chip-lbl">Denuncia Ambiental</span>\n              </div>\n              <div class="tipo-chip" onclick="selTipo(\'areas_verdes\')" data-tipo="areas_verdes">\n                <span class="chip-ic">🌳</span><span class="chip-lbl">Áreas Verdes</span>\n              </div>\n              <div class="tipo-chip" onclick="selTipo(\'poda_arbol\')" data-tipo="poda_arbol">\n                <span class="chip-ic">✂️</span><span class="chip-lbl">Poda de Árbol</span>\n              </div>\n              <div class="tipo-chip" onclick="selTipo(\'derribo_arbol\')" data-tipo="derribo_arbol">\n                <span class="chip-ic">🪓</span><span class="chip-lbl">Derribo de Árbol</span>\n              </div>\n              <div class="tipo-chip" onclick="selTipo(\'residuos_solidos\')" data-tipo="residuos_solidos">\n                <span class="chip-ic">🗑️</span><span class="chip-lbl">Residuos Sólidos</span>\n              </div>\n              <div class="tipo-chip" onclick="selTipo(\'tiradero_basura\')" data-tipo="tiradero_basura">\n                <span class="chip-ic">🗑</span><span class="chip-lbl">Tiradero de Basura</span>\n              </div>\n              <div class="tipo-chip" onclick="selTipo(\'tiradero_escombro\')" data-tipo="tiradero_escombro">\n                <span class="chip-ic">🧱</span><span class="chip-lbl">Tiradero de Escombro</span>\n              </div>\n              <div class="tipo-chip" onclick="selTipo(\'agua_contaminada\')" data-tipo="agua_contaminada">\n                <span class="chip-ic">💧</span><span class="chip-lbl">Agua Contaminada</span>\n              </div>\n              <div class="tipo-chip" onclick="selTipo(\'ruido\')" data-tipo="ruido">\n                <span class="chip-ic">🔊</span><span class="chip-lbl">Ruido</span>\n              </div>\n              <div class="tipo-chip" onclick="selTipo(\'animal_calle\')" data-tipo="animal_calle">\n                <span class="chip-ic">🐾</span><span class="chip-lbl">Animal en Calle</span>\n              </div>\n              <div class="tipo-chip" onclick="selTipo(\'perro_agresivo\')" data-tipo="perro_agresivo">\n                <span class="chip-ic">🐕</span><span class="chip-lbl">Perro Agresivo</span>\n              </div>\n              <div class="tipo-chip" onclick="selTipo(\'otro\')" data-tipo="otro" style="grid-column:1/-1">\n                <span class="chip-ic">📌</span><span class="chip-lbl">Otro</span>\n              </div>\n            </div>\n          </div>\n        </div>\n\n        <!-- DESCRIPCIÓN -->\n        <div class="form-card">\n          <div class="form-card-header"><span class="ic">📝</span><span>Descripción *</span></div>\n          <div class="form-card-body">\n            <div class="fgroup">\n              <textarea id="nr-desc" placeholder="Describe la situación con el mayor detalle posible: qué ocurre, desde cuándo, qué tan urgente es..." rows="4"></textarea>\n            </div>\n          </div>\n        </div>\n\n        <!-- UBICACIÓN -->\n        <div class="form-card">\n          <div class="form-card-header"><span class="ic">📍</span><span>Ubicación *</span></div>\n          <div class="form-card-body">\n            <div class="map-btns">\n              <button class="map-btn" onclick="usarGPS()">📡 Usar mi ubicación</button>\n              <button class="map-btn" onclick="setMapLayer(\'sat\')" id="btn-sat">🛰️ Satelital</button>\n              <button class="map-btn" onclick="setMapLayer(\'osm\')" id="btn-osm">🗺️ Calles</button>\n            </div>\n            <div id="map-app" style="margin-top:10px"></div>\n            <div class="map-addr" id="map-addr">📍 Toca el mapa o usa tu GPS para marcar la ubicación exacta</div>\n\n            <!-- Dirección autocompletada -->\n            <div class="addr-grid" id="addr-grid" style="margin-top:10px">\n              <div class="fgroup">\n                <label>Calle</label>\n                <input id="nr-calle" placeholder="Se autocompleta">\n              </div>\n              <div class="fgroup">\n                <label>Número</label>\n                <input id="nr-numero" placeholder="Núm. ext.">\n              </div>\n              <div class="fgroup">\n                <label>Colonia *</label>\n                <input id="nr-colonia" placeholder="Colonia o fraccionamiento">\n              </div>\n              <div class="fgroup">\n                <label>C.P.</label>\n                <input id="nr-cp" placeholder="Código postal">\n              </div>\n            </div>\n            <input type="hidden" id="nr-lat">\n            <input type="hidden" id="nr-lon">\n          </div>\n        </div>\n\n        <!-- DATOS PERSONALES -->\n        <div class="form-card">\n          <div class="form-card-header"><span class="ic">👤</span><span>Tus datos (opcionales)</span></div>\n          <div class="form-card-body">\n            <div class="fgroup">\n              <label>Nombre completo</label>\n              <input id="nr-nombre" placeholder="Tu nombre (opcional)">\n            </div>\n            <div class="fgroup">\n              <label>Teléfono</label>\n              <input id="nr-tel" type="tel" placeholder="449 000 0000 (opcional)">\n            </div>\n          </div>\n        </div>\n\n        <!-- FIRMA -->\n        <div class="form-card">\n          <div class="form-card-header"><span class="ic">✍️</span><span>Firma digital (opcional)</span></div>\n          <div class="form-card-body">\n            <canvas id="sig-app"></canvas>\n            <div style="display:flex;gap:8px;margin-top:8px">\n              <div class="fgroup" style="flex:1">\n                <input id="nr-firmante" placeholder="Nombre del firmante">\n              </div>\n              <button class="map-btn" onclick="clearSigApp()" style="flex:none;width:44px">🗑</button>\n            </div>\n          </div>\n        </div>\n\n        <!-- PANEL ANIMAL AGRESIVO (se muestra solo cuando tipo=perro_agresivo o animal_calle) -->\n        <div id="panel-animal-agresivo" class="form-card">\n          <div class="form-card-header"><span class="ic">🐾</span><span>Información del Incidente</span></div>\n          <div class="form-card-body">\n\n            <!-- DATOS DEL AFECTADO -->\n            <div style="font-size:.72rem;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:var(--azul);margin-bottom:8px">👤 Datos del Afectado</div>\n            <div class="fgroup">\n              <label>Nombre completo del afectado *</label>\n              <input id="a-afectado-nombre" placeholder="Nombre de la persona afectada">\n            </div>\n            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">\n              <div class="fgroup">\n                <label>Teléfono *</label>\n                <input id="a-afectado-tel" type="tel" placeholder="449 000 0000">\n              </div>\n              <div class="fgroup">\n                <label>Correo electrónico</label>\n                <input id="a-afectado-email" type="email" placeholder="correo@ejemplo.com">\n              </div>\n            </div>\n            <div class="fgroup">\n              <label>Domicilio del afectado *</label>\n              <input id="a-afectado-domicilio" placeholder="Calle, número, colonia">\n            </div>\n\n            <!-- ¿FUE MORDIDA? -->\n            <label class="animal-check" style="margin-top:4px">\n              <input type="checkbox" id="a-hubo-mordida" onchange="toggleMordida()">\n              <span>🦷 ¿El animal mordió a la víctima?</span>\n            </label>\n\n            <!-- DATOS DE LA MORDIDA -->\n            <div id="panel-mordida" style="display:none;margin-top:10px">\n              <div style="font-size:.72rem;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:#dc2626;margin-bottom:8px">🩸 Datos de la Mordida</div>\n\n              <!-- Mapa corporal SVG -->\n              <div class="fgroup">\n                <label>¿Dónde ocurrió la mordida? (toca el cuerpo)</label>\n                <p style="font-size:.75rem;color:var(--muted);margin-bottom:6px">Puede seleccionar más de una zona</p>\n                <div class="body-map-wrap">\n                  <svg viewBox="0 0 160 340" xmlns="http://www.w3.org/2000/svg" style="overflow:visible">\n                    <!-- Cabeza -->\n                    <g class="bzone" id="bz-cabeza" onclick="toggleZona(\'cabeza\')">\n                      <ellipse cx="80" cy="28" rx="24" ry="26" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.5"/>\n                      <text x="80" y="32" text-anchor="middle" font-size="10" fill="#475569" font-weight="700">Cabeza</text>\n                    </g>\n                    <!-- Cuello -->\n                    <g class="bzone" id="bz-cuello" onclick="toggleZona(\'cuello\')">\n                      <rect x="68" y="54" width="24" height="16" rx="6" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.5"/>\n                      <text x="80" y="66" text-anchor="middle" font-size="8" fill="#475569" font-weight="700">Cuello</text>\n                    </g>\n                    <!-- Hombros + Torso -->\n                    <g class="bzone" id="bz-pecho" onclick="toggleZona(\'pecho\')">\n                      <rect x="42" y="70" width="76" height="70" rx="8" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.5"/>\n                      <text x="80" y="109" text-anchor="middle" font-size="10" fill="#475569" font-weight="700">Pecho/Torso</text>\n                    </g>\n                    <!-- Brazo izq -->\n                    <g class="bzone" id="bz-brazo-izq" onclick="toggleZona(\'brazo_izq\')">\n                      <rect x="14" y="72" width="26" height="58" rx="8" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.5"/>\n                      <text x="27" y="103" text-anchor="middle" font-size="8" fill="#475569" font-weight="700">Brazo</text>\n                      <text x="27" y="113" text-anchor="middle" font-size="8" fill="#475569" font-weight="700">Izq.</text>\n                    </g>\n                    <!-- Brazo der -->\n                    <g class="bzone" id="bz-brazo-der" onclick="toggleZona(\'brazo_der\')">\n                      <rect x="120" y="72" width="26" height="58" rx="8" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.5"/>\n                      <text x="133" y="103" text-anchor="middle" font-size="8" fill="#475569" font-weight="700">Brazo</text>\n                      <text x="133" y="113" text-anchor="middle" font-size="8" fill="#475569" font-weight="700">Der.</text>\n                    </g>\n                    <!-- Abdomen -->\n                    <g class="bzone" id="bz-abdomen" onclick="toggleZona(\'abdomen\')">\n                      <rect x="50" y="140" width="60" height="44" rx="8" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.5"/>\n                      <text x="80" y="167" text-anchor="middle" font-size="10" fill="#475569" font-weight="700">Abdomen</text>\n                    </g>\n                    <!-- Mano izq -->\n                    <g class="bzone" id="bz-mano-izq" onclick="toggleZona(\'mano_izq\')">\n                      <rect x="10" y="132" width="22" height="22" rx="5" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.5"/>\n                      <text x="21" y="147" text-anchor="middle" font-size="7.5" fill="#475569" font-weight="700">Mano I</text>\n                    </g>\n                    <!-- Mano der -->\n                    <g class="bzone" id="bz-mano-der" onclick="toggleZona(\'mano_der\')">\n                      <rect x="128" y="132" width="22" height="22" rx="5" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.5"/>\n                      <text x="139" y="147" text-anchor="middle" font-size="7.5" fill="#475569" font-weight="700">Mano D</text>\n                    </g>\n                    <!-- Pierna izq -->\n                    <g class="bzone" id="bz-pierna-izq" onclick="toggleZona(\'pierna_izq\')">\n                      <rect x="46" y="184" width="30" height="80" rx="8" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.5"/>\n                      <text x="61" y="226" text-anchor="middle" font-size="8.5" fill="#475569" font-weight="700">Pierna</text>\n                      <text x="61" y="238" text-anchor="middle" font-size="8.5" fill="#475569" font-weight="700">Izq.</text>\n                    </g>\n                    <!-- Pierna der -->\n                    <g class="bzone" id="bz-pierna-der" onclick="toggleZona(\'pierna_der\')">\n                      <rect x="84" y="184" width="30" height="80" rx="8" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.5"/>\n                      <text x="99" y="226" text-anchor="middle" font-size="8.5" fill="#475569" font-weight="700">Pierna</text>\n                      <text x="99" y="238" text-anchor="middle" font-size="8.5" fill="#475569" font-weight="700">Der.</text>\n                    </g>\n                    <!-- Pie izq -->\n                    <g class="bzone" id="bz-pie-izq" onclick="toggleZona(\'pie_izq\')">\n                      <rect x="38" y="264" width="34" height="18" rx="5" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.5"/>\n                      <text x="55" y="277" text-anchor="middle" font-size="7.5" fill="#475569" font-weight="700">Pie Izq.</text>\n                    </g>\n                    <!-- Pie der -->\n                    <g class="bzone" id="bz-pie-der" onclick="toggleZona(\'pie_der\')">\n                      <rect x="88" y="264" width="34" height="18" rx="5" fill="#e2e8f0" stroke="#94a3b8" stroke-width="1.5"/>\n                      <text x="105" y="277" text-anchor="middle" font-size="7.5" fill="#475569" font-weight="700">Pie Der.</text>\n                    </g>\n                  </svg>\n                </div>\n                <div id="zonas-sel-txt" style="font-size:.78rem;color:var(--azul);font-weight:700;text-align:center;margin-top:4px;min-height:18px">Ninguna zona seleccionada</div>\n              </div>\n\n              <!-- Gravedad -->\n              <div class="fgroup">\n                <label>Gravedad de la mordida</label>\n                <div class="gravedad-btns">\n                  <button type="button" class="grav-btn" id="grav-superficial" onclick="selGravedad(\'superficial\')">\n                    ✅ Superficial<br><small style="font-weight:400">Sin perforación profunda</small>\n                  </button>\n                  <button type="button" class="grav-btn" id="grav-profunda" onclick="selGravedad(\'profunda\')">\n                    ⚠️ Profunda<br><small style="font-weight:400">Perforación / hemorragia</small>\n                  </button>\n                </div>\n                <input type="hidden" id="a-gravedad-mordida">\n              </div>\n\n              <!-- Atención médica -->\n              <label class="animal-check">\n                <input type="checkbox" id="a-atencion-medica">\n                <span>🏥 ¿El afectado recibió o requiere atención médica?</span>\n              </label>\n              <label class="animal-check" style="margin-top:8px">\n                <input type="checkbox" id="a-vacuna-antirabica">\n                <span>💉 ¿Se requiere vacuna antirrábica?</span>\n              </label>\n            </div>\n\n            <!-- DATOS DEL ANIMAL -->\n            <div style="font-size:.72rem;font-weight:800;text-transform:uppercase;letter-spacing:.06em;color:var(--azul);margin:14px 0 8px">🐕 Datos del Animal</div>\n            <div class="fgroup">\n              <label>Descripción del animal *</label>\n              <input id="a-animal-desc" placeholder="Ej: Perro mediano café con manchas negras">\n            </div>\n            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">\n              <div class="fgroup">\n                <label>Especie</label>\n                <select id="a-animal-especie">\n                  <option value="">-- Tipo --</option>\n                  <option value="perro">🐕 Perro</option>\n                  <option value="gato">🐈 Gato</option>\n                  <option value="otro">Otro animal</option>\n                </select>\n              </div>\n              <div class="fgroup">\n                <label>Color(es) *</label>\n                <input id="a-animal-color" placeholder="Negro, café, blanco...">\n              </div>\n            </div>\n            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">\n              <div class="fgroup">\n                <label>Tamaño aproximado</label>\n                <select id="a-animal-tamanio">\n                  <option value="">-- Talla --</option>\n                  <option value="pequeño">Pequeño (&lt;10 kg)</option>\n                  <option value="mediano">Mediano (10-30 kg)</option>\n                  <option value="grande">Grande (&gt;30 kg)</option>\n                </select>\n              </div>\n              <div class="fgroup">\n                <label>Señas particulares</label>\n                <input id="a-animal-senias" placeholder="Collar, cicatrices...">\n              </div>\n            </div>\n            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:4px">\n              <label class="animal-check">\n                <input type="checkbox" id="a-tiene-duenio" onchange="toggleDuenio()">\n                <span>🏠 ¿Tiene dueño conocido?</span>\n              </label>\n              <label class="animal-check">\n                <input type="checkbox" id="a-tiene-vacunas">\n                <span>💊 ¿Tiene vacunas?</span>\n              </label>\n            </div>\n            <div id="panel-duenio" style="display:none;margin-top:8px">\n              <div class="fgroup">\n                <label>Datos del dueño / responsable</label>\n                <input id="a-duenio-datos" placeholder="Nombre, teléfono, domicilio del dueño">\n              </div>\n            </div>\n\n            <!-- SITUACIÓN DEL ANIMAL -->\n            <div class="fgroup" style="margin-top:8px">\n              <label>Situación actual del animal</label>\n              <select id="a-animal-situacion">\n                <option value="">-- Seleccionar --</option>\n                <option value="en_lugar">Sigue en el lugar</option>\n                <option value="huyó">Huyó / no se sabe dónde está</option>\n                <option value="controlado">Está controlado / encerrado</option>\n                <option value="capturado">Ya fue capturado</option>\n              </select>\n            </div>\n          </div>\n        </div>\n\n        <button class="btn-enviar" onclick="enviarReporte()" id="btn-enviar">\n          📨 Enviar Reporte\n        </button>\n        <button class="btn-sec" onclick="limpiarForm()">↺ Limpiar formulario</button>\n        <div style="height:20px"></div>\n      </div>\n    </div>\n\n    <!-- ══════════ MIS REPORTES ══════════ -->\n    <div id="screen-mis" class="screen">\n      <div class="screen-pad">\n        <div id="mis-alert"></div>\n        <div id="mis-lista">\n          <div class="empty-state">\n            <div class="em-ic">📋</div>\n            <p>Aquí aparecerán tus reportes enviados.<br>¡Haz tu primer reporte!</p>\n          </div>\n        </div>\n      </div>\n    </div>\n\n    <!-- ══════════ ACERCA ══════════ -->\n    <div id="screen-acerca" class="screen">\n      <div class="screen-pad">\n\n        <div class="form-card">\n          <div class="about-logo">\n            <div class="big-ic">🌿</div>\n            <h2>IMBIO Ciudadano</h2>\n            <p style="font-size:.78rem;line-height:1.4">Instituto Municipal de Biodiversidad y Protección Ambiental de Pabellón de Arteaga</p>\n          </div>\n          <div class="form-card-body" style="padding-top:0">\n            <div class="about-row">\n              <div class="row-ic">🏛️</div>\n              <div class="row-info"><label>Institución</label><span>Instituto Municipal de Biodiversidad y Protección Ambiental de Pabellón de Arteaga</span></div>\n            </div>\n            <div class="about-row">\n              <div class="row-ic">📱</div>\n              <div class="row-info"><label>Versión</label><span>1.0.0 — SGO-IMBIO</span></div>\n            </div>\n            <div class="about-row">\n              <div class="row-ic">🔗</div>\n              <div class="row-info" style="flex:1">\n                <label>Servidor SGO-IMBIO</label>\n                <div class="server-input" style="margin-top:6px">\n                  <input id="server-url" type="url" placeholder="http://192.168.1.X:8080" value="">\n                  <button onclick="guardarServidor()">✓</button>\n                </div>\n              </div>\n            </div>\n            <div class="about-row">\n              <div class="row-ic" id="conn-status-ic">🔴</div>\n              <div class="row-info"><label>Estado de conexión</label><span id="conn-status-txt">Sin conexión</span></div>\n            </div>\n            <div class="about-row">\n              <div class="row-ic">👨\u200d💻</div>\n              <div class="row-info"><label>Desarrollo</label><span>Biol. Luis Felipe Lozano Román</span></div>\n            </div>\n            <div class="about-row">\n              <div class="row-ic">📧</div>\n              <div class="row-info"><label>Contacto</label><span>imbio@pabellon.gob.mx</span></div>\n            </div>\n            <div class="about-row">\n              <div class="row-ic">©</div>\n              <div class="row-info"><label>Derechos</label><span>2026 · Municipio de Pabellón de Arteaga</span></div>\n            </div>\n            <div class="about-row">\n              <div class="row-ic">📞</div>\n              <div class="row-info"><label>Emergencias</label><span>911 / Protección Civil</span></div>\n            </div>\n          </div>\n        </div>\n\n        <div class="about-card" style="padding:16px">\n          <p style="font-size:.8rem;color:var(--muted);text-align:center;line-height:1.6">\n            Esta aplicación permite a los ciudadanos de Pabellón de Arteaga reportar\n            incidencias ambientales y de servicios urbanos directamente al sistema\n            municipal SGO-IMBIO para su atención por las brigadas operativas.\n          </p>\n        </div>\n      </div>\n    </div>\n\n  </div><!-- /content -->\n</div><!-- /app -->\n\n<script>\n// ════════════════════════════════════════════════════════\n//  IMBIO CIUDADANO — App JavaScript\n// ════════════════════════════════════════════════════════\n\n// ── Config ────────────────────────────────────────────\nconst DEFAULT_SERVER = window.location.origin; // mismo servidor\nlet SERVER_URL = localStorage.getItem(\'imbio_server\') || DEFAULT_SERVER;\nlet tipoSel = \'\';\nlet mapApp = null, appMarker = null, appLayerActive = null;\nlet sigAppCanvas, sigAppCtx, sigDrawing = false;\nlet misReportes = JSON.parse(localStorage.getItem(\'imbio_mis_reportes\') || \'[]\');\n\n// ── Splash ────────────────────────────────────────────\nwindow.addEventListener(\'load\', () => {\n  setTimeout(() => {\n    document.getElementById(\'splash\').classList.add(\'hide\');\n    initApp();\n  }, 1800);\n});\n\nfunction initApp() {\n  initMapApp();\n  initSigApp();\n  cargarMisReportes();\n  checkConexion();\n  setInterval(checkConexion, 15000);\n  // Cargar server guardado\n  document.getElementById(\'server-url\').value = SERVER_URL;\n  // Service Worker\n  if (\'serviceWorker\' in navigator) {\n    navigator.serviceWorker.register(\'/app/sw.js\').catch(() => {});\n  }\n}\n\n// ── Tabs ──────────────────────────────────────────────\nfunction setTab(name) {\n  [\'nuevo\',\'mis\',\'acerca\'].forEach(t => {\n    document.getElementById(\'screen-\' + t).classList.toggle(\'active\', t === name);\n    document.getElementById(\'tab-\' + t).classList.toggle(\'active\', t === name);\n  });\n  if (name === \'mis\') cargarMisReportes();\n  if (name === \'nuevo\') setTimeout(() => mapApp && mapApp.invalidateSize(), 150);\n}\n\n// ── Conexión ──────────────────────────────────────────\nasync function checkConexion() {\n  try {\n    const r = await fetch(SERVER_URL + \'/health\', { signal: AbortSignal.timeout(4000) });\n    const ok = r.ok;\n    document.getElementById(\'conn-dot\').className = \'conn-dot\' + (ok ? \'\' : \' off\');\n    document.getElementById(\'conn-status-ic\').textContent = ok ? \'🟢\' : \'🔴\';\n    document.getElementById(\'conn-status-txt\').textContent = ok ? \'Conectado al SGO-IMBIO\' : \'Sin conexión\';\n  } catch {\n    document.getElementById(\'conn-dot\').className = \'conn-dot off\';\n    document.getElementById(\'conn-status-ic\').textContent = \'🔴\';\n    document.getElementById(\'conn-status-txt\').textContent = \'Sin conexión al servidor\';\n  }\n}\n\nfunction guardarServidor() {\n  const url = document.getElementById(\'server-url\').value.trim().replace(/\\/$/, \'\');\n  if (!url) return;\n  SERVER_URL = url;\n  localStorage.setItem(\'imbio_server\', url);\n  checkConexion();\n  alert(\'Servidor guardado: \' + url);\n}\n\n// ── Tipo chips ─────────────────────────────────────────\nfunction selTipo(t) {\n  tipoSel = t;\n  document.querySelectorAll(\'.tipo-chip\').forEach(c => c.classList.toggle(\'sel\', c.dataset.tipo === t));\n  const panelAnimal = document.getElementById(\'panel-animal-agresivo\');\n  if (panelAnimal) {\n    panelAnimal.style.display = (t === \'perro_agresivo\' || t === \'animal_calle\') ? \'block\' : \'none\';\n  }\n}\n\n// ── Mapa ──────────────────────────────────────────────\nconst TILES = {\n  osm: { url: \'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png\', attr: \'© OSM\' },\n  sat: { url: \'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}\', attr: \'© Esri\' }\n};\n\nfunction initMapApp() {\n  mapApp = L.map(\'map-app\', { zoomControl: true, attributionControl: false }).setView([22.1508, -102.2913], 15);\n  const cfg = TILES.osm;\n  appLayerActive = L.tileLayer(cfg.url, { attribution: cfg.attr, maxZoom: 19 }).addTo(mapApp);\n  mapApp.on(\'click\', e => geocodePos(e.latlng.lat, e.latlng.lng));\n}\n\nfunction setMapLayer(name) {\n  if (!mapApp) return;\n  mapApp.removeLayer(appLayerActive);\n  const cfg = TILES[name];\n  appLayerActive = L.tileLayer(cfg.url, { attribution: cfg.attr, maxZoom: 19 }).addTo(mapApp);\n}\n\nfunction usarGPS() {\n  if (!navigator.geolocation) { showAlert(\'form-alert\', \'err\', \'Tu dispositivo no soporta GPS.\'); return; }\n  showLoading(true);\n  navigator.geolocation.getCurrentPosition(\n    pos => {\n      showLoading(false);\n      const { latitude: lat, longitude: lng } = pos.coords;\n      mapApp.setView([lat, lng], 17);\n      geocodePos(lat, lng);\n    },\n    () => { showLoading(false); showAlert(\'form-alert\', \'err\', \'No se pudo obtener tu ubicación. Toca el mapa manualmente.\'); },\n    { enableHighAccuracy: true, timeout: 10000 }\n  );\n}\n\nfunction makeAppIcon() {\n  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 36" width="28" height="42">\n    <path d="M12 0C5.37 0 0 5.37 0 12c0 9 12 24 12 24s12-15 12-24C24 5.37 18.63 0 12 0z" fill="#003B7A" stroke="white" stroke-width="1.5"/>\n    <circle cx="12" cy="12" r="5" fill="white" opacity="0.9"/>\n  </svg>`;\n  return L.divIcon({ html: svg, className: \'\', iconSize: [28,42], iconAnchor: [14,42], popupAnchor: [0,-44] });\n}\n\nasync function geocodePos(lat, lng) {\n  document.getElementById(\'nr-lat\').value = lat.toFixed(7);\n  document.getElementById(\'nr-lon\').value = lng.toFixed(7);\n  document.getElementById(\'map-addr\').textContent = \'🔍 Buscando dirección...\';\n  if (appMarker) mapApp.removeLayer(appMarker);\n  appMarker = L.marker([lat, lng], { icon: makeAppIcon() }).addTo(mapApp);\n\n  try {\n    const r   = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&addressdetails=1&accept-language=es`);\n    const geo = await r.json();\n    const a   = geo.address || {};\n    const calle   = a.road || a.pedestrian || a.footway || \'\';\n    const numero  = a.house_number || \'\';\n    const colonia = a.neighbourhood || a.suburb || a.quarter || a.village || \'\';\n    const cp      = a.postcode || \'\';\n\n    document.getElementById(\'nr-calle\').value   = calle;\n    document.getElementById(\'nr-numero\').value  = numero;\n    document.getElementById(\'nr-colonia\').value = colonia;\n    document.getElementById(\'nr-cp\').value      = cp;\n\n    // Resaltar campos llenados\n    [\'nr-calle\',\'nr-numero\',\'nr-colonia\',\'nr-cp\'].forEach(id => {\n      const el = document.getElementById(id);\n      if (el.value) el.style.borderColor = \'#1976D2\';\n    });\n\n    const partes = [calle, numero, colonia, cp].filter(Boolean);\n    document.getElementById(\'map-addr\').innerHTML =\n      `<b style="color:#003B7A">✅ Domicilio detectado:</b><br>${partes.join(\', \')}`;\n\n    appMarker.bindPopup(`<b>${partes.slice(0,2).join(\' \')}</b><br><small>${colonia}</small>`).openPopup();\n  } catch {\n    document.getElementById(\'map-addr\').textContent = `📍 ${lat.toFixed(5)}, ${lng.toFixed(5)}`;\n  }\n}\n\n// ── Firma ─────────────────────────────────────────────\nfunction initSigApp() {\n  sigAppCanvas = document.getElementById(\'sig-app\');\n  sigAppCtx    = sigAppCanvas.getContext(\'2d\');\n  sigAppCtx.strokeStyle = \'#003B7A\';\n  sigAppCtx.lineWidth   = 2.5;\n  sigAppCtx.lineCap     = \'round\';\n  sigAppCtx.lineJoin    = \'round\';\n\n  function getPos(e) {\n    const r = sigAppCanvas.getBoundingClientRect();\n    const src = e.touches ? e.touches[0] : e;\n    return { x: src.clientX - r.left, y: src.clientY - r.top };\n  }\n  sigAppCanvas.addEventListener(\'mousedown\',  e => { sigDrawing=true; sigAppCtx.beginPath(); const p=getPos(e); sigAppCtx.moveTo(p.x,p.y); });\n  sigAppCanvas.addEventListener(\'mousemove\',  e => { if(!sigDrawing)return; const p=getPos(e); sigAppCtx.lineTo(p.x,p.y); sigAppCtx.stroke(); });\n  sigAppCanvas.addEventListener(\'mouseup\',    () => sigDrawing=false);\n  sigAppCanvas.addEventListener(\'mouseleave\', () => sigDrawing=false);\n  sigAppCanvas.addEventListener(\'touchstart\', e => { e.preventDefault(); sigDrawing=true; sigAppCtx.beginPath(); const p=getPos(e); sigAppCtx.moveTo(p.x,p.y); }, {passive:false});\n  sigAppCanvas.addEventListener(\'touchmove\',  e => { e.preventDefault(); if(!sigDrawing)return; const p=getPos(e); sigAppCtx.lineTo(p.x,p.y); sigAppCtx.stroke(); }, {passive:false});\n  sigAppCanvas.addEventListener(\'touchend\',   () => sigDrawing=false);\n}\n\nfunction clearSigApp() {\n  sigAppCtx.clearRect(0, 0, sigAppCanvas.width, sigAppCanvas.height);\n}\nfunction sigIsEmpty() {\n  return !sigAppCtx.getImageData(0,0,sigAppCanvas.width,sigAppCanvas.height).data.some(v=>v!==0);\n}\n\n// ── Enviar reporte ────────────────────────────────────\nasync function enviarReporte() {\n  const alertEl = document.getElementById(\'form-alert\');\n  alertEl.innerHTML = \'\';\n\n  const tipo   = tipoSel;\n  const desc   = document.getElementById(\'nr-desc\').value.trim();\n  const lat    = document.getElementById(\'nr-lat\').value;\n  const lon    = document.getElementById(\'nr-lon\').value;\n  const colonia= document.getElementById(\'nr-colonia\').value.trim();\n  const calle  = document.getElementById(\'nr-calle\').value.trim();\n  const numero = document.getElementById(\'nr-numero\').value.trim();\n  const cp     = document.getElementById(\'nr-cp\').value.trim();\n  const nombre = document.getElementById(\'nr-nombre\').value.trim();\n  const tel    = document.getElementById(\'nr-tel\').value.trim();\n\n  // Validaciones\n  if (!tipo)         { showAlert(\'form-alert\',\'err\',\'Selecciona el tipo de incidencia.\'); scrollTop(); return; }\n  if (desc.length<10){ showAlert(\'form-alert\',\'err\',\'La descripción debe tener al menos 10 caracteres.\'); return; }\n  if (!lat || !lon)  { showAlert(\'form-alert\',\'err\',\'📍 Marca la ubicación en el mapa o usa tu GPS.\'); return; }\n  if (!colonia)      { showAlert(\'form-alert\',\'err\',\'Escribe o confirma la colonia.\'); return; }\n\n  const body = {\n    tipo, descripcion: desc,\n    colonia: colonia || \'Sin colonia\',\n    domicilio: [calle, numero ? \'#\'+numero : \'\', colonia, cp].filter(Boolean).join(\', \') || null,\n    lat: parseFloat(lat), lon: parseFloat(lon),\n    nombre_reportante: nombre || null,\n    telefono: tel || null,\n  };\n  // Datos extra para animal agresivo\n  if (tipo === \'perro_agresivo\' || tipo === \'animal_calle\') {\n    const afNombre  = document.getElementById(\'a-afectado-nombre\')?.value.trim();\n    const afTel     = document.getElementById(\'a-afectado-tel\')?.value.trim();\n    const afEmail   = document.getElementById(\'a-afectado-email\')?.value.trim();\n    const afDom     = document.getElementById(\'a-afectado-domicilio\')?.value.trim();\n    const huboMord  = document.getElementById(\'a-hubo-mordida\')?.checked;\n    const zonas     = Array.from(zonasSeleccionadas).join(\',\');\n    const gravedad  = document.getElementById(\'a-gravedad-mordida\')?.value;\n    const atMed     = document.getElementById(\'a-atencion-medica\')?.checked;\n    const vacAnti   = document.getElementById(\'a-vacuna-antirabica\')?.checked;\n    const aniDesc   = document.getElementById(\'a-animal-desc\')?.value.trim();\n    const aniEsp    = document.getElementById(\'a-animal-especie\')?.value;\n    const aniColor  = document.getElementById(\'a-animal-color\')?.value.trim();\n    const aniTam    = document.getElementById(\'a-animal-tamanio\')?.value;\n    const aniSen    = document.getElementById(\'a-animal-senias\')?.value.trim();\n    const tieneDue  = document.getElementById(\'a-tiene-duenio\')?.checked;\n    const dueData   = document.getElementById(\'a-duenio-datos\')?.value.trim();\n    const tieVac    = document.getElementById(\'a-tiene-vacunas\')?.checked;\n    const situacion = document.getElementById(\'a-animal-situacion\')?.value;\n    if (afNombre) body.afectado_nombre = afNombre;\n    if (afTel)    body.afectado_telefono = afTel;\n    if (afEmail)  body.afectado_email = afEmail;\n    if (afDom)    body.afectado_domicilio = afDom;\n    body.mordida = huboMord || false;\n    if (huboMord) {\n      body.zonas_mordida = zonas;\n      body.gravedad_mordida = gravedad;\n      body.requiere_atencion_medica = atMed || false;\n      body.requiere_vacuna_antirabica = vacAnti || false;\n    }\n    if (aniDesc)  body.animal_descripcion = aniDesc;\n    if (aniEsp)   body.animal_especie  = aniEsp;\n    if (aniColor) body.animal_color    = aniColor;\n    if (aniTam)   body.animal_tamanio  = aniTam;\n    if (aniSen)   body.animal_senias   = aniSen;\n    body.animal_tiene_duenio = tieneDue || false;\n    if (tieneDue && dueData) body.duenio_datos = dueData;\n    body.animal_vacunado = tieVac || false;\n    if (situacion) body.animal_situacion = situacion;\n  }\n\n  if (!sigIsEmpty()) {\n    const firmante = document.getElementById(\'nr-firmante\').value.trim();\n    if (firmante) {\n      body.firma_base64    = sigAppCanvas.toDataURL(\'image/png\');\n      body.nombre_firmante = firmante;\n    }\n  }\n\n  showLoading(true);\n  try {\n    const r = await fetch(SERVER_URL + \'/api/reports\', {\n      method: \'POST\',\n      headers: { \'Content-Type\': \'application/json\' },\n      body: JSON.stringify(body),\n      signal: AbortSignal.timeout(15000)\n    });\n    const data = await r.json();\n    showLoading(false);\n    if (data.success) {\n      // Guardar en historial local\n      const entry = {\n        id:      data.data.report.id,\n        folio:   data.data.report.folio,\n        tipo,\n        colonia,\n        desc:    desc.slice(0, 80),\n        estado:  \'reportado\',\n        fecha:   new Date().toISOString(),\n        lat, lon\n      };\n      misReportes.unshift(entry);\n      if (misReportes.length > 50) misReportes.pop();\n      localStorage.setItem(\'imbio_mis_reportes\', JSON.stringify(misReportes));\n      mostrarExito(data.data.report.folio);\n      limpiarForm();\n    } else {\n      showAlert(\'form-alert\', \'err\', data.message || \'Error al enviar el reporte.\');\n    }\n  } catch(e) {\n    showLoading(false);\n    showAlert(\'form-alert\', \'err\', \'⚠️ Sin conexión al servidor SGO-IMBIO. Verifica tu red en la pestaña "Acerca".\');\n  }\n}\n\nfunction mostrarExito(folio) {\n  document.getElementById(\'exito-folio\').textContent = \'📋 Folio: \' + folio;\n  document.getElementById(\'screen-exito\').classList.add(\'show\');\n}\nfunction cerrarExito() {\n  document.getElementById(\'screen-exito\').classList.remove(\'show\');\n  setTab(\'nuevo\');\n}\n\n// ── Mis Reportes ──────────────────────────────────────\nfunction cargarMisReportes() {\n  const el = document.getElementById(\'mis-lista\');\n  if (!misReportes.length) {\n    el.innerHTML = \'<div class="empty-state"><div class="em-ic">📋</div><p>Aún no has enviado reportes.<br>¡Haz tu primer reporte desde la pestaña "Nuevo"!</p></div>\';\n    return;\n  }\n  const TIPO_LABELS = {\n    emergencia:\'🚨 Emergencia\', denuncia_ambiental:\'🌱 Denuncia Ambiental\',\n    areas_verdes:\'🌳 Áreas Verdes\', poda_arbol:\'✂️ Poda de Árbol\',\n    derribo_arbol:\'🪓 Derribo de Árbol\', residuos_solidos:\'🗑️ Residuos Sólidos\',\n    tiradero_basura:\'🗑 Tiradero Basura\', tiradero_escombro:\'🧱 Tiradero Escombro\',\n    agua_contaminada:\'💧 Agua Contaminada\', ruido:\'🔊 Ruido\',\n    animal_calle:\'🐾 Animal en Calle\', perro_agresivo:\'🐕 Perro Agresivo\',\n    otro:\'📌 Otro\'\n  };\n  el.innerHTML = misReportes.map(r => `\n    <div class="reporte-card est-${r.estado}">\n      <div class="reporte-card-head">\n        <span class="reporte-folio">${r.folio}</span>\n        <span class="reporte-estado est-badge-${r.estado}">${r.estado.replace(\'_\',\' \')}</span>\n      </div>\n      <div class="reporte-tipo">${TIPO_LABELS[r.tipo] || r.tipo}</div>\n      <div class="reporte-desc">${r.desc}</div>\n      <div class="reporte-foot">\n        <span class="reporte-fecha">${fmtFecha(r.fecha)}</span>\n        <span class="reporte-colonia">📍 ${r.colonia}</span>\n      </div>\n    </div>`).join(\'\');\n\n  // Actualizar estados desde servidor en background\n  actualizarEstados();\n}\n\nasync function actualizarEstados() {\n  if (!misReportes.length) return;\n  try {\n    const ids = misReportes.map(r => r.id).slice(0, 10);\n    for (const id of ids) {\n      const r = await fetch(SERVER_URL + `/api/reports/${id}`, { signal: AbortSignal.timeout(5000) });\n      if (!r.ok) continue;\n      const data = await r.json();\n      if (data.success) {\n        const entry = misReportes.find(m => m.id === id);\n        if (entry) entry.estado = data.data.estado;\n      }\n    }\n    localStorage.setItem(\'imbio_mis_reportes\', JSON.stringify(misReportes));\n    cargarMisReportes();\n  } catch {}\n}\n\n// ── Helpers ───────────────────────────────────────────\nfunction limpiarForm() {\n  tipoSel = \'\';\n  document.querySelectorAll(\'.tipo-chip\').forEach(c => c.classList.remove(\'sel\'));\n  [\'nr-desc\',\'nr-calle\',\'nr-numero\',\'nr-colonia\',\'nr-cp\',\'nr-nombre\',\'nr-tel\',\'nr-firmante\',\'nr-lat\',\'nr-lon\']\n    .forEach(id => { const el = document.getElementById(id); if(el) el.value = \'\'; });\n  [\'nr-calle\',\'nr-numero\',\'nr-colonia\',\'nr-cp\'].forEach(id => {\n    document.getElementById(id).style.borderColor = \'\';\n  });\n  document.getElementById(\'map-addr\').textContent = \'📍 Toca el mapa o usa tu GPS para marcar la ubicación exacta\';\n  document.getElementById(\'form-alert\').innerHTML = \'\';\n  if (appMarker && mapApp) { mapApp.removeLayer(appMarker); appMarker = null; }\n  clearSigApp();\n  resetAnimalForm();\n  const p = document.getElementById(\'panel-animal-agresivo\');\n  if (p) p.style.display = \'none\';\n}\n\nfunction showAlert(containerId, type, msg) {\n  const classes = { ok:\'alert-ok\', err:\'alert-err\', inf:\'alert-inf\' };\n  document.getElementById(containerId).innerHTML =\n    `<div class="alert ${classes[type]}">${msg}</div>`;\n}\n\nfunction showLoading(show) {\n  document.getElementById(\'loading-overlay\').className = \'loading-overlay\' + (show ? \' show\' : \'\');\n  document.getElementById(\'loading-overlay\').style.display = show ? \'flex\' : \'none\';\n}\n\nfunction scrollTop() {\n  document.querySelector(\'.content\').scrollTo({ top: 0, behavior: \'smooth\' });\n}\n\nfunction fmtFecha(iso) {\n  if (!iso) return \'–\';\n  return new Date(iso).toLocaleString(\'es-MX\', { dateStyle: \'short\', timeStyle: \'short\' });\n}\n\n// ── Animal Agresivo ──────────────────────────────────────────────────────────\nlet zonasSeleccionadas = new Set();\nlet gravedadMordida    = \'\';\n\nfunction toggleZona(zona) {\n  const g = document.getElementById(\'bz-\' + zona.replace(\'_\',\'-\'));\n  if (!g) return;\n  if (zonasSeleccionadas.has(zona)) {\n    zonasSeleccionadas.delete(zona);\n    g.classList.remove(\'sel\');\n  } else {\n    zonasSeleccionadas.add(zona);\n    g.classList.add(\'sel\');\n  }\n  const labels = {\n    cabeza:\'Cabeza\', cuello:\'Cuello\', pecho:\'Pecho/Torso\',\n    brazo_izq:\'Brazo izq.\', brazo_der:\'Brazo der.\',\n    mano_izq:\'Mano izq.\', mano_der:\'Mano der.\',\n    abdomen:\'Abdomen\', pierna_izq:\'Pierna izq.\',\n    pierna_der:\'Pierna der.\', pie_izq:\'Pie izq.\', pie_der:\'Pie der.\'\n  };\n  const el = document.getElementById(\'zonas-sel-txt\');\n  if (el) el.textContent = zonasSeleccionadas.size\n    ? Array.from(zonasSeleccionadas).map(z => labels[z]||z).join(\', \')\n    : \'Ninguna zona seleccionada\';\n}\n\nfunction selGravedad(g) {\n  gravedadMordida = g;\n  document.getElementById(\'a-gravedad-mordida\').value = g;\n  document.getElementById(\'grav-superficial\').className = \'grav-btn\' + (g===\'superficial\'?\' sel-sup\':\'\');\n  document.getElementById(\'grav-profunda\').className    = \'grav-btn\' + (g===\'profunda\'?\' sel-pro\':\'\');\n}\n\nfunction toggleMordida() {\n  var checked = document.getElementById(\'a-hubo-mordida\').checked;\n  document.getElementById(\'panel-mordida\').style.display = checked ? \'block\' : \'none\';\n}\n\nfunction toggleDuenio() {\n  var checked = document.getElementById(\'a-tiene-duenio\').checked;\n  document.getElementById(\'panel-duenio\').style.display = checked ? \'block\' : \'none\';\n}\n\nfunction resetAnimalForm() {\n  zonasSeleccionadas.clear();\n  gravedadMordida = \'\';\n  document.querySelectorAll(\'.bzone\').forEach(g => g.classList.remove(\'sel\'));\n  const txt = document.getElementById(\'zonas-sel-txt\');\n  if (txt) txt.textContent = \'Ninguna zona seleccionada\';\n  document.getElementById(\'grav-superficial\').className = \'grav-btn\';\n  document.getElementById(\'grav-profunda\').className = \'grav-btn\';\n  [\'a-hubo-mordida\',\'a-atencion-medica\',\'a-vacuna-antirabica\',\'a-tiene-duenio\',\'a-tiene-vacunas\']\n    .forEach(id => { const el=document.getElementById(id); if(el) el.checked=false; });\n  [\'a-afectado-nombre\',\'a-afectado-tel\',\'a-afectado-email\',\'a-afectado-domicilio\',\n   \'a-animal-desc\',\'a-animal-color\',\'a-animal-senias\',\'a-duenio-datos\']\n    .forEach(id => { const el=document.getElementById(id); if(el) el.value=\'\'; });\n  [\'a-animal-especie\',\'a-animal-tamanio\',\'a-animal-situacion\']\n    .forEach(id => { const el=document.getElementById(id); if(el) el.value=\'\'; });\n  document.getElementById(\'panel-mordida\').style.display = \'none\';\n  document.getElementById(\'panel-duenio\').style.display = \'none\';\n}\n</script>\n</body>\n</html>\n'
APP_SW       = "// SGO-IMBIO Ciudadano – Service Worker\nconst CACHE = 'imbio-ciudadano-v1';\nconst OFFLINE_URLS = ['/app'];\n\nself.addEventListener('install', e => {\n  e.waitUntil(\n    caches.open(CACHE).then(c => c.addAll(OFFLINE_URLS))\n  );\n  self.skipWaiting();\n});\n\nself.addEventListener('activate', e => {\n  e.waitUntil(\n    caches.keys().then(keys =>\n      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))\n    )\n  );\n  self.clients.claim();\n});\n\nself.addEventListener('fetch', e => {\n  // API calls: network first, no cache\n  if (e.request.url.includes('/api/')) return;\n  e.respondWith(\n    fetch(e.request)\n      .catch(() => caches.match(e.request).then(r => r || caches.match('/app')))\n  );\n});\n"
APP_MANIFEST = '{\n  "name": "IMBIO Ciudadano",\n  "short_name": "IMBIO",\n  "description": "Reporta incidencias ambientales al Instituto Municipal de Biodiversidad y Protección Ambiental de Pabellón de Arteaga",\n  "start_url": "/app",\n  "display": "standalone",\n  "background_color": "#002A5C",\n  "theme_color": "#003B7A",\n  "orientation": "portrait",\n  "icons": [\n    { "src": "/app/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable" },\n    { "src": "/app/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable" }\n  ],\n  "categories": ["utilities", "government"],\n  "lang": "es-MX"\n}\n'
APP_ICON_192 = base64.b64decode('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')
APP_ICON_512 = base64.b64decode('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')


TIPOS_VALIDOS  = [
    "denuncia_ambiental","areas_verdes","emergencia","residuos_solidos",
    "agua_contaminada","ruido",
    "poda_arbol","derribo_arbol",
    "animal_calle","perro_agresivo",
    "tiradero_escombro","tiradero_basura",
    "otro"
]
ESTADOS_VALIDOS = ["reportado","asignado","en_proceso","cerrado"]


# ── Auto-crear directorios y DB si no existen ─────────────────────────────
def _init_storage():
    """Crea carpetas y db.json con datos demo si no existen. Sin acentos para maximo compatibilidad."""
    UPLOAD_EV.mkdir(parents=True, exist_ok=True)
    UPLOAD_SIG.mkdir(parents=True, exist_ok=True)
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    if DB_FILE.exists():
        return
    def hp(pw): return __import__('hashlib').sha256(pw.encode()).hexdigest()
    def n(): return __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
    db = {
        "users": [
            {"id":1,"nombre":"Administrador IMBIO","username":"admin",      "password":hp("admin123"),     "rol":"admin",    "activo":True},
            {"id":2,"nombre":"Operador Central",   "username":"operador",   "password":hp("operador123"),  "rol":"operador", "activo":True},
            {"id":3,"nombre":"Inspector Campo 01", "username":"inspector01","password":hp("inspector123"), "rol":"inspector","activo":True},
        ],
        "reports": [
            {"id":1,"folio":"IMBIO-2026-0001","tipo":"emergencia",        "descripcion":"Arbol caido en calle principal bloqueando el paso","colonia":"Centro",         "lat":22.1508,"lon":-102.2913,"estado":"reportado", "nombre_reportante":"Maria Lopez",    "telefono":"449 100 1000","fecha_creacion":n(),"fecha_actualizacion":n()},
            {"id":2,"folio":"IMBIO-2026-0002","tipo":"denuncia_ambiental","descripcion":"Quema ilegal de residuos en terreno baldio",       "colonia":"Los Pinos",      "lat":22.1518,"lon":-102.2923,"estado":"reportado", "nombre_reportante":"Carlos Hernandez","telefono":"449 111 1111","fecha_creacion":n(),"fecha_actualizacion":n()},
            {"id":3,"folio":"IMBIO-2026-0003","tipo":"areas_verdes",      "descripcion":"Poda urgente de arboles con ramas sobre cables",   "colonia":"Jardines",       "lat":22.1528,"lon":-102.2933,"estado":"asignado",  "nombre_reportante":"Ana Garcia",     "telefono":None,          "fecha_creacion":n(),"fecha_actualizacion":n()},
            {"id":4,"folio":"IMBIO-2026-0004","tipo":"residuos_solidos",  "descripcion":"Contenedores desbordados sin recoleccion 5 dias",  "colonia":"La Providencia","lat":22.1538,"lon":-102.2943,"estado":"en_proceso","nombre_reportante":"Roberto Diaz",   "telefono":"449 133 1333","fecha_creacion":n(),"fecha_actualizacion":n()},
            {"id":5,"folio":"IMBIO-2026-0005","tipo":"agua_contaminada",  "descripcion":"Mancha oscura en arroyo olor fetido posible derrame","colonia":"Villas del Rey","lat":22.1548,"lon":-102.2953,"estado":"cerrado",  "nombre_reportante":"Lucia Martinez", "telefono":"449 144 1444","fecha_creacion":n(),"fecha_actualizacion":n()},
            {"id":6,"folio":"IMBIO-2026-0006","tipo":"ruido",             "descripcion":"Ruido excesivo de establecimiento despues 11pm",   "colonia":"El Mirador",    "lat":22.1558,"lon":-102.2963,"estado":"reportado", "nombre_reportante":None,             "telefono":None,          "fecha_creacion":n(),"fecha_actualizacion":n()},
            {"id":7,"folio":"IMBIO-2026-0007","tipo":"otro",              "descripcion":"Bache profundo en Av Principal riesgo vehiculos",  "colonia":"San Antonio",   "lat":22.1568,"lon":-102.2973,"estado":"asignado",  "nombre_reportante":"Pedro Ramirez",  "telefono":"449 166 1666","fecha_creacion":n(),"fecha_actualizacion":n()},
            {"id":8,"folio":"IMBIO-2026-0008","tipo":"poda_arbol",          "descripcion":"Arbol con ramas que obstruyen el alumbrado publico",  "colonia":"Las Flores",    "lat":22.1578,"lon":-102.2983,"estado":"reportado", "nombre_reportante":"Sofia Reyes",    "telefono":"449 177 1777","fecha_creacion":n(),"fecha_actualizacion":n()},
            {"id":9,"folio":"IMBIO-2026-0009","tipo":"perro_agresivo",      "descripcion":"Perro sin dueno ataca a transeuntes en parque",       "colonia":"El Roble",      "lat":22.1488,"lon":-102.2893,"estado":"reportado", "nombre_reportante":"Miguel Torres",  "telefono":"449 188 1888","fecha_creacion":n(),"fecha_actualizacion":n()},
            {"id":10,"folio":"IMBIO-2026-0010","tipo":"tiradero_escombro",  "descripcion":"Deposito ilegal de escombro en via publica",          "colonia":"Industrial",    "lat":22.1498,"lon":-102.2903,"estado":"reportado", "nombre_reportante":None,             "telefono":None,          "fecha_creacion":n(),"fecha_actualizacion":n()},
        ],
        "assignments": [
            {"id":1,"report_id":3,"brigada":"Brigada Verde A", "inspector":"Carlos Mendez","notas":"","fecha_asignacion":n()},
            {"id":2,"report_id":4,"brigada":"Brigada Azul B",  "inspector":"Laura Torres", "notas":"Atencion prioritaria","fecha_asignacion":n()},
            {"id":3,"report_id":5,"brigada":"Brigada Naranja C","inspector":"Jose Ruiz",   "notas":"Atencion prioritaria","fecha_asignacion":n()},
            {"id":4,"report_id":7,"brigada":"Brigada Verde A", "inspector":"Carlos Mendez","notas":"","fecha_asignacion":n()},
        ],
        "evidence": [
            {"id":1,"report_id":4,"photo_url":"uploads/evidence/demo_4.jpg","comentario":"Situacion confirmada en campo.","lat_captura":22.1538,"lon_captura":-102.2943,"fecha":n()},
            {"id":2,"report_id":5,"photo_url":"uploads/evidence/demo_5.jpg","comentario":"Derrame atendido y contenido.", "lat_captura":22.1548,"lon_captura":-102.2953,"fecha":n()},
        ],
        "signatures": [],
        "folio_counter": 10,
        "actas": [],
    }
    DB_FILE.write_text(__import__('json').dumps(db, indent=2, ensure_ascii=False), encoding='utf-8')
    print("[DB] Base de datos inicializada con datos demo.")

_init_storage()

# ── Leaflet servido localmente (descarga diferida, sin bloquear arranque) ───
import urllib.request as _urllib
import threading as _thr

_LEAFLET_CSS = b''
_LEAFLET_JS  = b''

INSPECTOR_MANIFEST = '{\n  "name": "IMBIO Inspector",\n  "short_name": "Inspector IMBIO",\n  "description": "App para inspectores del Instituto Municipal de Biodiversidad y Protecci\u00f3n Ambiental de Pabll\u00f3n de Arteaga",\n  "start_url": "/inspector",\n  "display": "standalone",\n  "background_color": "#0d1f35",\n  "theme_color": "#003B7A",\n  "orientation": "portrait",\n  "icons": [\n    { "src": "/inspector/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable" },\n    { "src": "/inspector/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable" }\n  ],\n  "categories": ["utilities"],\n  "lang": "es"\n}'

INSPECTOR_SW = "// IMBIO Inspector SW\nconst CACHE='imbio-insp-v1';\nself.addEventListener('install',e=>{self.skipWaiting();});\nself.addEventListener('activate',e=>{self.clients.claim();});\nself.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));});"

def _fetch_leaflet():
    global _LEAFLET_CSS, _LEAFLET_JS
    try:
        print('[INIT] Descargando Leaflet...')
        _LEAFLET_CSS = _urllib.urlopen(
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css', timeout=15).read()
        _LEAFLET_JS  = _urllib.urlopen(
            'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',  timeout=15).read()
        print(f'[INIT] Leaflet OK: CSS={len(_LEAFLET_CSS)//1024}KB JS={len(_LEAFLET_JS)//1024}KB')
    except Exception as e:
        print(f'[INIT] Sin Leaflet ({e}) - usando fallback')
        _LEAFLET_CSS = b'/* leaflet offline */'
        _LEAFLET_JS  = b'window.L={map:function(){return{on:function(){return this},setView:function(){return this},invalidateSize:function(){},removeLayer:function(){},fitBounds:function(){},addLayer:function(){},remove:function(){}};},tileLayer:function(){return{addTo:function(){return this}};},marker:function(){return{addTo:function(){return this},bindPopup:function(){return this},openPopup:function(){return this},closePopup:function(){},remove:function(){}};},icon:function(){return{};},divIcon:function(){return{};},featureGroup:function(a){return{getBounds:function(){return{pad:function(){return{};}};},addTo:function(){return this;}};},LatLng:function(){}};'

_thr.Thread(target=_fetch_leaflet, daemon=True).start()


# ── Pre-compilar y comprimir HTML a bytes ────────────────────────────────
import gzip as _gzip
_APP_BYTES        = _gzip.compress(APP_HTML.encode('utf-8'),        compresslevel=9)
_APP_BYTES_RAW    = APP_HTML.encode('utf-8')
_INSPECTOR_BYTES  = _gzip.compress(INSPECTOR_HTML.encode('utf-8'),  compresslevel=9)
_INSPECTOR_BYTES_RAW = INSPECTOR_HTML.encode('utf-8')
print(f'[INIT] App: {len(_APP_BYTES_RAW)//1024}KB → gzip {len(_APP_BYTES)//1024}KB | '
      f'Inspector: {len(_INSPECTOR_BYTES_RAW)//1024}KB → gzip {len(_INSPECTOR_BYTES)//1024}KB')

# ── Utilidades DB (JSON file como persistence) ─────────────────────────────
db_lock = threading.Lock()

def _init_sqlite():
    """Create SQLite DB and seed from JSON if first run."""
    DB_SQLITE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_SQLITE))
    conn.execute("""CREATE TABLE IF NOT EXISTS store (
        id   INTEGER PRIMARY KEY,
        data TEXT NOT NULL
    )""")
    conn.commit()
    row = conn.execute("SELECT data FROM store WHERE id=1").fetchone()
    if not row:
        # Seed from JSON file if it exists, otherwise use defaults
        if DB_FILE.exists():
            seed = DB_FILE.read_text(encoding='utf-8')
        else:
            seed = json.dumps({
                "reports": [], "assignments": [], "users": [
                    {"id":1,"username":"admin","password": hashlib.sha256(b"admin123").hexdigest(),"nombre":"Administrador IMBIO","rol":"admin","activo":True},
                    {"id":2,"username":"operador","password": hashlib.sha256(b"operador123").hexdigest(),"nombre":"Operador IMBIO","rol":"operador","activo":True},
                    {"id":3,"username":"inspector01","password": hashlib.sha256(b"inspector123").hexdigest(),"nombre":"Inspector Campo 01","rol":"inspector","brigada":"Brigada 1","activo":True}
                ], "actas": []
            }, ensure_ascii=False)
        conn.execute("INSERT INTO store(id,data) VALUES(1,?)", (seed,))
        conn.commit()
    conn.close()

def read_db():
    with db_lock:
        conn = sqlite3.connect(str(DB_SQLITE))
        row = conn.execute("SELECT data FROM store WHERE id=1").fetchone()
        conn.close()
        db = json.loads(row[0])
        # Migración automática
        changed = False
        if 'actas' not in db:
            db['actas'] = []; changed = True
        for idx_u, u in enumerate(db.get('users', [])):
            if 'id' not in u:
                u['id'] = idx_u + 1; changed = True
        if changed:
            write_db(db)
        return db

def write_db(db):
    with db_lock:
        conn = sqlite3.connect(str(DB_SQLITE))
        conn.execute("UPDATE store SET data=? WHERE id=1",
                     (json.dumps(db, ensure_ascii=False),))
        conn.commit()
        conn.close()

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def generate_folio(db):
    db["folio_counter"] += 1
    return f"IMBIO-2026-{db['folio_counter']:04d}"

# ── JWT minimalista (HMAC-SHA256) ──────────────────────────────────────────
def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * (pad % 4))

def jwt_sign(payload: dict) -> str:
    import hmac
    header  = b64url_encode(json.dumps({"alg":"HS256","typ":"JWT"}).encode())
    body    = b64url_encode(json.dumps(payload).encode())
    msg     = f"{header}.{body}".encode()
    sig     = b64url_encode(hmac.new(JWT_SECRET.encode(), msg, hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"

def jwt_verify(token: str):
    import hmac
    try:
        parts = token.split(".")
        if len(parts) != 3: return None
        header, body, sig = parts
        msg      = f"{header}.{body}".encode()
        expected = b64url_encode(hmac.new(JWT_SECRET.encode(), msg, hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected): return None
        return json.loads(b64url_decode(body))
    except Exception:
        return None

# ── HTML Frontend (una sola página SPA) ───────────────────────────────────


# ── HTTP Handler ────────────────────────────────────────────────────────────
class IMBIOHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Log limpio
        print(f"[HTTP] {self.address_string()} {fmt % args}")

    # ── Parsers ────────────────────────────────────────────────
    def parse_json_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length == 0: return {}
        raw = self.rfile.read(length)
        try:    return json.loads(raw)
        except: return {}

    def parse_multipart(self):
        """Parseo básico multipart para subida de archivos."""
        ct   = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in ct: return {}, []
        boundary = ct.split('boundary=')[1].encode()
        length   = int(self.headers.get('Content-Length', 0))
        raw      = self.rfile.read(length)
        fields   = {}
        files    = []
        parts    = raw.split(b'--' + boundary)
        for part in parts[1:-1]:
            if b'\r\n\r\n' not in part: continue
            header_raw, body = part.split(b'\r\n\r\n', 1)
            body = body.rstrip(b'\r\n')
            header_str = header_raw.decode('utf-8', errors='replace')
            if 'filename=' in header_str:
                m = re.search(r'filename="([^"]+)"', header_str)
                fname = m.group(1) if m else f"file_{uuid.uuid4().hex[:8]}"
                files.append({'filename': fname, 'data': body})
            else:
                m = re.search(r'name="([^"]+)"', header_str)
                if m: fields[m.group(1)] = body.decode('utf-8', errors='replace')
        return fields, files

    # ── Responses ──────────────────────────────────────────────
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def ok(self, data=None, message='OK', status=200):
        self.send_json({'success': True, 'message': message, 'data': data}, status)

    def err(self, message='Error', status=400):
        self.send_json({'success': False, 'message': message}, status)

    # ── Auth helper ────────────────────────────────────────────
    def get_user(self):
        auth = self.headers.get('Authorization', '')
        if not auth.startswith('Bearer '): return None
        return jwt_verify(auth[7:])

    def require_auth(self, *roles):
        user = self.get_user()
        if not user:
            self.err('Token de autenticación requerido.', 401)
            return None
        if roles and user.get('rol') not in roles:
            self.err(f"Acceso denegado. Rol requerido: {', '.join(roles)}.", 403)
            return None
        return user

    # ══════════════════════════════════════════════════════════
    #  GET
    # ══════════════════════════════════════════════════════════
    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip('/')
        qs     = parse_qs(parsed.query)

        # ── Serve frontend ─────────────────────────────────────
        if path in ('', '/'):
            body = HTML.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(body))
            self.send_header('Cache-Control', 'max-age=60')
            self.end_headers()
            self.wfile.write(body)
            return

        # ── Health ─────────────────────────────────────────────
        # ── Assets estáticos (Leaflet cached) ─────────────────────────
        if path == '/static/leaflet.css':
            self.send_response(200)
            self.send_header('Content-Type', 'text/css')
            self.send_header('Cache-Control', 'public, max-age=86400')
            self.send_header('Content-Length', len(_LEAFLET_CSS))
            self.end_headers()
            self.wfile.write(_LEAFLET_CSS)
            return
        if path == '/static/leaflet.js.map':
            self.send_response(204)  # No Content - silencia el 404 en logs
            self.end_headers()
            return

        if path == '/static/leaflet.js':

            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.send_header('Cache-Control', 'public, max-age=86400')
            self.send_header('Content-Length', len(_LEAFLET_JS))
            self.end_headers()
            self.wfile.write(_LEAFLET_JS)
            return

        if path == '/health':
            self.ok({'service': 'SGO-IMBIO', 'version': '1.0.0', 'status': 'running'}, 'OK')
            return

        # ── Auth me ────────────────────────────────────────────
        if path == '/api/auth/me':
            user = self.require_auth()
            if user: self.ok(user, 'Usuario autenticado.')
            return

        # ── List reports ───────────────────────────────────────
        if path == '/api/reports':
            user = self.require_auth()
            if not user: return
            db     = read_db()
            reps   = db['reports']
            estado  = qs.get('estado', [None])[0]
            tipo    = qs.get('tipo',   [None])[0]
            colonia = qs.get('colonia',[None])[0]
            if estado:  reps = [r for r in reps if r['estado'] == estado]
            if tipo:    reps = [r for r in reps if r['tipo']   == tipo]
            if colonia: reps = [r for r in reps if colonia.lower() in r['colonia'].lower()]
            # Ordenar más reciente primero
            reps = sorted(reps, key=lambda r: r['fecha_creacion'], reverse=True)
            # Enriquecer con brigada/inspector de la última asignación
            for rep in reps:
                asigs = [a for a in db['assignments'] if a['report_id'] == rep['id']]
                if asigs:
                    last = sorted(asigs, key=lambda a: a['fecha_asignacion'])[-1]
                    rep['brigada']   = last['brigada']
                    rep['inspector'] = last['inspector']
                else:
                    rep['brigada'] = rep['inspector'] = None
            # Paginación
            page  = int(qs.get('page',  [1])[0])
            limit = int(qs.get('limit', [20])[0])
            total = len(reps)
            start = (page - 1) * limit
            page_reps = reps[start:start + limit]
            self.ok({
                'reportes': page_reps,
                'paginacion': {
                    'total': total, 'pagina': page, 'por_pagina': limit,
                    'total_paginas': max(1, (total + limit - 1) // limit)
                }
            }, f'{total} reporte(s) encontrado(s).')
            return

        # ── Listado de actas (panel admin) ──────────────────────────
        if path == '/api/actas':
            user = self.require_auth('admin', 'operador')
            if not user: return
            db = read_db()
            actas = list(db.get('actas', []))
            # Filtros opcionales
            tipo_f    = qs.get('tipo_acta',  [None])[0]
            estado_f  = qs.get('estado',     [None])[0]
            inspector_f = qs.get('inspector',[None])[0]
            if tipo_f:      actas = [a for a in actas if a.get('tipo_acta')  == tipo_f]
            if estado_f:    actas = [a for a in actas if a.get('estado')     == estado_f]
            if inspector_f: actas = [a for a in actas if inspector_f.lower() in (a.get('inspector','') or '').lower()]
            actas = sorted(actas, key=lambda a: a.get('fecha',''), reverse=True)
            # Enriquecer con datos del reporte origen
            reps_idx = {r['id']: r for r in db.get('reports', [])}
            for a in actas:
                rep = reps_idx.get(a.get('report_id'))
                if rep:
                    a['reporte_folio'] = rep.get('folio','')
                    a['reporte_tipo']  = rep.get('tipo','')
                    a['reporte_colonia'] = rep.get('colonia','')
                else:
                    a['reporte_folio'] = a['reporte_tipo'] = a['reporte_colonia'] = ''
            # Paginación
            page  = int(qs.get('page',  [1])[0])
            limit = int(qs.get('limit', [50])[0])
            total = len(actas)
            start = (page - 1) * limit
            self.ok({
                'actas': actas[start:start+limit],
                'paginacion': {
                    'total': total, 'pagina': page, 'por_pagina': limit,
                    'total_paginas': max(1, (total + limit - 1) // limit)
                }
            }, f'{total} acta(s) encontrada(s).')
            return

        # ── Acta individual ─────────────────────────────────────────
        m = re.match(r'^/api/actas/(\d+)$', path)
        if m:
            user = self.require_auth('admin', 'operador')
            if not user: return
            aid = int(m.group(1))
            db = read_db()
            acta = next((a for a in db.get('actas', []) if a['id'] == aid), None)
            if not acta:
                self.err('Acta no encontrada.', 404); return
            self.ok({'acta': acta}, 'OK.')
            return

        # ── Reportes asignados al inspector ─────────────────────────
        if path == '/api/inspector/reportes':
            user = self.require_auth('inspector', 'admin', 'operador')
            if not user: return
            db   = read_db()
            reps = db['reports']
            # Filtrar por estado activo (no cerrado)
            estado = qs.get('estado', [None])[0]
            if estado:
                reps = [r for r in reps if r['estado'] == estado]
            else:
                reps = [r for r in reps if r['estado'] in ('asignado', 'en_proceso')]
            # ── Filtrar por inspector si el usuario es inspector ──────────
            if user.get('rol') == 'inspector':
                nombre_insp = (user.get('nombre') or user.get('username') or '').strip()
                username_insp = (user.get('username') or '').strip().lower()
                # Un reporte pertenece al inspector si tiene una asignación con su nombre o username
                def es_del_inspector(rep):
                    asigs = [a for a in db['assignments'] if a['report_id'] == rep['id']]
                    if not asigs:
                        return False
                    last = sorted(asigs, key=lambda a: a['fecha_asignacion'])[-1]
                    asig_insp = (last.get('inspector') or '').strip()
                    return (asig_insp.lower() == nombre_insp.lower() or
                            asig_insp.lower() == username_insp)
                reps = [r for r in reps if es_del_inspector(r)]
            reps = sorted(reps, key=lambda r: r['fecha_creacion'], reverse=True)
            # Enriquecer con asignacion
            for rep in reps:
                asigs = [a for a in db['assignments'] if a['report_id'] == rep['id']]
                rep['asignacion'] = sorted(asigs, key=lambda a: a['fecha_asignacion'])[-1] if asigs else None
                rep['evidencias'] = [e for e in db['evidence']   if e['report_id'] == rep['id']]
                rep['actas']      = [a for a in db.get('actas',[]) if a['report_id'] == rep['id']]
            self.ok({'reportes': reps, 'total': len(reps)}, f'{len(reps)} reporte(s) activos.')
            return

        # ── Listar inspectores ───────────────────────────────────────────
        if path == '/api/inspectores':
            user = self.require_auth('admin', 'operador')
            if not user: return
            db = read_db()
            inspectores = [u for u in db['users'] if u.get('rol') == 'inspector']
            safe = [{k:v for k,v in u.items() if k != 'password'} for u in inspectores]
            self.ok({'inspectores': safe, 'total': len(safe)}, f'{len(safe)} inspector(es).')
            return

        # ── Estado público de un reporte (sin auth) ────────────────
        m = re.match(r'^/api/reports/(\d+)/status$', path)
        if m:
            rid = int(m.group(1))
            db  = read_db()
            rep = next((r for r in db['reports'] if r['id'] == rid), None)
            if not rep:
                self.ok({'estado': 'no_encontrado'}, 'OK')
            else:
                self.ok({'estado': rep['estado'], 'folio': rep['folio']}, 'OK')
            return

        # ── Get report by id ───────────────────────────────────
        m = re.match(r'^/api/reports/(\d+)$', path)
        if m:
            user = self.require_auth()
            if not user: return
            rid = int(m.group(1))
            db  = read_db()
            rep = next((r for r in db['reports'] if r['id'] == rid), None)
            if not rep: self.err(f'Reporte {rid} no encontrado.', 404); return
            rep = dict(rep)
            rep['asignaciones'] = [a for a in db['assignments'] if a['report_id'] == rid]
            rep['evidencias']   = [e for e in db['evidence']    if e['report_id'] == rid]
            rep['firmas']       = [s for s in db['signatures']  if s['report_id'] == rid]
            rep['actas']        = [a for a in db.get('actas', []) if a['report_id'] == rid]
            self.ok(rep, 'Reporte encontrado.')
            return

        # ── Static uploads ─────────────────────────────────────
        if path.startswith('/uploads/'):
            file_path = BASE_DIR / path.lstrip('/')
            if file_path.exists():
                body = file_path.read_bytes()
                ext  = file_path.suffix.lower()
                ct   = {'jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png'}.get(ext[1:], 'application/octet-stream')
                self.send_response(200)
                self.send_header('Content-Type', ct)
                self.send_header('Content-Length', len(body))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.err('Archivo no encontrado.', 404)
            return

        # ── App Ciudadano ─────────────────────────────────────
        # ── App Inspector ──────────────────────────────────────────
        if path in ('/inspector', '/inspector/'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(_INSPECTOR_BYTES_RAW))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(_INSPECTOR_BYTES_RAW)
            return

        if path in ('/app', '/app/'):

            ae2 = self.headers.get('Accept-Encoding', '')
            body2 = _APP_BYTES if 'gzip' in ae2 else _APP_BYTES_RAW
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(body2))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'max-age=300')
            if 'gzip' in ae2: self.send_header('Content-Encoding', 'gzip')
            self.end_headers()
            self.wfile.write(body2)
            return

        if path == '/app/sw.js':
            body = APP_SW.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == '/app/manifest.json':
            body = APP_MANIFEST.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/manifest+json')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == '/app/icon-192.png':
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', len(APP_ICON_192))
            self.end_headers()
            self.wfile.write(APP_ICON_192)
            return

        if path == '/app/icon-512.png':
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', len(APP_ICON_512))
            self.end_headers()
            self.wfile.write(APP_ICON_512)
            return

        if path == '/inspector/manifest.json':
            body = INSPECTOR_MANIFEST.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/manifest+json')
            self.send_header('Content-Length', len(body))
            self.end_headers(); self.wfile.write(body); return

        if path == '/inspector/sw.js':
            body = INSPECTOR_SW.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.send_header('Content-Length', len(body))
            self.end_headers(); self.wfile.write(body); return

        if path in ('/inspector/icon-192.png', '/inspector/icon-512.png'):
            icon = APP_ICON_192 if '192' in path else APP_ICON_512
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', len(icon))
            self.end_headers(); self.wfile.write(icon); return


        # ── App Ciudadano ─────────────────────────────────────
        if path in ('/app', '/app/'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', len(_APP_BYTES))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'max-age=120')
            self.end_headers()
            self.wfile.write(_APP_BYTES)
            return

        if path == '/app/sw.js':
            body = APP_SW.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == '/app/manifest.json':
            body = APP_MANIFEST.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/manifest+json')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == '/app/icon-192.png':
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', len(APP_ICON_192))
            self.end_headers()
            self.wfile.write(APP_ICON_192)
            return

        if path == '/app/icon-512.png':
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', len(APP_ICON_512))
            self.end_headers()
            self.wfile.write(APP_ICON_512)
            return

        # ── Listar actas de un reporte ──────────────────────────────
        m = re.match(r'^/api/reports/(\d+)/actas$', path)
        if m:
            user = self.require_auth()
            if not user: return
            rid = int(m.group(1))
            db  = read_db()
            actas = [a for a in db.get('actas', []) if a['report_id'] == rid]
            self.ok({'actas': actas, 'total': len(actas)}, f'{len(actas)} acta(s).')
            return

        self.err('Ruta no encontrada.', 404)

    # ══════════════════════════════════════════════════════════
    #  POST
    # ══════════════════════════════════════════════════════════
    def do_POST(self):
        path = urlparse(self.path).path.rstrip('/')

        # ── CORS preflight ─────────────────────────────────────
        # ── Login ──────────────────────────────────────────────
        # ── Crear inspector ─────────────────────────────────────────────
        if path == '/api/inspectores':
            user = self.require_auth('admin')
            if not user: return
            body = self.parse_json_body()
            nombre = body.get('nombre','').strip()
            username = body.get('username','').strip().lower()
            password = body.get('password','').strip()
            telefono = body.get('telefono','').strip()
            brigada  = body.get('brigada','').strip()
            if not nombre:   self.err('El nombre es requerido.', 422); return
            if not username: self.err('El usuario es requerido.', 422); return
            if not password: self.err('La contrasena es requerida.', 422); return
            db = read_db()
            if any(u['username'] == username for u in db['users']):
                self.err('El usuario ya existe.', 409); return
            uid = (max((u.get('id',0) for u in db['users']), default=0)) + 1
            nuevo = {'id':uid,'username':username,'password':hash_pw(password),'nombre':nombre,'rol':'inspector','telefono':telefono,'brigada':brigada,'activo':True,'fecha_registro':now_iso()}
            db['users'].append(nuevo)
            write_db(db)
            safe = {k:v for k,v in nuevo.items() if k != 'password'}
            self.ok({'inspector': safe}, f'Inspector {nombre} registrado.', 201)
            return

        if path == '/api/auth/login':
            body = self.parse_json_body()
            username = body.get('username', '').strip().lower()
            password = body.get('password', '')
            if not username or not password:
                self.err('Usuario y contraseña son requeridos.', 400); return
            db   = read_db()
            user = next((u for u in db['users'] if u['username'] == username), None)
            if not user or user['password'] != hash_pw(password):
                print(f"[AUTH] ⚠️  Login fallido: {username}")
                self.err('Credenciales inválidas.', 401); return
            if not user.get('activo', True):
                self.err('Cuenta desactivada.', 403); return
            payload = {'id': user['id'], 'username': user['username'], 'nombre': user['nombre'], 'rol': user['rol']}
            token   = jwt_sign(payload)
            print(f"[AUTH] ✅ Login: {username} | rol: {user['rol']}")
            self.ok({'token': token, 'usuario': payload, 'expires_in': '8h'}, 'Sesión iniciada.')
            return

        # ── Create report ──────────────────────────────────────
        if path == '/api/reports':
            body    = self.parse_json_body()
            tipo    = body.get('tipo', '')
            desc    = body.get('descripcion', '').strip()
            colonia = body.get('colonia', '').strip()
            if tipo not in TIPOS_VALIDOS:   self.err('Tipo de reporte inválido.', 422); return
            if len(desc) < 10:              self.err('Descripción muy corta (min 10 chars).', 422); return
            if not colonia:                 self.err('Colonia es requerida.', 422); return

            db    = read_db()
            folio = generate_folio(db)
            now   = now_iso()
            rid   = (max((r['id'] for r in db['reports']), default=0)) + 1
            report = {
                'id': rid, 'folio': folio, 'tipo': tipo,
                'descripcion': desc, 'colonia': colonia,
                'lat': body.get('lat'), 'lon': body.get('lon'),
                'estado': 'reportado',
                'nombre_reportante': body.get('nombre_reportante'),
                'telefono': body.get('telefono'),
                'fecha_creacion': now, 'fecha_actualizacion': now,
            }
            db['reports'].append(report)

            # Firma ciudadano
            firma_reg = None
            firma_b64 = body.get('firma_base64')
            firmante  = body.get('nombre_firmante', '')
            if firma_b64 and firmante:
                try:
                    img_data = re.sub(r'^data:image/\w+;base64,', '', firma_b64)
                    fname    = f"{folio.replace('-','_')}_ciudadano_{int(datetime.now().timestamp())}.png"
                    fpath    = UPLOAD_SIG / fname
                    fpath.write_bytes(base64.b64decode(img_data))
                    sid = (max((s['id'] for s in db['signatures']), default=0)) + 1
                    firma_reg = {
                        'id': sid, 'report_id': rid,
                        'signature_path': f"uploads/signatures/{fname}",
                        'nombre_firmante': firmante, 'rol_firmante': 'ciudadano',
                        'fecha_firma': now
                    }
                    db['signatures'].append(firma_reg)
                    print(f"[FIRMA] ✅ Firma ciudadano guardada: {fname}")
                except Exception as e:
                    print(f"[FIRMA] ⚠️  Error guardando firma: {e}")

            write_db(db)
            print(f"[NUEVO REPORTE] Folio: {folio} | Tipo: {tipo} | Colonia: {colonia}")
            self.ok({'report': report, 'firma': firma_reg}, f'Reporte {folio} creado exitosamente.', 201)
            return

        # ── Assign report ──────────────────────────────────────
        m = re.match(r'^/api/reports/(\d+)/assign$', path)
        if m:
            user = self.require_auth('admin', 'operador')
            if not user: return
            rid  = int(m.group(1))
            body = self.parse_json_body()
            brigada  = body.get('brigada', '').strip()
            inspector= body.get('inspector', '').strip()
            notas    = body.get('notas', '').strip()
            if not brigada or not inspector:
                self.err('Brigada e inspector son requeridos.', 422); return
            db  = read_db()
            rep = next((r for r in db['reports'] if r['id'] == rid), None)
            if not rep:  self.err(f'Reporte {rid} no encontrado.', 404); return
            if rep['estado'] == 'cerrado': self.err('No se puede asignar un reporte cerrado.', 409); return
            now  = now_iso()
            aid  = (max((a['id'] for a in db['assignments']), default=0)) + 1
            asig = {'id': aid, 'report_id': rid, 'brigada': brigada, 'inspector': inspector, 'notas': notas, 'fecha_asignacion': now}
            db['assignments'].append(asig)
            rep['estado'] = 'asignado'
            rep['fecha_actualizacion'] = now
            write_db(db)
            print(f"[ASIGNACIÓN] Folio: {rep['folio']} → Brigada: {brigada} | Inspector: {inspector}")
            self.ok({'reporte': rep, 'asignacion': asig}, f"Reporte asignado a brigada '{brigada}'.")
            return

        # ── Add evidence ───────────────────────────────────────
        m = re.match(r'^/api/reports/(\d+)/evidence$', path)
        if m:
            user = self.require_auth('admin', 'operador', 'inspector')
            if not user: return
            rid = int(m.group(1))
            ct  = self.headers.get('Content-Type', '')

            if 'multipart/form-data' in ct:
                fields, files = self.parse_multipart()
                comentario  = fields.get('comentario', '')
                lat_captura = fields.get('lat_captura')
                lon_captura = fields.get('lon_captura')
                nuevo_estado= fields.get('nuevo_estado', '')
            else:
                body        = self.parse_json_body()
                fields      = body
                files       = []
                comentario  = body.get('comentario', '')
                lat_captura = body.get('lat_captura')
                lon_captura = body.get('lon_captura')
                nuevo_estado= body.get('nuevo_estado', '')

            db  = read_db()
            rep = next((r for r in db['reports'] if r['id'] == rid), None)
            if not rep:  self.err(f'Reporte {rid} no encontrado.', 404); return
            if rep['estado'] == 'cerrado': self.err('Reporte ya cerrado.', 409); return

            now = now_iso()
            inserted = []

            # Guardar archivos o crear evidencia mock
            targets = files if files else [{'filename': f'mock_{uuid.uuid4().hex[:6]}.jpg', 'data': b''}]
            for f in targets:
                fname = f"evidence_{rid}_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:4]}.jpg"
                fpath = UPLOAD_EV / fname
                if f['data']: fpath.write_bytes(f['data'])
                eid = (max((e['id'] for e in db['evidence']), default=0)) + 1
                ev  = {
                    'id': eid, 'report_id': rid,
                    'photo_url': f"uploads/evidence/{fname}",
                    'comentario': comentario or None,
                    'lat_captura': float(lat_captura) if lat_captura else None,
                    'lon_captura': float(lon_captura) if lon_captura else None,
                    'fecha': now
                }
                db['evidence'].append(ev)
                inserted.append(ev)

            if nuevo_estado in ('en_proceso', 'cerrado'):
                rep['estado'] = nuevo_estado
                rep['fecha_actualizacion'] = now
                print(f"[ESTADO] Folio: {rep['folio']} → {nuevo_estado.upper()}")

            write_db(db)
            print(f"[EVIDENCIA] {len(inserted)} foto(s) registradas para Folio: {rep['folio']}")
            self.ok({'evidencias': inserted, 'reporte': rep}, f"{len(inserted)} evidencia(s) registrada(s).", 201)
            return

        # ── Crear acta ──────────────────────────────────────────────
        m = re.match(r'^/api/reports/(\d+)/acta$', path)
        if m:
            user = self.require_auth('inspector', 'admin', 'operador')
            if not user: return
            rid  = int(m.group(1))
            ct   = self.headers.get('Content-Type', '')
            if 'multipart/form-data' in ct:
                fields, files = self.parse_multipart()
            else:
                fields = self.parse_json_body()
                files  = []
            db  = read_db()
            rep = next((r for r in db['reports'] if r['id'] == rid), None)
            if not rep: self.err(f'Reporte {rid} no encontrado.', 404); return
            now  = now_iso()
            aid  = (max((a['id'] for a in db['actas']), default=0)) + 1
            tipo_acta = (fields.get('tipo_acta', '') or 'circunstanciada').strip()
            # Guardar fotos del acta
            fotos = []
            for f in files:
                fname = f"acta_{rid}_{aid}_{int(__import__('datetime').datetime.now().timestamp())}_{uuid.uuid4().hex[:4]}.jpg"
                fpath = UPLOAD_EV / fname
                if f['data']: fpath.write_bytes(f['data'])
                fotos.append(f"uploads/evidence/{fname}")
            acta = {
                'id':             aid,
                'report_id':      rid,
                'tipo_acta':      tipo_acta,
                'folio_acta':     f"ACTA-{(tipo_acta[:3] if tipo_acta else 'GEN').upper()}-{now[:10].replace('-','')}-{aid:04d}",
                # Datos básicos
                'inspector':      fields.get('inspector', user.get('nombre', '')),
                'nombre_firmante_inspector': fields.get('nombre_firmante_inspector', ''),
                'infractor':      fields.get('infractor', ''),
                'domicilio':      fields.get('domicilio', rep.get('domicilio', rep.get('colonia', ''))),
                'descripcion':    fields.get('descripcion', ''),
                'fundamento':     fields.get('fundamento', ''),
                'medida':         fields.get('medida', ''),
                'monto_sancion':  fields.get('monto_sancion', ''),
                'observaciones':  fields.get('observaciones', ''),
                'lat_acta':       fields.get('lat_acta', ''),
                'lon_acta':       fields.get('lon_acta', ''),
                'fotos':          fotos,
                'estado':         'emitida',
                'fecha':          now,
                # Tipo de reporte (árbol, animal, ambiental)
                'tipo_reporte':   fields.get('tipo_reporte', ''),
                # Datos árbol
                'arb_especie':    fields.get('arb_especie', ''),
                'arb_dap':        fields.get('arb_dap', ''),
                'arb_altura':     fields.get('arb_altura', ''),
                'arb_vigor':      fields.get('arb_vigor', ''),
                'arb_estructura': fields.get('arb_estructura', ''),
                'arb_copa':       fields.get('arb_copa', ''),
                'fs_plagas':      fields.get('fs_plagas', ''),
                'fs_enfermedades':fields.get('fs_enfermedades', ''),
                'fs_infra':       fields.get('fs_infra', ''),
                'fs_raiz':        fields.get('fs_raiz', ''),
                'arb_metodo':     fields.get('arb_metodo', ''),
                'dictamen':       fields.get('dictamen', ''),
                'nivel_riesgo':   fields.get('nivel_riesgo', ''),
                'comp_categoria': fields.get('comp_categoria', ''),
                'comp_arboles':   fields.get('comp_arboles', ''),
                'comp_especie':   fields.get('comp_especie', ''),
                # Datos animal / mordida
                'vic_nombre':     fields.get('vic_nombre', ''),
                'vic_edad':       fields.get('vic_edad', ''),
                'vic_telefono':   fields.get('vic_telefono', ''),
                'vic_domicilio':  fields.get('vic_domicilio', ''),
                'vic_atencion':   fields.get('vic_atencion', ''),
                'vic_gravedad':   fields.get('vic_gravedad', ''),
                'mordida_zonas':  fields.get('mordida_zonas', ''),
                'mordida_gravedad': fields.get('mordida_gravedad', ''),
                'anim_especie':   fields.get('anim_especie', ''),
                'anim_raza':      fields.get('anim_raza', ''),
                'anim_cantidad':  fields.get('anim_cantidad', ''),
                'anim_condicion': fields.get('anim_condicion', ''),
                'anim_situacion': fields.get('anim_situacion', ''),
                'anim_duenio':    fields.get('anim_duenio', ''),
                'anim_destino':   fields.get('anim_destino', ''),
                'acciones_animal': fields.get('acciones_animal', ''),
                # Datos denuncia ambiental
                'da_tipo_infraccion': fields.get('da_tipo_infraccion', ''),
                'da_tiempo':          fields.get('da_tiempo', ''),
                'da_superficie':  fields.get('da_superficie', ''),
                'da_severidad':   fields.get('da_severidad', ''),
                'da_responsable': fields.get('da_responsable', ''),
                'da_plazo':       fields.get('da_plazo', ''),
                'medidas_denuncia': fields.get('medidas_denuncia', ''),
                # Firmas
                'firma_inspector_base64': fields.get('firma_inspector_base64', ''),
                'firma_visitado_base64':  fields.get('firma_visitado_base64', ''),
                # Campos adaptativos por tipo de acta
                'voz_imputado':       fields.get('voz_imputado', ''),
                'imputado_presente':  fields.get('imputado_presente', ''),
                'firmado_enterado':   fields.get('firmado_enterado', ''),
                'gravedad_infraccion':fields.get('gravedad_infraccion', ''),
                'reincidente':        fields.get('reincidente', ''),
                'tiene_permiso':      fields.get('tiene_permiso', ''),
                'num_permiso':        fields.get('num_permiso', ''),
                'permiso_autoridad':  fields.get('permiso_autoridad', ''),
                'nombre_visitado':        fields.get('nombre_visitado', ''),
            }
            if not db.get('actas'): db['actas'] = []
            db['actas'].append(acta)
            # Cambiar estado del reporte
            nuevo_estado = fields.get('nuevo_estado', '')
            if nuevo_estado in ('en_proceso', 'cerrado'):
                rep['estado'] = nuevo_estado
                rep['fecha_actualizacion'] = now
            write_db(db)
            print(f"[ACTA] {acta['folio_acta']} | Reporte: {rep['folio']} | Tipo: {tipo_acta}")
            self.ok({'acta': acta, 'reporte': rep}, f"Acta {acta['folio_acta']} generada.", 201)
            return

        self.err('Ruta no encontrada.', 404)

    def do_PATCH(self):
        path = urlparse(self.path).path.rstrip('/')
        # ── Editar inspector ──────────────────────────────────────────
        mi = re.match(r'^/api/inspectores/(\d+)$', path)
        if mi:
            user = self.require_auth('admin')
            if not user: return
            uid  = int(mi.group(1))
            body = self.parse_json_body()
            db   = read_db()
            insp = next((u for u in db['users'] if u.get('id') == uid), None)
            if not insp: self.err(f'Inspector {uid} no encontrado.', 404); return
            if 'nombre'   in body and body['nombre'].strip(): insp['nombre']   = body['nombre'].strip()
            if 'brigada'  in body: insp['brigada']  = body['brigada'].strip()
            if 'telefono' in body: insp['telefono'] = body['telefono'].strip()
            if 'activo'   in body: insp['activo']   = bool(body['activo'])
            if body.get('password'): insp['password'] = hash_pw(body['password'].strip())
            write_db(db)
            safe = {k:v for k,v in insp.items() if k != 'password'}
            self.ok({'inspector': safe}, 'Inspector actualizado.')
            return

        m = re.match(r'^/api/reports/(\d+)$', path)
        if m:
            # Admin/operador pueden editar todo; inspector solo puede cambiar estado de sus reportes
            user = self.require_auth('admin', 'operador', 'inspector')
            if not user: return
            rid  = int(m.group(1))
            body = self.parse_json_body()
            db   = read_db()
            rep  = next((r for r in db['reports'] if r['id'] == rid), None)
            if not rep:
                self.err(f'Reporte {rid} no encontrado.', 404); return
            if user.get('rol') == 'inspector':
                # Inspector solo puede cambiar el estado (no otros campos)
                campos_permitidos = ['estado']
            else:
                campos_permitidos = ['tipo','colonia','descripcion','estado','nombre_reportante','telefono','domicilio']
            for campo in campos_permitidos:
                if campo in body:
                    rep[campo] = body[campo]
            rep['fecha_actualizacion'] = now_iso()
            write_db(db)
            print(f"[EDICION] Folio: {rep['folio']} → estado={rep.get('estado','')} por {user['username']}")
            self.ok(rep, f"Reporte {rep['folio']} actualizado.")
            return
        self.err('Ruta no encontrada.', 404)

    def do_DELETE(self):
        path = urlparse(self.path).path.rstrip('/')
        # ── Eliminar inspector ──────────────────────────────────────────
        di = re.match(r'^/api/inspectores/(\d+)$', path)
        if di:
            user = self.require_auth('admin')
            if not user: return
            uid  = int(di.group(1))
            db   = read_db()
            insp = next((u for u in db['users'] if u.get('id') == uid), None)
            if not insp: self.err(f'Inspector {uid} no encontrado.', 404); return
            if insp.get('rol') != 'inspector': self.err('Solo se pueden eliminar inspectores.', 403); return
            db['users'] = [u for u in db['users'] if u.get('id') != uid]
            write_db(db)
            print(f'[USER] Inspector eliminado: {insp["username"]}')
            self.ok({}, f'Inspector {insp["nombre"]} eliminado.')
            return

        m = re.match(r'^/api/reports/(\d+)$', path)
        if m:
            user = self.require_auth('admin')
            if not user: return
            rid = int(m.group(1))
            db  = read_db()
            rep = next((r for r in db['reports'] if r['id'] == rid), None)
            if not rep:
                self.err(f'Reporte {rid} no encontrado.', 404); return
            folio = rep['folio']
            db['reports']     = [r for r in db['reports']     if r['id'] != rid]
            db['assignments'] = [a for a in db['assignments'] if a['report_id'] != rid]
            db['evidence']    = [e for e in db['evidence']    if e['report_id'] != rid]
            db['signatures']  = [s for s in db['signatures']  if s['report_id'] != rid]
            write_db(db)
            print(f"[ELIMINADO] Folio: {folio} por {user['username']}")
            self.ok(None, f'Reporte {folio} eliminado.')
            return
        # ── Eliminar acta ──────────────────────────────────────────────
        ma = re.match(r'^/api/actas/(\d+)$', path)
        if ma:
            user = self.require_auth('admin', 'operador', 'inspector')
            if not user: return
            aid = int(ma.group(1))
            db  = read_db()
            before = len(db.get('actas', []))
            db['actas'] = [a for a in db.get('actas', []) if a['id'] != aid]
            if len(db['actas']) == before:
                self.err(f'Acta {aid} no encontrada.', 404); return
            write_db(db)
            print(f"[ACTA_DEL] id={aid} eliminada por {user['username']}")
            self.ok({}, 'Acta eliminada.')
            return

        self.err('Ruta no encontrada.', 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()


# ── Arranque ────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('╔══════════════════════════════════════════════════════╗')
    print('║       SGO-IMBIO – Sistema de Gestión Operativa       ║')
    print('║  Instituto Municipal de Biodiversidad y Protección   ║')
    print('║     Pabellón de Arteaga, Aguascalientes               ║')
    print('╠══════════════════════════════════════════════════════╣')
    print(f'║  🚀 SGO-IMBIO:    http://localhost:{PORT}                   ║')
    print(f'║  📱 App Ciudadano:  http://localhost:{PORT}/app           ║')
    print(f'║  👷 App Inspector:  http://localhost:{PORT}/inspector     ║')
    print('║                                                      ║')
    print('║  CREDENCIALES:                                       ║')
    print('║    admin      / admin123     (Administrador)         ║')
    print('║    operador   / operador123  (Operador)              ║')
    print('║    inspector01/ inspector123 (Inspector)             ║')
    print('╚══════════════════════════════════════════════════════╝')
    class QuietHandler(IMBIOHandler):
        def log_message(self, fmt, *args):
            print(f'[HTTP] {self.address_string()} {fmt % args}')
        def handle_error(self, request, client_address):
            import sys
            exc = sys.exc_info()[1]
            if isinstance(exc, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
                return
            super().handle_error(request, client_address)

    from http.server import ThreadingHTTPServer
    _init_sqlite()
    server = ThreadingHTTPServer(('0.0.0.0', PORT), QuietHandler)
    server.socket.setsockopt(__import__('socket').SOL_SOCKET, __import__('socket').SO_REUSEADDR, 1)
    server.serve_forever()

