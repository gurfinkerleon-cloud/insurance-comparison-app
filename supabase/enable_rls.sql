-- BituachBot: lock down the ביטוחים project.
--
-- RUN THIS ONLY AFTER Streamlit (SUPABASE_KEY) and the n8n "Supabase account"
-- credential both use the service_role key. The service_role key bypasses RLS;
-- the anon key will be blocked from every table below (no policies = no access).

alter table public.agents              enable row level security;
alter table public.profiles            enable row level security;
alter table public.user_policies       enable row level security;
alter table public.master_annexes      enable row level security;
alter table public.insurance_companies enable row level security;
alter table public.verification_codes  enable row level security;

-- Belt and braces: remove direct grants from the public roles.
revoke all on public.agents, public.profiles, public.user_policies,
              public.master_annexes, public.insurance_companies,
              public.verification_codes
  from anon, authenticated;

-- Check: every table should show rowsecurity = true
select tablename, rowsecurity
from pg_tables
where schemaname = 'public'
order by tablename;
