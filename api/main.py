"""
定义后端的所有的接口
"""
# 1、导入FastAPI
from fastapi import FastAPI
from pydantic import BaseModel
import sys
sys.path.append(r"D:\PycharmProjects\lessons\1020_llm\SmartOrderingAgent")
from agent.langchain_assitant import assistant_query,mysql_connection
# 引入StreamingResponse，用于发送事件流：EventStream
from starlette.responses import StreamingResponse
from difflib import SequenceMatcher
from sqlalchemy import text
import os
from dotenv import load_dotenv
from typing import Optional,List
from datetime import datetime
load_dotenv()

# 2、创建一个application 简称app
app = FastAPI()
client = None
# 3、配置app的路由映射函数：每一个端点所对应的处理函数

def _get_redis_client():
    global client
    if client is None:
        from redis.asyncio import Redis
        client = Redis.from_url(os.getenv("REDIS_URL"),decode_responses=True)
    return client

class ChatRequest(BaseModel):
    query:str

class FaqItem(BaseModel):
    question:str
    answer:str

class FAQResponse(BaseModel):
    success:bool
    query:str
    # 针对于用户的一个query，需要给到前端多个faq，
    suggestions:list[FaqItem]

class ReservationItem(BaseModel):
    id: int
    num_people: int
    num_children: int
    arrival_time: Optional[str] = None
    seat_preference: Optional[str] = None
    main_dish_preference: Optional[str] = None
    other_comments: Optional[str] = None
    created_at: Optional[str] = None

class ReservationListResponse(BaseModel):
    success: bool
    reservations: List[ReservationItem]
    count: int
    message: str

class MenuItem(BaseModel):
    id:int
    dish_name:str
    price:float
    formatted_price:str # 格式化后的价格，例如：¥12.50
    description:str
    category:str
    spice_level:int
    spice_text:str
    flavor:str
    main_ingredients:str
    cooking_method:str
    is_vegetarian:bool
    allergens:str
    is_available:bool

# 定义菜品列表响应模型
class MenuListResponse(BaseModel):
    """菜品列表响应"""
    success: bool
    menu_items: List[MenuItem] # 菜品列表
    count: int # 菜品数
    message: str # 响应消息提示

async def _load_faq_items_from_redis()->list[FaqItem]:

    # 1、构建client 对象
    redis_client = _get_redis_client()
    pipeline = redis_client.pipeline()

    # 2、从redis set 中获取到faq所对应的所有keys
    faq_keys = await redis_client.smembers("faq:all_items")

    # 3、加载faq_keys所对应的所有faq，每个faq，构造成FaqItem对象
    for faq_key in faq_keys:
        pipeline.hgetall(faq_key)

    all_faq_items = await pipeline.execute()
    print(all_faq_items)
    return [
            FaqItem(
                question=item["question"],
                answer=item["answer"]
            )
        for item in all_faq_items
    ]

def _get_similarity_score(query:str,faq_question:str)->float:
    """
    使用简单的字符串匹配算法，计算query和faq_question的相似度得分
    (备注：实际生产环境下，可以通过更复杂的算法，比如进行embedding再来计算余弦相似度等，来计算相似度得分)
    """
    # 1、算法一：使用一个包：difflib.SequenceMatcher
        # 底层原理：递归地比较两个字符串的最长公共子序列
            # 例如： a = abcdef b = rtabcedgef
            # 第一步：找到这两个字符串里面最长的公共子序列：abc
            # 第二步：把a串切成三部分["","abc","def"] 把b串同样也切成三部分:["rt","abc","edgef"]
            # 第三步：分别比较a串和b串左侧和右侧的部分，再找出公共最长子序列，依此类推，直到找不到最长公共子序列
            # 第四步：计算得分：2*所有最长公共子序列的长度和 / (a的长度+b的长度)
            # 通过该算法，能够捕捉到query和faq_question之间的带位置信息的相似度
        # 该算法的问题：
            # 举例：query: 密码忘记了怎么办，question：忘记了密码怎么办 
            # 针对于这种基本包含的关键词一致，但是关键词的语序位置不一样的匹配，得分会偏低
    sequence_matcher = SequenceMatcher(None,query,faq_question)
    score = sequence_matcher.ratio()

    # 2、算法二：实现一个算法，只计算query包含的关键词/字和question包含的关键词/字，所构成一个词袋，之间的相似度。
        # 此处引入Jaccard相似度：Jaccard相似度用来计算两个集合之间的相似度
        # Jaccard相似度的定义： set a 和 set b 的交集的元素数量 / (set a 和 set b 的并集的数量)
    a = set(list(query))
    b = set(list(faq_question))
    jaccard_score = len(a.intersection(b)) / len(a.union(b))

    # 3、对这两个分数做一个加权
    return 0.6*score + 0.4*jaccard_score



        
    


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


