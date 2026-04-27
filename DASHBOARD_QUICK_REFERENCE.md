# Quick Dashboard Reference Guide

## Current Dashboard (Running Now)
**Location**: `frontend/src/App.jsx`
**Current Code**: 8 lines (minimal version)
**Running on**: http://localhost:5173

## Access the Code
```bash
# View current dashboard code
cat frontend/src/App.jsx

# Edit dashboard
code frontend/src/App.jsx
```

## Restore Previous Versions

### Restore Full BusIQ Control Room (1,442 lines with maps, charts, fleet tracking)
```bash
git checkout 7362c3e -- frontend/src/App.jsx
npm install
npm run dev
```

### Restore Original BusIQ (774 lines)
```bash
git checkout ae930c8 -- frontend/src/App.jsx
npm install
npm run dev
```

## Healthcare Dashboard (NOT IN THIS PROJECT)
The healthcare screenshot you saw is from a completely different application - it does not exist in this repository's git history.

## To Modify Current Dashboard
1. Edit `frontend/src/App.jsx`
2. Save file
3. Vite dev server will auto-reload
4. Check http://localhost:5173

## To Create New Dashboard
Replace contents of `frontend/src/App.jsx` with your own React component code.
