---
title: 术语表
weight: 500
breadcrumbs: false
---
> 须知：本词汇表所列定义简明扼要，仅传达术语之核心要义，未涵盖其全部细微差别。欲究详尽，宜循文末参引，查阅正文相应章节。
### 异步
不待某事完成（如将数据经网络发送至另一节点），亦不预设其耗时。参见[“同步与异步复制”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch06.html#sec_replication_sync_async)、[“同步与异步网络”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch09.html#sec_distributed_sync_networks)及[“系统模型与现实”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch09.html#sec_distributed_system_model)。
### 原子性
1. 并发语境下：指一操作看似于单一时点完成，故其余并发进程永不可见其“半完成”状态。参见 *隔离性*（isolation）。

2. 事务语境下：将一组写操作聚为原子单元，须全提交或全回滚，纵有故障亦不破此律。参见[“原子性”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch08.html#sec_transactions_acid_atomicity)与[“两阶段提交（2PC）”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch08.html#sec_transactions_2pc)。
### 反压
令数据发送方降速，以防接收方处理不及。亦称*流控*。参见[“过载系统何以难自愈”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch02.html#sidebar_metastable)。
### 批处理
一种计算：以某个固定（通常规模较大）的数据集为输入，输出另一组数据，且不修改原始输入。参见[第 11 章](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch11.html#ch_batch)。
### 有界
具已知之上界或规模。  
例见网络延迟语境（参见[“超时与无界延迟”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch09.html#sec_distributed_queueing)），及数据集语境（参见[第 12 章](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch12.html#ch_stream)引言）。
### 拜占庭容错（Byzantine Fault）
一种行为异常之节点，其异常方式任意，例如向其他节点发送相互矛盾或恶意之消息。参见[“拜占庭故障”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch09.html#sec_distributed_byzantine)。
### 缓存
一种缓存组件，用于暂存近期访问的数据，以加速后续对相同数据的读取。  
其内容通常不完整；若所查数据未命中缓存，则须回源至底层较慢但数据完备的存储系统中获取。
### CAP 定理
一广为误读之理论结论，实无实用价值。参见[“CAP 定理”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch10.html#sec_consistency_cap)。
### 因果性
事件间因系统中某事“先于”另一事发生而产生的依赖关系。例如：后发事件响应先发事件，或基于先发事件而生成，或须结合先发事件方得理解。参见[“happens-before 关系与并发”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch06.html#sec_replication_happens_before)。
### 共识
分布式计算中一根本难题，谓之“共识”（Consensus）：令多个节点就某一事项达成一致（例如，数据库集群中何者应为领导者）。此问题远较初观为难。参见[“共识”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch10.html#sec_consistency_consensus)。
### 数据仓库
一种数据库，其数据整合自多个不同的 OLTP 系统，并经清洗、转换与建模，专为分析用途而优化。参见[“数据仓库”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch01.html#sec_introduction_dwh)。
### 声明式
描述某物应具备之性质，而非实现该物之具体步骤。数据库查询中，查询优化器接收一声明式查询，据以判定其最优执行方案。参见[“术语：声明式查询语言”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch03.html#sidebar_declarative)。
### 去规范化
为提升读取性能，在*规范化*数据集中引入一定程度的冗余或重复，通常体现为*缓存*或*索引*。非规范化值即一种预计算的查询结果，类同物化视图。参见[“规范化、非规范化与联接”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch03.html#sec_datamodels_normalization)。
### 衍生数据
一种经可复现流程由原始数据生成的数据集；必要时，该流程可重新执行。  
衍生数据多用于加速特定类型的读取访问。  
索引（indexes）、缓存（caches）、物化视图（materialized views）皆属此类。  
参见[“源系统与衍生数据”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch01.html#sec_introduction_derived)。
### 确定性
描述一函数：若输入相同，则输出恒定。  
此谓之“确定性函数”。  
其不得依赖随机数、系统时间、网络通信，或其他不可预测之因素。  
参见［《确定性之力》］(https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch09.html#sidebar_distributed_determinism)。
### 分布式
运行于若干经网络互连的节点之上。其特征为*局部故障*：系统中部分组件可能失效，而其余部分仍正常运行；软件往往无法确切判定具体何者已损。参见[“故障与局部失效”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch09.html#sec_distributed_partial_failure)。
### 持久化
以冗余与容错之法存贮数据，务使纵遇诸般故障，亦不致遗失。参见[“Durability”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch08.html#sec_transactions_acid_durability)。
### ETL
抽取–转换–载入（ETL）。自源数据库提取数据，将其转换为更适于分析查询的格式，并载入数据仓库或批处理系统。参见[“数据仓库”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch01.html#sec_introduction_dwh)。
### 故障转移
在单主节点系统中，故障转移（failover）即领导权由一节点移至另一节点之过程。参见[“处理节点宕机”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch06.html#sec_replication_failover)。
容错
故障时可自动恢复（如机器宕机或网络链路中断）。参见[“可靠性与容错性”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch02.html#sec_introduction_reliability)。
### 流程控制
参见*背压*。
### 关注者
一种不直接接受客户端写入、仅处理来自领导者（leader）之数据变更的副本。亦称 *从节点*（secondary）、*只读副本*（read replica）或 *热备节点*（hot standby）。参见[“单领导者复制”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch06.html#sec_replication_leader)。
### 全文检索
按任意关键词检索文本，常附带近似拼写匹配、同义词匹配等功能。全文索引是一种*二级索引*，专为支持此类查询而设。参见[“全文搜索”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch04.html#sec_storage_full_text)。
### 图
一种数据结构，由*顶点*（即可被引用之对象，亦称*节点*或*实体*）与*边*（即顶点之间的连接，亦称*关系*或*弧*）构成。参见[“类图数据模型”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch03.html#sec_datamodels_graph)。
### 哈希
一种将输入转换为看似随机之数的函数。同一输入恒得同一输出；不同输入极大概率产生不同输出，然亦有小概率产出相同输出（此谓“碰撞”）。参见[“按键哈希分片”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch07.html#sec_sharding_hash)。
### 幂等
描述一种可安全重试的操作：无论执行多少次，其效果均等同于仅执行一次。参见[“幂等性”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch12.html#sec_stream_idempotence)。
### 索引
一种可高效检索某字段值为特定值之全部记录的数据结构。参见[“OLTP 的存储与索引”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch04.html#sec_storage_oltp)。
### 隔离
在事务语境中，描述并发执行之事务相互干扰之程度。*可串行化*（Serializable）隔离提供最强保障；然实务中亦常采用较弱之隔离级别。参见[“隔离性”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch08.html#sec_transactions_acid_isolation)。
### 连接
将具有共同属性的记录关联起来。最常见于一条记录引用另一条记录的情形（如外键、文档引用、图中的边），此时查询需获取该引用所指向的记录。参见[“规范化、反规范化与连接”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch03.html#sec_datamodels_normalization)及[“JOIN 与 GROUP BY”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch11.html#sec_batch_join)。
### 领导者
当数据或服务在多个节点间复制时，**领导者（leader）** 乃指定之副本，唯其可执行写入变更。  
其选任或依共识协议自动选举，或由管理员手动指定。  
亦称 **主节点（primary）** 或 **源节点（source）**。  
参见 [“单领导者复制”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch06.html#sec_replication_leader)。
### 线性一致性
视系统中数据仅存一份，且仅通过原子操作更新。参见[“线性一致性”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch10.html#sec_consistency_linearizability)。
### 局部性
性能优化之一：若若干数据常被同时访问，则将其置于同一位置。参见[“读写操作的数据局部性”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch03.html#sec_datamodels_document_locality)。
### 锁
一种机制，确保仅一个线程、节点或事务可访问某资源；其余欲访问者须等待该锁释放。参见[“两阶段锁定（2PL）”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch08.html#sec_transactions_2pl)与[“分布式锁与租约”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch09.html#sec_distributed_lock_fencing)。
日志
一种仅追加写入（append-only）的数据存储文件。  
*预写式日志*（Write-Ahead Log, WAL）用于提升存储引擎的崩溃恢复能力（参见[“使 B 树可靠”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch04.html#sec_storage_btree_wal)）；  
*日志结构化*（Log-Structured）存储引擎以日志为底层主存储格式（参见[“日志结构化存储”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch04.html#sec_storage_log_structured)）；  
*复制日志*（Replication Log）用于将主节点（leader）的写操作同步至从节点（followers）（参见[“单主复制”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch06.html#sec_replication_leader)）；  
*事件日志*（Event Log）可表征数据流（参见[“基于日志的消息代理”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch12.html#sec_stream_log)）。
### Materialize
主动计算并立即写出结果，而非按需延迟求值。参见［“事件溯源与命令查询职责分离”］(https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch03.html#sec_datamodels_events)。
### 节点
某软件在计算机上运行之实例，藉由网络与其他节点通信，以协同完成特定任务。
### 归一化
结构严谨，无冗余、无重复。在规范化数据库中，某项数据若需更新，仅须修改一处，而非多处副本。参见[“规范化、反规范化与联接”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch03.html#sec_datamodels_normalization)。
### 联机分析处理
联机分析处理。访问模式以对大量记录执行聚合操作（如计数、求和、平均）为特征。参见[“运行系统与分析系统之辨”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch01.html#sec_introduction_analytics)。
### 联机事务处理
联机事务处理（OLTP）。访问模式特征为：查询响应迅捷，每次仅读取或写入少量记录，且通常通过键索引定位。参见[“运行型系统与分析型系统”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch01.html#sec_introduction_analytics)。
### 分片
将过大规模之数据集或计算任务，拆分为若干较小部分，并分发至多台机器并行处理。亦称“分区”（partitioning）。参见[第七章](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch07.html#ch_sharding)。
### 百分位数
一种通过统计高于或低于某阈值的数值数量，来刻画数值分布的方法。例如，某时段内响应时间的第 95 百分位数，即时间 *t*，满足：该时段内 95% 的请求耗时小于 *t*，其余 5% 耗时大于 *t*。参见[“描述性能”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch02.html#sec_introduction_percentiles)。
### 主键
主键：一值（常为数字或字符串），用以唯一标识某条记录。  
其一、系统多于创建记录时自动生成主键，方式如递增、随机等；  
其二、用户通常不手动设定；  
其三、参见 *secondary index*（次级索引）。
### 法定人数
操作被视作成功前，须参与投票的最少节点数。参见[“读写法定人数”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch06.html#sec_replication_quorum_condition)。
### 再平衡
为均衡负载，将数据或服务自一节点迁移至另一节点。参见[“键值数据分片”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch07.html#sec_sharding_key_value)。
### 复制
在多个节点上保存同一份数据的副本（*replicas*），以确保当某个节点不可达时，数据仍可访问。参见[第 6 章](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch06.html#ch_replication)。
### 模式
数据结构之描述，含其字段及对应数据类型。数据是否符合某模式（schema），可在其生命周期之不同阶段校验（参见[“文档模型中的模式灵活性”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch03.html#sec_datamodels_schema_flexibility)）；且模式本身可随时间演进（参见[第 5 章](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch05.html#ch_encoding)）。
### 次级索引
一种与主数据存储并存的附加数据结构，用于高效检索满足特定条件的记录。参见[“多列索引与二级索引”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch04.html#sec_storage_index_multicolumn)及[“分片与二级索引”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch07.html#sec_sharding_secondary_indexes)。
### 可序列化
一种**隔离性**保证：若多个事务并发执行，则其效果等同于以某种串行顺序依次执行。参见[“可串行化”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch08.html#sec_transactions_serializability)。
### 无共享架构
一种架构：各节点相互独立，皆配备专属 CPU、内存与磁盘，节点间借由通用网络互连；此有别于共享内存（shared-memory）或共享磁盘（shared-disk）架构。参见［“共享内存、共享磁盘与无共享架构”］(https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch02.html#sec_introduction_shared_nothing)。
### 偏度
1. 分片负载不均：部分分片承载大量请求或数据，其余分片负载显著偏低，亦称“热点”。参见[“倾斜工作负载与缓解热点”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch07.html#sec_sharding_skew)。

2. 时序异常：事件呈现非预期、非顺序之排列。详见[“快照隔离与可重复读”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch08.html#sec_transactions_snapshot_isolation)中关于*读倾斜*（read skew）的讨论、[“写倾斜与幻象”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch08.html#sec_transactions_write_skew)中关于*写倾斜*（write skew）的讨论，以及[“用于事件排序的时间戳”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch09.html#sec_distributed_lww)中关于*时钟偏斜*（clock skew）的讨论。
### 脑分裂（Split Brain）
一种场景：两个节点同时自认为主节点，可能导致系统保障失效。参见[“处理节点宕机”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch06.html#sec_replication_failover)与[“多数派原则”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch09.html#sec_distributed_majority)。
### 存储过程
一种将事务逻辑编码为可在数据库服务器端完整执行之形式的方法，其间无需与客户端往返通信。参见[“实际串行执行”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch08.html#sec_transactions_serial)。
### 流处理
一种持续运行的计算过程，以无穷尽的事件流为输入，并从中推导出输出。参见[第 12 章](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch12.html#ch_stream)。
### 同步
同步（synchronous）
### 源系统
一种存有某类数据之主版本、权威版本的系统，亦称“事实源头”。所有变更须先写入此系统；其余数据集皆可由此系统派生。参见[“记录系统与派生数据”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch01.html#sec_introduction_derived)。
### 超时
检测故障最简方法之一，即观察是否在限定时间内无响应。然超时之因，或系远端节点失常，或系网络异常，二者难辨。参见[“超时与无界延迟”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch09.html#sec_distributed_queueing)。
### 全序
一种比较事物（如时间戳）的方法，可恒定判定二者中何者为大、何者为小。若某些事物之间不可比（即无法判定孰大孰小），则称此关系为*偏序*。
### 事务
将若干读写操作归并为一个逻辑单元，以简化错误处理与并发问题。参见[第 8 章](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch08.html#ch_transactions)。
### 两阶段提交（2PC）
一种确保多个数据库节点对事务**原子性地全部提交或全部中止**的算法。参见[“两阶段提交（2PC）”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch08.html#sec_transactions_2pc)。
### 两阶段锁（2PL）
一种实现**可串行化隔离**（serializable isolation）的算法：事务在读取或写入数据时，须获取对应数据的锁，并将锁持有至事务结束。参见[“两阶段锁协议（2PL）”](https://learning.oreilly.com/library/view/designing-data-intensive-applications/9781098119058/ch08.html#sec_transactions_2pl)。
### 无界
无已知上界，亦无已知尺寸。与“有界（bounded）”相反。
