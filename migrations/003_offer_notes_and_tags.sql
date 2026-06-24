-- Migracja 003: tabele notatek i tagów użytkownika do ogłoszeń
-- Uruchom w Supabase → SQL Editor

-- Notatki użytkownika do ogłoszenia (pełna historia z timestampem)
create table if not exists offer_notes (
  id         serial primary key,
  user_id    integer not null references users(id) on delete cascade,
  offer_id   bigint  not null,
  note_text  text    not null,
  created_at text    not null  -- ISO-8601, np. 2024-06-24T15:30:00
);

create index if not exists idx_offer_notes_user_offer
  on offer_notes(user_id, offer_id);

create index if not exists idx_offer_notes_text
  on offer_notes using gin(to_tsvector('simple', note_text));

-- Tagi użytkownika do ogłoszenia (historia tagów z datą)
create table if not exists offer_tags (
  id         serial primary key,
  user_id    integer not null references users(id) on delete cascade,
  offer_id   bigint  not null,
  tag        text    not null,
  created_at text    not null
);

create index if not exists idx_offer_tags_user_offer
  on offer_tags(user_id, offer_id);
