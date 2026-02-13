# Cheapest Deployment (Free-Tier Friendly)

This setup uses:
- Frontend: Cloudflare Pages
- Backend: Render Web Service (Free)
- Database: Neon Postgres (Free)

## 1. Create Neon Postgres

1. Create a Neon project and database.
2. Copy the connection string.
3. Make sure SSL is enabled in the URL (for Neon use `sslmode=require`).

Example:
`postgresql://user:password@ep-xxxx.us-east-2.aws.neon.tech/dbname?sslmode=require`

## 2. Deploy Backend to Render

This repo includes `render.yaml`, so Render can detect service settings.

1. In Render, create from repo (Blueprint).
2. Select this repository and deploy.
3. Set environment variables for the backend service:
   - `DATABASE_URL` = Neon connection string
   - `ALLOWED_ORIGINS` = `https://<your-pages-domain>.pages.dev,https://<your-custom-domain>`
   - `FIREBASE_PROJECT_ID`
   - `FIREBASE_PRIVATE_KEY_ID`
   - `FIREBASE_PRIVATE_KEY`
   - `FIREBASE_CLIENT_EMAIL`
   - `FIREBASE_CLIENT_ID`
4. Redeploy after saving env vars.
5. Confirm health:
   - `https://<render-backend-domain>/health`
   - `https://<render-backend-domain>/docs`

Notes:
- Render free web services can spin down when idle.
- WebSocket support is enabled by default; this app uses Socket.IO over the same backend URL.

## 3. Deploy Frontend to Cloudflare Pages

1. In Cloudflare Pages, connect this Git repository.
2. Set build settings:
   - Framework preset: `Vite`
   - Build command: `npm run build`
   - Build output directory: `dist`
   - Root directory: `frontend`
3. Set Pages environment variables:
   - `VITE_API_URL` = `https://<render-backend-domain>`
   - `VITE_SOCKET_URL` = `https://<render-backend-domain>`
   - `VITE_FIREBASE_API_KEY`
   - `VITE_FIREBASE_AUTH_DOMAIN`
   - `VITE_FIREBASE_PROJECT_ID`
   - `VITE_FIREBASE_STORAGE_BUCKET`
   - `VITE_FIREBASE_MESSAGING_SENDER_ID`
   - `VITE_FIREBASE_APP_ID`
   - Optional:
     - `VITE_YJS_SEND_DEBOUNCE_MS` (default `1000`)
     - `VITE_YJS_SEND_MAX_INTERVAL_MS` (default `5000`)
4. Deploy.

This repo includes `frontend/public/_redirects` so SPA routes work on refresh.

## 4. Firebase Console Checks

Add your frontend domain(s) in Firebase:
- Authentication > Settings > Authorized domains
- Include:
  - `<your-pages-domain>.pages.dev`
  - your custom domain (if used)

## 5. Final Verification

1. Open frontend URL.
2. Log in with Firebase auth.
3. Create/open a note.
4. Confirm:
   - realtime collaboration works
   - version history loads
   - restore action writes version entries with user name

## 6. If CORS Fails

Update backend `ALLOWED_ORIGINS` to exactly match frontend origins, comma-separated, no trailing slash mismatch:

Example:
`https://my-notes.pages.dev,https://notes.example.com`
