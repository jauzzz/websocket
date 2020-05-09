# -*- coding: utf-8 -*-
import redis
import logging

logger = logging.getLogger(__name__)
print("进入监控")
logger.info("进入监控")
disconnect_user = redis.Redis(host="localhost", port=6379, decode_responses=True, db=0)
connect_user = redis.Redis(host="localhost", port=6379, decode_responses=True, db=1)
sid_user_live = redis.Redis(host="localhost", port=6379, decode_responses=True, db=2)

pub = connect_user.pubsub()  # Return a Publish/Subscribe object.
pub.subscribe("__keyevent@0__:expired")

for msg in pub.listen():
    data = msg["data"]
    # 接收到数据过期通知，确定人员是否存在
    if isinstance(data, str):
        # user_id = bytes.decode(data)
        print(data)
        li = data.split("_")
        room = li[0]
        user_id = li[1]
        logger.info(user_id)
        sid = connect_user.hget(room, user_id)
        # 所查询人员未在直播列表中,回退限制
        if sid and not sid_user_live.exists(sid):
            print(data)
            logger.info("开始回退")
            # 减少用户
            connect_user.hdel(room, user_id)
            print("4", len(connect_user.keys(room)))
