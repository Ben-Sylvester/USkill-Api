from fastapi import FastAPI
from app.services.executor import execute_in_docker
from app.services.adapter import hybrid_adapter
from app.services.ranker import rank_graphs

app = FastAPI()

@app.post("/run/")
def run():
    graphs = [
        {"nodes":["start","loop","condition","print"],"edges":[["start","loop"],["loop","condition"],["condition","print"]]},
        {"nodes":["start","loop","print"],"edges":[["start","loop"],["loop","print"]]}
    ]

    ranked = rank_graphs(graphs)
    best = ranked[0]

    plan = best["nodes"]
    code = hybrid_adapter(plan,"software")

    result = execute_in_docker(code)

    return {"plan":plan,"code":code,"execution":result}
