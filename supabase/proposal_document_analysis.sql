create table if not exists public.proposal_document_analysis (
    document_id bigint primary key
        references public.proposal_documents(id) on delete cascade,
    economy smallint not null check (economy between 0 and 100),
    health smallint not null check (health between 0 and 100),
    education smallint not null check (education between 0 and 100),
    security smallint not null check (security between 0 and 100),
    social smallint not null check (social between 0 and 100),
    infrastructure smallint not null check (infrastructure between 0 and 100),
    analysis_model text not null,
    analysis_version text not null,
    analyzed_at timestamptz not null default now()
);

alter table public.proposal_document_analysis enable row level security;

create or replace function public.replace_proposal_chunks_with_analysis(
    target_document_id bigint,
    new_chunks jsonb,
    new_analysis jsonb,
    analysis_model_name text,
    analysis_version_name text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
    -- Evita dois processamentos simultâneos substituírem o mesmo documento.
    perform pg_advisory_xact_lock(target_document_id);

    delete from public.proposal_chunks
    where document_id = target_document_id;

    insert into public.proposal_chunks (document_id, page, content, embedding)
    select
        target_document_id,
        (chunk->>'page')::integer,
        chunk->>'content',
        (chunk->>'embedding')::vector
    from jsonb_array_elements(new_chunks) as chunk;

    insert into public.proposal_document_analysis (
        document_id,
        economy,
        health,
        education,
        security,
        social,
        infrastructure,
        analysis_model,
        analysis_version,
        analyzed_at
    )
    values (
        target_document_id,
        (new_analysis->>'economy')::smallint,
        (new_analysis->>'health')::smallint,
        (new_analysis->>'education')::smallint,
        (new_analysis->>'security')::smallint,
        (new_analysis->>'social')::smallint,
        (new_analysis->>'infrastructure')::smallint,
        analysis_model_name,
        analysis_version_name,
        now()
    )
    on conflict (document_id) do update set
        economy = excluded.economy,
        health = excluded.health,
        education = excluded.education,
        security = excluded.security,
        social = excluded.social,
        infrastructure = excluded.infrastructure,
        analysis_model = excluded.analysis_model,
        analysis_version = excluded.analysis_version,
        analyzed_at = excluded.analyzed_at;
end;
$$;

revoke all on function public.replace_proposal_chunks_with_analysis(
    bigint, jsonb, jsonb, text, text
) from public;

grant execute on function public.replace_proposal_chunks_with_analysis(
    bigint, jsonb, jsonb, text, text
) to service_role;
