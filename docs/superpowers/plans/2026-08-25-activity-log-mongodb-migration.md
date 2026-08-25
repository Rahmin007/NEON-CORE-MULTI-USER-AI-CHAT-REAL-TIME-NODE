# Activity Log MongoDB Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `ActivityLog` off SQLite into a MongoDB `activity_logs` collection, keep `User`/`ChatMessage` on SQLite, restrict the activity-log read endpoint to ADMIN, and add a lightweight frontend event-tracking hook for meaningful UI interactions.

**Architecture:** Polyglot persistence — SQLite/SQLAlchemy stays authoritative for `User` and `ChatMessage`; a new `pymongo`-backed module owns a single `activity_logs` collection with a flexible `details` field. `log_activity()` becomes the only write path into Mongo and is used by both existing server-side call sites and a new generic `POST /api/v1/logs/event` route the frontend calls.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (unchanged), `pymongo` (new), MongoDB Atlas free-tier M0 (or any reachable `mongod` for local dev).

**Spec:** `docs/superpowers/specs/2026-08-25-activity-log-mongodb-migration-design.md`

## Global Constraints

- Demo/personal project scope — no production hardening (no retry queues, no log shipping, no alerting).
- No automated test suite is being introduced. Verification is manual, per the spec's Testing section.
- Do not touch `User` or `ChatMessage` models/tables — SQLite stays exactly as-is for those.
- Use sync `pymongo`, not `motor` — one DB access style shared by sync and async routes.
- `log_activity()` must never raise — Mongo failures are caught, logged to console, and the caller's request proceeds normally.
- `GET /api/v1/logs/` is ADMIN-only (MODERATOR loses access to this specific route; MODERATOR keeps delete/warn/mute).
- No global click-capture instrumentation on the frontend — only the specific interaction points listed in the spec.

---

### Task 1: Mongo dependency, config, and `.env.example`

**Files:**
- Modify: `requirements.txt`
- Modify: `app/core/config.py:30-42`
- Create: `.env.example`

**Interfaces:**
- Produces: `settings.MONGODB_URI: str`, `settings.MONGODB_DB_NAME: str`

- [ ] **Step 1: Add the `pymongo` dependency**

Append to `requirements.txt`:

```text
pymongo>=4.8,<5
```

- [ ] **Step 2: Add Mongo settings**

In `app/core/config.py`, inside the `Settings` dataclass, add two fields right before the closing of the class (after `ALLOW_ORIGINS`, before the blank line and `settings = Settings()`):

```python
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "neon_core")
```

- [ ] **Step 3: Create `.env.example`**

```text
PROJECT_NAME=AI Chat Engine
SECRET_KEY=change-me-to-a-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DATABASE_URL=sqlite:///./chat.db
OPENROUTER_API_KEY=
OPENROUTER_MODEL=openrouter/free
ALLOW_ORIGINS=*
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster-host>/?retryWrites=true&w=majority
MONGODB_DB_NAME=neon_core
```

- [ ] **Step 4: Install and verify**

Run: `python -m pip install -r requirements.txt`
Expected: `pymongo` installs with no errors.

Run: `python -c "from app.core.config import settings; print(settings.MONGODB_URI, settings.MONGODB_DB_NAME)"`
Expected: prints `mongodb://localhost:27017 neon_core` (or your `.env` values if set).

- [ ] **Step 5: Commit**

```bash
git add requirements.txt app/core/config.py .env.example
git commit -m "feat: add MongoDB config and .env.example"
```

---

### Task 2: Mongo connection module

**Files:**
- Create: `app/db/mongo.py`
- Modify: `main.py:13-16`

**Interfaces:**
- Consumes: `settings.MONGODB_URI`, `settings.MONGODB_DB_NAME` (Task 1)
- Produces: `app.db.mongo.activity_logs: pymongo.collection.Collection`, `app.db.mongo.init_mongo_indexes() -> None`

- [ ] **Step 1: Create the Mongo module**

