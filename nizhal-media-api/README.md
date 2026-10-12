# Nizhal Community — Media API Backend

Production-ready serverless REST API backend for the **Nizhal Community** scrapbook page (*our little scrapbook ♡*). Built with **Next.js App Router**, **TypeScript**, **Supabase PostgreSQL**, and deployed on **Vercel**.

This backend operates independently as its own Vercel deployment, completely decoupled from the frontend web application.

---

## 🌟 Architecture Overview

```mermaid
flowchart LR
    subgraph Frontend ["Nizhal Web App (Vercel)"]
        F["/media & /events\n(our little scrapbook ♡)"]
    end

    subgraph Backend ["Media API Backend (Vercel)"]
        G["GET /api/media\n(Public Read-Only)"]
        P["POST /api/media\n(Admin Bearer Token)"]
        O["OPTIONS /api/media\n(CORS Preflight)"]
    end

    subgraph Database ["Supabase PostgreSQL"]
        DB[("public.media\nRLS Protected")]
    end

    F -->|HTTPS GET\nOrigin: FRONTEND_ORIGIN| G
    G -->|Service Role / RLS| DB
    Admin["Authorized Admin / Scripts"] -->|HTTPS POST + Bearer ADMIN_API_KEY| P
    P -->|Service Role INSERT| DB
    F -->|Preflight OPTIONS| O
```

---

## 📁 Repository Structure

```text
nizhal-media-api/
├── .env.example                               # Sample environment variables
├── .gitignore                                 # Git ignore patterns
├── README.md                                  # Setup & deployment documentation
├── next.config.mjs                            # Next.js configuration
├── package.json                               # Dependencies & scripts
├── tsconfig.json                              # TypeScript configuration
├── scripts/
│   └── test-api.mjs                           # Automated end-to-end API test suite
├── supabase/
│   └── migrations/
│       └── 20261012_create_media_table.sql    # Supabase PostgreSQL schema, index & RLS policies
└── src/
    ├── app/
    │   ├── api/
    │   │   ├── media/
    │   │   │   └── route.ts                   # GET, POST, OPTIONS /api/media handler
    │   │   └── health/
    │   │       └── route.ts                   # Health check endpoint
    │   ├── globals.css                        # Documentation styles
    │   ├── layout.tsx                         # Root layout
    │   └── page.tsx                           # Interactive API documentation page
    └── lib/
        ├── cors.ts                            # Origin validation & CORS headers
        ├── supabase.ts                        # Server-side Supabase client singleton
        ├── types.ts                           # Data contracts & TypeScript types
        └── validators.ts                      # Zod validation schema & Google Drive helper
```

---

## 🛠️ Supabase Database Setup

