# BusIQ Deployment Guide

## Vercel Deployment

### Quick Setup

1. **Connect GitHub Repository to Vercel**
   - Go to [vercel.com](https://vercel.com)
   - Sign in with GitHub
   - Click "Add New Project"
   - Select the `lkshi0406/silk-road-bus-allocation` repository
   - Click "Import"

2. **Configure Vercel Project**
   - **Framework Preset:** Vite
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`

3. **Environment Variables** (optional)
   - `VITE_API_URL`: Backend API endpoint (if using external backend)

4. **Deploy**
   - Click "Deploy"
   - Your app will be live at: `https://your-project.vercel.app`

### Manual Deployment via CLI

```bash
# Install Vercel CLI (if not already installed)
npm install -g vercel

# Login to Vercel
vercel login

# Navigate to frontend directory
cd frontend

# Deploy to production
vercel --prod

# Deploy to preview
vercel
```

### Automated Deployment with GitHub Actions

The repository includes a GitHub Actions workflow (`.github/workflows/deploy.yml`) that automatically deploys to Vercel on every push to the `main` branch.

**Setup Required:**

1. Create Vercel project
2. Get your Vercel tokens:
   - Go to [Vercel Dashboard Settings](https://vercel.com/account/tokens)
   - Create a new token
   - Copy `VERCEL_TOKEN`

3. Add GitHub Secrets:
   - Go to your GitHub repo
   - Settings → Secrets and variables → Actions
   - Add three secrets:
     - `VERCEL_TOKEN`: Your Vercel API token
     - `VERCEL_ORG_ID`: Your Vercel org/account ID (from project settings)
     - `VERCEL_PROJECT_ID`: Your Vercel project ID (from project settings)

4. Push to main branch - deployment happens automatically!

### Current Deployment Status

- **Repository:** https://github.com/lkshi0406/silk-road-bus-allocation
- **Latest Commits:**
  - `25cad48` - Improve UI spacing and typography for better readability
  - `7362c3e` - Add dispatch recommendation engine with scoring and modals
  - `ae930c8` - Add React control-room frontend with Vite
  - `7e7f6b2` - Initial MVP with Streamlit and forecasting

### Post-Deployment

- Monitor builds: https://vercel.com/dashboard
- View logs: Click project → "Deployments" tab
- Rollback if needed: Click deployment → "Promote to Production"

### Troubleshooting

**Build fails?**
- Check that `frontend/package.json` exists
- Verify all dependencies are listed: `npm run build` works locally
- Check Environment Variables are correct

**Front-end not updating?**
- Clear Vercel cache: Project Settings → "Git" section → Clear Build Cache
- Redeploy: Click "Redeploy" button

**API issues?**
- Set `VITE_API_URL` environment variable if using backend API
- Ensure CORS is properly configured on backend

## Local Development

```bash
# Install dependencies
cd frontend
npm install

# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Next Steps

1. Connect repository to Vercel
2. Configure environment variables (if needed)
3. Add GitHub secrets for CI/CD
4. Push changes - automated deployment will trigger
5. Monitor your live dashboard at your Vercel deployment URL
