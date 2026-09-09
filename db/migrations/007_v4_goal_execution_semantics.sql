-- v4 goal execution semantics: blocked/owner tasks must never appear runnable.

-- Derived views are dropped first because adding base-table columns changes SELECT g.* projection order.
drop view if exists public.v_owner_action_queue_v4;
drop view if exists public.v_goal_queue_v4;

alter table public.goals add column if not exists execution_mode text not null default 'autonomous';
alter table public.goals drop constraint if exists goals_execution_mode_check;
alter table public.goals add constraint goals_execution_mode_check check (execution_mode in ('autonomous','hybrid','owner'));

alter table public.goals add column if not exists blocker_type text not null default 'none';
alter table public.goals drop constraint if exists goals_blocker_type_check;
alter table public.goals add constraint goals_blocker_type_check check (blocker_type in ('none','dependency','external_account','owner_policy','connector','technical'));

update public.goals set execution_mode='hybrid', blocker_type='external_account', status='blocked'
where goal_key='deploy-cloud-runtime';
update public.goals set execution_mode='hybrid', blocker_type='connector', status='blocked'
where goal_key in ('wire-drive-crm-runtime','wire-market-providers','wire-funding-feed','tectum-cloud-underwriting-golden','tectum-cloud-render-golden','execute-first-real-loop');
update public.goals set execution_mode='hybrid', blocker_type='external_account', status='blocked'
where goal_key='complete-lovable-cockpit';
update public.goals set execution_mode='owner', blocker_type='owner_policy', status='blocked'
where goal_key='define-outreach-envelope';

create view public.v_goal_queue_v4 as
select g.*,
  coalesce((select count(*) from public.goal_dependencies gd join public.goals d on d.id=gd.depends_on_goal_id where gd.goal_id=g.id and gd.dependency_type='hard' and d.status<>'succeeded'),0) as blocking_dependencies,
  case
    when g.expires_at is not null and g.expires_at<=now() then false
    when g.status not in ('proposed','ready') then false
    when g.execution_mode='owner' then false
    when g.blocker_type<>'none' then false
    when exists(select 1 from public.goal_dependencies gd join public.goals d on d.id=gd.depends_on_goal_id where gd.goal_id=g.id and gd.dependency_type='hard' and d.status<>'succeeded') then false
    else true
  end as runnable,
  (least(greatest(g.expected_economic_value/1000.0,0),1)+g.strategic_value*0.6+g.urgency*0.5+g.confidence*0.7+g.reversibility*0.3-g.risk*0.8
   - coalesce((select count(*) from public.goal_dependencies gd join public.goals d on d.id=gd.depends_on_goal_id where gd.goal_id=g.id and gd.dependency_type='hard' and d.status<>'succeeded'),0)*2.0) as priority_score
from public.goals g;

create view public.v_owner_action_queue_v4 as
select * from public.v_goal_queue_v4
where execution_mode='owner' and status not in ('succeeded','failed','cancelled','expired')
order by priority_score desc, created_at;
