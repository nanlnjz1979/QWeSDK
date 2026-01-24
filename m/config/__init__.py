import json
import os

class GlobalConfig:
    """
    全局配置类，使用类变量实现，不需要实例化就能访问配置
    自动从 config.json 文件中加载配置
    """
    # 默认配置
    DATABASE_IP = "127.0.0.1:9000"
    
    @classmethod
    def load_config(cls):
        """
        从 config.json 文件中加载配置
        """
        config_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config.json")
        
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                # 加载数据库配置
                if "database" in config:
                    db_config = config["database"]
                    db_ip = db_config.get("ip", "127.0.0.1")
                    db_port = db_config.get("port", 9000)
                    cls.DATABASE_IP = f"{db_ip}:{db_port}"
                    
                print(f"[INFO] 成功加载配置文件: {config_file_path}")
                print(f"[INFO] 数据库IP: {cls.DATABASE_IP}")
        except FileNotFoundError:
            print(f"[WARNING] 配置文件 {config_file_path} 未找到，使用默认配置")
        except json.JSONDecodeError as e:
            print(f"[ERROR] 解析配置文件失败: {e}")
        except Exception as e:
            print(f"[ERROR] 加载配置文件失败: {e}")
    
    @classmethod
    def get_config(cls, key, default=None):
        """
        动态获取配置
        
        参数:
        key: 配置键名
        default: 默认值
        
        返回:
        配置值
        """
        return getattr(cls, key, default)
    
    @classmethod
    def set_config(cls, key, value):
        """
        动态设置配置
        
        参数:
        key: 配置键名
        value: 配置值
        """
        setattr(cls, key, value)

# 类加载时自动加载配置
GlobalConfig.load_config()
