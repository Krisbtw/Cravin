# Cravin

[![Deployment Status](https://img.shields.io/badge/deployment-live-emerald?style=flat-square)](https://cravin-three.vercel.app/)
[![Frontend](https://img.shields.io/badge/Frontend-Next.js%20%7C%20React%2018-black?style=flat-square&logo=next.js)](https://nextjs.org/)
[![Backend](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.10+-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Database](https://img.shields.io/badge/Database-PostgreSQL%20%7C%20SQLite-336791?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
[![Styling](https://img.shields.io/badge/Styling-Tailwind%20CSS-38bdf8?style=flat-square&logo=tailwindcss)](https://tailwindcss.com/)

> Hyperlocal D2C food-tech platform connecting health-conscious consumers with verified local home bakers for zero-sugar, zero-maida, macro-tracked desserts.

🔗 **Live Platform:** [https://cravin-three.vercel.app/](https://cravin-three.vercel.app/)

---

## Core Focus Areas

- **Clean Ingredients:** Strict exclusion of refined sugars and processed flours. Every formulation utilizes diabetic-friendly, gut-conscious bases including monk fruit extract, certified almond flour, and stone-ground ragi (finger millet).
- **Real-Time Caloric Reconciliation:** Dynamic macro tracking engine computing net carbs, plant/whey protein ratios, and caloric impact before checkout, bridging indulgence with metabolic goals.
- **Hyperlocal Kitchen Fulfillment:** Decentralized micro-bakery routing connecting buyers directly with vetted residential artisan bakers within a tight delivery radius.

---

## System Architecture

```text
+-----------------------------------------------------------------------------------+
|                                 Next.js / React                                    |
|             (Client Deck, Dynamic Macros UI, Live SSE Order Tracker)             |
+-----------------------------------------------------------------------------------+
                                         │
                                         │  HTTPS / REST / SSE
                                         ▼
+-----------------------------------------------------------------------------------+
|                              FastAPI REST Gateway                                 |
|               (Auth Service, Route Handlers, Rate Limiting, CORS)                 |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                   Pydantic v2 Validation & Nutrition Calculator                   |
|           (Schema Integrity, Portion Math, Net Carb & Macro Verification)         |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                               Baker Matching Engine                               |
|        (Geospatial Radius Query, Baker Skillsets, Slot & Capacity Allocator)      |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                             SQLAlchemy 2.0 Async ORM                              |
+-----------------------------------------------------------------------------------+
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
   [Production] PostgreSQL Database           [Local Dev] SQLite Database
   (Orders, Items, Bakers, Profiles)          (Local Persistence / Prototyping)
```

---

## Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | [Next.js](https://nextjs.org/) / [React](https://react.dev/), [Tailwind CSS](https://tailwindcss.com/), [Framer Motion](https://www.framer.com/motion/) (gestural decks & physics-based micro-interactions), [Lucide Icons](https://lucide.dev/) |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+), [Pydantic v2](https://docs.pydantic.dev/) (runtime validation & serialization), [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (Async ORM) |
| **Database** | [PostgreSQL](https://www.postgresql.org/) (production via asyncpg/psycopg2), [SQLite](https://www.sqlite.org/) (local dev via aiosqlite) |
| **Infrastructure** | [Vercel](https://vercel.com/) (edge frontend hosting & CDN), [Render](https://render.com/) / [Google Cloud Run](https://cloud.google.com/run) (containerized backend services) |

---

## Core Features

- **3D Stacked-Card Curations Deck (`/curations`):** Gesture-driven, swipeable card deck powered by Framer Motion. Enables natural multi-axis browsing across curated spotlights (Keto, Diabetic-Safe, Vegan, High-Protein) without pagination friction.
- **Dynamic Nutrition Reconciliation:** Instantaneous macro recalculation based on customized ingredient swaps (e.g., erythritol vs. monk fruit, ragi vs. almond flour). Compares item macros against user-defined daily limits in real time.
- **Hyperlocal Baker Dispatch:** Order dispatch pipeline scoring available neighborhood home bakers against proximity coordinates, operational prep times, equipment constraints, and verified nutritional compliance.
- **Material Dark UI:** Custom carbon design system (`#0B0D13`) accented by frosted glassmorphic card overlays, contextual glow indicators, and responsive tactile press states.

---

## API Route Overview

### Primary Endpoints

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `GET` | `/api/items` | Full dessert catalog with macro breakdowns (calories, protein, fats, net carbs) | No |
| `GET` | `/api/curations` | Featured collection spotlights and thematic dietary bundles | No |
| `POST` | `/api/orders` | Checkout endpoint; executes baker matching and dispatches order payload | Yes |
| `PATCH` | `/api/user/profile` | Updates dietary targets (macro goals, allergies, demographic details) | Yes |

### Order Dispatch Payload (`POST /api/orders`)

```json
{
  "items": [
    {
      "dessert_id": "item_ragi_dark_choco_brownie",
      "quantity": 2,
      "customization": {
        "sweetener": "monk_fruit",
        "flour_base": "ragi_almond"
      }
    }
  ],
  "fulfillment_type": "delivery",
  "baker_id": "bkr_indiranagar_04",
  "delivery_address": "Flat 302, Palm Heights, Indiranagar, Bengaluru",
  "delivery_latitude": 12.9716,
  "delivery_longitude": 77.6412,
  "delivery_notes": "Leave at front door",
  "payment_method": "upi",
  "redeem_points": 0
}
```

---

## Local Development Setup

### Prerequisites
- Python 3.10 or higher
- Node.js 18.x or higher
- npm or yarn

### 1. Backend Setup

```bash
# Clone the repository
git clone https://github.com/Krisbtw/Cravin.git
cd Cravin

# Create and activate virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env

# Run database migrations and seed initial data
python -m app.seed

# Start the API server on port 8001
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Backend API documentation will be available at `http://127.0.0.1:8001/docs`.

### 2. Frontend Setup

```bash
# Navigate to frontend directory (or project root if mono-repo setup)
cd frontend

# Install Node dependencies
npm install

# Configure environment variables
cat <<EOF > .env.local
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001
EOF

# Start development server
npm run dev
```

The web application will boot at `http://localhost:3000`.

---

## Roadmap

- **Phase 1 (Current):** Hyperlocal D2C MVP with verified home bakers, gestural curation deck, real-time macro calculation, and SSE-driven order fulfillment.
- **Phase 2:** Institutional fitness kiosks, smart gym inventory integrations, and corporate B2B health-snack subscription partnerships.
- **Phase 3:** Centralized bulk procurement for specialized ingredients (Monk fruit, organic almond flour) and third-party NABL-certified nutritional lab verification.
