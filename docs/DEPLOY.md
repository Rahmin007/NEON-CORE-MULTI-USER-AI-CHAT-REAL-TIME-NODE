# Deploying NEON//CORE (free tiers)

MongoDB Atlas (database) → Render (FastAPI backend) → Vercel (React frontend).

## 1. MongoDB Atlas

1. Sign up at **mongodb.com/atlas** and create a **free M0** cluster. Pick the region closest to your Render region, e.g. Singapore.
2. Go to **Database Access → Add New Database User**. Choose username + password, with the role "Read and write to any database". Save the password somewhere.
3. Go to **Network Access → Add IP Address → Allow access from anywhere** (`0.0.0.0/0`). Render's free tier has no fixed IP, so this is required. Your database is still protected by the username and password.
4. Go to **Database → Connect → Drivers** and copy the connection string:
   `mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`
   Replace `<password>` with the real password. If the password contains `@ : / ? #`, URL-encode it, or pick a password without those characters.

## 2. Backend on Render

1. Push this repository to GitHub.
2. On **render.com**, sign in with GitHub, then choose **New → Blueprint** and select the repository. Render reads `render.yaml`.
3. Fill in the secret values:
   - `MONGODB_URI`: the Atlas string from step 1
   - `FRONTEND_ORIGINS`: use `https://example.com` for now; you'll change it in step 4
   - `OPENROUTER_API_KEY`: from openrouter.ai/keys. It can be left empty; the AI then explains that it isn't configured.
   - `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`: your admin login, created on first start
4. Click **Apply**. When the deploy is live, open `https://<your-service>.onrender.com/health`. It should show `{"status":"ok","database":"connected"}`.

## 3. Frontend on Vercel

1. On **vercel.com**, go to **Add New → Project** and import the same repository.
2. Set **Root Directory** to `frontend`. The framework preset **Vite** is detected automatically.
3. Under **Environment Variables**, add `VITE_API_URL` = `https://<your-service>.onrender.com`, with no trailing slash.
4. Click **Deploy** and copy the production domain, e.g. `https://neon-core.vercel.app`.

## 4. Connect them

On Render, go to **your service → Environment**. Set `FRONTEND_ORIGINS` to your exact Vercel domain, for example `https://neon-core.vercel.app`. Use no trailing slash, and separate several domains with commas. Save; Render redeploys automatically.

## 5. Test

Open the Vercel site. Log in as your admin, then open a second browser and register a normal user.

- Messages should appear instantly in both windows.
- `@ai hello` should get an AI reply.
- Muting the user from the console should disable their input straight away.

The free Render service sleeps after 15 minutes without traffic. The first visit afterwards takes about 50 seconds while it wakes up, and the page shows "Reconnecting" until then.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| "Cannot reach the server" on login | `VITE_API_URL` is wrong or the backend is asleep. Open `/health` on Render first, then redeploy Vercel after changing the variable. |
| Browser console shows a CORS error | `FRONTEND_ORIGINS` doesn't exactly match the Vercel URL (check `https://` and remove any trailing `/`). |
| `/health` shows `"database":"unreachable"` | Check the Atlas password in `MONGODB_URI` and that Network Access allows `0.0.0.0/0`. |
| Deploy fails with "SECRET_KEY must be…" | The blueprint generates this automatically. If you created the service by hand, add a 32+ character random `SECRET_KEY`. |
| Everyone gets logged out after each deploy | `SECRET_KEY` changed; keep it fixed in Render's environment. |
