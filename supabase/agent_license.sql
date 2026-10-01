-- BituachBot is a tool for licensed insurance agents.
-- 1) Every agent stores their license number (רשות שוק ההון) — shown to their clients.
-- 2) bot_messages keeps the client ↔ WhatsApp-bot conversation log (record keeping).
-- Safe to run more than once.

alter table public.agents add column if not exists license_number text;

create table if not exists public.bot_messages (
  id          bigserial primary key,
  created_at  timestamptz not null default now(),
  user_id     text,
  agent_id    text,
  phone       text,
  role        text not null check (role in ('user', 'assistant')),
  content     text not null,
  channel     text not null default 'whatsapp'
);
create index if not exists bot_messages_user_idx on public.bot_messages (user_id, created_at desc);

alter table public.bot_messages enable row level security;
revoke all on public.bot_messages from anon, authenticated;

-- Check
select column_name from information_schema.columns
where table_schema = 'public' and table_name = 'agents' and column_name = 'license_number';
