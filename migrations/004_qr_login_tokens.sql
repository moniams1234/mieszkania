-- Migracja 004: tokeny do logowania przez QR kod
-- Uruchom w Supabase → SQL Editor

create table if not exists qr_login_tokens (
  token      text primary key,          -- unikalny UUID tokenu
  user_id    integer references users(id) on delete cascade,
  created_at text not null,
  expires_at text not null,             -- token ważny np. 5 minut
  used       boolean not null default false
);

create index if not exists idx_qr_tokens_expires
  on qr_login_tokens(expires_at);
