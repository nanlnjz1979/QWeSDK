import json
import os
import urllib.parse

class GlobalConfig:
    """
    全局配置类，使用类变量实现，不需要实例化就能访问配置
    自动从 config.json 文件中加载配置
    """
    # 默认配置
    DATABASE_IP = "127.0.0.1:9000"
    DATABASE_USER = "default"
    DATABASE_PASSWORD = "123456"
    
    @classmethod
    def load_config(cls):
        """
        从当前文件所在目录读取 config.json 文件
        """
        # 当前文件所在目录
        config_dir = os.path.dirname(__file__)
        config_file_path = os.path.join(config_dir, "config.json")
        
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
                # 加载数据库配置
                if "database" in config:
                    db_config = config["database"]
                    db_ip = db_config.get("ip", "127.0.0.1")
                    db_port = db_config.get("port", 8123)
                    cls.DATABASE_IP = f"{db_ip}:{db_port}"
                    cls.DATABASE_USER = db_config.get("username", "default")
                    cls.DATABASE_PASSWORD = db_config.get("password", "123456")
                    
                print(f"[INFO] 成功加载配置文件: {config_file_path}")
        except FileNotFoundError:
            print(f"[WARNING] 配置文件 {config_file_path} 未找到，使用默认配置")
        except json.JSONDecodeError as e:
            print(f"[ERROR] 解析配置文件 {config_file_path} 失败: {e}")
        except Exception as e:
            print(f"[ERROR] 加载配置文件 {config_file_path} 失败: {e}")
        cls._apply_clickhouse_env()
        print(f"[INFO] 数据库IP: {cls.DATABASE_IP}")

    @classmethod
    def _apply_clickhouse_env(cls):
        """Worker 环境变量覆盖配置文件，使选股和日线读取同一台 ClickHouse。"""
        url = os.environ.get("QWESDK_CLICKHOUSE_URL", "").strip()
        if url:
            parsed = urllib.parse.urlparse(url)
            if parsed.hostname:
                cls.DATABASE_IP = f"{parsed.hostname}:{parsed.port or 8123}"
        user = os.environ.get("QWESDK_CLICKHOUSE_USER", "").strip()
        if user:
            cls.DATABASE_USER = user
        if "QWESDK_CLICKHOUSE_PASSWORD" in os.environ:
            cls.DATABASE_PASSWORD = os.environ["QWESDK_CLICKHOUSE_PASSWORD"]
    
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

    @classmethod
    def get_database_auth(cls):
        """Return credentials for ClickHouse HTTP Basic Authentication."""
        return (
            cls.get_config("DATABASE_USER", "default"),
            cls.get_config("DATABASE_PASSWORD", "123456"),
        )

# 类加载时自动加载配置
GlobalConfig.load_config()
