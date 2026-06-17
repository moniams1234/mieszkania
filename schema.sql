-- Uruchom to w Supabase → SQL Editor

create table if not exists offers (
  id               bigint primary key,
  city             text not null,
  title            text,
  price_pln        integer,
  area_m2          real,
  rooms            integer,
  floor            integer,
  address          text,
  url              text,
  scraped_at       text,
  developer        text,
  market           text,
  development      text,
  district         text,
  first_scraped_at text
);

create table if not exists investments (
  id               serial primary key,
  developer        text not null,
  city             text not null,
  district         text,
  investment_name  text not null,
  status           text,
  apartments_total integer,
  price_min        integer,
  price_max        integer,
  completion_year  integer,
  unique(developer, city, investment_name)
);

create table if not exists users (
  id            serial primary key,
  login         text unique not null,
  password_hash text not null,
  created_at    text not null
);

create table if not exists favorites (
  user_id  integer not null references users(id),
  offer_id bigint  not null,
  added_at text    not null,
  primary key (user_id, offer_id)
);

create table if not exists offer_history (
  offer_id        bigint primary key,
  fetched_at      text,
  price_history   text,
  views_count     integer,
  days_on_market  integer,
  first_listed_at text,
  raw_data        text
);