@app.get("/faq/suggest",response_model=FAQResponse)
async def faq_endpoint(query:str,limit:int=1):

    limit =1 
    # 1、从redis中获取所有的faq 的数据
    faq_items = await _load_faq_items_from_redis()
    # 2、将这些数据中的question和用户的query，进行比较，得到相似度得分
    scores_list = []
    for faq_item in faq_items:
        score = _get_similarity_score(query,faq_item.question)
        scores_list.append((score,faq_item))
        # 此处可以根据实际情况，调整不同的阈值，来筛选出哪些question是和用户query相关的
        # 如果不配置阈值的，总能够得到一个结果
    # 3、将这些得分进行排序，得到最相似的前1条数据
    scores_list.sort(key=lambda x:x[0],reverse=True)

    top_k_items = scores_list[:limit]
    # 4、将这个结果，返回给前端
    return FAQResponse(
        success=True,
        query=query,
        suggestions=[faq_item  for score,faq_item in top_k_items]
    )


@app.get("/reservation/list",response_model=ReservationListResponse)
async def reservation_list():
    """
    获取到预订列表
    """
    # 获取到sqlalchemy.engine.Connection，这个对象和pymysql.Connection有点区别
    with mysql_connection().connect() as conn:
        sql = """
        select
            id,
            num_people,
            num_children,
            arrival_time,
            seat_preference,
            main_dish_preference,
            other_comments,
            created_at
        from
            menu.reservation_order
        """
        # 直接通过conn.execute().fetchall() 获取到的是一个列表，列表的每个元素是一个元组
        # results = conn.execute(text(sql)).fetchall()
        # 通过conn.execute().mappings().fetchall() 获取到的是一个列表，列表的每个元素是一个字典
        results = conn.execute(text(sql)).mappings().fetchall()
        # 把results 转换为 ReservationItem 模型的列表
        item_list = []
        for result in results:
            item = ReservationItem(
                id=result["id"],
                num_people=result["num_people"],
                num_children=result["num_children"],
                arrival_time=datetime.strftime(result["arrival_time"],"%Y-%m-%d %H:%M:%S"),
                seat_preference=result["seat_preference"],
                main_dish_preference=result["main_dish_preference"],
                other_comments=result["other_comments"],
                created_at=datetime.strftime(result["created_at"],"%Y-%m-%d %H:%M:%S"),
            )
            item_list.append(item)

    return ReservationListResponse(
        success=True,
        reservations=item_list,
        count=len(item_list),
        message="success"
    )


@app.get("/menu/list",response_model=MenuListResponse)
async def menu_list():
    """
    获取到菜单列表
    """
    with mysql_connection().connect() as conn:
        sql = """
            SELECT 
                                id, dish_name, price, description, category, 
                                spice_level, flavor, main_ingredients, cooking_method, 
                                is_vegetarian, allergens, is_available
                                FROM menu_items 
                                WHERE is_available = 1
                                ORDER BY category, dish_name
        """
        results = conn.execute(text(sql)).mappings().fetchall()
        # 把results 转换为 MenuItem 模型的列表
        item_list = []

        for result in results:
            spice_levels = {0: "不辣", 1: "微辣", 2: "中辣", 3: "重辣"}
            spice_text = spice_levels.get(result["spice_level"], "未知")
            item = MenuItem(
                id=result["id"],
                dish_name=result["dish_name"],
                price=result["price"],
                formatted_price=f"¥{result['price']:.2f}",
                description=result["description"],
                category=result["category"],
                spice_level=result["spice_level"],
                spice_text=spice_text,
                flavor=result["flavor"],
                main_ingredients=result["main_ingredients"],
                cooking_method=result["cooking_method"],
                is_vegetarian=result["is_vegetarian"],
                allergens=result["allergens"],
                is_available=result["is_available"],
            )
            item_list.append(item)

    return MenuListResponse(
        success=True,
        menu_items=item_list,
        count=len(item_list),
        message="success"
    )

if __name__ == "__main__":
    res = _get_similarity_score("位置在哪里","大堂电话是多少")
    print(res)