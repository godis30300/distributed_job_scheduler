-- Production seed file.
--
-- Creates one default administrator for first-time login.
-- The login secret is hashed during database initialization.
--
-- Default account:
--   username: admin
--   email: admin@gmail.com

CREATE EXTENSION IF NOT EXISTS pgcrypto;

INSERT INTO users (id, username, email, password_hash, role)
VALUES (
    '90000000-0000-0000-0000-000000000001',
    'admin',
    'admin@gmail.com',
    crypt('admin' || '123', gen_salt('bf', 12)),
    'admin'
)
ON CONFLICT (username) DO UPDATE
SET
    email = EXCLUDED.email,
    password_hash = EXCLUDED.password_hash,
    role = EXCLUDED.role;
