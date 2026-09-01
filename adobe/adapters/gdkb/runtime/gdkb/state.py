from copy import deepcopy

class StateError(Exception):
    pass

def empty_state():
    return {
        "entities": {},
        "aliases": {},
        "merges": {},
        "assertions": {},
        "observations": {},
        "events_applied": []
    }

def _require_entity(state, entity_id):
    if entity_id not in state["entities"]:
        raise StateError(f"unknown entity: {entity_id}")

def apply_event(state, event):
    s=deepcopy(state)
    t=event.event_type
    eid=event.entity_id
    payload=event.payload or {}

    if t=="ENTITY_CREATED":
        if not eid:
            raise StateError("ENTITY_CREATED requires entity_id")
        if eid in s["entities"]:
            raise StateError(f"entity already exists: {eid}")
        s["entities"][eid]={
            "id":eid,
            "kind":payload["kind"],
            "canonical_name":payload["canonical_name"],
            "status":"active"
        }

    elif t=="ENTITY_DEPRECATED":
        _require_entity(s,eid)
        s["entities"][eid]["status"]="deprecated"

    elif t=="ENTITY_RESTORED":
        _require_entity(s,eid)
        s["entities"][eid]["status"]="active"

    elif t=="OBSERVATION_ADDED":
        if not payload.get("observation_id"):
            raise StateError("OBSERVATION_ADDED requires observation_id")
        s["observations"][payload["observation_id"]]=deepcopy(payload)

    elif t=="ASSERTION_CREATED":
        _require_entity(s,eid)
        aid=payload["assertion_id"]
        s["assertions"][aid]=deepcopy(payload)

    elif t=="MERGE":
        _require_entity(s,eid)
        target=event.target_entity_id
        _require_entity(s,target)
        if eid==target:
            raise StateError("self merge")
        s["merges"][eid]=target
        s["entities"][eid]["status"]="merged"

    elif t=="SPLIT":
        _require_entity(s,eid)
        # Split is represented as a lifecycle event; historical state remains.
        s["entities"][eid]["status"]="active"
        s.setdefault("splits",[]).append(deepcopy(event.body()))

    else:
        raise StateError(f"unsupported event type: {t}")

    s["events_applied"].append(event.id)
    return s

def build_state(events):
    state=empty_state()
    for event in sorted(events,key=lambda e:e.sequence):
        if event.id in state["events_applied"]:
            raise StateError(f"duplicate event id: {event.id}")
        state=apply_event(state,event)
    return state
