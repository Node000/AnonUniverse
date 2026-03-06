import os
import shutil
import datetime

BACKUP_DIR = "backups"
DATA_DIR = "data"

def rollback():
    if not os.path.exists(BACKUP_DIR):
        print("未发现备份文件夹或备份记录。")
        return

    # 获取所有备份文件夹并排序
    backups = sorted([d for d in os.listdir(BACKUP_DIR) if os.path.isdir(os.path.join(BACKUP_DIR, d))], reverse=True)
    
    if not backups:
        print("未发现备份记录。")
        return

    print("=== 数据回滚脚本 ===")
    print(f"当前存在的备份: {', '.join(backups)}")
    
    try:
        days_ago = input("要回滚到几天前？ (0 表示取消): ")
        if not days_ago.isdigit():
            print("输入无效，请输入数字。")
            return
            
        days_ago = int(days_ago)
        if days_ago == 0:
            print("回滚取消。")
            return
            
        target_date = (datetime.date.today() - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")
        target_path = os.path.join(BACKUP_DIR, target_date)
        
        if not os.path.exists(target_path):
            print(f"找不到日期为 {target_date} 的备份。请检查已有日期。")
            return
            
        confirm = input(f"此操作将删除当前的「data」文件夹，并使用「{target_date}」的备份覆盖，是否确定？ (y/n): ")
        if confirm.lower() != 'y':
            print("操作取消。")
            return
            
        # 开始回滚
        if os.path.exists(DATA_DIR):
            shutil.rmtree(DATA_DIR)
        shutil.copytree(target_path, DATA_DIR)
        print(f"成功回滚至 {target_date} 的数据状态。")
        
    except KeyboardInterrupt:
        print("\n操作已中断。")
    except Exception as e:
        print(f"回滚失败: {e}")

if __name__ == "__main__":
    rollback()