1. Open your [Supabase Dashboard](https://supabase.com/dashboard) and navigate to your project.
2. Go to the **SQL Editor** from the left navigation.
3. Open or copy the contents of [`supabase/migrations/20261012_create_media_table.sql`](./supabase/migrations/20261012_create_media_table.sql).
4. Click **Run**.

### Schema Summary:
| Column | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `id` | `UUID` | `gen_random_uuid()` | `PRIMARY KEY` | Unique record ID |
| `title` | `TEXT` | None | `NOT NULL` | Media/memory headline |
| `description` | `TEXT` | `''` | `NOT NULL` | Handwritten note / details |
| `url` | `TEXT` | None | `NOT NULL` | HTTPS asset or Google Drive URL |
| `category` | `TEXT` | `'gathering'` | `NOT NULL` | Category group |
| `media_type` | `TEXT` | None | `CHECK (image, video, link)` | Type of asset |
| `sort_order` | `INTEGER` | `0` | `NOT NULL` | Scrapbook display priority |
| `is_published` | `BOOLEAN` | `true` | `NOT NULL` | Publish visibility status |
| `created_at` | `TIMESTAMPTZ` | `timezone('utc', now())` | `NOT NULL` | Timestamp |

- **Partial Composite Index**: `idx_media_published_sort_created` on `(sort_order ASC, created_at DESC) WHERE is_published = true` ensures sub-millisecond retrieval.
- **Row Level Security (RLS)**: Public `anon` / `authenticated` roles can **only** read records where `is_published = true`. Direct public write operations are denied.

---

## 🔑 Environment Variables Configuration

Copy `.env.example` to `.env.local`:
```bash
cp .env.example .env.local
```

Fill in the required values:

```env
# 1. Supabase Project URL (Supabase Dashboard -> Settings -> API -> Project URL)
SUPABASE_URL="https://your-project-id.supabase.co"

# 2. Supabase Service Role Secret Key (Supabase Dashboard -> Settings -> API -> service_role secret)
# CAUTION: Server-side only. NEVER expose to the browser!
SUPABASE_SERVICE_ROLE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# 3. Deployed Frontend Origin (allowed origin for CORS requests)
# Multiple origins can be comma-separated: "https://nizhalcommunity.in,http://localhost:5173"
FRONTEND_ORIGIN="https://nizhalcommunity.in"

# 4. Secret Admin API Key (used as Bearer token for POST /api/media)
# Generate a secure key: openssl rand -hex 32
ADMIN_API_KEY="your-random-32-char-secret-admin-key"
```

---

## 🚀 Local Development & Testing

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Start development server** (runs on port 3001 to avoid colliding with frontend ports):
   ```bash
   npm run dev
   ```

3. **Open browser documentation**:
   Navigate to [http://localhost:3001](http://localhost:3001) to view the API dashboard and status.

4. **Run automated API test suite**:
   ```bash
   npm run test:api
   ```

---

## 📡 API Reference & Example Requests

### 1. GET `/api/media` (Public Scrapbook Retrieval)
Retrieves all published scrapbook media records, ordered by `sort_order ASC, created_at DESC`.

#### Example Request:
```bash
curl -X GET "http://localhost:3001/api/media" \
  -H "Origin: https://nizhalcommunity.in"
```

#### Example 200 OK Response:
```json
{
  "media": [
    {
      "id": "e2f7b8c0-3940-4f51-b883-938b8c2df1a4",
      "title": "Human. Stories. Connection.",
      "description": "listening deeply, no rush, just warmth ♡",
      "url": "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=1200&q=80",
      "category": "gathering",
      "media_type": "image",
      "sort_order": 1,
      "created_at": "2026-10-12T06:30:00Z"
    }
  ]
}
```

---

### 2. POST `/api/media` (Admin Add Media)
Adds a new media record. Requires Bearer authentication.

#### Example Request (HTTPS Image):
```bash
curl -X POST "http://localhost:3001/api/media" \
  -H "Authorization: Bearer your-random-32-char-secret-admin-key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Campfire Reflections",
    "description": "Acoustic notes under the stars ✨",
    "url": "https://images.unsplash.com/photo-1511632765486-a01980e01a18?auto=format&fit=crop&w=1200&q=80",
    "category": "gathering",
    "media_type": "image",
    "sort_order": 2,
    "is_published": true
  }'
```

#### Example Request (Google Drive Link):
```bash
curl -X POST "http://localhost:3001/api/media" \
  -H "Authorization: Bearer your-random-32-char-secret-admin-key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Beach Cleanup Montage",
    "description": "Memories from Sunday morning gathering ♡",
    "url": "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OGvE2upms/view?usp=sharing",
    "category": "beach",
    "media_type": "image",
    "sort_order": 3,
    "is_published": true
  }'
```

#### Example 201 Created Response:
```json
{
  "media": {
    "id": "7d9b7346-60c7-43c2-a8c7-402a70bf1c94",
    "title": "Beach Cleanup Montage",
    "description": "Memories from Sunday morning gathering ♡",
    "url": "https://drive.google.com/file/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OGvE2upms/view?usp=sharing",
    "category": "beach",
    "media_type": "image",
    "sort_order": 3,
    "is_published": true,
    "created_at": "2026-10-12T07:15:22.184Z"
  },
  "message": "Media record created successfully"
}
```

#### Error Responses:
- **401 Unauthorized**: Missing or incorrect `ADMIN_API_KEY`.
  ```json
  { "error": "Unauthorized: Missing or invalid Admin Bearer token" }
  ```
- **400 Bad Request**: Input validation failure.
  ```json
  {
    "error": "Validation failed: Check provided fields",
    "details": [
      { "field": "url", "message": "URL must be a valid HTTPS URL (e.g., https://... or Google Drive share link)" },
      { "field": "media_type", "message": "media_type must be either 'image', 'video', or 'link'" }
    ]
  }
  ```

---

### 3. OPTIONS `/api/media` (CORS Preflight)
```bash
curl -I -X OPTIONS "http://localhost:3001/api/media" \
  -H "Origin: https://nizhalcommunity.in" \
  -H "Access-Control-Request-Method: POST"
```

Response headers returned:
- `Access-Control-Allow-Origin: https://nizhalcommunity.in`
- `Access-Control-Allow-Methods: GET, POST, OPTIONS`
- `Access-Control-Allow-Headers: Content-Type, Authorization`

---

## 🚢 Vercel Deployment Guide

Deploy this backend as an independent project on Vercel:

1. **Push repository to GitHub**:
   - Push this `nizhal-media-api` project to your GitHub repository (e.g., `dinesh20073/nizhal-media-api`).
2. **Import into Vercel**:
   - Log into [Vercel](https://vercel.com).
   - Click **Add New...** -> **Project**.
   - Select your repository (`nizhal-media-api`).
   - Framework Preset: **Next.js** (detected automatically).
3. **Configure Environment Variables in Vercel**:
   In the project settings, add:
   - `SUPABASE_URL` = `https://your-project-id.supabase.co`
   - `SUPABASE_SERVICE_ROLE_KEY` = `your_supabase_service_role_secret`
   - `FRONTEND_ORIGIN` = `https://nizhalcommunity.in`
   - `ADMIN_API_KEY` = `your_strong_admin_key`
4. **Deploy**:
   Click **Deploy**.
5. **Obtain your live API URL**:
   Your public API endpoint will be:
   ```text
   https://YOUR-BACKEND-VERCEL-DOMAIN.vercel.app/api/media
   ```

---

## 🔗 Connecting with the Frontend

In the Nizhal Community frontend repository (`Nizhal`), configure the environment variable:

1. In `.env.production` (or Vercel project environment variables for the frontend):
   ```env
   NEXT_PUBLIC_MEDIA_API_URL="https://YOUR-BACKEND-VERCEL-DOMAIN.vercel.app/api/media"
   ```

2. Fetching in the frontend component (`our little scrapbook ♡`):
   ```typescript
   export interface ScrapbookMedia {
     id: string;
     title: string;
     description: string;
     url: string;
     category: string;
     media_type: 'image' | 'video' | 'link';
     sort_order: number;
     created_at: string;
   }

   export async function fetchScrapbookMedia(): Promise<ScrapbookMedia[]> {
     const apiUrl = import.meta.env.VITE_MEDIA_API_URL || process.env.NEXT_PUBLIC_MEDIA_API_URL;
     const res = await fetch(apiUrl, {
       headers: { 'Accept': 'application/json' },
     });
     if (!res.ok) throw new Error('Failed to load scrapbook media');
     const data = await res.json();
     return data.media;
   }
   ```

---

## 🔧 Troubleshooting Guide

### 1. CORS Errors (`Blocked by CORS policy`)
- **Symptom**: Browser console logs `Access to fetch at '...' from origin 'https://...' has been blocked by CORS policy`.
- **Fix**:
  1. Check the `FRONTEND_ORIGIN` variable in Vercel settings of the backend.
  2. Ensure it exactly matches your frontend domain (e.g., `https://nizhalcommunity.in` without trailing slash).
  3. If testing locally, set `FRONTEND_ORIGIN="https://nizhalcommunity.in,http://localhost:5173"`.
  4. Redeploy the backend after updating environment variables.

### 2. Database Errors (HTTP 500)
- **Symptom**: GET or POST returns `{"error": "Failed to retrieve media records from database"}`.
- **Fix**:
  1. Ensure `20261012_create_media_table.sql` was executed in the Supabase SQL Editor.
  2. Verify `SUPABASE_URL` begins with `https://` and does not have extra whitespace.
  3. Confirm `SUPABASE_SERVICE_ROLE_KEY` is the `service_role` key (not the public `anon` key), as it needs administrative permission to bypass restrictive write RLS policies.
  4. Check the Vercel Runtime Logs for server-side error descriptions.

### 3. Google Drive Links Not Displaying
- **Symptom**: The URL is stored correctly, but images or videos fail to load in the browser.
- **Fix**:
  1. In Google Drive, click **Share** -> Change General Access to **"Anyone with the link"** (Viewer).
  2. If using standard share links (`https://drive.google.com/file/d/FILE_ID/view`), standard browser `<img>` tags cannot render the Drive HTML viewer page directly.
  3. For direct image display, transform the link to the Google Drive direct thumbnail/export format:
     `https://drive.google.com/uc?export=view&id=FILE_ID` or `https://lh3.googleusercontent.com/d/FILE_ID`.
  4. For Google Drive videos, use the preview embed URL in an `<iframe>`:
     `https://drive.google.com/file/d/FILE_ID/preview`.
