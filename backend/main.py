from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import json
import os
import shutil
import uuid
import datetime
import httpx

app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bangumi OAuth Config
BGM_CLIENT_ID = os.getenv("BGM_CLIENT_ID", "default_id")
BGM_CLIENT_SECRET = os.getenv("BGM_CLIENT_SECRET", "default_secret")
BGM_REDIRECT_URI = os.getenv("BGM_REDIRECT_URI", "http://localhost:8000/api/auth/callback")

DATA_FILE = "data.json"
IMAGES_DIR = "images"
USERS_FILE = "users.json"
ADMINS_FILE = "admins.json"
HISTORY_FILE = "history.json"

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else []
    except (json.JSONDecodeError, IOError):
        return []

def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except IOError:
        pass

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except (json.JSONDecodeError, IOError):
        return {}

def save_users(users):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    except IOError:
        pass

def get_user_quota(user_id: str):
    users = load_users()
    today = str(datetime.date.today())
    if user_id not in users:
        users[user_id] = {"last_date": today, "adds": 0, "edits": 0, "deletes": 0}
    
    user = users[user_id]
    if user.get("last_date") != today:
        user["last_date"] = today
        user["adds"] = 0
        user["edits"] = 0
        user["deletes"] = 0
    
    save_users(users)
    return user

