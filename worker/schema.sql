-- Schéma de référence ; la base est créée par les migrations de migrations/.
CREATE TABLE licenses (
  key TEXT PRIMARY KEY,
  key_hash TEXT UNIQUE, -- empreinte portée par les jetons (tokens.ts)
  email TEXT,
  stripe_customer TEXT UNIQUE,
  stripe_subscription TEXT,
  status TEXT,
  period_end INTEGER,
  synced_at INTEGER,
  created_at INTEGER
);

CREATE TABLE activations (
  key TEXT,
  device_id TEXT,
  device_name TEXT,
  last_seen INTEGER,
  PRIMARY KEY (key, device_id)
);

-- Idempotence des webhooks Stripe.
CREATE TABLE events (
  id TEXT PRIMARY KEY,
  received_at INTEGER
);

-- Limite de fréquence de /retrouver.
CREATE TABLE recover_requests (
  ip_email_hash TEXT,
  at INTEGER
);

CREATE INDEX licenses_email ON licenses (email);
CREATE INDEX recover_requests_hash ON recover_requests (ip_email_hash, at);
