"""Load local .env without requiring extra dependencies; start one Uvicorn worker."""
import os
from pathlib import Path
p=Path(__file__).parent/'.env'
if p.exists():
    for raw in p.read_text(encoding='utf-8').splitlines():
        line=raw.strip()
        if not line or line.startswith('#') or '=' not in line:continue
        key,value=line.split('=',1)
        os.environ.setdefault(key.strip(),value.strip())
import uvicorn
uvicorn.run('app:app',host='127.0.0.1',port=8000,workers=1)
