def rank_graphs(graphs):
    scored=[]
    for g in graphs:
        score = len(g["nodes"]) + len(g["edges"])*0.5
        scored.append((score,g))
    scored.sort(reverse=True,key=lambda x:x[0])
    return [g for _,g in scored]
