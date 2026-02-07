"""
定义后端的所有的接口
"""
# 1、导入FastAPI
from fastapi import FastAPI
from pydantic import BaseModel

from agent.langchain_assitant import assistant_query
# 引入StreamingResponse，用于发送事件流：EventStream
from starlette.responses import StreamingResponse

# 2、创建一个application 简称app
app = FastAPI()

# 3、配置app的路由映射函数：每一个端点所对应的处理函数

class ChatRequest(BaseModel):
    query:str

# 3.1 配置/chat接口
@app.post("/chat")
async def chat_endpoint(request:ChatRequest):
    """
    处理/chat接口的POST请求
    :param request: 包含用户查询的ChatRequest对象
    """
    query = request.query

    # return {"response":assistant_query(query)}
    return StreamingResponse(
        assistant_query(query), # 传入一个异步生成器，用于逐块发送响应
        media_type="text/event-stream" # HTTP规范里面定义的事件媒体类型
    )
