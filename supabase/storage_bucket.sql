-- Private bucket for clients' original PDFs (policies / נספחים).
-- Files live at client-documents/<profile_id>/<timestamp>__<client|agent|bot>__<name>.
-- The app reads and writes it with the service_role key; there are no public policies.
insert into storage.buckets (id, name, public)
values ('client-documents', 'client-documents', false)
on conflict (id) do nothing;
