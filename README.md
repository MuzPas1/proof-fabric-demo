# Proof Fabric Protocol — RBI Sandbox Demo

A minimal, professional web app for generating and verifying Financial Evidence Artifacts (FEA) using cryptographic proofs. 

## Features

- **Create Transaction**: Record transactions with user ID and amount
- **Generate Proof**: Create SHA256-based Financial Evidence Artifacts (FEA)
- **Verify Proof**: Verify FEA integrity by recomputing hashes
- **Export FEA**: Download FEA as JSON files for compliance

## Quick Setup (< 10 minutes)

### 1. Supabase Setup

1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Create a new project (or use existing)
3. Go to **SQL Editor** and run this SQL:

```sql
-- Create transactions table
CREATE TABLE transactions (
  id UUID PRIMARY KEY,
  user_id TEXT NOT NULL,
  amount DECIMAL(15,2) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create proofs table
CREATE TABLE proofs (
  id UUID PRIMARY KEY,
  fea_id TEXT UNIQUE NOT NULL,
  transaction_id UUID REFERENCES transactions(id),
  user_id TEXT NOT NULL,
  amount DECIMAL(15,2) NOT NULL,
  transaction_created_at TIMESTAMPTZ NOT NULL,
  hash TEXT NOT NULL,
  proof_status TEXT DEFAULT 'VERIFIED',
  issuer TEXT DEFAULT 'Proof Fabric Protocol v0.1',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security (optional but recommended)
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE proofs ENABLE ROW LEVEL SECURITY;

-- Allow public access for demo (adjust policies for production)
CREATE POLICY "Allow all transactions" ON transactions FOR ALL USING (true);
CREATE POLICY "Allow all proofs" ON proofs FOR ALL USING (true);
```

4. Get your credentials from **Project Settings → API**:
   - Project URL (e.g., `https://xxxxx.supabase.co`)
   - Anon public key

### 2. Local Development

```bash
# Clone and install
git clone <your-repo>
cd proof-fabric-protocol
npm install

# Copy environment file and add your Supabase credentials
cp .env.example .env
# Edit .env with your SUPABASE_URL and SUPABASE_ANON_KEY

# Run development server
npm run dev
```

### 3. Deploy to Vercel

1. Push your code to GitHub
2. Go to [Vercel](https://vercel.com) and import your repository
3. Add environment variables:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
4. Deploy!

## How It Works

### Hash Generation

The FEA hash is computed using SHA256:
```
SHA256(user_id + "|" + amount + "|" + created_at)
```

### Verification Process

1. Fetch stored proof by FEA ID
2. Recompute hash from original data
3. Compare stored hash with computed hash
4. Display verification status

### FEA Export Format

```json
{
  "fea_id": "FEA-XXXXXXXX",
  "transaction": {
    "id": "uuid",
    "user_id": "USER001",
    "amount": 10000,
    "created_at": "2025-01-15T10:30:00Z"
  },
  "hash": "a1b2c3d4...",
  "timestamp": "2025-01-15T10:30:05Z",
  "proof_status": "VERIFIED",
  "issuer": "Proof Fabric Protocol v0.1"
}
```

## Tech Stack

- **Frontend**: Next.js 14, React 18, TypeScript
- **Styling**: Tailwind CSS, shadcn/ui
- **Backend**: Supabase (PostgreSQL)
- **Crypto**: Web Crypto API (SHA256)

## License

MIT
