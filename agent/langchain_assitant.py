"""
用来定义agent的主要的代码，
"""
from langchain.tools import tool
import pymysql
import os
from dotenv import load_dotenv
from pathlib import Path
from pymysql.cursors import DictCursor
from sqlalchemy import text
load_dotenv()
root_path = Path(__file__).parent.parent
embeddings =None
milvus_client = None
engine = None
def get_embeddings():
    global embeddings
    if embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings
        embeddings = HuggingFaceEmbeddings(model=str(root_path / "models" / "bge-m3"))
    return embeddings

def get_milvus_client():
    global milvus_client
    if milvus_client is None:
        from pymilvus import MilvusClient
        milvus_client = MilvusClient(
            uri=os.getenv("MILVUS_URI"),
            token=os.getenv("MILVUS_TOKEN")
        )
    return milvus_client

def mysql_connection():
    global engine
    if engine is None:
        from sqlalchemy import create_engine
        engine = create_engine(
            url=f"mysql+pymysql://{os.getenv('MYSQL_USERNAME')}:{os.getenv('MYSQL_PASSWORD')}@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DATABASE')}",
            pool_size=15
        )
    return engine


@tool
def search_main_dishes():
    """
    用来搜索餐厅当中的主菜
    """
    key_name_mapping={
        "dish_name":"主菜名称",
        "price":"价格",
        "description":"描述",
        "category":"分类",
        "spice_level":" 辣度等级",
        "flavor":"口味",
        "main_ingredients":"主要食材",
        "cooking_method":"烹饪方法",
        "is_vegetarian":"是否为素食",
        "allergens":"过敏信息"
    }
    with pymysql.connect(host=os.getenv("MYSQL_HOST"),
                         user=os.getenv("MYSQL_USERNAME"),
                         password=os.getenv("MYSQL_PASSWORD"),port=int(os.getenv("MYSQL_PORT"))) as conn:
        with conn.cursor(DictCursor) as cursor:
            sql = """
                select
                    dish_name,
                    price,
                    description,
                    category,
                    spice_level,
                    flavor,
                    main_ingredients,
                    cooking_method,
                    is_vegetarian,
                    allergens
                from
                    menu.menu_items
                where
                    is_featured=1
            """

            cursor.execute(sql)
            results = cursor.fetchall()
            # 定义json的键，将数据封装成json
            json_results = []
            for item in results:
                json_item = {}
                for key, value in item.items():
                    json_item[key_name_mapping[key]] = value
                json_results.append(json_item)
            
            return json_results
            
            # 定义json的键，将数据封装成json



@tool
def user_flavor_search(user_query:str):
    """
    基于用户的口味，来去查找相关的菜品
    """
    import pymilvus
    from langchain_huggingface import HuggingFaceEmbeddings

    # 1、构建用户query的向量
    embeddings = get_embeddings()

    query_vector = embeddings.embed_query(user_query)

    # 2、连接milvus，进行向量搜索
    client = get_milvus_client()

    # 3、进行向量搜索
    search_res = client.search(
        collection_name="menu_items",
        data=[query_vector],
        anns_field="vector",
        output_fields=["text"],
        limit=1
    )
    print("当前查找结果为：",search_res)
    # 4、解析搜索结果
    if search_res:
        all_results = search_res[0]
        # all_results: 列表
        final_result = []

        for item in all_results:
            item_str = item["entity"]['text']
            final_result.append(item_str)
        
        return final_result
    else:
        return "在当前库里面没有找到和用户喜好相关的菜品"
    
from pydantic import BaseModel,Field

class ReservationToolArgsInfo(BaseModel):
    num_people:int = Field(description="预约的总人数")
    num_children:int = Field(description="预约的0-2岁儿童人数")
    arrival_time:str = Field(description="预约的到达时间,格式：YYYY-MM-DD HH")
    seat_preference:str = Field(description="预约的座位偏好，当用户没有特殊需求时，传递空字符串即可")
    main_dish_preference:str = Field(description="预约的主菜偏好，当用户没有特殊需求时，传递空字符串即可")
    comment:str = Field(description="预约的其他备注，当用户没有特殊需求时，传递空字符串即可")

@tool(args_schema=ReservationToolArgsInfo)
def make_reservation(num_people:int,num_children:int,arrival_time:str,seat_preference:str,main_dish_preference:str,comment:str):
    """
    用来进行餐厅预定的工具：
    通过MySQL向数据库当中写入数据
    """
    engine = mysql_connection()
    with engine.connect() as conn:
        sql = """
INSERT INTO reservation_order
(num_people, num_children, arrival_time, seat_preference, main_dish_preference, other_comments)
VALUES
(:num_people, :num_children, :arrival_time, :seat_preference, :main_dish_preference, :other_comments)
"""
        # 
        params = {
    "num_people": num_people,
    "num_children": num_children,
    "arrival_time": arrival_time,
    "seat_preference": seat_preference,
    "main_dish_preference": main_dish_preference,
    "other_comments": comment,
}
        conn.execute(statement=text(sql),parameters=params)

        conn.commit()

        return "预订成功"
    


    



async def create_agent():
    from pathlib import Path
    from langchain.agents import create_agent
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI()
    with open(str(root_path / 'agent' /"prompts" / 'system_prompt.txt')) as f:
        system_prompt = f.read()

    agent = create_agent(
        model=llm,
        system_prompt=system_prompt,
        tools=[]
    )


if __name__ == '__main__':
    # num_people:int,num_children:int,arrival_time:str,seat_preference:str,main_dish_preference:str,comment:str
    res= make_reservation.invoke({"num_people":2,"num_children":1,"arrival_time":"2024-01-01 18","seat_preference":"","main_dish_preference":"","comment":""})
    print(res)