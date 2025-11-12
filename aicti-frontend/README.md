## AI-CTI Frontend

This directory hosts the Next.js + Tailwind UI for the AI-CTI newsroom dashboard.

### Local development

```bash
pnpm install   # or npm install / yarn install
cp docs.env.local.example .env.local
pnpm dev       # or npm run dev
```

Visit [http://localhost:3000/dashboard](http://localhost:3000/dashboard).

### Environment variables

| Variable | Description |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | Base URL for the FastAPI backend (e.g. `http://127.0.0.1:8000`). |

### Build

```bash
pnpm build && pnpm start
```

### Deployment

Deploy to Vercel:
1. Import the repository, set the root directory to `aicti-frontend`.
2. Add `NEXT_PUBLIC_API_URL=https://your-backend-url`.
3. Trigger build.

See the root [`README_DEPLOY.md`](../README_DEPLOY.md) for full-stack deployment guidance.
