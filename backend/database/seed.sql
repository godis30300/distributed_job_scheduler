-- Production seed file.
--
-- Creates one default administrator for first-time login.
-- Password is stored as a bcrypt hash, not plaintext.
--
-- Default account:
--   username: admin
--   password: admin123
--   email: admin@gmail.com

INSERT INTO users (id, username, email, password_hash, role)
VALUES (
    '90000000-0000-0000-0000-000000000001',
    'admin',
    'admin@gmail.com',
    '$2b$12$YkOZu7z.r6mgJAnkJOjpIemVcWCyo10akVg8/yG7FHlDhrMGbEwOq',
    'admin'
)
ON CONFLICT (username) DO UPDATE
SET
    email = EXCLUDED.email,
    password_hash = EXCLUDED.password_hash,
    role = EXCLUDED.role;
