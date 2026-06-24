-- Migracja 001: tabela kursów walut (NBP)
-- Uruchom w Supabase → SQL Editor

create table if not exists currency_rates (
  id           serial primary key,
  currency     text not null,       -- kod waluty, np. EUR, USD, CHF
  currency_name text not null,      -- pełna nazwa, np. euro
  rate         numeric(12,6) not null, -- kurs w PLN za 1 jednostkę waluty
  effective_date date not null,     -- data obowiązywania kursu
  table_no     text,                -- numer tabeli NBP, np. "A001/2024"
  fetched_at   text not null,       -- kiedy pobraliśmy dane
  unique(currency, effective_date)
);

create index if not exists idx_currency_rates_date
  on currency_rates(effective_date desc);

create index if not exists idx_currency_rates_currency
  on currency_rates(currency, effective_date desc);
