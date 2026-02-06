"""
同步数据至Milvus当中去

"""
from decimal import Decimal
import os
from dotenv import load_dotenv
from pymysql.cursors import DictCursor
from pymilvus import DataType,IndexType
load_dotenv()
def insert_data():

    # 1、连接到MySQL数据库，获取到menu_items当中的所有数据
    import pymysql
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
            """

            cursor.execute(sql)
            results = cursor.fetchall()
            # 定义json的键，将数据封装成json
            str_results = []
            for item in results:
                new_result = ""
                for key, value in item.items():
                    if type(value) == Decimal:
                        value = float(value)
                    new_result += f"{key_name_mapping[key]}: {value}\n"
                str_results.append(new_result)
    # 2、连接到Milvus数据库，获取到client对象
    from pymilvus import MilvusClient
    client = MilvusClient(
        uri=os.getenv("MILVUS_URI"),
        token=""
    )
    client.drop_collection(collection_name="menu_items")
    # 3、创建collection  
    schema = MilvusClient.create_schema(
        auto_id=True
    ).add_field(
        field_name="id",
        datatype=DataType.INT64,
        is_primary = True,
    ).add_field(
        field_name="vector",
        datatype=DataType.FLOAT_VECTOR,
        dim=1024
    ).add_field(
        field_name="text",
        datatype=DataType.VARCHAR,
        max_length = 1500
    )

    index_params = MilvusClient.prepare_index_params()

    # L2: 0 , COSINE: 1
    index_params.add_index(
        field_name="vector",
        index_type=IndexType.HNSW,
        metric_type = "L2"
    )

    res = client.create_collection(
        collection_name="menu_items",
        schema=schema,
        index_params=index_params
    )

    # 4、使用embedding模型对menu_items数据进行向量化
    from langchain_huggingface import HuggingFaceEmbeddings
    embedding_model = HuggingFaceEmbeddings(
        model = r"../models/bge-m3"
    )
        
    
    vector_list = embedding_model.embed_documents(str_results)

    # 5、将向量化后的结果插入到Milvus当中去

    insert_data=[]
    for vector, str_item in zip(vector_list,str_results):
        insert_data.append(
            {
                "vector":vector,
                "text":str_item
            }
        )

    insert_res = client.insert(data=insert_data,collection_name="menu_items")
    print(insert_res)

insert_data()

    