from openai import OpenAI
API_KEY = 'Your OpenAI Key'


client = OpenAI(api_key=API_KEY)

def constraint_map(plan):
    lines=[]
    for s in plan:
        if s=="loop": lines.append("for i in range(1,11):")
        elif s=="condition": lines.append("    if i%2==0:")
        elif s=="print": lines.append("        print(i)")
    return "\n".join(lines)

def hybrid_adapter(plan, domain):
    base = constraint_map(plan)

    try:
        resp = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role":"system","content":"Improve code but keep structure"},
                {"role":"user","content":base}
            ],
            temperature=0.2
        )
        return resp.choices[0].message.content
    except:
        return base
