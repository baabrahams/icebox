CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  phone_number TEXT NOT NULL UNIQUE,
  household_size INTEGER,
  interview_time TIME DEFAULT '17:00',
  timezone TEXT DEFAULT 'America/New_York',
  onboarding_complete BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_phone ON users(phone_number);

CREATE TABLE dietary_restrictions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('allergy', 'dislike', 'diet')),
  value TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('onboarding', 'learned'))
);

CREATE INDEX idx_dietary_user ON dietary_restrictions(user_id);

CREATE TABLE pantry_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  category TEXT,
  added_at TIMESTAMPTZ DEFAULT NOW(),
  last_confirmed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pantry_user ON pantry_items(user_id);

CREATE TABLE conversation_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  media_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_convo_user_time ON conversation_history(user_id, created_at DESC);

CREATE TABLE dinner_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date DATE NOT NULL DEFAULT CURRENT_DATE,
  recipe_name TEXT NOT NULL,
  recipe_source TEXT,
  status TEXT NOT NULL CHECK (status IN ('suggested', 'made', 'skipped')) DEFAULT 'suggested',
  user_rating INTEGER CHECK (user_rating BETWEEN 1 AND 5),
  items_used TEXT[]
);

CREATE INDEX idx_dinner_user_date ON dinner_logs(user_id, date DESC);
