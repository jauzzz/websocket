功能：限制人数

## 方案：

### Redis Count

协程虽然是单线程，但是它的调度是不确定的。

请求进入房间的流程如下：
1. 获取 count（redis）
2. 判断 count < max_people（asyncio）
3. 更新 count（redis）loooooooooo

这种方案有一个问题：
    由于 asyncio 的调度是不定的，判断count和增加count不是连续的；
    所以，在临界值时，可能有多个客户端都满足条件，最后都得到了更新，导致最终的 count 超出了限制

解决方案：让步骤1-3，以原子方式执行
    1. redis lua 脚本
    2. asyncio 的同步机制（本地锁）
    3. redis 官方提供的锁
    4. redis 加锁 (三种加锁思路：incr、setnx、set)（分布式锁：https://xiaomi-info.github.io/2019/12/17/redis-distributed-lock/）


### 队列

1. 使用定长队列：Queue，内部使用了锁来临时阻止竞争线程（自带了阻塞）
2. 使用 redis zset：
    不定长，uid直接 add，value用时间戳；
    准入判断：返回 uid 的索引值，是否小于 maxcount


## 性能测试

性能指标：
- 准确性
- 连接数（并发数，指系统同时能处理的最大请求数量，反应了系统的负载能力）
- 吞吐量 TPS：每秒事务（一个事务是指一个客户端向服务器发送请求然后服务器做出响应的过程）
- QPS：每秒请求
- 响应速度 RT

需要一个 benchmark
