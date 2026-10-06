"""Choose a continuous palm roll path from anatomically feasible candidates.

Candidate quaternions must be unit quaternions. This planner never adds poses
outside the supplied feasible set or expands the adjacent rotation bound.
"""
import math


def select_roll_path(layers, max_step_deg=20, smoothness=2):
    if not layers or any(not layer for layer in layers):
        raise ValueError('Every sample needs a nonempty feasible set')
    if not 0 < max_step_deg <= 30 or not math.isfinite(smoothness) or smoothness < 0:
        raise ValueError('Invalid continuity policy')
    for layer in layers:
        for node in layer:
            q=node['quaternion'];score=node['palm_error_rad']
            if len(q)!=4 or any(not math.isfinite(v) for v in q) or abs(sum(v*v for v in q)-1)>1e-5:
                raise ValueError('Candidate quaternion must be finite and normalized')
            if not math.isfinite(score) or not 0 <= score <= math.pi:
                raise ValueError('Invalid palm error')
    costs=[node['palm_error_rad']**2 for node in layers[0]];parents=[]
    for layer in range(1,len(layers)):
        next_cost=[];links=[]
        for node in layers[layer]:
            options=[]
            for k,previous in enumerate(layers[layer-1]):
                dot=min(1.0,abs(sum(a*b for a,b in zip(previous['quaternion'],node['quaternion']))))
                step=2*math.acos(dot)
                if step<=math.radians(max_step_deg)+1e-9 and math.isfinite(costs[k]):
                    options.append((costs[k]+node['palm_error_rad']**2+smoothness*step**2,k))
            cost,parent=min(options) if options else (math.inf,-1)
            next_cost.append(cost);links.append(parent)
        if not any(math.isfinite(c) for c in next_cost):
            raise ValueError(f'No continuous feasible roll path at sample {layer+1}')
        costs=next_cost;parents.append(links)
    chosen=min(range(len(costs)),key=costs.__getitem__);path=[chosen]
    for layer in range(len(layers)-2,-1,-1):
        chosen=parents[layer][chosen];path.append(chosen)
    return list(reversed(path))