def load_admins():
    if not os.path.exists(ADMINS_FILE):
        return ["1173408"]
    try:
        with open(ADMINS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            admins = json.loads(content) if content else ["1173408"]
            return admins if isinstance(admins, list) else ["1173408"]
    except (json.JSONDecodeError, IOError):
        return ["1173408"]

def check_permission(user_id: str, action: str):
    if user_id == "guest":
        return False
    admins = load_admins()
    if user_id in admins:
        return True
    
    user = get_user_quota(user_id)
    if action == "add" and user["adds"] >= 1: return False
    if action == "edit" and user["edits"] >= 1: return False
    if action == "delete" and user["deletes"] >= 1: return False
    return True

def record_action(user_id: str, action: str, node_id: int, node_name: str, nickname: str = "未知用户"):
    # Record history
    history = load_history()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    admins = load_admins()
    role = "admin" if user_id in admins else "user"
    
    history.append({
        "time": now,
        "user_id": user_id,
        "nickname": nickname,
        "role": role,
        "node_id": node_id,
        "node_name": node_name,
        "action": action
    })
    save_history(history)

    # Record quota
    if user_id in admins: return
    users = load_users()
    if action == "add": users[user_id]["adds"] += 1
    elif action == "edit": users[user_id]["edits"] += 1
    elif action == "delete": users[user_id]["deletes"] += 1
    save_users(users)

# Ensure images directory exists
os.makedirs(IMAGES_DIR, exist_ok=True)

# Mount images directory to serve static files
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"nodes": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- Auth Routes ---

@app.get("/api/auth/login")
def login():
    # Redirect user to Bangumi
    auth_url = f"https://bgm.tv/oauth/authorize?client_id={BGM_CLIENT_ID}&response_type=code&redirect_uri={BGM_REDIRECT_URI}"
    return {"url": auth_url}

@app.get("/api/auth/callback")
async def auth_callback(code: str):
    async with httpx.AsyncClient() as client:
        # 1. Exchange code for access token
        token_resp = await client.post("https://bgm.tv/oauth/access_token", data={
            "grant_type": "authorization_code",
            "client_id": BGM_CLIENT_ID,
            "client_secret": BGM_CLIENT_SECRET,
            "code": code,
            "redirect_uri": BGM_REDIRECT_URI
        })
        token_data = token_resp.json()
        if "access_token" not in token_data:
            raise HTTPException(400, "Failed to get access token")
        
        access_token = token_data["access_token"]
        user_id = str(token_data["user_id"])
        
        # 2. Get user profile to get the real nick (optional but good for display)
        profile_resp = await client.get("https://api.bgm.tv/v0/me", headers={
            "Authorization": f"Bearer {access_token}"
        })
        profile = profile_resp.json()
        nickname = profile.get("nickname", access_token[:8])
        
        # In a real app, you'd set a secure cookie or JWT here.
        # For this setup, we redirect back to frontend with info in query params
        base_frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173/")
        # Ensure it ends with /
        if not base_frontend_url.endswith("/"):
            base_frontend_url += "/"
        
        frontend_url = f"{base_frontend_url}?user_id={user_id}&nickname={nickname}"
        return Response(status_code=302, headers={"Location": frontend_url})

# --- Node Routes ---

@app.get("/api/nodes")
def get_nodes():
    return load_data()

@app.get("/api/user/info")
def get_user_info(user_id: str = "guest", nickname: str = "游客"):
    if user_id == "guest":
        return {"logged_in": False, "role": "visitor"}
    
    admins = load_admins()
    quota = get_user_quota(user_id)
    role = "admin" if user_id in admins else "user"
    return {
        "logged_in": True,
        "user_id": user_id,
        "nickname": nickname,
        "role": role,
        "quota": quota
    }

@app.post("/api/nodes")
def add_node(
    name: str = Form(...),
    source: str = Form(...),
    related: str = Form(...),
    tags: str = Form(...),
    extension: str = Form(...),
    introduction: str = Form(""),
    x: float = Form(0.0),
    y: float = Form(0.0),
    user_id: str = Form("guest"),
    nickname: str = Form("未知用户"),
    parent_id: Optional[int] = Form(None),
    image: Optional[UploadFile] = File(None)
):
    if user_id == "guest":
        raise HTTPException(403, "游客状态-请登录后进行新增")
    if not check_permission(user_id, "add"):
        raise HTTPException(403, "普通用户-你今天已经新增了一个爱音了，明天再来吧")
    
    data = load_data()
    nodes = data.get("nodes", [])
    
    new_id = max([n.get("id", 0) for n in nodes], default=0) + 1
    
    image_url = ""
    if image:
        ext = image.filename.split(".")[-1]
        filename = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(IMAGES_DIR, filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        image_url = f"/images/{filename}"
    
    new_node = {
        "id": new_id,
        "name": name,
        "image": image_url,
        "source": json.loads(source),
        "related": json.loads(related),
        "tags": json.loads(tags),
        "extension": json.loads(extension),
        "introduction": introduction,
        "x": x,
        "y": y
    }
    
    # Automatic connection from parent to new node
    if parent_id is not None:
        parent = next((n for n in nodes if n["id"] == parent_id), None)
        if parent:
            if "extension" not in parent:
                parent["extension"] = []
            if new_id not in parent["extension"]:
                parent["extension"].append(new_id)

    nodes.append(new_node)
    data["nodes"] = nodes
    save_data(data)
    record_action(user_id, "add", new_node["id"], new_node["name"], nickname)
    return new_node

@app.put("/api/nodes/{node_id}")
def update_node(
    node_id: int,
    name: str = Form(...),
    source: str = Form(...),
    related: str = Form(...),
    tags: str = Form(...),
    extension: str = Form(...),
    introduction: str = Form(""),
    user_id: str = Form("guest"),
    nickname: str = Form("未知用户"),
    image: Optional[UploadFile] = File(None)
):
    if user_id == "guest":
        raise HTTPException(403, "游客状态-请登录后进行修改")
    if not check_permission(user_id, "edit"):
        raise HTTPException(403, "普通用户-你今天已经修改了一个爱音了，明天再来吧")
        
    data = load_data()
    nodes = data.get("nodes", [])
    
    node_idx = next((i for i, n in enumerate(nodes) if n["id"] == node_id), None)
    if node_idx is None:
        raise HTTPException(status_code=404, detail="Node not found")
        
    node = nodes[node_idx]
    
    if image:
        ext = image.filename.split(".")[-1]
        filename = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(IMAGES_DIR, filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        node["image"] = f"/images/{filename}"
        
    node["name"] = name
    node["source"] = json.loads(source)
    node["related"] = json.loads(related)
    node["tags"] = json.loads(tags)
    node["extension"] = json.loads(extension)
    node["introduction"] = introduction
    
    save_data(data)
    record_action(user_id, "edit", node["id"], node["name"], nickname)
    return node

@app.delete("/api/nodes/{node_id}")
def delete_node(node_id: int, user_id: str = "guest", nickname: str = "未知用户"):
    if user_id == "guest":
        raise HTTPException(403, "游客状态-请登录后进行删除")
    if not check_permission(user_id, "delete"):
        raise HTTPException(403, "普通用户-你今天已经删除了一个爱音了，明天再来吧")
        
    data = load_data()
    nodes = data.get("nodes", [])
    
    node_idx = next((i for i, n in enumerate(nodes) if n["id"] == node_id), None)
    if (node_idx is None):
        raise HTTPException(status_code=404, detail="Node not found")
    
    node = nodes[node_idx]
    
    # Check if any other node's extension points to this node? (Referenced elsewhere)
    # The requirement: if it has extensions (children), it cannot be deleted.
    if ("extension" in node and len(node["extension"]) > 0):
        # Specific block: if this node has sub-nodes (branches), it cannot be deleted unless children are gone.
        raise HTTPException(
            status_code=400, 
            detail=f"该形象「{node['name']}」尚有后续的分支/后辈节点，无法删除（请先删除其关联的所有后辈形象）。"
        )

    # Special protection for the root node if it's the only one of its kind? 
    # Or as the user mentioned: "只要有一个其他爱音存在，id为1的千早爱音就是不能删除的"
    if (node_id == 1 and len(nodes) > 1):
        raise HTTPException(status_code=400, detail="根节点爱音受到宇宙法则保护，在其他爱音被清理完之前不可删除。")
        
    # Remove extensions pointing to this node
    for n in nodes:
        if "extension" in n and node_id in n["extension"]:
            n["extension"].remove(node_id)
        # Handle old key if it exists
        if "connections" in n and node_id in n["connections"]:
            n["connections"].remove(node_id)
            
    deleted_name = nodes[node_idx]["name"]
    nodes.pop(node_idx)
    data["nodes"] = nodes
    save_data(data)
    record_action(user_id, "delete", node_id, deleted_name, nickname)
    return {"message": "Node deleted successfully"}

@app.get("/api/history")
def get_history(node_id: Optional[int] = None):
    history = load_history()
    if node_id is not None:
        # Filter by node_id and only return the last 10 records for that node
        node_history = [h for h in history if h.get("node_id") == node_id]
        return node_history[-10:][::-1]
    
    # Return global history limited to the last 100 records
    return history[-100:][::-1]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
