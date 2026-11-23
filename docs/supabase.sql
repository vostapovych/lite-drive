-- Run in Supabase Dashboard -> SQL Editor.
create table if not exists public.files (
  id             uuid primary key,
  owner_id       uuid not null references auth.users(id) on delete cascade,
  name           text not null,
  storage_path   text not null,
  size           bigint not null default 0,
  created_at     timestamptz not null default now(),
  modified_at    timestamptz not null default now(),
  uploaded_by    uuid not null references auth.users(id),
  last_edited_by uuid not null references auth.users(id),
  committed      boolean not null default false,
  unique (owner_id, name)
);
create index if not exists files_owner_idx on public.files(owner_id);

-- Only the server (secret key, bypasses RLS) touches this table. Enabling RLS with no
-- policies means the publishable key can never read or write it directly.
alter table public.files enable row level security;

-- Private bucket for the bytes (signed URLs only).
insert into storage.buckets (id, name, public) values ('drive', 'drive', false)
on conflict (id) do nothing;
