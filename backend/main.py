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
import urllib.parse

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

DATA_DIR = "data"
IMAGES_DIR = "images"
USERS_FILE = "users.json"
ADMINS_FILE = "admins.json"
HISTORY_FILE = "history.json"
APPLICATIONS_FILE = "applications.json"

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

def load_data():
    nodes = []
    if os.path.exists(DATA_DIR):
        for filename in os.listdir(DATA_DIR):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(DATA_DIR, filename), "r", encoding="utf-8") as f:
                        node = json.load(f)
                        nodes.append(node)
                except (json.JSONDecodeError, IOError):
                    continue
    return {"nodes": nodes}

def save_node(node):
    node_id = node.get("id")
    if node_id is None:
        return
    with open(os.path.join(DATA_DIR, f"{node_id}.json"), "w", encoding="utf-8") as f:
        json.dump(node, f, ensure_ascii=False, indent=2)

def delete_node_file(node_id: int):
    # Load node data to find image path
    file_path = os.path.join(DATA_DIR, f"{node_id}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                node = json.load(f)
                image_url = node.get("image", "")
                # Delete image if it is not default
                if image_url and not image_url.endswith("default.png") and image_url.startswith("/images/"):
                    image_path = image_url.lstrip("/")
                    if os.path.exists(image_path):
                        os.remove(image_path)
        except:
            pass
        os.remove(file_path)

def load_applications():
    if not os.path.exists(APPLICATIONS_FILE):
        return []
    try:
        with open(APPLICATIONS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else []
    except (json.JSONDecodeError, IOError):
        return []

def save_applications(apps):
    try:
        with open(APPLICATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(apps, f, ensure_ascii=False, indent=2)
    except IOError:
        pass

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
        users[user_id] = {"last_date": today, "adds": 0, "edits": 0, "deletes": 0, "applies": 0}
    
    user = users[user_id]
    if user.get("last_date") != today:
        user["last_date"] = today
        user["adds"] = 0
        user["edits"] = 0
        user["deletes"] = 0
        user["applies"] = 0
    
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
    if action == "add" and user["adds"] >= 10: return False
    if action == "edit" and user["edits"] >= 10: return False
    if action == "delete" and user["deletes"] >= 1: return False
    if action == "apply" and user["applies"] >= 1: return False
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
    elif action == "apply_famous": users[user_id]["applies"] += 1
    save_users(users)

# Ensure images directory exists
os.makedirs(IMAGES_DIR, exist_ok=True)

# Mount images directory to serve static files
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

# load_data is now at the top

# --- Auth Routes ---

@app.get("/api/auth/login")
def login():
    # Redirect user to Bangumi
    auth_url = f"https://bgm.tv/oauth/authorize?client_id={BGM_CLIENT_ID}&response_type=code&redirect_uri={BGM_REDIRECT_URI}"
    return {"url": auth_url}

@app.get("/api/auth/callback")
async def auth_callback(code: str):
    # Increased timeout to prevent ReadTimeout
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Exchange code for access token
        try:
            token_resp = await client.post("https://bgm.tv/oauth/access_token", data={
                "grant_type": "authorization_code",
                "client_id": BGM_CLIENT_ID,
                "client_secret": BGM_CLIENT_SECRET,
                "code": code,
                "redirect_uri": BGM_REDIRECT_URI
            })
            token_resp.raise_for_status()
        except httpx.HTTPError:
            raise HTTPException(400, "Failed to exchange token with Bangumi")
            
        token_data = token_resp.json()
        if "access_token" not in token_data:
            raise HTTPException(400, "Failed to get access token")
        
        access_token = token_data["access_token"]
        user_id = str(token_data["user_id"])
        
        # 2. Get user profile to get the real nick (optional but good for display)
        try:
            profile_resp = await client.get("https://api.bgm.tv/v0/me", headers={
                "Authorization": f"Bearer {access_token}"
            })
            if profile_resp.status_code == 200:
                profile = profile_resp.json()
                nickname = profile.get("nickname", "User_" + access_token[:8])
            else:
                nickname = "User_" + access_token[:8]
        except:
            nickname = "User_" + access_token[:8]
        
        # In a real app, you'd set a secure cookie or JWT here.
        # For this setup, we redirect back to frontend with info in query params
        base_frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173/")
        
        # Fix: UnicodeEncodeError - Use urllib.parse.quote for non-ASCII chars in headers
        redirect_params = {
            "user_id": user_id,
            "nickname": nickname
        }
        query_string = urllib.parse.urlencode(redirect_params)
        
        # Ensure base url has ? or & correctly
        if "?" in base_frontend_url:
            frontend_url = f"{base_frontend_url}&{query_string}"
        else:
            # Handle trailing slash logic if needed, but usually query params are fine
            if base_frontend_url.endswith("/"):
                 frontend_url = f"{base_frontend_url}?{query_string}"
            else:
                 frontend_url = f"{base_frontend_url}/?{query_string}"

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
        raise HTTPException(403, "普通用户-你今天已经新增了10个爱音了，明天再来吧")
    
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
        parent_file = os.path.join(DATA_DIR, f"{parent_id}.json")
        if os.path.exists(parent_file):
            with open(parent_file, "r", encoding="utf-8") as f:
                parent = json.load(f)
                if "extension" not in parent: parent["extension"] = []
                if new_id not in parent["extension"]:
                    parent["extension"].append(new_id)
                    save_node(parent)

    save_node(new_node)
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
        raise HTTPException(403, "普通用户-你今天已经修改了10个爱音了，明天再来吧")
        
    node_file = os.path.join(DATA_DIR, f"{node_id}.json")
    if not os.path.exists(node_file):
        raise HTTPException(status_code=404, detail="Node not found")
        
    with open(node_file, "r", encoding="utf-8") as f:
        node = json.load(f)
    
    if image:
        # Delete old image if it exists and is not default
        old_image = node.get("image", "")
        if old_image and not old_image.endswith("default.png") and old_image.startswith("/images/"):
            try:
                os.remove(old_image.lstrip("/"))
            except: pass

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
    
    save_node(node)
    record_action(user_id, "edit", node["id"], node["name"], nickname)
    return node

@app.patch("/api/nodes/{node_id}/position")
def update_node_position(
    node_id: int,
    x: float = Form(...),
    y: float = Form(...),
    user_id: str = Form("guest"),
    nickname: str = Form("未知用户")
):
    if user_id == "guest":
        raise HTTPException(403, "游客状态-请登录后进行修改")
    admins = load_admins()
    if user_id not in admins:
        raise HTTPException(403, "仅管理员可保存节点位置")
        
    node_file = os.path.join(DATA_DIR, f"{node_id}.json")
    if not os.path.exists(node_file):
        raise HTTPException(status_code=404, detail="Node not found")
        
    with open(node_file, "r", encoding="utf-8") as f:
        node = json.load(f)
    node["x"] = x
    node["y"] = y
    
    save_node(node)
    record_action(user_id, "edit", node["id"], node["name"], nickname)
    return node

@app.delete("/api/nodes/{node_id}")
def delete_node(node_id: int, user_id: str = "guest", nickname: str = "未知用户"):
    if user_id == "guest":
        raise HTTPException(403, "游客状态-请登录后进行删除")
    if not check_permission(user_id, "delete"):
        raise HTTPException(403, "普通用户-你今天已经删除了一个爱音了，明天再来吧")
        
    node_file = os.path.join(DATA_DIR, f"{node_id}.json")
    if not os.path.exists(node_file):
        raise HTTPException(status_code=404, detail="Node not found")
    
    with open(node_file, "r", encoding="utf-8") as f:
        node = json.load(f)
    
    if ("extension" in node and len(node["extension"]) > 0):
        raise HTTPException(
            status_code=400, 
            detail=f"该形象「{node['name']}」尚有后续的分支/后辈节点，无法删除（请先删除其关联的所有后辈形象）。"
        )

    other_nodes_exist = any(f.endswith(".json") and f != "1.json" for f in os.listdir(DATA_DIR))
    if (node_id == 1 and other_nodes_exist):
        raise HTTPException(status_code=400, detail="根节点爱音受到宇宙法则保护，在其他爱音被清理完之前不可删除。")
        
    deleted_name = node["name"]
    
    # Remove references from other nodes
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".json") and filename != f"{node_id}.json":
            other_file = os.path.join(DATA_DIR, filename)
            try:
                with open(other_file, "r", encoding="utf-8") as f:
                    other_node = json.load(f)
                changed = False
                if "extension" in other_node and node_id in other_node["extension"]:
                    other_node["extension"].remove(node_id)
                    changed = True
                if "connections" in other_node and node_id in other_node["connections"]:
                    other_node["connections"].remove(node_id)
                    changed = True
                if changed:
                    save_node(other_node)
            except: continue
            
    delete_node_file(node_id)
    record_action(user_id, "delete", node_id, deleted_name, nickname)
    return {"message": "Node deleted successfully"}
    
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

@app.get("/api/applications")
def get_applications(user_id: str = "guest"):
    if user_id == "guest":
        raise HTTPException(403, "Unauthorized")
    admins = load_admins()
    if user_id not in admins:
        raise HTTPException(403, "Unauthorized")
    return load_applications()

@app.post("/api/applications")
def apply_famous(
    node_id: int = Form(...),
    user_id: str = Form("guest"),
    nickname: str = Form("未知用户")
):
    if user_id == "guest":
        raise HTTPException(403, "请登录后操作")
    if not check_permission(user_id, "apply"):
        raise HTTPException(403, "今日申请次数已用完")
        
    node_file = os.path.join(DATA_DIR, f"{node_id}.json")
    if not os.path.exists(node_file):
        raise HTTPException(404, "Node not found")
        
    with open(node_file, "r", encoding="utf-8") as f:
        node = json.load(f)
        
    apps = load_applications()
    if any(a["node_id"] == node_id for a in apps):
        raise HTTPException(400, "该节点已在申请中")
        
    new_app = {
        "id": str(uuid.uuid4()),
        "node_id": node_id,
        "node_name": node["name"],
        "user_id": user_id,
        "nickname": nickname,
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    apps.append(new_app)
    save_applications(apps)
    
    # record_action will handle quota deduction
    record_action(user_id, "apply_famous", node_id, node["name"], nickname)
    return new_app

@app.post("/api/applications/{app_id}/process")
def process_application(
    app_id: str,
    action: str = Form(...),
    user_id: str = Form("guest"),
    nickname: str = Form("未知用户")
):
    admins = load_admins()
    if user_id not in admins:
        raise HTTPException(403, "Unauthorized")
        
    apps = load_applications()
    app_idx = next((i for i, a in enumerate(apps) if a["id"] == app_id), None)
    if app_idx is None:
        raise HTTPException(404, "Application not found")
        
    application = apps[app_idx]
    node_id = application["node_id"]
    node_name = application["node_name"]
    
    if action == "approve":
        node_file = os.path.join(DATA_DIR, f"{node_id}.json")
        if os.path.exists(node_file):
            with open(node_file, "r", encoding="utf-8") as f:
                node = json.load(f)
            node["is_famous"] = True
            save_node(node)
        record_action(user_id, "approve_famous", node_id, node_name, nickname)
    else:
        record_action(user_id, "reject_famous", node_id, node_name, nickname)
        
    apps.pop(app_idx)
    save_applications(apps)
    return {"message": "Processed"}

@app.patch("/api/nodes/{node_id}/famous")
def toggle_famous(
    node_id: int,
    is_famous: bool = Form(...),
    user_id: str = Form("guest"),
    nickname: str = Form("未知用户")
):
    admins = load_admins()
    if user_id not in admins:
        raise HTTPException(403, "Unauthorized")
        
    node_file = os.path.join(DATA_DIR, f"{node_id}.json")
    if not os.path.exists(node_file):
        raise HTTPException(404, "Node not found")
        
    with open(node_file, "r", encoding="utf-8") as f:
        node = json.load(f)
        
    node["is_famous"] = is_famous
    save_node(node)
    record_action(user_id, "edit", node_id, node["name"], nickname)
    return node

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
