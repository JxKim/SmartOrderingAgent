def redis_command_demo1():
    """
    redis相关的命令demo演示
    """

    from redis import Redis

    # 1、获取到client对象

    client = Redis.from_url("redis://localhost:6379",decode_responses=True)

    # 2、使用client对象，执行一些命令:
        # 命令很多，可以将命令做一些分类：
            # 字符串相关的命令
            # hash map相关的命令
            # list相关的命令
            # set相关的命令
            # zset相关的命令

    # 2.1 字符串相关的命令：执行set命令，创建一个value类型为string的key-value对
    client.set("name","张三")

    # 执行get命令，获取到key为name的value
    name = client.get("name")
    print(name)

    # 2.2 hash map 相关的命令：创建一个value为hash map 的 key-value对
    client.hset(
        "faq:items:address:test",
        mapping={
            "question":"地址是多少？",
            "answer":"北京市海淀区"
        }
    )

    # 获取到某一个key所对应hash map
    faq_item = client.hgetall("faq:items:address:test")

    print(faq_item)

    # # 2.3 set相关的命令：value为一个集合的key-value对
    # 添加了一个 key=faq:items value={"address","phone","email"} 的一个key-value对
    client.sadd(
        "faq:items3",
        "addres","phone","email"
    )

    # result就是key=faq:items 对应的value集合
    result = client.smembers(
        "faq:items3"
    )

    print(result)
    

def redis_command_demo2():
    """
    redis的pipeline命令的演示：
    1、
    """

    from redis import Redis

    # 1、获取到client对象

    client = Redis.from_url("redis://localhost:6379",decode_responses=True)

    # 2、通过client，获取到pipeline对象

    pipeline = client.pipeline()

    # 3、使用pipeline声明，需要执行的命令
    pipeline.set("name3","张三")
    import time
    time.sleep(30)
    pipeline.get("name2")

    pipeline.hset(
        "faq:items:phone:test",
        mapping={
            "question":"手机号是多少？",
            "answer":"13800000000"
        }
    )

    # 4、 执行pipeline中的命令
    results = pipeline.execute()

    print(results)


redis_command_demo1()
