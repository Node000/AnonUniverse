from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import json
import os
import shutil
import uuid
from datetime import date
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
BGM_CLIENT_ID = "bgm5638699e79a509c04"
BGM_CLIENT_SECRET = "bc249e0d9b9dd71e5d225253e5cc23a2"
BGM_REDIRECT_URI = "http://localhost:8000/api/auth/callback" # This should match your Bangumi App settings

DATA_FILE = "data.json"
IMAGES_DIR = "images"
USERS_FILE = "users.json"
ADMINS = ["1173408"] # Bangumi User IDs

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def get_user_quota(user_id: str):
    users = load_users()
    today = str(date.today())
    if user_id not in users:
        users[user_id] = {"last_date": today, "adds": 0, "edits": 0, "deletes": 0}
    
    user = users[user_id]
    if user["last_date"] != today:
        user["last_date"] = today
        user["adds"] = 0
        user["edits"] = 0
        user["deletes"] = 0
    
    save_users(users)
    return user

def check_permission(user_id: str, action: str):
    if user_id == "guest":
        return False
    if user_id in ADMINS:
        return True
    
    user = get_user_quota(user_id)
    if action == "add" and user["adds"] >= 1: return False
    if action == "edit" and user["edits"] >= 1: return False
    if action == "delete" and user["deletes"] >= 1: return False
    return True

def record_action(user_id: str, action: str):
    if user_id in ADMINS: return
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
        # For this simple setup, we'll redirect back to frontend with info in query params
        # (Note: This is just for demonstration; use better session management for production)
        frontend_url = f"http://localhost:5173/?user_id={user_id}&nickname={nickname}"
        return Response(status_code=302, headers={"Location": frontend_url})

# --- Node Routes ---

@app.get("/api/nodes")
def get_nodes():
    return load_data()

@app.get("/api/user/info")
def get_user_info(user_id: str = "guest", nickname: str = "游客"):
    if user_id == "guest":
        return {"logged_in": False, "role": "visitor"}
    
    quota = get_user_quota(user_id)
    role = "admin" if user_id in ADMINS else "user"
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
    connections: str = Form(...),
    x: float = Form(0.0),
    y: float = Form(0.0),
    user_id: str = Form("guest"),
    image: Optional[UploadFile] = File(None)
):
    if not check_permission(user_id, "add"):
        raise HTTPException(403, "今日新增次数已达上限或权限不足")
    
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
        "source": source,
        "related": related,
        "tags": json.loads(tags),
        "connections": json.loads(connections),
        "x": x,
        "y": y
    }
    
    nodes.append(new_node)
    data["nodes"] = nodes
    save_data(data)
    record_action(user_id, "add")
    return new_node

@app.put("/api/nodes/{node_id}/position")
def update_node_position(node_id: int, pos: dict):
    data = load_data()
    nodes = data.get("nodes", [])
    node = next((n for n in nodes if n["id"] == node_id), None)
    if node:
        node["x"] = pos.get("x", 0)
        node["y"] = pos.get("y", 0)
        save_data(data)
    return {"status": "ok"}

@app.put("/api/nodes/{node_id}")
def update_node(
    node_id: int,
    name: str = Form(...),
    source: str = Form(...),
    related: str = Form(...),
    tags: str = Form(...),
    connections: str = Form(...),
    user_id: str = Form("guest"),
    image: Optional[UploadFile] = File(None)
):
    if not check_permission(user_id, "edit"):
        raise HTTPException(403, "今日修改次数已达上限或权限不足")
        
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
    node["source"] = source
    node["related"] = related
    node["tags"] = json.loads(tags)
    node["connections"] = json.loads(connections)
    
    save_data(data)
    record_action(user_id, "edit")
    return node

@app.delete("/api/nodes/{node_id}")
def delete_node(node_id: int, user_id: str = "guest"):
    if not check_permission(user_id, "delete"):
        raise HTTPException(403, "今日删除次数已达上限或权限不足")
        
    data = load_data()
    nodes = data.get("nodes", [])
    
    node_idx = next((i for i, n in enumerate(nodes) if n["id"] == node_id), None)
    if node_idx is None:
        raise HTTPException(status_code=404, detail="Node not found")
        
    # Remove connections to this node
    for n in nodes:
        if node_id in n.get("connections", []):
            n["connections"].remove(node_id)
            
    nodes.pop(node_idx)
    data["nodes"] = nodes
    save_data(data)
    record_action(user_id, "delete")
    return {"message": "Node deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
