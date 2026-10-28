# TraceLink frontend

React 18 + TypeScript + Vite. No UI library and no map-tile service: the chart is plain SVG drawn from your own data.

## Run (two terminals)

```bash
# 1. backend (from ../backend, with DEMO_MODE=true in .env)
uvicorn app.main:app --reload

# 2. frontend
cd frontend
npm install
npm run dev          # http://localhost:5173
```

The browser calls `/api/...` on the Vite server, which forwards to `http://localhost:8000` (override with `BACKEND_URL`). Same origin, so the backend needs no CORS settings. For a production build, serve `dist/` behind a reverse proxy that does the same forwarding.

## Screens

- **Sign in / create account**
- **Your phones**: add a phone (IMEI check digit verified in the browser first), prove ownership (the demo code is shown and labelled "Demo"), report as lost, open or review cases.
- **Case**: progress, sightings chart, sighting list, "Add demo sightings" (four scenarios), "What the evidence supports" (fixed-rule counts beside the AI explanation).

## Design decisions

- **Chart, not map tiles.** Tiles would send the coordinates of a lost phone to a third party and fail offline during a demo. The chart is a local flat projection with error rings, a scale bar and a north arrow. It is not a street map.
- **Zoom to passed sightings** by default, so one impossible outlier does not squash the real cluster. Outliers sit at the edge, labelled with their distance. Overlapping markers are spread apart slightly.
- **Citations are interactive.** Hover or focus a number under an AI statement and that sighting lights up on the chart and in the list.
- **Never colour alone.** Passed = circle, flagged = diamond. Keyboard focus, screen-reader labels and reduced motion are supported.
- **Honesty labels.** A yellow "Demo data" band appears whenever sightings are simulated; the explanation panel says whether the text came from AI or the standard summary, and why.
- The access token is kept in `sessionStorage` (cleared when the tab closes). A real product would use an HttpOnly cookie.
