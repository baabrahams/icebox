CREATE UNIQUE INDEX idx_pantry_user_name ON pantry_items (user_id, LOWER(name));
