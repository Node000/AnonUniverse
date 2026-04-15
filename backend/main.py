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
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def backend_path(*parts):
    return os.path.join(BASE_DIR, *parts)


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

DATA_DIR = backend_path("data")
IMAGES_DIR = backend_path("images")
USERS_DIR = backend_path("users")
ADMINS_FILE = backend_path("admins.json")
BANNED_FILE = backend_path("banned.json")
HISTORY_FILE = backend_path("history.json")
APPLICATIONS_FILE = backend_path("applications.json")
MAILBOX_FILE = backend_path("mailbox.json")
MAILBOX_HISTORY_FILE = backend_path("mailhistory.json")
HISTORY_ARCHIVE_FILE = backend_path("historyarchive.json")
BACKUP_DIR = backend_path("backups")


def image_storage_path(image_url: str):
    if not image_url or not image_url.startswith("/images/"):
        return None
    return os.path.join(IMAGES_DIR, os.path.basename(image_url))

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(USERS_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

def perform_data_backup():
    """
    备份 data 文件夹并保留最近 3 天的数据。
    增加了额外的日期锁文件检查，确保全站每天仅触发一次备份。
    """
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    lock_file = os.path.join(BACKUP_DIR, f".backup_done_{today_str}")
    backup_path = os.path.join(BACKUP_DIR, today_str)
    
    # 只要锁文件存在，说明今天已经备份过了
    if os.path.exists(lock_file):
        return

    # 执行备份
    if not os.path.exists(backup_path):
        try:
            shutil.copytree(DATA_DIR, backup_path)
            # 写入锁文件，防止其他用户再次触发
            with open(lock_file, "w") as f:
                f.write(datetime.datetime.now().strftime("%H:%M:%S"))
            print(f"Daily full backup completed to {backup_path}")
        except Exception as e:
            print(f"Backup failed: {e}")
            return # 失败时不执行清理
            
    # 清理 3 天前的备份和对应的锁文件
    try:
        all_items = os.listdir(BACKUP_DIR)
        dirs = sorted([d for d in all_items if os.path.isdir(os.path.join(BACKUP_DIR, d))])
        
        if len(dirs) > 3:
            for old_backup in dirs[:-3]:
                shutil.rmtree(os.path.join(BACKUP_DIR, old_backup))
                # 同时尝试清理旧的锁文件
                old_lock = os.path.join(BACKUP_DIR, f".backup_done_{old_backup}")
                if os.path.exists(old_lock):
                    os.remove(old_lock)
                print(f"Deleted expired backup and lock: {old_backup}")
    except Exception as e:
        print(f"Cleanup failed: {e}")

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

def clean_old_new_status():
    """
    遍历所有节点，检查 'new' 属性。如果创建于 3 天前，则移除 'new' 状态。
    """
    if not os.path.exists(DATA_DIR):
        return
    
    today = datetime.date.today()
    threshold = today - datetime.timedelta(days=3)
    
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(DATA_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    node = json.load(f)
                
                changed = False
                # 如果有 new 属性且为 True
                if node.get("new"):
                    created_at_str = node.get("time") # 格式: YYYY-MM-DD
                    if created_at_str:
                        try:
                            created_at = datetime.datetime.strptime(created_at_str, "%Y-%m-%d").date()
                            if created_at <= threshold:
                                node["new"] = False
                                changed = True
                        except ValueError:
                            pass
                
                if changed:
                    save_node(node)
            except Exception:
                continue

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
                    image_path = image_storage_path(image_url)
                    if image_path and os.path.exists(image_path):
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

def load_mailbox():
    if not os.path.exists(MAILBOX_FILE):
        return []
    try:
        with open(MAILBOX_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else []
    except (json.JSONDecodeError, IOError):
        return []

def save_mailbox(messages):
    try:
        with open(MAILBOX_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except IOError:
        pass

def load_mail_history():
    if not os.path.exists(MAILBOX_HISTORY_FILE):
        return []
    try:
        with open(MAILBOX_HISTORY_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else []
    except (json.JSONDecodeError, IOError):
        return []

def save_mail_history(history):
    try:
        with open(MAILBOX_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except IOError:
        pass

def archive_old_mail():
    messages = load_mailbox()
    if not messages:
        return
    
    today = datetime.datetime.now()
    threshold = today - datetime.timedelta(days=30)
    
    current_messages = []
    to_archive = []
    
    for msg in messages:
        try:
            msg_time = datetime.datetime.strptime(msg["time"], "%Y-%m-%d %H:%M:%S")
            if msg_time < threshold:
                to_archive.append(msg)
            else:
                current_messages.append(msg)
        except (ValueError, KeyError):
            current_messages.append(msg)
            
    if to_archive:
        history = load_mail_history()
        history.extend(to_archive)
        save_mail_history(history)
        save_mailbox(current_messages)

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

def load_history_archive():
    if not os.path.exists(HISTORY_ARCHIVE_FILE):
        return []
    try:
        with open(HISTORY_ARCHIVE_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else []
    except (json.JSONDecodeError, IOError):
        return []

def save_history_archive(archive):
    try:
        with open(HISTORY_ARCHIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(archive, f, ensure_ascii=False, indent=2)
    except IOError:
        pass

def archive_old_history():
    history = load_history()
    if len(history) <= 50:
        return
    
    # 按照时间从新到旧排序（假设 record_action 是 append 到末尾，所以最后面的是最新的）
    # 但为了保险，我们取最后 50 条作为保留，前面的移入归档
    to_archive = history[:-50]
    to_keep = history[-50:]
    
    if to_archive:
        archive = load_history_archive()
        archive.extend(to_archive)
        save_history_archive(archive)
        save_history(to_keep)

def load_users():
    """Deprecated: using individual files. Returns a fake dict for compatibility."""
    users = {}
    if os.path.exists(USERS_DIR):
        for filename in os.listdir(USERS_DIR):
            if filename.endswith(".json"):
                try:
                    uid = filename[:-5]
                    with open(os.path.join(USERS_DIR, filename), "r", encoding="utf-8") as f:
                        users[uid] = json.load(f)
                except: continue
    return users

def load_user(user_id: str):
    user_file = os.path.join(USERS_DIR, f"{user_id}.json")
    if not os.path.exists(user_file):
        return None
    try:
        with open(user_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return None

def save_user(user_id: str, user_data: dict):
    user_file = os.path.join(USERS_DIR, f"{user_id}.json")
    try:
        with open(user_file, "w", encoding="utf-8") as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
    except: pass

def get_user_quota(user_id: str):
    user = load_user(user_id)
    today = str(datetime.date.today())
    if not user:
        user = {"last_date": today, "adds": 0, "edits": 0, "deletes": 0, "applies": 0, "messages": 0, "notifications": []}
    
    if user.get("last_date") != today:
        user["last_date"] = today
        user["adds"] = 0
        user["edits"] = 0
        user["deletes"] = 0
        user["applies"] = 0
        user["messages"] = 0
        # 每天第一次登录时触发备份、归档和状态清理
        perform_data_backup()
        archive_old_history()
        archive_old_mail()
        clean_old_new_status()
    
    save_user(user_id, user)
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

def load_banned():
    if not os.path.exists(BANNED_FILE):
        return []
    try:
        with open(BANNED_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            banned = json.loads(content) if content else []
            return banned if isinstance(banned, list) else []
    except (json.JSONDecodeError, IOError):
        return []

def check_permission(user_id: str, action: str):
    if user_id == "guest":
        return False
    
    # 封禁检查
    banned = load_banned()
    if user_id in banned:
        return False
        
    admins = load_admins()
    if user_id in admins:
        return True
    
    user = get_user_quota(user_id)
    if action == "add" and user["adds"] >= 10: return False
    if action == "edit" and user["edits"] >= 10: return False
    if action == "delete" and user["deletes"] >= 1: return False
    if action == "apply" and user["applies"] >= 1: return False
    if action == "message" and user["messages"] >= 3: return False
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
    user = load_user(user_id)
    if not user:
        user = {"last_date": str(datetime.date.today()), "adds": 0, "edits": 0, "deletes": 0, "applies": 0, "messages": 0, "notifications": []}
    
    if action == "add": user["adds"] += 1
    elif action == "edit": user["edits"] += 1
    elif action == "delete": user["deletes"] += 1
    elif action == "apply_famous": user["applies"] += 1
    elif action == "send_message": user["messages"] += 1
    save_user(user_id, user)

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
    
    banned = load_banned()
    if user_id in banned:
        return {
            "logged_in": True,  # 允许显示登录态
            "user_id": user_id,
            "nickname": nickname,  # 恢复原名，不需要提示
            "role": "banned",      # 角色设为 banned
            "quota": {"adds": 0, "edits": 0, "deletes": 0, "applies": 0, "messages": 0}, # 配额全设为 0
            "notifications": []
        }
        
    admins = load_admins()
    user_data = load_user(user_id)
    quota = get_user_quota(user_id)
    role = "admin" if user_id in admins else "user"
    notifications = user_data.get("notifications", []) if user_data else []
    return {
        "logged_in": True,
        "user_id": user_id,
        "nickname": nickname,
        "role": role,
        "quota": quota,
        "notifications": notifications
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
        filename = f"{uuid.uuid4()}.webp"
        filepath = os.path.join(IMAGES_DIR, filename)
        try:
            with Image.open(image.file) as img:
                if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")
                img.save(filepath, "WEBP")
            image_url = f"/images/{filename}"
        except Exception as e:
            raise HTTPException(500, f"Image processing failed: {str(e)}")
    
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
        "y": y,
        "time": str(datetime.date.today()),
        "new": True
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
        # Check if old_image is not default (simplified check for 'default')
        if old_image and "default" not in old_image and old_image.startswith("/images/"):
            try:
                old_image_path = image_storage_path(old_image)
                if old_image_path and os.path.exists(old_image_path):
                    os.remove(old_image_path)
            except: pass

        filename = f"{uuid.uuid4()}.webp"
        filepath = os.path.join(IMAGES_DIR, filename)
        try:
            with Image.open(image.file) as img:
                # Handle transparency
                if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")
                img.save(filepath, "WEBP")
            node["image"] = f"/images/{filename}"
        except Exception as e:
            raise HTTPException(500, f"Image processing failed: {str(e)}")
        
    node["name"] = name
    node["source"] = json.loads(source)
    node["related"] = json.loads(related)
    node["tags"] = json.loads(tags)
    node["extension"] = json.loads(extension)
    node["introduction"] = introduction
    
    save_node(node)
    record_action(user_id, "edit", node["id"], node["name"], nickname)
    return node

@app.patch("/api/nodes/{node_id}/extension")
def update_node_extension(
    node_id: int,
    target_id: int = Form(...),
    action: str = Form("add"), # "add" or "remove"
    user_id: str = Form("guest"),
    nickname: str = Form("未知用户")
):
    if user_id == "guest":
        raise HTTPException(403, "请登录后重试")
    admins = load_admins()
    if user_id not in admins:
        raise HTTPException(403, "仅管理员可修改连线")
        
    node_file = os.path.join(DATA_DIR, f"{node_id}.json")
    if not os.path.exists(node_file):
        raise HTTPException(404, "Node not found")
        
    with open(node_file, "r", encoding="utf-8") as f:
        node = json.load(f)
    
    if "extension" not in node:
        node["extension"] = []
    
    if action == "add":
        if target_id not in node["extension"]:
            node["extension"].append(target_id)
    elif action == "remove":
        if target_id in node["extension"]:
            node["extension"].remove(target_id)
    
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
    # 先处理全站历史的 50 条限制归档
    archive_old_history()
    
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

# --- Mailbox Routes ---

@app.get("/api/mailbox")
def get_mailbox(user_id: str = "guest"):
    if user_id == "guest":
        raise HTTPException(403, "请登录后查看信箱")
    
    # 在获取信箱内容前先执行归档操作
    archive_old_mail()
    
    messages = load_mailbox()

    unprocessed = [m for m in messages if m.get("status") == "unprocessed"]
    handled = [m for m in messages if m.get("status") != "unprocessed"]

    unprocessed.sort(key=lambda x: x.get("time", ""), reverse=True)
    handled.sort(
        key=lambda x: x.get("processed_time") or x.get("time", ""),
        reverse=True
    )

    return unprocessed + handled

@app.post("/api/mailbox")
def send_message(
    content: str = Form(...),
    user_id: str = Form("guest"),
    nickname: str = Form("未知用户")
):
    if user_id == "guest":
        raise HTTPException(403, "请登录后发送信箱")
    
    if not check_permission(user_id, "message"):
        raise HTTPException(403, "今日信件投递次数已用完")
        
    if len(content) > 200:
        raise HTTPException(400, "信件内容不能超过200字")
        
    messages = load_mailbox()
    new_msg = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "nickname": nickname,
        "content": content,
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "unprocessed"
    }
    messages.append(new_msg)
    save_mailbox(messages)
    
    # 投递信件不再记录在全站历史里
    # record_action(user_id, "send_message", 0, "Mailbox", nickname)
    return new_msg

@app.post("/api/mailbox/{msg_id}/process")
def process_message(
    msg_id: str,
    action: str = Form("process"), # "process" or "reject"
    feedback: str = Form(""),
    user_id: str = Form("guest"),
    nickname: str = Form("未知用户")
):
    admins = load_admins()
    if user_id not in admins:
        raise HTTPException(403, "Unauthorized")
        
    messages = load_mailbox()
    msg = next((m for m in messages if m["id"] == msg_id), None)
    if not msg:
        raise HTTPException(404, "Message not found")
        
    msg["status"] = "processed" if action == "process" else "rejected"
    msg["processed_by"] = nickname
    msg["processed_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg["feedback"] = feedback if feedback.strip() else "无"
    
    # 获取信件投递人并更新其通知列表
    sender_id = msg.get("user_id")
    if sender_id and sender_id != "guest":
        user = load_user(sender_id)
        if user:
            # 记录需要通知用户的信件ID列表 (id_list)
            if "notifications" not in user:
                user["notifications"] = []
            if msg_id not in user["notifications"]:
                user["notifications"].append(msg_id)
            save_user(sender_id, user)
    
    save_mailbox(messages)
    return {"message": "Success"}

@app.post("/api/user/clear_notifications")
def clear_notifications(user_id: str = Form(...)):
    user = load_user(user_id)
    if user:
        user["notifications"] = []
        save_user(user_id, user)
        return {"status": "success"}
    return {"status": "not_found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
