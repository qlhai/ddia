---
title: "7. 分片"
weight: 207
breadcrumbs: false
---

<a id="ch_sharding"></a>
![](/map/ch06.png)

> *显而易见，须破除顺序之桎梏，不可拘束于计算机之线性执行。当明确定义，厘清数据之优先级与描述；当申明关系，而非罗列步骤。*  
> ——格蕾丝·默里·霍珀，《管理与未来计算机》（1962）

分布式数据库通常以两种方式将数据分布于各节点：

1. **复制（Replication）**：同一份数据在多个节点上保存副本。此内容已于[第六章](/zh-cn/ch6#ch_replication)详述。  
2. **分片（Sharding）**：若不欲各节点均存全部数据，则可将大规模数据划分为若干较小的**分片（shards）** 或 **分区（partitions）**，并使不同分片驻于不同节点。本章即专论分片。

通常，分片之划分方式确保每条数据（即每条记录、每一行或每一个文档）**仅归属唯一分片**。其实现方法多样，本章将深入剖析。实质上，每个分片本身即为一个小型独立数据库；尽管部分数据库系统支持跨分片操作，但该能力属额外扩展，非分片之固有属性。

分片常与复制结合使用：即对每个分片生成若干副本，并将其分别存储于不同节点。由此，虽每条记录仅属一个分片，却仍可因冗余副本而存于多个节点，以保障容错性（fault tolerance）。

单个节点可承载多个分片。若采用单主复制（single-leader replication）模型，则分片与复制之组合形态可如[图7-1](/zh-cn/ch7#fig_sharding_replicas)所示：每个分片之主节点（leader）被指派至某一节点，其从节点（followers）则分布于其余节点；任一节点既可为某些分片之主节点，亦可为另一些分片之从节点；然每一分片仍仅有一个主节点。
{{< figure src="/fig/ddia_0701.png" id="fig_sharding_replicas" caption="Figure 7-1. Combining replication and sharding: each node acts as leader for some shards and follower for other shards." class="w-full my-4" >}}
第六章（[数据库复制](/zh-cn/ch6#ch_replication)）所论复制原理，悉适用于分片之复制。盖分片策略与复制策略大体正交，故本章为简明起见，暂略复制不谈。

> [!TIP] 分片与分区

本章所谓 *分片（shard）*，在不同系统中称谓各异：Kafka 中称 *分区（partition）*，CockroachDB 中称 *范围（range）*，HBase 与 TiDB 中称 *区域（region）*，Bigtable 与 YugabyteDB 中称 *平板（tablet）*，Cassandra、ScyllaDB 与 Riak 中称 *虚拟节点（vnode）*，Couchbase 中称 *虚拟桶（vBucket）*，仅举数例而已。

部分数据库将 *分区（partitioning）* 与 *分片（sharding）* 视为两个不同概念。例如 PostgreSQL 中，分区指将大表逻辑切分为多个子表，各子表仍存于同一台机器上（此举有若干优势，如整区删除极快）；而分片则将数据集横向分布于多台机器 [^1] [^2]。  
然在多数系统中，“分区”即“分片”之同义词。

“分区”一词表意清晰；“分片”之名则稍显突兀。据一说，“shard”源于在线角色扮演游戏《网络创世纪》（*Ultima Online*）：游戏中一枚魔法水晶碎裂为若干片，每一片皆折射出一份游戏世界副本 [^3]。由此，“shard”渐指一组并行运行的游戏服务器，后延用于数据库领域。另有一说，“shard”原为 *System for Highly Available Replicated Data*（高可用复制数据系统）之首字母缩写——此系一九八〇年代数据库系统，惜其详已不可考。

顺带一提：此处“分区（partitioning）”与 *网络分区（network partitions）*（即节点间网络故障所致的“netsplit”）毫无关联。此类故障将于第九章（[分布式系统](/zh-cn/ch9#ch_distributed)）详述。
## 分片之利弊 {#sec_sharding_reasons}
数据库分片之主因，在于**可扩展性**（scalability）：当数据量或写入吞吐量超出单节点承载能力时，分片可将数据与写操作分散至多个节点。

若瓶颈仅在于读吞吐量，则未必需分片；此时可采用**读扩展**（read scaling），详见[第6章](/zh-cn/ch6#ch_replication)。

分片实为实现**水平扩展**（horizontal scaling，即“向外扩展”，scale-out）之核心手段，如[“共享内存、共享磁盘与无共享架构”](/zh-cn/ch2#sec_introduction_shared_nothing)节所述：系统扩容不依赖升级单机硬件，而靠增配更多（较小）机器。若能将工作负载均分，使各分片承担近似等量任务，即可将分片部署于不同机器，并行处理数据与查询。

复制（replication）在小规模与大规模系统中均有价值，因其可提升容错性与离线可用性；而分片属重型方案，多见于大规模场景。若当前数据量与写入吞吐仍可由单机承载（今之单机性能已甚可观），则宜避免分片，坚守单分片架构。

此建议之由，在于分片常引入复杂性：须选定**分区键**（partition key），据此决定每条记录归属何分片；**相同分区键之所有记录，必存于同一分片** [^4]。  
此选择至关重要：若已知记录所在分片，则访问极快；若未知分片，则须遍历全部分片，效率低下；且分片策略一旦确立，后续变更殊为困难。

故分片尤适于键值型（key-value）数据——可依键直接分片；而对关系型数据则较棘手：或需按二级索引检索，或需跨分片联结（join）记录。此问题详见[“分片与二级索引”](/zh-cn/ch7#sec_sharding_secondary_indexes)。

另一难题在于：一次写操作可能需更新多个分片中的关联记录。单节点事务虽常见（参见[第8章](/zh-cn/ch8#ch_transactions)），但跨分片一致性须赖**分布式事务**（distributed transaction）。如[第8章](/zh-cn/ch8#ch_transactions)所示，虽部分数据库支持分布式事务，然其性能远逊单节点事务，易成系统瓶颈，更有系统根本未予支持。

另有系统于单机内亦用分片，通常为每CPU核心运行一单线程进程，以利用CPU并行能力，或适配**非统一内存访问**（NUMA）架构——即某些内存bank物理上更靠近某CPU而非他者 [^5]。  
例如，Redis、VoltDB 与 FoundationDB 均采每核一进程之设计，并借分片将负载摊至同一机器之各CPU核心 [^6]。
### 分片实现多租户 {#sec_sharding_multitenancy}
软件即服务（SaaS）产品与云服务常采用*多租户*（multitenant）架构，其中每个“租户”（tenant）对应一位客户。同一租户下可有多个用户登录，但各租户的数据集彼此隔离、自成一体。例如，在电子邮件营销服务中，每家注册企业通常为独立租户，因其订阅名单、投递数据等均与其他企业严格分离。

多租户系统有时借由*分片*（sharding）实现：或为每个租户分配独立分片，或把多个小型租户聚合成一个较大分片。此类分片可为物理上分离的数据库（此前在[“嵌入式存储引擎”](/zh-cn/ch4#sidebar_embedded)中已述），亦可为大型逻辑数据库中可独立管理的子集 [^7]。  
以分片支撑多租户，具六项优势：

**资源隔离**  
：若某租户执行计算密集型操作，而其运行于独立分片，则其余租户性能受扰之概率较低。

**权限隔离**  
：若访问控制逻辑存在缺陷，当租户数据物理隔离时，误授一租户访问他租户数据之风险亦随之降低。

**单元化架构**（cell-based architecture）  
：分片不仅可用于数据存储层，亦可延展至承载应用代码的服务层。在*单元化架构*中，一组租户所对应的服务与存储被封装为自包含之*单元*（cell）；各单元设计为可近乎独立运行。此法提供*故障隔离*能力：任一单元内故障，仅限于该单元内部，其余单元所承载之租户不受影响 [^8]。

**按租户备份与恢复**  
：对各租户分片单独备份，即可在不波及其他租户前提下，从备份中还原该租户状态。此于租户误删或覆写关键数据时尤为实用 [^9]。

**合规性支持**  
：《通用数据保护条例》（GDPR）等数据隐私法规赋予个人查阅及删除其全部数据之权利。若每人数据独占一分片，则导出与删除操作可简化为对该分片之直接操作 [^10]。

**数据驻留要求**（data residence）  
：若某租户数据依属地法规须存于特定司法管辖区，则区域感知型数据库（region-aware database）可将其分片显式调度至对应地理区域。

**渐进式模式发布**  
：模式迁移（schema migrations；前文[“文档模型中的模式灵活性”](/zh-cn/ch3#sec_datamodels_schema_flexibility)已述）可逐租户推进。此举降低风险——问题可在波及全体租户前被发现；但跨租户事务一致性难以保障 [^11]。

然以分片实现多租户，亦存三重挑战：

* 其一，此法预设单个租户体量足够小，可容纳于单一节点。若不然——如遇超大规模租户，单机不堪承载——则须在租户内部再行分片，复归至为*可扩展性*而分片之原初命题 [^12]。  
* 其二，若租户数量庞大而个体微小，为每一租户独设分片将引发过高开销。虽可聚合若干小租户共用一分片，但租户成长后如何在分片间迁移，又成新难题。  
* 其三，若需实现横跨多租户之功能（如跨租户数据关联），而数据散落于不同分片，则涉及多分片联结（join）之操作，实施难度陡增。
## 键值数据分片 {#sec_sharding_key_value}
设数据量浩繁，欲行分片（sharding），则须定策：何 record 归何 node？

**其要旨有三：均载、可衡、避热。**

一曰均载。  
分片之本，在使数据量与查询负载均摊于各 node。若十 node 各负其均，则理论吞吐可较单 node 增十倍（忽略复制开销）。此为理想线性扩展之前提。

二曰可衡。  
增删 node 时，须能重平衡（rebalance）：加至十一 node，则原数据须重分布，使十一者各承其均；减至九 node，亦须同理。故分片算法不可固化映射，须容动态再分配。

三曰避热。  
若分片不均，谓之偏斜（skew）。偏斜之极，全量负载聚于一 shard，余九 node 闲置，瓶颈尽系于单点——此即热片（hot shard）或热点（hot spot）。若偏斜源于单一高频键（如社交网络中某明星之 user_id），则称热键（hot key）。

故需一映射算法：  
- 输入为记录之分片键（partition key）：键值系统中，常即 key 本身，或其前缀；关系模型中，可为某列（未必为主键）；  
- 输出为 shard ID（或 node 地址）；  
- 此算法须满足：确定性（同键恒映射同 shard）、低迁移率（增删 node 时，仅少量数据需搬移）、抗偏斜（对真实分布鲁棒，不因键分布不均而致负载倾轧）。

常用法有二：  
其一，哈希分片（hash-based）：`shard_id = hash(key) mod N`。简单高效，但 `N` 变则全量重映射，迁移成本高。  
其二，一致性哈希（consistent hashing）或虚拟节点（virtual nodes）：将 key 空间映射至环，node 占环上若干区间。增删 node 仅扰动邻近区间，迁移量小。  
其三，范围分片（range-based）：按 key 排序切分区间（如 `A–F`, `G–M`, …）。利于范围查询，但易生偏斜（如时间戳键致新数据全入末 shard），须辅以手动拆分或自动分裂。

综之：  
- 首择哈希类法以保均匀；  
- 次依业务选一致性哈希以利伸缩；  
- 若需范围查询且键分布可控，方用范围分片，并配监控与自动分裂机制；  
- 无论何法，必配热键探测与局部隔离策略（如拆分热键、加缓存、限流），以防单点坍塌。
### 按键值范围分片 {#sec_sharding_key_range}
分片之法，其一为按连续键值区间分配：每一分片承载一连续键值段（自某下界至某上界），类比纸质百科全书之卷册，如[图7-2](/zh-cn/ch7#fig_sharding_encyclopedia)所示。此处，条目之分区键即为其标题。若欲查某标题所对应条目，但须定位其所在分片——可先判该标题落于何一区间，即知其所属卷册，遂取架上相应之书即可。
{{< figure src="/fig/ddia_0702.png" id="fig_sharding_encyclopedia" caption="Figure 7-2. A print encyclopedia is sharded by key range." class="w-full my-4" >}}
键值区间未必等距划分，盖因数据分布本不均匀。例如，[图7-2](/zh-cn/ch7#fig_sharding_encyclopedia)中，第1卷涵盖以A、B开头之词，而第12卷则涵盖以T、U、V、W、X、Y、Z开头之词；若机械地按字母表每两字母设一卷，则各卷所载数据量悬殊甚巨。欲使数据均衡分布，分片边界须依实际数据密度动态调整。

分片边界可由管理员手动设定，亦可由数据库自动推定。Vitess（MySQL之分片中间件）即采手动键范围分片；自动推定者，则见于Bigtable、其开源对应物HBase、MongoDB之范围分片选项、CockroachDB、RethinkDB及FoundationDB [^6]；YugabyteDB则兼备手动与自动tablet分裂能力。

各分片内部，键按序存储（如第4章所述之B树或SSTable结构）；此法便于范围扫描，并可将键视作复合索引，藉单次查询获取多个关联记录（参见[“多维与全文索引”](/zh-cn/ch4#sec_storage_multidimensional)）。例如，传感器网络应用中，若以测量时间戳为键，则范围扫描极为实用——可便捷提取某月全部读数。

然键范围分片之弊，在于邻近键高频写入易致热点分片。若键为时间戳，则分片即对应时间区间（如每月一分片）；不幸者，传感器数据随采随写，所有新写入皆涌向当月所属分片，致该分片写负载过载，余者闲置空转 [^13]。

为避此弊于传感器数据库中，不可单以时间戳为键首部。宜将传感器ID前置，使键排序先依ID、再依时间戳。假定多传感器并发活跃，则写负载自然均摊至各分片。其弊则在于：若需跨时段检索多传感器数据，须对每个传感器分别执行一次范围查询。
#### 重平衡键范围分片数据 {#rebalancing-key-range-sharded-data}
初次建库之时，尚无键区间可作分片之用。部分数据库（如 HBase、MongoDB）允在空库上预设初始分片集，此谓 *预分片（pre-splitting）*。然此举须预估键分布形态，方能择定合宜之键区间边界 [^14]。

其后，随数据量与写入吞吐增长，基于键区间之分片系统，借将既有分片一分为二（或更多），以实现扩容：各新分片持原分片键区间之一连续子区间；继而可将诸小分片分置多节点。若大量数据被删，则亦需将若干相邻之小分片合并为一大分片。

此机制类同 B 树顶层之分裂与合并（参见 [“B 树”](/zh-cn/ch4#sec_storage_b_trees)）。

于自动管理分片边界的数据库中，分片分裂通常由下述条件触发：

* 分片达配置大小（例：HBase 默认阈值为 10 GB）；  
* 或于部分系统中，写入吞吐持续逾某阈值——故热点分片纵数据量未巨，亦可分裂，以均衡写负载。

键区间分片之优，在于分片数随数据量自适应：数据少则分片少，开销微；数据巨则单分片大小受限于可配之上限 [^15]，不致失控。

其弊在于分片分裂代价高昂：须重写全部数据至新文件，类同日志结构存储引擎之压缩（compaction）。而亟待分裂之分片，常已处高负载状态；分裂本身所增开销，反易加剧过载风险。
### 按键哈希分片 {#sec_sharding_hash}
键范围分片适用于需将邻近（但不相同）的分区键记录聚于同一分片之场景；例如，时间戳即属此类。若分区键是否邻近无关紧要（如多租户应用中的租户 ID），则常见做法为：先对分区键作哈希，再依哈希值映射至分片。

优良哈希函数可将偏斜数据转化为均匀分布。设有一 32 位哈希函数，输入为字符串，则每次输入新字符串，均返回一个看似随机、介于 $0$ 至 $2^{32} - 1$ 之间的整数。即使输入字符串高度相似，其哈希值亦在此区间内均匀散布；且同一输入恒得同一输出。

就分片而言，哈希函数无需具备密码学强度：例如，MongoDB 采用 MD5，Cassandra 与 ScyllaDB 采用 Murmur3。多数编程语言内置简易哈希函数（供哈希表使用），但未必适于分片：例如 Java 的 `hashCode()` 与 Ruby 的 `hash()` 在不同进程间可能为同一键生成不同哈希值，故不适用于分片一致性要求。
#### 哈希取模节点数法 {#hash-modulo-number-of-nodes}
哈希键值后，如何选定存储分片？初想或取哈希值对节点总数 $ N $ 取模（多数编程语言中以 `& MASK_0` 实现）。例如，`hash(key) % 10` 得 0 至 9 间整数（若哈希值以十进制表示，则余数即末位数字）；若有编号为 0 至 9 的 10 个节点，此法似可简易映射键至节点。

然 `mod N` 法之弊，在于节点数 $ N $ 变更时，绝大多数键须重分配。[图 7-3](/zh-cn/ch7#fig_sharding_hash_mod_n) 示：原三节点扩容至四节点时，重平衡前后映射剧变——原属节点 0 之键（哈希值为 0、3、6、9…）悉数迁移：哈希 3 者移至节点 3，哈希 6 者移至节点 2，哈希 9 者移至节点 1，余类推。
{{< figure src="/fig/ddia_0703.png" id="fig_sharding_hash_mod_n" caption="Figure 7-3. Assigning keys to nodes by hashing the key and taking it modulo the number of nodes. Changing the number of nodes results in many keys moving from one node to another." class="w-full my-4" >}}
模 $N$ 函数虽易计算，然致再平衡极低效：节点间记录迁移频仍，且多属冗余。  
故须另择策略，务使数据迁移量趋最小。
#### 固定分片数 {#fixed-number-of-shards}
一种简明而常用之法，是令分片（shard）总数远超节点（node）数目，并于各节点上分配多个分片。  
例如：十节点集群所运行之数据库，初始即划分为一千分片，每节点承负百片。  
键（key）之存储位置为第 `hash(key) % 1000` 号分片；系统另以独立元数据记录各分片所在节点。

若集群新增一节点，则系统可自既有节点迁移若干分片至新节点，直至各节点负载复归均衡——此过程见[图7-4](/zh-cn/ch7#fig_sharding_rebalance_fixed)。  
若节点被移除，则反向执行：将其所持分片重分配至余下节点。
{{< figure src="/fig/ddia_0704.png" id="fig_sharding_rebalance_fixed" caption="Figure 7-4. Adding a new node to a database cluster with multiple shards per node." class="w-full my-4" >}}
此模型中，仅整块分片（shard）在节点间迁移，较拆分分片为省；  
分片总数不变，键（key）至分片之映射亦不变；唯分片至节点之分配可变。  
然此分配变更非即时：因需经网络传输大量数据，故迁移期间，读写操作仍沿用旧分配。

常取分片数为高合数（如 360、720），以便数据集可均分于不同数量之节点——无须节点数必为 2 的幂次（例如 [^4]）。  
亦可适配集群内硬件异构：将更多分片指派予更强节点，使其承担更高负载。

此分片法见于 Citus（PostgreSQL 分片层）、Riak、Elasticsearch、Couchbase 等系统。  
其效优，前提为建库之初对所需分片数有较准预估。此后增删节点皆易，唯受限于：节点数不可逾分片数。

若初设分片数失当——例如规模扩张后，所需节点数已超分片数——则须执行代价高昂之重分片（resharding）：  
逐一分片拆解，并写入新文件，过程耗用大量额外磁盘空间；  
部分系统更禁止重分片期间并发写入，致变更分片数必伴停机。

若数据集总规模高度可变（如起始甚小，后续剧增），则择定分片数尤难。  
因每分片恒占总数据之固定比例，故分片大小随集群总数据量线性增长。  
分片过大，则再平衡（rebalancing）与节点故障恢复成本剧增；  
分片过小，则元数据、连接、调度等开销过重。  
最优性能生于分片大小“恰如其分”之时——既非过大，亦非过小；  
然若分片数固定而数据量浮动，则此“恰如其分”殊难持守。
#### 按哈希范围分片 {#sharding-by-hash-range}
若分片数量无法预先确定，则宜采用可随负载动态伸缩的分片方案。前述基于键范围（key-range）的分片法即具此特性，然其存在热点风险：当大量写操作集中于邻近键时，易致某一分片负载过重。一解法是将键范围分片与哈希函数结合，使每一分片承载一段**哈希值区间**，而非原始**键区间**。

[图 7-5](/zh-cn/ch7#fig_sharding_hash_range) 示意一例：采用 16 位哈希函数，输出为 $0$ 至 $65{,}535 = 2^{16} - 1$ 之间的整数（实际中哈希值通常为 32 位或更长）。即便输入键高度相似（如连续时间戳），其哈希值亦在此范围内均匀分布。继而可将哈希值空间划分为若干连续子区间，分别分配至各分片：例如，哈希值 $0$ 至 $16{,}383$ 归属分片 0，$16{,}384$ 至 $32{,}767$ 归属分片 1，依此类推。
{{< figure src="/fig/ddia_0705.png" id="fig_sharding_hash_range" caption="Figure 7-5. Assigning a contiguous range of hash values to each shard." class="w-full my-4" >}}
如键值范围分片（key-range sharding）一样，哈希-范围分片（hash-range sharding）中，单一分片亦可于其体积过大或负载过重时拆分。此操作虽仍昂贵，然可按需触发，故分片总数随数据量动态伸缩，而非预先固定。

相较键值范围分片，其弊在于：对分区键（partition key）的范围查询不再高效——因范围内各键经哈希后散落于全部分片。然若键由两列及以上构成，且仅首列为分区键，则仍可对第二列及后续列执行高效范围查询：只要该范围查询所涉所有记录共享同一分区键，其必共存于同一分片。

> [!TIP] 数据仓库中的分区与范围查询  
> BigQuery、Snowflake 与 Delta Lake 等数据仓库支持类似索引机制，术语略有差异。例如，在 BigQuery 中，分区键（partition key）决定记录归属之分区，而“聚簇列”（cluster columns）决定记录在该分区内之排序方式。Snowflake 自动将记录分配至“微分区”（micro-partitions），但允许用户为表定义聚簇键（clustering key）。Delta Lake 支持手动与自动分区分配，并支持聚簇键。数据聚簇不仅提升范围扫描性能，亦可增强压缩率与过滤性能。

哈希-范围分片见于 YugabyteDB 与 DynamoDB（[^17]），MongoDB 将其列为可选方案。Cassandra 与 ScyllaDB 则采用此法之变体，如[图 7-6](/zh-cn/ch7#fig_sharding_cassandra)所示：哈希值空间被划分为若干区间，区间数正比于节点数（[图 7-6](/zh-cn/ch7#fig_sharding_cassandra)中为每节点 3 区间；实际部署中，Cassandra 默认每节点 8 区间，ScyllaDB 默认每节点 256 区间），区间边界随机设定。由此，各区间长度不等；但因每节点承载多个区间，负载不均倾向趋于抵消（[^15] [^18]）。
{{< figure src="/fig/ddia_0706.png" id="fig_sharding_cassandra" caption="Figure 7-6. Cassandra and ScyllaDB split the range of possible hash values (here 0–1023) into contiguous ranges with random boundaries, and assign several ranges to each node." class="w-full my-4" >}}
节点增删之时，区间边界随之增删，分片亦相应分裂或合并，[^19]。  
如[图7-6](/zh-cn/ch7#fig_sharding_cassandra)所示：节点3加入时，节点1将其两个区间的部分数据移交节点3，节点2将其一个区间的部分数据移交节点3。此举使新节点获得数据集之大致均等份额，且节点间数据迁移量不逾必要之限。
#### 一致性哈希 {#sec_sharding_consistent_hashing}
一致性哈希（*consistent hashing*）是一种哈希算法，将键映射至指定数量的分片（shard），须满足两项性质：

1. 各分片所承载之键数大致均衡；  
2. 分片总数变动时，迁移键的数量应尽可能少。

须注意：此处“一致性”（*consistent*）与副本一致性（参见[第6章](/zh-cn/ch6#ch_replication)）或 ACID 一致性（参见[第8章](/zh-cn/ch8#ch_transactions)）无关，仅指键在分片中归属位置的稳定性——即同一键在分片规模变化时，仍尽可能保留在原分片。

Cassandra 与 ScyllaDB 所用分片算法，近似于一致性哈希之原始定义 [^20]；然另有多种一致性哈希变体亦被提出 [^21]，例如 *最高随机权重法*（*highest random weight*），亦称 * rendezvous 哈希*（*rendezvous hashing*）[^22]，以及 *jump consistent hash* [^23]。  

Cassandra 算法中，新增一节点时，仅少数既有分片被拆分为子区间；而 rendezvous 哈希与 jump consistent hash 则为新节点直接分配若干离散键——这些键此前均匀散布于全部既有节点之上。优劣取舍，取决于具体应用场景。
### 偏斜工作负载与热点缓解 {#sec_sharding_skew}
一致性哈希可使键均匀分布于各节点，然此不等于实际负载亦均匀分布。若工作负载高度倾斜——即某些分区键所承载之数据量远超其余键，或某些键之请求速率远高于其余键——则仍可能出现部分服务器过载、而其余服务器几近空闲之情形。

例如，在社交网站中，某拥有数百万关注者的名人用户，一旦其执行某操作 [^24]，即可能引发流量风暴。  
此事可致大量读写集中于同一键（该分区键或为该名人之用户 ID，或为众人评论所涉动作之 ID）。

此时，需采用更灵活之分片策略 [^25] [^26]。  
若系统依键值范围（或哈希值范围）定义分片，则可将单个热键独占一 shard，甚或为其指派专用机器 [^27]。

亦可在应用层补偿倾斜。例如，若已知某键极热，一种简易技术是在键首或键尾附加随机数。  
仅两位十进制随机数，即可将对该键之写入均分至 100 个不同键，从而将其分散至不同分片。

然写入既已分散，则读取须额外工作：须从全部 100 个键读取并合并数据。  
各分片所承受之读负载并未降低；仅写负载得以拆分。此法尚需额外簿记：仅对少量热键追加随机数方具意义；对绝大多数低吞吐键施加此操作，反成冗余开销。故须另设机制，以追踪哪些键已被拆分，并实现常规键向特管热键之转换。

负载随时间变化，更使问题复杂化：例如，某条走红之社交帖文，或于数日内承受高负载，此后则趋于平缓；且某些键或写热，另一些则读热，所需应对策略亦当有别。

部分系统（尤指面向大规模之云服务）已具备自动处理热分片之能力；例如，Amazon 称之为 *heat management* [^28] 或 *adaptive capacity* [^17]。  
此类系统之具体实现细节，已超出本书范畴。
### 操作：自动或手动再平衡 {#sec_sharding_operations}
关于分片再平衡，有一关键问题此前未予深究：**分片拆分与再平衡，系自动触发，抑或人工干预？**

部分系统可全自动判定分片拆分时机及跨节点迁移时机，全程无需人工介入；另有一些系统则将分片策略完全交由管理员显式配置。亦有折中方案：例如 Couchbase 与 Riak 可自动生成分片分配建议，然须经管理员确认后方生效。

全自动再平衡虽便利——日常运维负担较轻，且可依负载变化自动伸缩——云数据库（如 DynamoDB）即以此为卖点，宣称可在数分钟内自动增删分片，以应对负载的剧烈涨落 [^17] [^29]。

然自动分片管理亦存不可控之虞。再平衡本身开销甚巨：须重路由请求，并在节点间迁移海量数据。若调度失当，易致网络或节点过载，进而拖累其他请求之性能。再平衡期间，系统仍须持续处理写入；若写入吞吐已近上限，则分片拆分过程甚至无法追上新写入速率 [^29]。

此等自动化，若与自动故障检测耦合，尤具风险。例如：某节点因过载而响应迟缓，其余节点误判其“宕机”，遂自动触发再平衡，将负载迁出。此举反向加剧余下节点与网络之负载，恶化全局状况。更甚者，或引发级联失败——其余节点相继过载，继而被误判为宕机。

故而，再平衡环节保留人工介入，反为审慎之举。虽较全自动为慢，却可规避运维意外。
## 请求路由 {#sec_sharding_routing}
我们已讨论数据集如何分片至多节点，以及节点增删时如何重平衡分片。今转而探讨一关键问题：若需读写某一特定键（key），当知其应路由至何节点——即目标节点之 IP 地址与端口号。

此即所谓**请求路由**（request routing），其原理近似前文所述之**服务发现**（service discovery）（参见[“负载均衡器、服务发现与服务网格”](/zh-cn/ch5#sec_encoding_service_discovery)）。二者最大差异在于：应用服务实例通常无状态，负载均衡器可将请求任意分发至任一实例；而分片数据库中，某键之请求仅能由该键所属分片之副本节点处理。

故请求路由须明晓两层映射关系：其一，键至分片之映射；其二，分片至节点之映射。概言之，有三类主流解法（见[图 7-7](/zh-cn/ch7#fig_sharding_routing)）：

1. 客户端可连任一节点（例如经轮询式负载均衡器）。若该节点恰为所涉分片之主/副本，则直答；否则，转发请求至目标节点，收得响应后回传客户端。  
2. 所有客户端请求先达**路由层**（routing tier）；该层依分片映射判定目标节点，再行转发。路由层自身不处理业务逻辑，唯作分片感知型负载均衡器。  
3. 客户端自持分片策略及分片-节点映射表。此时客户端可直连目标节点，无需中介。
{{< figure src="/fig/ddia_0707.png" id="fig_sharding_routing" caption="Figure 7-7. Three different ways of routing a request to the right node." class="w-full my-4" >}}
各类场景下，皆存若干关键问题：

* 分片归属决策由谁作出？即：何者判定某分片应驻于何节点？  
  最简方案，乃设单一协调者（coordinator）统管此事；然若该协调者所在节点宕机，如何保障其容错性？  
  若协调者角色可故障转移至他节点，则又须防“脑裂”（split-brain）——即两协调者并存、就同一分片作出互斥指派（参见[“节点故障处理”](/zh-cn/ch6#sec_replication_failover)）。

* 执行路由之组件（或为数据节点自身，或为独立路由层，或为分片感知型客户端），如何获知分片—节点映射之变更？

* 分片迁移期间，新旧节点存在交叠窗口：新节点已接管服务，而发往旧节点之请求仍可能在途。此类请求当如何处置？

诸多分布式数据系统，借由独立协调服务（如 ZooKeeper 或 etcd）维护分片归属映射，如[图7-8](/zh-cn/ch7#fig_sharding_zookeeper)所示。  
其依托共识算法（参见[第10章](/zh-cn/ch10#ch_consistency)），实现容错与脑裂防护。  
各节点向 ZooKeeper 自注册；ZooKeeper 持有且仅持有分片至节点之权威映射。  
路由层或分片感知型客户端等参与者，可订阅 ZooKeeper 中该映射。  
一旦分片归属变更，或节点增删，ZooKeeper 即刻通知路由层，使其路由信息实时同步。
{{< figure src="/fig/ddia_0708.png" id="fig_sharding_zookeeper" caption="Figure 7-8. Using ZooKeeper to keep track of assignment of shards to nodes." class="w-full my-4" >}}
例如，HBase 与 SolrCloud 借助 ZooKeeper 管理分片（shard）分配；Kubernetes 则以 etcd 记录各服务实例的运行位置。MongoDB 架构类似，但其采用自研 *config server* 及 *mongos* 守护进程作为路由层。Kafka、YugabyteDB 与 TiDB 则内建 Raft 共识协议实现协调功能。

Cassandra、ScyllaDB 与 Riak 另辟蹊径：节点间通过 *gossip 协议* 传播集群状态变更。此法一致性弱于共识协议；可能出现“脑裂”（split brain），即同一分片在集群不同区域被赋予互异的节点归属。无主数据库（leaderless database）可容忍此情形，盖因其本就仅提供弱一致性保证（参见［“Quorum 一致性之局限”］(/zh-cn/ch6#sec_replication_quorum_limitations)）。

若采用路由层，或向随机节点发送请求，客户端仍须获知待连 IP 地址。此类地址变动频次远低于分片—节点映射关系，故常以 DNS 解决即可。

以上关于请求路由之讨论，聚焦于单个键（key）所对应分片之定位，此对分片型 OLTP 数据库最为关键。分析型数据库亦常分片，然其查询执行模式迥异：查询通常需并行聚合、联结（JOIN）多个分片之数据，而非限于单一分片。此类并行查询执行技术，详见［“JOIN 与 GROUP BY”］(/zh-cn/ch11#sec_batch_join)。
## 分片与二级索引 {#sec_sharding_secondary_indexes}
此前所论分片方案，皆以客户端知晓待访问记录之分区键为前提。此在键值数据模型中最易实现：分区键即主键之首部（或即主键本身），故可依分区键判定所属分片，进而将读写请求路由至对应节点。

若引入二级索引（参见[“多列索引与二级索引”](/zh-cn/ch4#sec_storage_index_multicolumn)），情形则趋复杂。二级索引通常不唯一标识记录，而仅提供按特定值检索的途径：如查用户 `123` 所有操作、查含词 `hogwash` 的全部文章、查颜色为 `red` 的全部汽车等。

键值存储常无二级索引；然其为关系型数据库之核心功能，亦广泛见于文档数据库；更乃 Solr 与 Elasticsearch 等全文检索引擎之立身根本（*raison d’être*）。二级索引之难，在于其难以自然映射至分片。对含二级索引之数据库实施分片，主流方案有二：本地索引（local index）与全局索引（global index）。
### 本地二级索引 {#id166}
例如，设有一二手车销售网站（参见[图7-9](/zh-cn/ch7#fig_sharding_local_secondary)）。每条车辆信息具唯一 ID，该 ID 用作分片键（shard key）：ID ∈ [0, 499] 归入分片 0，ID ∈ [500, 999] 归入分片 1，依此类推。

若需支持用户按颜色（color）与品牌（make）筛选车辆，则须在 `color` 与 `make` 上建立二级索引（secondary index）：在文档数据库中，二者为字段（field）；在关系型数据库中，二者为列（column）。索引一经声明，数据库即自动维护。例如，当一条红色车辆记录写入数据库时，所在分片自动将其 ID 加入索引项 `color:red` 对应的 ID 列表中。如[第4章](/zh-cn/ch4#ch_storage)所述，该 ID 列表亦称 *倒排列表*（postings list）。
{{< figure src="/fig/ddia_0709.png" id="fig_sharding_local_secondary" caption="Figure 7-9. Local secondary indexes: each shard indexes only the records within its own shard." class="w-full my-4" >}}
> [!WARNING] 警告

若数据库仅支持键值模型，你或会试图在应用层自行实现二级索引——即通过代码维护“值→ID”的映射。此路径须格外审慎，以确保索引与底层数据始终一致。竞态条件及间歇性写入失败（部分变更已落盘、其余未落盘）极易导致数据失同步——参见[“多对象事务之必要”](/zh-cn/ch8#sec_transactions_need)。

--------

此索引方案中，各分片完全独立：每一分片仅维护自身所含记录的二级索引，不感知他片所存数据。凡向数据库写入（新增、删除或更新记录），只需操作该记录所属之分片。故此类二级索引称作*本地索引*（*local index*）；在信息检索领域亦称*文档分区索引*（*document-partitioned index*）[^30]。

读取本地二级索引时，若已知目标记录之分区键，可直接于对应分片执行查询；若仅需*部分*结果（非全部），亦可任选一分片发起请求。

然若需获取*全部*匹配结果，且事先未知其分区键，则须向所有分片广播查询，并合并返回结果——因匹配记录可能散落于各分片。如[图7-9](/zh-cn/ch7#fig_sharding_local_secondary)所示，红色车辆同时出现于分片0与分片1。

此法查询分片数据库之二级索引，读性能开销颇高。纵使并行查询各分片，仍易受尾部延迟放大效应所累（参见[“响应时间度量之用”](/zh-cn/ch2#sec_introduction_slo_sla)）。亦制约应用可扩展性：增分片可扩存储容量，却无法提升查询吞吐——盖因每查询皆须遍历全体分片。

然本地二级索引仍被广泛采用 [^31]：例如 MongoDB、Riak、Cassandra [^32]、Elasticsearch [^33]、SolrCloud 与 VoltDB [^34]，悉以此为默认索引机制。
### 全局二级索引 {#id167}
与其为每个分片维护各自独立的本地二级索引，不如构建一个覆盖所有分片数据的**全局索引**。  
然此索引不可集中存储于单节点——否则必成性能瓶颈，反使分片之效尽失。  
故全局索引亦须分片，但其分片策略可异于主键索引。

[图 7-10](/zh-cn/ch7#fig_sharding_global_secondary) 示意此结构：所有分片中红色汽车（`red`）之 ID 均归入索引中 `color:red` 项下；  
然该索引自身按颜色首字母分片——首字母为 *a* 至 *r* 者入分片 0，*s* 至 *z* 者入分片 1。  
同理，汽车品牌（`make`）索引亦作类似划分，分片边界设于字母 *f* 与 *h* 之间。
{{< figure src="/fig/ddia_0710.png" id="fig_sharding_global_secondary" caption="Figure 7-10. A global secondary index reflects data from all shards, and is itself sharded by the indexed value." class="w-full my-4" >}}
此类索引亦称**按项分片索引**（*term-partitioned* [^30]）：  
前文[“全文检索”](/zh-cn/ch4#sec_storage_full_text)已述，全文检索中，“项”（*term*）指文本中可被检索的关键词；此处将其泛化为：**可在二级索引中被检索的任意值**。

全局索引以“项”为分区键，故查询特定项或值时，可直接定位所需查询的分片。分片划分方式一如往常：其一，按项的连续字典范围分配（见[图7-10](/zh-cn/ch7#fig_sharding_global_secondary)）；其二，按项的哈希值分配。

全局索引之优，在于单条件查询（如 *color = red*）仅需访问一个分片，即可获取倒排列表（postings list）。然若需读取完整记录而非仅ID，则仍须访问所有承载这些ID的分片。

若含多个检索条件或多项（例如：同时按颜色与品牌筛选汽车，或检索同一文本中同时出现的多个词），则各项极可能落于不同分片。此时，系统须计算两倒排列表之交集，以实现逻辑与（AND）运算。若倒排列表甚短，此操作无碍；若过长，则跨网络传输并求交，将显著拖慢性能 [^30]。

全局二级索引另一难点在于写入复杂度高于本地索引：单条记录写入，可能触发索引中多个分片的更新（因文档内各“项”或散落于不同分片）。此使二级索引与底层数据保持强一致更为困难。一种解法是采用分布式事务，原子性地同步更新主记录所在分片及其关联的全部二级索引分片（参见[第8章](/zh-cn/ch8#ch_transactions)）。

CockroachDB、TiDB 与 YugabyteDB 均采用全局二级索引；DynamoDB 则同时支持本地与全局二级索引。在 DynamoDB 中，全局索引之更新为异步，故从中读取的数据可能存在滞后（类同[“复制延迟问题”](/zh-cn/ch6#sec_replication_lag)所述之复制延迟）。  
然若读吞吐远高于写吞吐，且倒排列表长度可控，则全局索引仍具实用价值。
## 概要 {#summary}
本章探讨将大规模数据集分片（sharding）为若干子集的不同方法。

分片之必要，缘于数据量过大，单机已不堪存储与计算之重。

分片之要旨，在于将数据与查询负载均摊至多台机器，避热点（即负载畸高之节点）。此需择适配数据特征之分片策略，并于集群增删节点时动态再平衡各分片。

兹述两种主流分片法：

* *键值区间分片（key range sharding）*：按键排序，每一分片持有某最小键至某最大键之间全部键值。排序之利，在于可高效执行范围查询；然若应用常访问排序邻近之键，则易生热点。

 此法中，分片再平衡通常借“分裂”实现——当某分片过大，即将其键区间一分为二，各成新分片。

* *哈希分片（hash sharding）*：对每一键施以哈希函数，各分片持有某段哈希值区间（或采用一致性哈希等算法映射哈希值至分片）。此法弃键序，致范围查询低效；然负载分布往往更均衡。

 哈希分片常预先设定固定分片总数，使每节点承载多个分片；增删节点时，整分片迁移即可；亦可如区间分片般分裂分片。

实践中，常取键之前缀为分区键（partition key），用以定位分片；而在该分片内，再依键之其余部分排序记录。如此，同属一分区键之记录间，仍可高效执行范围查询。

复论分片与二级索引之交互。二级索引亦须分片，其法有二：

* *本地二级索引（local secondary index）*：索引与对应主键-值共存于同一分片。写入时仅需更新单一分片；然索引查找须遍历全部分片。

* *全局二级索引（global secondary index）*：索引按被索引值独立分片。一条索引项可指向主键所有分片之记录。写入时，或需更新多个索引分片；然检索倒排表（postings list）可由单一分片响应（但获取实际记录仍须跨多分片读取）。

终论查询路由：须将请求精准导向目标分片；常借协调服务（coordination service）维护“分片→节点”映射关系。

分片数据库之设计本意，即令各分片高度自治——此乃其可横向扩展至多机之根基。然跨分片写入操作 fraught with hazard：若一 shard 写入成功，另一 shard 却失败，当如何？此问留待后章详析。
### 参考文献

[^1]: Claire Giordano. [Understanding partitioning and sharding in Postgres and Citus](https://www.citusdata.com/blog/2023/08/04/understanding-partitioning-and-sharding-in-postgres-and-citus/). *citusdata.com*, August 2023. Archived at [perma.cc/8BTK-8959](https://perma.cc/8BTK-8959) 
[^2]: Brandur Leach. [Partitioning in Postgres, 2022 edition](https://brandur.org/fragments/postgres-partitioning-2022). *brandur.org*, October 2022. Archived at [perma.cc/Z5LE-6AKX](https://perma.cc/Z5LE-6AKX) 
[^3]: Raph Koster. [Database “sharding” came from UO?](https://www.raphkoster.com/2009/01/08/database-sharding-came-from-uo/) *raphkoster.com*, January 2009. Archived at [perma.cc/4N9U-5KYF](https://perma.cc/4N9U-5KYF) 
[^4]: Garrett Fidalgo. [Herding elephants: Lessons learned from sharding Postgres at Notion](https://www.notion.com/blog/sharding-postgres-at-notion). *notion.com*, October 2021. Archived at [perma.cc/5J5V-W2VX](https://perma.cc/5J5V-W2VX) 
[^5]: Ulrich Drepper. [What Every Programmer Should Know About Memory](https://www.akkadia.org/drepper/cpumemory.pdf). *akkadia.org*, November 2007. Archived at [perma.cc/NU6Q-DRXZ](https://perma.cc/NU6Q-DRXZ) 
[^6]: Jingyu Zhou, Meng Xu, Alexander Shraer, Bala Namasivayam, Alex Miller, Evan Tschannen, Steve Atherton, Andrew J. Beamon, Rusty Sears, John Leach, Dave Rosenthal, Xin Dong, Will Wilson, Ben Collins, David Scherer, Alec Grieser, Young Liu, Alvin Moore, Bhaskar Muppana, Xiaoge Su, and Vishesh Yadav. [FoundationDB: A Distributed Unbundled Transactional Key Value Store](https://www.foundationdb.org/files/fdb-paper.pdf). At *ACM International Conference on Management of Data* (SIGMOD), June 2021. [doi:10.1145/3448016.3457559](https://doi.org/10.1145/3448016.3457559) 
[^7]: Marco Slot. [Citus 12: Schema-based sharding for PostgreSQL](https://www.citusdata.com/blog/2023/07/18/citus-12-schema-based-sharding-for-postgres/). *citusdata.com*, July 2023. Archived at [perma.cc/R874-EC9W](https://perma.cc/R874-EC9W) 
[^8]: Robisson Oliveira. [Reducing the Scope of Impact with Cell-Based Architecture](https://docs.aws.amazon.com/pdfs/wellarchitected/latest/reducing-scope-of-impact-with-cell-based-architecture/reducing-scope-of-impact-with-cell-based-architecture.pdf). AWS Well-Architected white paper, Amazon Web Services, September 2023. Archived at [perma.cc/4KWW-47NR](https://perma.cc/4KWW-47NR) 
[^9]: Gwen Shapira. [Things DBs Don’t Do - But Should](https://www.thenile.dev/blog/things-dbs-dont-do). *thenile.dev*, February 2023. Archived at [perma.cc/C3J4-JSFW](https://perma.cc/C3J4-JSFW) 
[^10]: Malte Schwarzkopf, Eddie Kohler, M. Frans Kaashoek, and Robert Morris. [Position: GDPR Compliance by Construction](https://cs.brown.edu/people/malte/pub/papers/2019-poly-gdpr.pdf). At *Towards Polystores that manage multiple Databases, Privacy, Security and/or Policy Issues for Heterogenous Data* (Poly), August 2019. [doi:10.1007/978-3-030-33752-0\_3](https://doi.org/10.1007/978-3-030-33752-0_3) 
[^11]: Gwen Shapira. [Introducing pg\_karnak: Transactional schema migration across tenant databases](https://www.thenile.dev/blog/distributed-ddl). *thenile.dev*, November 2024. Archived at [perma.cc/R5RD-8HR9](https://perma.cc/R5RD-8HR9) 
[^12]: Arka Ganguli, Guido Iaquinti, Maggie Zhou, and Rafael Chacón. [Scaling Datastores at Slack with Vitess](https://slack.engineering/scaling-datastores-at-slack-with-vitess/). *slack.engineering*, December 2020. Archived at [perma.cc/UW8F-ALJK](https://perma.cc/UW8F-ALJK) 
[^13]: Ikai Lan. [App Engine Datastore Tip: Monotonically Increasing Values Are Bad](https://ikaisays.com/2011/01/25/app-engine-datastore-tip-monotonically-increasing-values-are-bad/). *ikaisays.com*, January 2011. Archived at [perma.cc/BPX8-RPJB](https://perma.cc/BPX8-RPJB) 
[^14]: Enis Soztutar. [Apache HBase Region Splitting and Merging](https://www.cloudera.com/blog/technical/apache-hbase-region-splitting-and-merging.html). *cloudera.com*, February 2013. Archived at [perma.cc/S9HS-2X2C](https://perma.cc/S9HS-2X2C) 
[^15]: Eric Evans. [Rethinking Topology in Cassandra](https://www.youtube.com/watch?v=Qz6ElTdYjjU). At *Cassandra Summit*, June 2013. Archived at [perma.cc/2DKM-F438](https://perma.cc/2DKM-F438) 
[^16]: Martin Kleppmann. [Java’s hashCode Is Not Safe for Distributed Systems](https://martin.kleppmann.com/2012/06/18/java-hashcode-unsafe-for-distributed-systems.html). *martin.kleppmann.com*, June 2012. Archived at [perma.cc/LK5U-VZSN](https://perma.cc/LK5U-VZSN) 
[^17]: Mostafa Elhemali, Niall Gallagher, Nicholas Gordon, Joseph Idziorek, Richard Krog, Colin Lazier, Erben Mo, Akhilesh Mritunjai, Somu Perianayagam, Tim Rath, Swami Sivasubramanian, James Christopher Sorenson III, Sroaj Sosothikul, Doug Terry, and Akshat Vig. [Amazon DynamoDB: A Scalable, Predictably Performant, and Fully Managed NoSQL Database Service](https://www.usenix.org/conference/atc22/presentation/elhemali). At *USENIX Annual Technical Conference* (ATC), July 2022. 
[^18]: Brandon Williams. [Virtual Nodes in Cassandra 1.2](https://www.datastax.com/blog/virtual-nodes-cassandra-12). *datastax.com*, December 2012. Archived at [perma.cc/N385-EQXV](https://perma.cc/N385-EQXV) 
[^19]: Branimir Lambov. [New Token Allocation Algorithm in Cassandra 3.0](https://www.datastax.com/blog/new-token-allocation-algorithm-cassandra-30). *datastax.com*, January 2016. Archived at [perma.cc/2BG7-LDWY](https://perma.cc/2BG7-LDWY) 
[^20]: David Karger, Eric Lehman, Tom Leighton, Rina Panigrahy, Matthew Levine, and Daniel Lewin. [Consistent Hashing and Random Trees: Distributed Caching Protocols for Relieving Hot Spots on the World Wide Web](https://people.csail.mit.edu/karger/Papers/web.pdf). At *29th Annual ACM Symposium on Theory of Computing* (STOC), May 1997. [doi:10.1145/258533.258660](https://doi.org/10.1145/258533.258660) 
[^21]: Damian Gryski. [Consistent Hashing: Algorithmic Tradeoffs](https://dgryski.medium.com/consistent-hashing-algorithmic-tradeoffs-ef6b8e2fcae8). *dgryski.medium.com*, April 2018. Archived at [perma.cc/B2WF-TYQ8](https://perma.cc/B2WF-TYQ8) 
[^22]: David G. Thaler and Chinya V. Ravishankar. [Using name-based mappings to increase hit rates](https://www.cs.kent.edu/~javed/DL/web/p1-thaler.pdf). *IEEE/ACM Transactions on Networking*, volume 6, issue 1, pages 1–14, February 1998. [doi:10.1109/90.663936](https://doi.org/10.1109/90.663936) 
[^23]: John Lamping and Eric Veach. [A Fast, Minimal Memory, Consistent Hash Algorithm](https://arxiv.org/abs/1406.2294). *arxiv.org*, June 2014. 
[^24]: Samuel Axon. [3% of Twitter’s Servers Dedicated to Justin Bieber](https://mashable.com/archive/justin-bieber-twitter). *mashable.com*, September 2010. Archived at [perma.cc/F35N-CGVX](https://perma.cc/F35N-CGVX) 
[^25]: Gerald Guo and Thawan Kooburat. [Scaling services with Shard Manager](https://engineering.fb.com/2020/08/24/production-engineering/scaling-services-with-shard-manager/). *engineering.fb.com*, August 2020. Archived at [perma.cc/EFS3-XQYT](https://perma.cc/EFS3-XQYT) 
[^26]: Sangmin Lee, Zhenhua Guo, Omer Sunercan, Jun Ying, Thawan Kooburat, Suryadeep Biswal, Jun Chen, Kun Huang, Yatpang Cheung, Yiding Zhou, Kaushik Veeraraghavan, Biren Damani, Pol Mauri Ruiz, Vikas Mehta, and Chunqiang Tang. [Shard Manager: A Generic Shard Management Framework for Geo-distributed Applications](https://dl.acm.org/doi/pdf/10.1145/3477132.3483546). *28th ACM SIGOPS Symposium on Operating Systems Principles* (SOSP), pages 553–569, October 2021. [doi:10.1145/3477132.3483546](https://doi.org/10.1145/3477132.3483546) 
[^27]: Scott Lystig Fritchie. [A Critique of Resizable Hash Tables: Riak Core & Random Slicing](https://www.infoq.com/articles/dynamo-riak-random-slicing/). *infoq.com*, August 2018. Archived at [perma.cc/RPX7-7BLN](https://perma.cc/RPX7-7BLN) 
[^28]: Andy Warfield. [Building and operating a pretty big storage system called S3](https://www.allthingsdistributed.com/2023/07/building-and-operating-a-pretty-big-storage-system.html). *allthingsdistributed.com*, July 2023. Archived at [perma.cc/6S7P-GLM4](https://perma.cc/6S7P-GLM4) 
[^29]: Rich Houlihan. [DynamoDB adaptive capacity: smooth performance for chaotic workloads (DAT327)](https://www.youtube.com/watch?v=kMY0_m29YzU). At *AWS re:Invent*, November 2017. 
[^30]: Christopher D. Manning, Prabhakar Raghavan, and Hinrich Schütze. [*Introduction to Information Retrieval*](https://nlp.stanford.edu/IR-book/). Cambridge University Press, 2008. ISBN: 978-0-521-86571-5, available online at [nlp.stanford.edu/IR-book](https://nlp.stanford.edu/IR-book/) 
[^31]: Michael Busch, Krishna Gade, Brian Larson, Patrick Lok, Samuel Luckenbill, and Jimmy Lin. [Earlybird: Real-Time Search at Twitter](https://cs.uwaterloo.ca/~jimmylin/publications/Busch_etal_ICDE2012.pdf). At *28th IEEE International Conference on Data Engineering* (ICDE), April 2012. [doi:10.1109/ICDE.2012.149](https://doi.org/10.1109/ICDE.2012.149) 
[^32]: Nadav Har’El. [Indexing in Cassandra 3](https://github.com/scylladb/scylladb/wiki/Indexing-in-Cassandra-3). *github.com*, April 2017. Archived at [perma.cc/3ENV-8T9P](https://perma.cc/3ENV-8T9P) 
[^33]: Zachary Tong. [Customizing Your Document Routing](https://www.elastic.co/blog/customizing-your-document-routing/). *elastic.co*, June 2013. Archived at [perma.cc/97VM-MREN](https://perma.cc/97VM-MREN) 
[^34]: Andrew Pavlo. [H-Store Frequently Asked Questions](https://hstore.cs.brown.edu/documentation/faq/). *hstore.cs.brown.edu*, October 2013. Archived at [perma.cc/X3ZA-DW6Z](https://perma.cc/X3ZA-DW6Z) 