```python
# app/db/mongo.py
from pymongo import DESCENDING, MongoClient
from pymongo.collection import Collection

from app.core.config import settings

_client = MongoClient(settings.MONGODB_URI)
_db = _client[settings.MONGODB_DB_NAME]
activity_logs: Collection = _db["activity_logs"]


def init_mongo_indexes() -> None:
    activity_logs.create_index([("created_at", DESCENDING)])
```

- [ ] **Step 2: Wire index creation into app startup**

In `main.py`, the current lifespan is:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
```

Replace with:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_mongo_indexes()
    yield
```

And add the import alongside the existing `from app.db.session import init_db` line:

```python
from app.db.mongo import init_mongo_indexes
from app.db.session import init_db
```

- [ ] **Step 3: Verify against a real Mongo instance**

Set `MONGODB_URI` in your `.env` to a real MongoDB Atlas connection string (create a free M0 cluster if you don't have one yet — Atlas UI walks through it) or a local `mongodb://localhost:27017` if you have `mongod` running.

Run: `python -c "from app.db.mongo import activity_logs, init_mongo_indexes; init_mongo_indexes(); print(list(activity_logs.list_indexes()))"`
Expected: prints the default `_id_` index plus a `created_at_-1` index, with no connection errors.

- [ ] **Step 4: Commit**

```bash
git add app/db/mongo.py main.py
git commit -m "feat: add MongoDB connection module"
```

---

### Task 3: Activity log schemas

**Files:**
- Modify: `app/schemas/activity_log.py` (full rewrite, 11 lines)

**Interfaces:**
- Produces: `ActivityLogResponse` (`id: str`, `user_id: int | None`, `username: str | None`, `action: str`, `details: dict | str | None`, `ip_address: str | None`, `created_at: datetime`), `ActivityEventCreate` (`action: str`, `details: dict | None = None`)

- [ ] **Step 1: Rewrite the schema file**

```python
# app/schemas/activity_log.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class ActivityLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: int | None
    username: str | None
    action: str
    details: dict | str | None
    ip_address: str | None
    created_at: datetime

class ActivityEventCreate(BaseModel):
    action: str
    details: dict | None = None
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `python -c "from app.schemas.activity_log import ActivityLogResponse, ActivityEventCreate; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add app/schemas/activity_log.py
git commit -m "feat: update activity log schemas for MongoDB shape"
```

---

### Task 4: Rewrite activity logging end-to-end (service, model removal, call sites)

This is one task because the pieces are inseparable: changing `log_activity()`'s
signature requires updating every call site in the same change, and the old
SQL `ActivityLog` model can only be deleted once nothing imports it anymore.
Splitting this further would leave the app broken between commits.

**Files:**
- Modify: `app/services/activity_service.py` (full rewrite, 9 lines)
- Delete: `app/models/activity_log.py`
- Modify: `app/models/__init__.py:2`
- Modify: `app/db/session.py:16,28`
- Modify: `app/api/v1/auth.py:23,30,35`
- Modify: `app/api/v1/admin.py:24,33,42`
- Modify: `app/api/v1/chat.py:63,119,147,160,169`

**Interfaces:**
- Consumes: `app.db.mongo.activity_logs` (Task 2)
- Produces: `log_activity(user_id: int | None, username: str | None, action: str, details: dict | str | None = None, ip_address: str | None = None) -> None`

- [ ] **Step 1: Rewrite the activity service**

```python
# app/services/activity_service.py
import logging
from datetime import datetime, timezone

from app.db.mongo import activity_logs

logger = logging.getLogger(__name__)


def log_activity(
    user_id: int | None,
    username: str | None,
    action: str,
    details: dict | str | None = None,
    ip_address: str | None = None,
) -> None:
    try:
        activity_logs.insert_one(
            {
                "user_id": user_id,
                "username": username,
                "action": action,
                "details": details,
                "ip_address": ip_address,
                "created_at": datetime.now(timezone.utc),
            }
        )
    except Exception:
        logger.exception("Failed to write activity log for action=%s", action)
```

- [ ] **Step 2: Delete the SQL model and its references**

Delete `app/models/activity_log.py`.

In `app/models/__init__.py`, remove line 2 (`from app.models.activity_log import ActivityLog`), leaving:

```python
from app.models.user import User, UserRole
from app.models.chat import ChatMessage
```

In `app/db/session.py`, change line 16 from:

```python
    from app.models import ActivityLog, ChatMessage, User  # noqa: F401
```

to:

```python
    from app.models import ChatMessage, User  # noqa: F401
```

And change line 28 from:

```python
    required = {"users", "activity_logs", "chat_messages"}
```

to:

```python
    required = {"users", "chat_messages"}
```

- [ ] **Step 3: Update call sites in `app/api/v1/auth.py`**

Line 23, inside `register()`, change:

```python
    log_activity(db, user.id, "REGISTER", "Account created", request.client.host if request.client else None)
```

to:

```python
    log_activity(user.id, user.username, "REGISTER", "Account created", request.client.host if request.client else None)
```

Line 30, inside `login()` (failed-login branch), change:

```python
        log_activity(db, user.id if user else None, "LOGIN_FAILED", f"Username: {form_data.username}", request.client.host if request.client else None)
```

to:

```python
        log_activity(user.id if user else None, user.username if user else form_data.username, "LOGIN_FAILED", f"Attempted username: {form_data.username}", request.client.host if request.client else None)
```

Line 35, inside `login()` (success branch), change:

```python
    log_activity(db, user.id, "LOGIN_SUCCESS", None, request.client.host if request.client else None)
```

to:

```python
    log_activity(user.id, user.username, "LOGIN_SUCCESS", None, request.client.host if request.client else None)
```

- [ ] **Step 4: Update call sites in `app/api/v1/admin.py`**

Line 24, inside `create_user()`, change:

```python
    log_activity(db, current_user.id, "ADMIN_CREATE_USER", f"Created user {user.username} as {user.role.value}", request.client.host if request.client else None)
```

to:

```python
    log_activity(current_user.id, current_user.username, "ADMIN_CREATE_USER", f"Created user {user.username} as {user.role.value}", request.client.host if request.client else None)
```

Line 33, inside `update_role()`, change:

```python
    log_activity(db, current_user.id, "ADMIN_CHANGE_ROLE", f"User {user.username} -> {user.role.value}", request.client.host if request.client else None)
```

to:

```python
    log_activity(current_user.id, current_user.username, "ADMIN_CHANGE_ROLE", f"User {user.username} -> {user.role.value}", request.client.host if request.client else None)
```

Line 42, inside `update_status()`, change:

```python
    log_activity(db, current_user.id, "ADMIN_CHANGE_STATUS", f"User {user.username} active={user.is_active}", request.client.host if request.client else None)
```

to:

```python
    log_activity(current_user.id, current_user.username, "ADMIN_CHANGE_STATUS", f"User {user.username} active={user.is_active}", request.client.host if request.client else None)
```

- [ ] **Step 5: Update call sites in `app/api/v1/chat.py`**

Line 63, inside `send_message()`, change:

```python
    log_activity(db, current_user.id, "CHAT_MESSAGE", f"Prompt length: {len(text)}", request.client.host if request.client else None)
```

to:

```python
    log_activity(current_user.id, current_user.username, "CHAT_MESSAGE", f"Prompt length: {len(text)}", request.client.host if request.client else None)
```

Line 119, inside `websocket_chat()`, change:

```python
            log_activity(db, user.id, "CHAT_MESSAGE", f"Message length: {len(text)}", None)
```

to:

```python
            log_activity(user.id, user.username, "CHAT_MESSAGE", f"Message length: {len(text)}", None)
```

Line 147, inside `delete_message()`, change:

```python
    log_activity(db, current_user.id, "MOD_DELETE_MESSAGE", f"Deleted message {message_id}", request.client.host if request.client else None)
```

to:

```python
    log_activity(current_user.id, current_user.username, "MOD_DELETE_MESSAGE", f"Deleted message {message_id}", request.client.host if request.client else None)
```

Line 160, inside `mute_user()`, change:

```python
    log_activity(db, current_user.id, "MOD_MUTE_USER", f"Muted {user.username} for 10 minutes. {payload.reason}", request.client.host if request.client else None)
```

to:

```python
    log_activity(current_user.id, current_user.username, "MOD_MUTE_USER", f"Muted {user.username} for 10 minutes. {payload.reason}", request.client.host if request.client else None)
```

Line 169, inside `warn_user()`, change:

```python
    log_activity(db, current_user.id, "MOD_WARN_USER", f"Warned {user.username}. {payload.reason}", request.client.host if request.client else None)
```

to:

```python
    log_activity(current_user.id, current_user.username, "MOD_WARN_USER", f"Warned {user.username}. {payload.reason}", request.client.host if request.client else None)
```

- [ ] **Step 6: Verify end-to-end**

Run: `python scripts/init_db.py`
Expected: prints success. Then confirm the `activity_logs` table is gone:

Run: `python -c "from sqlalchemy import inspect; from app.db.session import engine; print(inspect(engine).get_table_names())"`
Expected: prints a list containing only `users` and `chat_messages`.

Run: `uvicorn main:app --reload` and in another terminal:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/register -H "Content-Type: application/json" -d "{\"username\":\"tester1\",\"email\":\"tester1@example.com\",\"password\":\"testpass123\"}"
```

Expected: `201` with the created user. Then check Mongo:

```bash
python -c "from app.db.mongo import activity_logs; print(list(activity_logs.find().sort('created_at', -1).limit(1)))"
```

Expected: one document with `action: "REGISTER"` and `username: "tester1"`.

- [ ] **Step 7: Commit**

```bash
git add app/services/activity_service.py app/models/__init__.py app/db/session.py app/api/v1/auth.py app/api/v1/admin.py app/api/v1/chat.py
git rm app/models/activity_log.py
git commit -m "feat: move activity logging to MongoDB"
```

---

### Task 5: Activity logs router — ADMIN-only feed + generic event endpoint

**Files:**
- Modify: `app/api/v1/activity_logs.py` (full rewrite, 15 lines)

**Interfaces:**
- Consumes: `app.db.mongo.activity_logs` (Task 2), `ActivityLogResponse`/`ActivityEventCreate` (Task 3), `log_activity` (Task 4), `RequireRole`/`get_current_user` (`app/api/dependencies.py`, unchanged)
- Produces: `GET /api/v1/logs/` (ADMIN-only), `POST /api/v1/logs/event` (any authenticated role)

- [ ] **Step 1: Rewrite the router**

```python
# app/api/v1/activity_logs.py
from fastapi import APIRouter, Depends, Request

from app.api.dependencies import RequireRole, get_current_user
from app.db.mongo import activity_logs
from app.models.user import User, UserRole
from app.schemas.activity_log import ActivityEventCreate, ActivityLogResponse
from app.services.activity_service import log_activity

router = APIRouter(prefix="/logs", tags=["Activity Audit"])
admin_only = RequireRole([UserRole.ADMIN])


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.get("/", response_model=list[ActivityLogResponse], dependencies=[Depends(admin_only)])
def get_activity_logs():
    rows = activity_logs.find().sort("created_at", -1).limit(500)
    return [_serialize(row) for row in rows]


@router.post("/event", status_code=201)
def create_event(payload: ActivityEventCreate, request: Request, current_user: User = Depends(get_current_user)):
    log_activity(
        current_user.id,
        current_user.username,
        payload.action,
        payload.details,
        request.client.host if request.client else None,
    )
    return {"ok": True}
```

- [ ] **Step 2: Verify ADMIN-only access and the event endpoint**

With the server running and using tokens obtained via `/api/v1/auth/login` for a MODERATOR and a USER test account (create one of each via `scripts/create_admin.py` for the admin, and normal registration + a role change via `/api/v1/admin/users/{id}/role` for the moderator):

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/v1/logs/ -H "Authorization: Bearer <moderator_token>"
```
Expected: `403`.

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/v1/logs/ -H "Authorization: Bearer <admin_token>"
```
Expected: `200` with a JSON array.

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/logs/event -H "Authorization: Bearer <any_valid_token>" -H "Content-Type: application/json" -d "{\"action\":\"TAB_SWITCH\",\"details\":{\"tab\":\"register\"}}"
```
Expected: `201` `{"ok": true}`, and the event shows up when the admin fetches `/api/v1/logs/`.

- [ ] **Step 3: Commit**

```bash
git add app/api/v1/activity_logs.py
git commit -m "feat: restrict activity log feed to ADMIN, add generic event endpoint"
```

---

### Task 6: Frontend event tracking and admin activity log panel

**Files:**
- Modify: `static/index.html` (JS section, lines 19-39, and the `adminDash` markup on line 16)

**Interfaces:**
- Consumes: `POST /api/v1/logs/event`, `GET /api/v1/logs/` (Task 5)

- [ ] **Step 1: Add the `trackEvent` helper**

In the `<script>` block, right after the line defining `authHeaders`/`read`/`status`/`toast` (the line starting `function authHeaders(){...}`), add:

```javascript
function trackEvent(action,details){if(!token)return;fetch(API+'/logs/event',{method:'POST',headers:authHeaders(),body:JSON.stringify({action,details:details||null})}).catch(()=>{})}
```

- [ ] **Step 2: Wire it into the existing interaction points**

In `tab(x)`, change:

```javascript
function tab(x){$('loginPane').classList.toggle('hidden',x!=='login');$('registerPane').classList.toggle('hidden',x!=='register');$('tabLogin').classList.toggle('active',x==='login');$('tabRegister').classList.toggle('active',x==='register');status('')}
```

to:

```javascript
function tab(x){trackEvent('TAB_SWITCH',{tab:x});$('loginPane').classList.toggle('hidden',x!=='login');$('registerPane').classList.toggle('hidden',x!=='register');$('tabLogin').classList.toggle('active',x==='login');$('tabRegister').classList.toggle('active',x==='register');status('')}
```

In `send()`, change:

```javascript
async function send(){const v=$('message').value.trim();if(!v)return;$('message').value='';if(!ws||ws.readyState!==WebSocket.OPEN){toast('Real-time link is offline.');return}ws.send(JSON.stringify({message:v}))}
```

to:

```javascript
async function send(){const v=$('message').value.trim();if(!v)return;$('message').value='';if(!ws||ws.readyState!==WebSocket.OPEN){toast('Real-time link is offline.');return}trackEvent('SEND_MESSAGE',{length:v.length});ws.send(JSON.stringify({message:v}))}
```

In `login()`, change:

```javascript
async function login(){try{const b=new URLSearchParams({username:$('luser').value.trim(),password:$('lpass').value});const r=await fetch(API+'/auth/login',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:b});const x=await read(r);if(!r.ok){status(x.detail||'ACCESS DENIED');return}token=x.access_token;localStorage.setItem('token',token);await load()}catch(e){status('NODE OFFLINE: '+e.message)}}
```

to:

```javascript
async function login(){try{const b=new URLSearchParams({username:$('luser').value.trim(),password:$('lpass').value});const r=await fetch(API+'/auth/login',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:b});const x=await read(r);if(!r.ok){status(x.detail||'ACCESS DENIED');return}token=x.access_token;localStorage.setItem('token',token);trackEvent('LOGIN');await load()}catch(e){status('NODE OFFLINE: '+e.message)}}
```

In `register()`, change:

```javascript
async function register(){try{const r=await fetch(API+'/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:$('ruser').value.trim(),email:$('remail').value.trim(),password:$('rpass').value})});const x=await read(r);if(!r.ok){status(x.detail||'REGISTRATION FAILED');return}$('luser').value=$('ruser').value.trim();$('lpass').value=$('rpass').value;status('IDENTITY CREATED // AUTHENTICATING...',true);await login()}catch(e){status('NODE OFFLINE: '+e.message)}}
```

to:

```javascript
async function register(){try{const r=await fetch(API+'/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:$('ruser').value.trim(),email:$('remail').value.trim(),password:$('rpass').value})});const x=await read(r);if(!r.ok){status(x.detail||'REGISTRATION FAILED');return}$('luser').value=$('ruser').value.trim();$('lpass').value=$('rpass').value;status('IDENTITY CREATED // AUTHENTICATING...',true);await login();trackEvent('REGISTER')}catch(e){status('NODE OFFLINE: '+e.message)}}
```

In `deleteMsg()`, change:

```javascript
async function deleteMsg(id){const r=await fetch(API+'/chat/'+id,{method:'DELETE',headers:authHeaders()});const x=await read(r);if(!r.ok)toast(x.detail||'Delete failed')}
```

to:

```javascript
async function deleteMsg(id){trackEvent('DELETE_MESSAGE',{id});const r=await fetch(API+'/chat/'+id,{method:'DELETE',headers:authHeaders()});const x=await read(r);if(!r.ok)toast(x.detail||'Delete failed')}
```

In `moderate()`, change:

```javascript
async function moderate(id,kind){const reason=prompt(kind==='warn'?'Warning reason:':'Mute reason:','Chat moderation');if(reason===null)return;const r=await fetch(API+`/chat/moderation/${id}/${kind}`,{method:'POST',headers:authHeaders(),body:JSON.stringify({reason})});const x=await read(r);toast(r.ok?(kind==='mute'?'User muted for 10 minutes.':'Warning recorded.'):(x.detail||'Action failed'))}
```

to:

```javascript
async function moderate(id,kind){const reason=prompt(kind==='warn'?'Warning reason:':'Mute reason:','Chat moderation');if(reason===null)return;trackEvent('MODERATE',{id,kind});const r=await fetch(API+`/chat/moderation/${id}/${kind}`,{method:'POST',headers:authHeaders(),body:JSON.stringify({reason})});const x=await read(r);toast(r.ok?(kind==='mute'?'User muted for 10 minutes.':'Warning recorded.'):(x.detail||'Action failed'))}
```

In `changeRole()`, change:

```javascript
async function changeRole(id,role){const r=await fetch(API+'/admin/users/'+id+'/role',{method:'PATCH',headers:authHeaders(),body:JSON.stringify({role})});const x=await read(r);if(!r.ok)toast(x.detail||'Role update failed');else{toast('Role updated.');loadAdminUsers()}}
```

to:

```javascript
async function changeRole(id,role){trackEvent('CHANGE_ROLE',{id,role});const r=await fetch(API+'/admin/users/'+id+'/role',{method:'PATCH',headers:authHeaders(),body:JSON.stringify({role})});const x=await read(r);if(!r.ok)toast(x.detail||'Role update failed');else{toast('Role updated.');loadAdminUsers()}}
```

In `toggleStatus()`, change:

```javascript
async function toggleStatus(id,current){const r=await fetch(API+'/admin/users/'+id+'/status',{method:'PATCH',headers:authHeaders(),body:JSON.stringify({is_active:!current})});const x=await read(r);if(!r.ok)toast(x.detail||'Status update failed');else{toast('Account status updated.');loadAdminUsers()}}
```

to:

```javascript
async function toggleStatus(id,current){trackEvent('TOGGLE_STATUS',{id,newStatus:!current});const r=await fetch(API+'/admin/users/'+id+'/status',{method:'PATCH',headers:authHeaders(),body:JSON.stringify({is_active:!current})});const x=await read(r);if(!r.ok)toast(x.detail||'Status update failed');else{toast('Account status updated.');loadAdminUsers()}}
```

In `logout()`, change (note: track *before* clearing `token`, since `trackEvent` no-ops without one):

```javascript
function logout(){if(ws)try{ws.close()}catch{};ws=null;token=null;me=null;localStorage.removeItem('token');$('app').classList.add('hidden');$('dashboard').classList.add('hidden');$('auth').classList.remove('hidden');tab('login')}
```

to:

```javascript
function logout(){trackEvent('LOGOUT');if(ws)try{ws.close()}catch{};ws=null;token=null;me=null;localStorage.removeItem('token');$('app').classList.add('hidden');$('dashboard').classList.add('hidden');$('auth').classList.remove('hidden');tab('login')}
```

Find the `$('clearBtn').onclick=...` line (inside the final event-wiring line) and change:

```javascript
$('clearBtn').onclick=()=>{$('chat').innerHTML='<div class="empty">VIEW CLEARED<br><span>Messages remain stored for everyone.</span></div>'};
```

to:

```javascript
$('clearBtn').onclick=()=>{trackEvent('CLEAR_VIEW');$('chat').innerHTML='<div class="empty">VIEW CLEARED<br><span>Messages remain stored for everyone.</span></div>'};
```

- [ ] **Step 3: Add the admin activity log panel**

In the HTML markup, change the `adminDash` div:

```html
<div id="adminDash" class="panel dash hidden"><h3>ADMIN CONTROL CENTER</h3><div class="sub">Admins manage users, roles and account status.</div><div id="adminUsers" style="margin-top:12px"></div></div>
```

to:

```html
<div id="adminDash" class="panel dash hidden"><h3>ADMIN CONTROL CENTER</h3><div class="sub">Admins manage users, roles and account status.</div><div id="adminUsers" style="margin-top:12px"></div><h3 style="margin-top:20px">ACTIVITY LOG</h3><div class="sub">Most recent 500 events across all users.</div><div id="activityLog" style="margin-top:12px"></div></div>
```

Add a loader function next to `loadAdminUsers`:

```javascript
async function loadActivityLog(){const r=await fetch(API+'/logs/',{headers:authHeaders()});if(!r.ok)return;const rows=await r.json();$('activityLog').innerHTML=`<table class="table"><tr><th>TIME</th><th>USER</th><th>ACTION</th><th>DETAILS</th></tr>${rows.map(l=>`<tr><td>${new Date(l.created_at).toLocaleString()}</td><td>${esc(l.username||'SYSTEM')}</td><td>${esc(l.action)}</td><td>${esc(typeof l.details==='object'&&l.details!==null?JSON.stringify(l.details):(l.details||''))}</td></tr>`).join('')}</table>`}
```

In `load()`, change:

```javascript
if(u.role==='ADMIN')loadAdminUsers()}
```

to:

```javascript
if(u.role==='ADMIN'){loadAdminUsers();loadActivityLog()}}
```

- [ ] **Step 4: Verify in the browser**

Run: `uvicorn main:app --reload`, open `http://127.0.0.1:8000` in two browser windows.

1. Register two users, log in as each, send messages, switch tabs, click "CLEAR VIEW".
2. Promote one to ADMIN via `scripts/create_admin.py` (or log in as an existing admin) and confirm the "ACTIVITY LOG" table appears under the admin console, listing `TAB_SWITCH`, `SEND_MESSAGE`, `LOGIN`, `REGISTER`, `CLEAR_VIEW` entries alongside the existing server-side actions (`CHAT_MESSAGE`, `LOGIN_SUCCESS`, etc.).
3. Log in as a MODERATOR (if you have one) and confirm no activity log panel/errors appear — moderators never call `GET /logs/` from the frontend, so this should be silent.

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat: add frontend event tracking and admin activity log panel"
```
