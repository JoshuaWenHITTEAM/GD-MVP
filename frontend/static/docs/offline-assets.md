# Offline Frontend Assets

The frontend templates now load external libraries from local static paths:

- `/static/vendor/tailwind/tailwindcss.js`
- `/static/vendor/iconify/iconify.min.js`
- `/static/vendor/echarts/echarts.min.js`
- `/static/fonts/local-fonts.css`
- `/static/images/admin-avatar.svg`
- `/static/images/offline-thermal.svg`

Downloaded local bundles:

- Tailwind CDN runtime: `frontend/static/vendor/tailwind/tailwindcss.js`
- Iconify browser runtime: `frontend/static/vendor/iconify/iconify.min.js`
- Iconify local collections: `frontend/static/vendor/iconify/material-symbols.json`, `frontend/static/vendor/iconify/mdi.json`
- ECharts 5.4.3 browser bundle: `frontend/static/vendor/echarts/echarts.min.js`
- Inter, Noto Sans SC, and Orbitron font files under `frontend/static/fonts/`

`frontend/static/vendor/tailwind/tailwind.css` is kept as a small fallback file, but the templates use `tailwindcss.js` to preserve the old CDN behavior offline.

After replacing these files, run:

```bash
rg -n "https?://|cdn\.tailwindcss|fonts\.googleapis|images\.unsplash|modao\.cc" frontend
```

Only API URLs that intentionally point to local services should remain.
