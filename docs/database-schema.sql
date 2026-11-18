-- =============================================================================
-- Neon Serverless PostgreSQL Relational Schema Blueprint
-- RGB ASCII & Retro FX Studio (INFRA-03 / D-06)
--
-- Architecture Note:
-- The v1 architecture operates completely stateless and in-memory to guarantee
-- $0/month deployment on free-tier infrastructure (Cloudflare Pages + Render Free).
-- This schema serves as the production blueprint for future persistence features
-- (user accounts, custom preset cloud sync, and historical export analytics).
--
-- Deployment Target:
-- Neon Serverless PostgreSQL (free tier: 0.5 GB storage, auto-suspend compute).
-- Connection string pattern:
--   DATABASE_URL=postgresql://<user>:<password>@<endpoint-id>.us-east-2.aws.neon.tech/neondb?sslmode=require
-- =============================================================================

-- Enable standard UUID generation extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- 1. Users Table
-- Supports future user accounts, OAuth sign-in, and tier tracking.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    avatar_url TEXT,
    tier VARCHAR(20) NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index on email for rapid user lookups during authentication
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users (created_at DESC);

-- -----------------------------------------------------------------------------
-- 2. Presets Table
-- Stores user-saved retro visual effects parameter configurations.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS presets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    effect_type VARCHAR(50) NOT NULL,
    -- JSONB parameter bag capturing shader uniforms, palette ramps, and matrix settings
    parameters JSONB NOT NULL,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    view_count INTEGER NOT NULL DEFAULT 0,
    fork_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- B-Tree indexes for user-specific queries, public catalog browsing, and sorting
CREATE INDEX IF NOT EXISTS idx_presets_user_id ON presets (user_id);
CREATE INDEX IF NOT EXISTS idx_presets_effect_type ON presets (effect_type);
CREATE INDEX IF NOT EXISTS idx_presets_is_public ON presets (is_public) WHERE is_public = TRUE;
CREATE INDEX IF NOT EXISTS idx_presets_created_at ON presets (created_at DESC);

-- GIN index for high-performance deep JSON queries on shader uniforms and parameters
CREATE INDEX IF NOT EXISTS idx_presets_parameters_gin ON presets USING gin (parameters);

-- -----------------------------------------------------------------------------
-- 3. Export Jobs Table
-- Records export telemetry, job states, durations, and resource metrics.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS export_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users (id) ON DELETE SET NULL,
    format VARCHAR(10) NOT NULL CHECK (format IN ('mp4', 'webm', 'gif')),
    resolution VARCHAR(20) NOT NULL CHECK (resolution IN ('720p', '1080p', 'source')),
    duration_sec NUMERIC(6, 2) NOT NULL,
    fps INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (
        status IN ('pending', 'capturing', 'uploading', 'encoding', 'completed', 'failed', 'cancelled', 'expired')
    ),
    file_size_bytes BIGINT,
    peak_rss_mb NUMERIC(6, 2),
    encode_duration_sec NUMERIC(6, 2),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- B-Tree indexes for filtering jobs by user, status, and creation date
CREATE INDEX IF NOT EXISTS idx_export_jobs_user_id ON export_jobs (user_id);
CREATE INDEX IF NOT EXISTS idx_export_jobs_status ON export_jobs (status);
CREATE INDEX IF NOT EXISTS idx_export_jobs_created_at ON export_jobs (created_at DESC);

-- -----------------------------------------------------------------------------
-- Automated updated_at Timestamp Trigger
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_timestamp_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp_column();

DROP TRIGGER IF EXISTS trg_presets_updated_at ON presets;
CREATE TRIGGER trg_presets_updated_at
    BEFORE UPDATE ON presets
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp_column();
