-- Migracja 002: kolumna preferred_currency w tabeli users
-- Uruchom w Supabase → SQL Editor

alter table users
  add column if not exists preferred_currency text not null default 'PLN';
