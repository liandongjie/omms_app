import os

import uvicorn
from dotenv import load_dotenv

# 加载环境变量
env = os.getenv("ENVIRONMENT", "development")
if env == "development":
    load_dotenv(".env.development")
elif env == "testing":
    load_dotenv(".env.testing")
elif env == "production":
    load_dotenv(".env.production")
else:
    load_dotenv(".env")

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8004))
    reload = env == "development"

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload
    )
