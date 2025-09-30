-- (2025-09-23 17:36 ET) — M0: Agent runtime tables using BIGINT identities + RLS
-- Rationale: avoids uuid dependency, plays nicely with LangGraph thread ids,
-- keeps your existing domain tables (emails/tasks/etc.) unchanged.

-- No pgcrypto needed for these tables

create table if not exists va_sessions (
  id bigint primary key generated always as identity,
  created_at timestamptz default now(),
  label text
);
alter table va_sessions enable row level security;

create table if not exists va_messages (
  id bigint primary key generated always as identity,
  created_at timestamptz default now(),
  session_id bigint references va_sessions(id) on delete cascade,
  role text check (role in ('user','assistant','system','tool')),
  content text
);
create index if not exists idx_va_messages_session_id on va_messages(session_id);
alter table va_messages enable row level security;

create table if not exists va_tool_events (
  id bigint primary key generated always as identity,
  created_at timestamptz default now(),
  session_id bigint references va_sessions(id) on delete cascade,
  tool_name text,
  input_json jsonb,
  output_json jsonb
);
create index if not exists idx_va_tool_events_session_id on va_tool_events(session_id);
alter table va_tool_events enable row level security;

create table if not exists va_settings (
  id bigint primary key generated always as identity,
  key text unique,
  value jsonb,
  updated_at timestamptz default now()
);
alter table va_settings enable row level security;

-- Optional seed
insert into va_settings(key, value)
values
  ('queue_reminder_minutes', '5'::jsonb),
  ('tts_speed', '1.0'::jsonb)
on conflict (key) do nothing;

-- NOTE: Service Role bypasses RLS; define finer-grained policies later for anon/public use.


create table if not exists va_meetings (
  id bigint primary key generated always as identity,
  created_at timestamptz default now(),
  label text,
  summary text,
  bullets jsonb,
  segment_count int default 0
);
alter table va_meetings enable row level security;

-- Task queue (write-only, safe if Supabase not configured)
create table if not exists va_tasks (
  id bigint primary key generated always as identity,
  created_at timestamptz default now(),
  title text not null,
  body text,
  status text check (status in ('queued','running','success','failed','cancelled')) default 'queued',
  branch text,
  pr_number bigint,
  error text
);
create index if not exists idx_va_tasks_status on va_tasks(status);

create table if not exists va_task_events (
  id bigint primary key generated always as identity,
  created_at timestamptz default now(),
  task_id bigint references va_tasks(id) on delete cascade,
  kind text,               -- 'log' | 'tick' | 'done' | 'error'
  data jsonb               -- free-form event payload
);
create index if not exists idx_va_task_events_task on va_task_events(task_id);
create table if not exists va_meeting_segments (
  id bigint primary key generated always as identity,
  created_at timestamptz default now(),
  meeting_id bigint references va_meetings(id) on delete cascade,
  "ts" double precision,
  idx int,
  text text
);
create index if not exists idx_va_meeting_segments_meeting_id on va_meeting_segments(meeting_id);
alter table va_meeting_segments enable row level security;
