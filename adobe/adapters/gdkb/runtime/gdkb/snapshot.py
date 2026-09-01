import hashlib, json

def canonical_state(state):
    return json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",",":"))

def state_hash(state):
    return hashlib.sha256(canonical_state(state).encode()).hexdigest()

def snapshot(state, snapshot_id, event_end):
    return {
        "snapshot_id":snapshot_id,
        "event_end":event_end,
        "state_hash":state_hash(state),
        "state":state
    }

def diff(a,b):
    out={}
    for key in sorted(set(a)|set(b)):
        if a.get(key)!=b.get(key):
            out[key]={"from":a.get(key),"to":b.get(key)}
    return out
