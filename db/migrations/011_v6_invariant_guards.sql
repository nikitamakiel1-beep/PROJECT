-- Creixement v6 invariant guards.
-- Apply after 010_v6_autonomic_operations.sql.

create or replace function public.creixement_guard_scheduler_binding_v6()
returns trigger language plpgsql set search_path=public
as $$
begin
  -- Seed/migration replays must never demote a verified active scheduler to a setup state.
  if old.state='active' and new.state in ('defined','needs_setup') then
    new.state := old.state;
    new.last_verified_at := old.last_verified_at;
    new.last_error := old.last_error;
    new.evidence_refs := old.evidence_refs;
  end if;
  return new;
end;
$$;

drop trigger if exists scheduler_bindings_v6_guard on public.scheduler_bindings_v6;
create trigger scheduler_bindings_v6_guard
before update on public.scheduler_bindings_v6
for each row execute function public.creixement_guard_scheduler_binding_v6();

create or replace function public.creixement_guard_owner_decision_v6()
returns trigger language plpgsql set search_path=public
as $$
begin
  if new.idempotency_key is distinct from old.idempotency_key
     or new.decision_key is distinct from old.decision_key
     or new.subject_type is distinct from old.subject_type
     or new.subject_key is distinct from old.subject_key
     or new.decision is distinct from old.decision
     or new.payload_digest is distinct from old.payload_digest
     or new.actor is distinct from old.actor
     or new.created_at is distinct from old.created_at then
    raise exception 'recorded owner-decision identity and content are immutable';
  end if;
  return new;
end;
$$;

drop trigger if exists owner_decisions_v6_guard on public.owner_decisions_v6;
create trigger owner_decisions_v6_guard
before update on public.owner_decisions_v6
for each row execute function public.creixement_guard_owner_decision_v6();

create or replace view public.v_owner_decision_audit_v6 as
select
  id,idempotency_key,decision_key,subject_type,subject_key,decision,payload_digest,
  status,actor,created_at,consumed_at,consumed_receipt_ref,evidence_refs
from public.owner_decisions_v6
order by created_at desc;
