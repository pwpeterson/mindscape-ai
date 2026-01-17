-- 20260117_0003_llm_http_payloads_prompt_text.sql
--
-- Add prompt_text column to llm_http_payloads (privacy-sensitive)
--
-- This stores the processed prompt (canonical JSON of messages) as a separate text column.
-- Written only when model-proxy explicitly enables STORE_PAYLOAD_PROMPT_TEXT.

begin;

alter table public.llm_http_payloads
  add column if not exists prompt_text text null;

comment on column public.llm_http_payloads.prompt_text is
  'Processed prompt text (canonical JSON messages). Privacy-sensitive; written only when enabled in model-proxy.';

commit;
