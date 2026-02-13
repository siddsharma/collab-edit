# AWS One-Go Deploy (Amplify + App Runner + RDS/Neon)

If you want AWS for app hosting in one flow:
- Frontend: AWS Amplify Hosting
- Backend: AWS App Runner (source deploy from this repo via `apprunner.yaml`)
- Database: either
  - AWS RDS PostgreSQL (fully AWS), or
  - Neon Postgres (cheaper, still works)

This repo already includes:
- `apprunner.yaml` for backend App Runner source deployment
- `amplify.yml` for frontend build in monorepo (`frontend/`)

## 0. Before You Start

Push your latest branch to GitHub first.

## 1. Create Database

Option A (AWS-native): RDS PostgreSQL
1. Create PostgreSQL instance.
2. Allow inbound from App Runner VPC connector/security group.
3. Copy connection URL:
`postgresql://<user>:<pass>@<host>:5432/<db>`

Option B (lower cost): Neon
1. Create Neon DB.
2. Use URL with `sslmode=require`.

## 2. Deploy Backend (App Runner)

1. App Runner -> Create service -> Source code repository.
2. Connect GitHub and pick this repo/branch.
3. Choose configuration source: **Use configuration file**.
4. App Runner reads `apprunner.yaml` automatically.
5. Add runtime environment variables:
   - `DATABASE_URL`
   - `ALLOWED_ORIGINS` (set later after Amplify URL is known, or temporary `*` for first deploy)
   - `FIREBASE_PROJECT_ID`
   - `FIREBASE_PRIVATE_KEY_ID`
   - `FIREBASE_PRIVATE_KEY`
   - `FIREBASE_CLIENT_EMAIL`
   - `FIREBASE_CLIENT_ID`
6. Deploy and copy backend URL:
`https://<service>.<region>.awsapprunner.com`

Verify:
- `https://<backend-url>/health`
- `https://<backend-url>/docs`

## 3. Deploy Frontend (Amplify)

1. Amplify -> New app -> Host web app -> GitHub.
2. Select this repo/branch.
3. Amplify auto-detects `amplify.yml`.
4. Set environment variables:
   - `VITE_API_URL=https://<backend-url>`
   - `VITE_SOCKET_URL=https://<backend-url>`
   - `VITE_FIREBASE_API_KEY`
   - `VITE_FIREBASE_AUTH_DOMAIN`
   - `VITE_FIREBASE_PROJECT_ID`
   - `VITE_FIREBASE_STORAGE_BUCKET`
   - `VITE_FIREBASE_MESSAGING_SENDER_ID`
   - `VITE_FIREBASE_APP_ID`
   - Optional:
     - `VITE_YJS_SEND_DEBOUNCE_MS` (default `1000`)
     - `VITE_YJS_SEND_MAX_INTERVAL_MS` (default `5000`)
5. Deploy and copy Amplify URL.

## 4. Final Cross-Wiring

1. Update backend `ALLOWED_ORIGINS` in App Runner:
   - `https://<amplify-domain>`
   - plus custom domain if any
2. Redeploy backend.
3. In Firebase Console -> Auth -> Authorized domains:
   - add Amplify domain + custom domain

## 5. Quick Validation

1. Open Amplify URL.
2. Sign in.
3. Edit note and verify collaboration.
4. Open version history and restore.

## Optional: AWS CLI Fast Path

You can also do this mostly via CLI:
1. `aws apprunner create-service --source-configuration ...`
2. `aws amplify create-app ...`
3. `aws amplify create-branch ...`
4. `aws amplify start-job ...`

Console is usually faster on first setup because OAuth + env secret entry are interactive.
