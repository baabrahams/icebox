-- Add time budget to users
ALTER TABLE users ADD COLUMN weeknight_time_minutes INTEGER DEFAULT 30;

-- Recipe sources table
CREATE TABLE recipe_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  source_name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_recipe_sources_user_source
  ON recipe_sources (user_id, LOWER(source_name));
