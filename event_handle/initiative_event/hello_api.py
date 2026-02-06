"""
应用启动入口

使用 uvicorn 启动 FastAPI 应用
"""
import uvicorn

from const import APP_HOST, APP_PORT
from app.main import app


# 为兼容早期版本启动方式，将文件命名为hello_api

if __name__ == "__main__":
    config = uvicorn.Config(
        "hello_api:app",
        host=APP_HOST,
        port=APP_PORT,
        reload=False
    )
    server = uvicorn.Server(config)
    server.run()
