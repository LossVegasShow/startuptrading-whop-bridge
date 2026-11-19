"""Static release gate: verifies essential routes, files, and safe defaults."""
from pathlib import Path
import ast
from config import Config
root=Path(__file__).resolve().parent
files=('app.py','clients.py','engine.py','store.py','member_lookup.py','purchaser_intake.py','customer_communications.py','security.py','config.py','templates/index.html','templates/activate.html','templates/onboarding.html','templates/admin_test.html','templates/admin.html','templates/invite.html','templates/result.html','static/site.css','static/v2.css','Dockerfile','requirements.txt')
missing=[name for name in files if not (root/name).is_file()]
if missing:raise SystemExit('Missing release files: '+', '.join(missing))
for file in root.glob('*.py'):ast.parse(file.read_text(),filename=str(file))
from app import app
paths={r.path for r in app.routes}
for required in ('/','/health','/oauth/login','/oauth/callback','/admin-test/login','/admin-test/intake','/onboarding','/activate','/checkout','/webhooks/whop'):
    assert required in paths,required
assert not Config().license_writes or (Config().allowed_test_email and Config().allowed_test_membership),'Unsafe license writes'
print('Release files, syntax, routes and license guard verified')
