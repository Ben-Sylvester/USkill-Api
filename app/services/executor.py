import subprocess, uuid, os, json

def execute_in_docker(code: str):
    fname = f"/tmp/{uuid.uuid4().hex}.py"
    with open(fname,"w") as f:
        f.write(code)

    cmd = [
        "docker","run","--rm",
        "-v",f"{fname}:/app/run.py",
        "python:3.10-slim",
        "python","/app/run.py"
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return {"success": res.returncode==0,"output":res.stdout,"error":res.stderr}
    except Exception as e:
        return {"success":False,"error":str(e)}
    finally:
        if os.path.exists(fname): os.remove(fname)
