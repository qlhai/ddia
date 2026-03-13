---
title: "3. 数据模型与查询语言"
weight: 103
breadcrumbs: false
---

<a id="ch_datamodels"></a>
![](/map/ch02.png)

> *我语言的界限，即我世界的界限。*  
> ——路德维希·维特根斯坦，《逻辑哲学论》（1922）

数据模型，或为软件开发中至为关键之部分，盖因其影响深远：不仅关乎代码如何编写，更塑造我们对所解问题之**思维方式**。

多数应用，皆以叠层方式构建数据模型。每层之核心诘问恒为：此层如何以**下一层之模型**表征？例如：

1. 作为应用开发者，你观照现实世界（其中有人、组织、商品、行为、资金流、传感器等），并将其建模为对象或数据结构，辅以操纵该结构之 API；此类结构常为应用专属。
2. 欲持久化存储此等结构，则须映射至通用数据模型——如 JSON 或 XML 文档、关系型数据库之表、图数据库之顶点与边。此等模型，即本章所论之主题。
3. 数据库软件之工程师，则进一步将前述文档/关系/图数据，表征为内存、磁盘或网络中之字节序列；此表征须支持查询、检索、变换与处理等操作。存储引擎之设计，将于[第四章](/zh-cn/ch4#ch_storage)详述。
4. 更底层者，硬件工程师已明晓如何以电流、光脉冲、磁场等物理机制表征字节。

复杂应用中，或存更多中间层（如 API 套 API），然其根本理则未变：**每层借由提供洁净之数据模型，屏蔽下层之复杂性**。此类抽象，使不同群体——譬如数据库厂商之工程师与使用其产品的应用开发者——得以高效协力。

实务中，多种数据模型并行不悖，各司其职。某些数据形态与查询需求，在一模型中简洁自然，于另一模型中则迂回笨拙。本章将比照**关系模型、文档模型、图模型、事件溯源（event sourcing）、数据框（dataframe）**，剖析其权衡取舍；亦简述适配各模型之查询语言。此比较可助你决断：何时当用何模型。

--------

> [!TIP] 术语提示：声明式查询语言

本章所涉诸多查询语言（如 SQL、Cypher、SPARQL、Datalog）皆属**声明式（declarative）**：你仅需申明所需数据之模式——结果须满足之条件，及数据应如何变换（如排序、分组、聚合）——而**无需指定达成目标之具体路径**。数据库之查询优化器，自会择定索引、联结算法及子句执行次序。

相较之下，多数编程语言要求你手写**算法**——即明确指令计算机依何顺序执行何种操作。声明式查询语言之优，在于通常更为简练、易写；然其要义尤在：**隐去查询引擎之实现细节**，使数据库系统得以引入性能改进，而无需修改既有查询。[^1]。

例如，数据库可自动将一声明式查询并行调度至多核 CPU 乃至多机集群，你无须操心并行机制之实现 [^2]；若以手写算法为之，则此等并行化工作量甚巨。
## 关系模型 versus 文档模型 {#sec_datamodels_history}
当今最广为人知的数据模型，当属 SQL 所依托的**关系模型**（relational model），该模型由 Edgar Codd 于 1970 年提出：  
数据组织为 *关系*（SQL 中称 *表*），每张关系为一组无序的 *元组*（SQL 中称 *行*）。

关系模型初为理论构想，彼时多有质疑，以为难以高效实现。然至 1980 年代中期，**关系型数据库管理系统**（RDBMS）与 SQL 已成多数结构化数据存储与查询之首选。数十年后，诸多数据管理场景仍以关系模型为主导——例如商业分析（参见[“星型与雪花型：分析用模式”](/zh-cn/ch3#sec_datamodels_analytics)）。

历年数据存储与查询之替代方案屡出：  
- 1970 至 1980 年代初，主流为 *网状模型*（network model）与 *层次模型*（hierarchical model），终为关系模型所取代；  
- 1980 年代末至 1990 年代初，面向对象数据库（object databases）昙花一现；  
- 2000 年代初，XML 数据库登场，然仅限小众应用。  
凡此竞品，皆曾喧腾一时，然热潮未久即衰——**其兴也勃，其亡也忽**。  
反观 SQL，则持续演进，于关系核心之外，渐次吸纳 XML、JSON 与图数据等新型数据类型。

2010 年代，“NoSQL” 成为挑战关系数据库霸权之最新热词。然 NoSQL 非单一技术，实为一组松散理念之总称，涵盖新数据模型、模式灵活、可扩展性提升，以及向开源许可模式之转向。另有数据库自诩为 *NewSQL*，意在兼得 NoSQL 之可扩展性，与传统关系数据库之数据模型及事务保障。NoSQL 与 NewSQL 思想深刻影响了数据系统设计；然随其原则渐成业界共识，术语本身反趋式微。

NoSQL 运动之持久遗产，在于 *文档模型*（document model）之普及，其通常以 JSON 表征数据。该模型初由 MongoDB、Couchbase 等专用文档数据库推动；今则多数关系数据库亦已内置 JSON 支持。相较常被诟病为“僵化难变”的关系表模式，JSON 文档素以“灵活易变”见称。

文档模型与关系模型之优劣，论争已久。兹列其要者，以资参详。
### 对象-关系范式错配 {#sec_datamodels_document}
当今多数应用开发采用面向对象编程语言，由此引出对 SQL 数据模型的一类常见批评：若数据以关系型表格形式存储，则需在应用代码中的对象与数据库的表、行、列模型之间构建一层笨拙的映射层。此两类模型间的割裂，习称“阻抗失配”（*impedance mismatch*）。

> [!NOTE]  
> “阻抗失配”一词借自电子学。任一电路之输入端与输出端皆具特定阻抗（即对交流电的阻力）。当一电路之输出端接至另一电路之输入端时，若二者输出阻抗与输入阻抗相等，则连接处功率传输达最大；阻抗失配则易致信号反射及其他异常。
#### 对象关系映射（Object-Relational Mapping，ORM）{#object-relational-mapping-orm}
对象关系映射（ORM）框架（如 ActiveRecord 与 Hibernate）可减少该转换层所需的样板代码，然常受诟病[^6]。  
常见批评如下：

* ORM 复杂度高，无法彻底屏蔽对象模型与关系模型之差异；开发者仍须兼顾数据的对象表示与关系表示。  
* ORM 多用于 OLTP 应用开发（参见[“事务处理与分析工作负载的特征”](/zh-cn/ch1#sec_introduction_oltp)）；而面向分析的数据工程仍需直接操作底层关系表示，故关系模式之设计在使用 ORM 时依然关键。  
* 多数 ORM 仅支持关系型 OLTP 数据库；若组织采用异构数据系统（如搜索引擎、图数据库、NoSQL 系统），则 ORM 支持往往不足。  
* 部分 ORM 自动生成功能关系模式，但所生成模式对直连关系数据的用户而言可能不直观，且在底层数据库上执行效率低下；若需定制 ORM 的模式定义或查询生成逻辑，则复杂度陡增，反使 ORM 初衷落空。  
* ORM 易致低效查询，典型者如 *N+1 查询问题* [^7]。  
  例：欲在页面展示用户评论列表，先执行一查询得 *N* 条评论，每条评论含作者 ID；为显示作者姓名，须依 ID 查 users 表。手写 SQL 通常以 JOIN 一次完成，返回评论及作者名；而 ORM 若未显式预加载，则可能对每条评论各发一查 users 表之查询，总计 *N*+1 次数据库访问，远逊于数据库内联查之性能。避此弊，须明示 ORM 同步获取作者信息。

然 ORM 亦有其利：

* 对适配关系模型之数据，内存对象表示与持久化关系表示之间必存转换；ORM 可显著削减此类转换所需之样板代码。复杂查询虽仍需绕过 ORM 实现，然简单、重复性操作可由 ORM 承担。  
* 部分 ORM 内置查询结果缓存机制，有助于降低数据库负载。  
* ORM 还可辅助管理模式迁移（schema migration）及其他运维任务。
#### 一对多关系的文档数据模型 {#the-document-data-model-for-one-to-many-relationships}
并非所有数据皆宜以关系模型表达；试举一例，以察其局限。[图3-1](/zh-cn/ch3#fig_obama_relational) 示意如何将一份简历（即 LinkedIn 个人档案）映射为关系模式。该档案整体可由唯一标识符 `user_id` 标识。字段如 `first_name` 与 `last_name` 每用户仅出现一次，故可建模为 `users` 表之列。

然多数人职业生涯中曾任职多岗（即“职位”），教育经历段数亦因人而异，联系方式更可有任意多项。此类 *一对多关系*，常见解法是将“职位”“教育经历”“联系方式”分别置于独立表中，并以外键引用 `users` 表，如 [图3-1](/zh-cn/ch3#fig_obama_relational) 所示。
{{< figure src="/fig/ddia_0301.png" id="fig_obama_relational" caption="Figure 3-1. Representing a LinkedIn profile using a relational schema." class="w-full my-4" >}}
另有一种表达方式，或更合自然直觉，且与应用代码中的对象结构映射更紧，即以 JSON 文档呈现，如[示例 3-1](/zh-cn/ch3#fig_obama_json) 所示。
{{< figure id="fig_obama_json" title="Example 3-1. Representing a LinkedIn profile as a JSON document" class="w-full my-4" >}}

```json
{
    "user_id": 251,
    "first_name": "Barack",
    "last_name": "Obama",
    "headline": "Former President of the United States of America",
    "region_id": "us:91",
    "photo_url": "/p/7/000/253/05b/308dd6e.jpg",
    "positions": [
        {"job_title": "President", "organization": "United States of America"},
        {"job_title": "US Senator (D-IL)", "organization": "United States Senate"}
    ],
    "education": [
        {"school_name": "Harvard University", "start": 1988, "end": 1991},
        {"school_name": "Columbia University", "start": 1981, "end": 1983}
    ],
    "contact_info": {
        "website": "https://barackobama.com",
        "twitter": "https://twitter.com/barackobama"
    }
}
```
部分开发者认为，JSON 模型可降低应用代码与存储层之间的阻抗失配。然如[第 5 章](/zh-cn/ch5#ch_encoding)所示，JSON 作为数据编码格式亦存若干问题。其无显式 Schema 常被视为优势；此点将于[“文档模型中的 Schema 灵活性”](/zh-cn/ch3#sec_datamodels_schema_flexibility)中详述。

相较[图 3-1](/zh-cn/ch3#fig_obama_relational)所示多表关系模式，JSON 表示法具有更优之*局部性*（见[“读写操作的数据局部性”](/zh-cn/ch3#sec_datamodels_document_locality)）。若在关系模型中获取用户档案，须执行多次查询（依 `user_id` 分别查各表），或对 `users` 表与其从属表 [^8] 进行复杂多表联结。而 JSON 表示法将全部相关数据聚于一处，故查询既快且简。

用户档案至其职位、教育经历及联系方式之间的一对多关系，在数据中天然构成树状结构；JSON 表示法使此树状结构显式可辨（见[图 3-2](/zh-cn/ch3#fig_json_tree)）。
{{< figure src="/fig/ddia_0302.png" id="fig_json_tree" caption="Figure 3-2. One-to-many relationships forming a tree structure." class="w-full my-4" >}}
> [!NOTE]  
> 此类关系偶称“一对少数”（one-to-few），而非“一对多”（one-to-many），盖因一份简历通常仅含少量职位经历[^9] [^10]。  
> 若关联项数量确极庞大——例如某名人在社交媒体上的一则帖文，其评论可达数千条——则将全部评论嵌入同一文档，将致结构臃肿、难于维护；此时，[图3-1](/zh-cn/ch3#fig_obama_relational)所示之关系型方案更为妥当。
### 规范化、反规范化与连接操作 {#sec_datamodels_normalization}
在前文[例3-1](/zh-cn/ch3#fig_obama_json)中，`region_id` 以 ID 形式给出，而非明文字符串 `"Washington, DC, United States"`。何故？

若用户界面提供自由文本字段供输入地区，则存为明文字符串亦属合理。然采用标准化地理区域列表，并令用户从下拉菜单或自动补全中选取，有五利：

其一、确保各档案中地区名称风格统一、拼写一致；  
其二、消歧义——同名异地者众（单书“Washington”，究指华盛顿特区，抑或华盛顿州？）；  
其三、易维护——名称仅存于一处，全局更新便捷（如因政局更易致城名变更）；  
其四、利本地化——网站译为他语时，标准列表可同步本地化，使地区名依浏览者语言呈现；  
其五、强检索——例如检索“美国东海岸人士”，可命中此档案，盖因区域列表可编码“Washington 位于东海岸”之语义关系（此义不可自字符串 `"Washington, DC"` 直观推得）。

ID 与明文之取舍，实为*规范化*（normalization）之权衡。用 ID 者，数据更规范：人类可读之信息（如“Washington, DC”）唯存于一源，其余皆引其 ID（该 ID 仅于数据库内具意义）；直存明文者，则人类可读信息于每条记录中重复出现，此即*反规范化*（denormalization）。

用 ID 之利，在于其本无语义，故永无需变更：所指实体之名虽异，ID 可岿然不动。凡具人类语义者，未来皆可能变更；若该信息被冗余复制，则所有副本须同步更新——此增代码量、增写操作、增磁盘开销，且易致不一致（部分副本已更，余者未更）。

然规范化之弊，在于每次展示含 ID 之记录时，必额外查表，方得人类可读之值。在关系型数据模型中，此操作藉*联结*（join）实现，例如：
```sql
SELECT users.*, regions.region_name
    FROM users
    JOIN regions ON users.region_id = regions.id
    WHERE users.id = 251;
```
文档数据库可存储规范化与非规范化数据，然实务中多用于非规范化——  
其一，JSON 数据模型天然便于嵌入冗余字段；  
其二，多数文档数据库对联结（join）支持薄弱，致使规范化反增负担。  

部分文档数据库甚至完全不支持联结，此时须于应用层手动实现：先查得含 ID 的文档，再依该 ID 发起二次查询以获取关联文档。  

MongoDB 例外：可在聚合管道（aggregation pipeline）中使用 `$$lookup` 操作符执行联结。
```mongodb-json
db.users.aggregate([
    { $match: { _id: 251 } },
    { $lookup: {
        from: "regions",
        localField: "region_id",
        foreignField: "_id",
        as: "region"
    } }
])
```

#### 规范化的权衡 {#trade-offs-of-normalization}
在简历示例中，``region_id`` 字段为指向标准化区域集合的引用，而 ``organization``（任职单位，即公司或政府机构）与 ``school_name``（就读院校）之名仅为字符串。此表示法属**非规范化**：多人或就职于同一单位，却无统一 ID 关联。

宜将组织与学校建模为独立实体，个人档案改以 ID 引用之？此理同区域 ID 引用——理由一致。例如，若需在名称之外补充学校或企业的 Logo：

- 非规范化表示下，须于每份个人简历中重复嵌入 Logo 的图片 URL；JSON 文档由此自包含，但一旦 Logo 更换，则须遍历全部简历、定位旧 URL 并逐一更新，[^9]。
- 规范化表示下，则另立组织/学校实体，其名、Logo URL 及其他属性（如简介、新闻源等）仅存一份；各简历仅存该实体 ID；Logo 更新即单点操作，简而无误。

通则而言：  
- 规范化数据，写入较快（仅一副本），查询较慢（需联结）；  
- 非规范化数据，读取较快（免联结），写入较贵（多副本更新、占更多磁盘空间）。  

可视非规范化为一种**派生数据**（参见［“主数据系统与派生数据”］(/zh-cn/ch1#sec_introduction_derived)），因其依赖额外机制维护冗余副本的一致性。

除更新开销外，尚须顾及**一致性风险**：若更新进程中途崩溃，数据库易陷不一致态。支持原子事务之数据库（参见［“原子性”］(/zh-cn/ch8#sec_transactions_acid_atomicity)）可缓解此忧，然非所有数据库允许多文档级原子性。亦可借流式处理保障一致性，详见［“保持系统同步”］(/zh-cn/ch12#sec_stream_sync)。

- OLTP 系统多宜规范化：读写双敏，皆不可缓；  
- 分析型系统常宜非规范化：批量更新为主，只读查询性能为首要关切；  
- 小至中等规模系统，规范化模型通常最优：无需操心多副本一致性，且联结代价可接受；  
- 超大规模系统中，联结开销或成瓶颈，此时非规范化或更适。
#### 社交网络案例研究中的反规范化 {#denormalization-in-the-social-networking-case-study}
在【案例研究：社交网络首页时间线】（/en/ch2#sec_introduction_twitter）中，我们对比了规范化表示（见图2-1 /en/ch2#fig_twitter_relational）与非规范化表示（预计算、物化的时间线）：此处，`posts` 与 `follows` 之间的联结开销过大，而物化时间线实为该联结结果之缓存。  
将新帖写入关注者时间线的扇出（fan-out）过程，即用以维系此非规范化表示之一致性。

然X平台（原Twitter）所实现之物化时间线，并不存储各帖之原始正文；每条记录仅存帖ID、发帖用户ID，及少量附加信息，用以标识转发（reposts）与回复（replies）[^11]。  
换言之，其本质为如下查询之预计算结果（近似）：
```sql
SELECT posts.id, posts.sender_id 
    FROM posts
    JOIN follows ON posts.sender_id = follows.followee_id
    WHERE follows.follower_id = current_user
    ORDER BY posts.timestamp DESC
    LIMIT 1000
```
此即谓：每当读取时间线时，服务仍须执行两次联结（join）——  
其一，依帖文 ID 查得原始帖文内容（含点赞数、回复数等统计信息）；  
其二，依发送者 ID 查得其用户档案（含用户名、头像及其他元数据）。  
此类依 ID 检索可读信息的过程，谓之 *ID 注水*（hydrating），实为在应用层代码中完成的联结操作 [^11]。

预计算时间线中仅存 ID，缘于其所指数据变动迅疾：热门帖文之点赞数与回复数每秒或更迭数次；部分用户亦常更易用户名或头像。因时间线须于呈现时显示最新点赞数与头像，故将此类信息反规范化（denormalize）至物化时间线中，既无必要，亦不可取。此外，此举将显著抬高存储开销。

本例表明：读取数据时需执行联结，并非如某些论点所称，必成高性能、可扩展服务之障碍。对帖文 ID 与用户 ID 执行注水操作，实属易于扩展之举——因其高度可并行，且开销不随关注人数或粉丝数增长而上升。

若需权衡是否于应用中反规范化某项数据，社交网络案例揭示：抉择并无显见答案。最具扩展性的方案，往往兼采反规范化与规范化：部分字段反规范化以加速访问，其余则保持规范化以控成本与一致性。决策时须审慎评估：  
- 数据更新频次；  
- 读写代价（其瓶颈常由离群值主导，例如社交网络中拥有海量关注者或粉丝的用户）。

规范化与反规范化，本无固有优劣；唯系读写性能、实现复杂度及存储成本之间之权衡耳。
### 一对多与多对多关系 {#sec_datamodels_many_to_many}
虽图3-1（见 `/en/ch3#fig_obama_relational`）中之 `positions` 与 `education` 属**一对多**或**一对少数**关系（一份简历含多个职位，而每职位仅属一份简历），然 `region_id` 字段则为**多对一**关系之例（多人居于同一地区；然设任一时刻，每人仅居于一地）。

若引入“机构”与“学校”两类实体，并于简历中以 ID 引用之，则复生**多对多**关系（一人曾供职于多家机构；一机构亦有若干现任或历任雇员）。在关系模型中，此类关系通常以**关联表**（associative table）或**连接表**（join table）表示，如图3-3（见 `/en/ch3#fig_datamodels_m2m_rel`）所示：每条职位记录，关联一个用户 ID 与一个机构 ID。
{{< figure src="/fig/ddia_0303.png" id="fig_datamodels_m2m_rel" caption="Figure 3-3. Many-to-many relationships in the relational model." class="w-full my-4" >}}
一对多与多对多关系，难以自然容纳于单一自包含 JSON 文档之中；其本质更适配规范化（normalized）表达。  
在文档模型中，一种可行表示见[示例 3-2](/zh-cn/ch3#fig_datamodels_m2m_json)，图示见[图 3-4](/zh-cn/ch3#fig_datamodels_many_to_many)：  
各虚线框内数据可聚为一文档；  
而组织（organizations）与学校（schools）之关联，则宜以引用（reference）形式指向他文档。
{{< figure id="fig_datamodels_m2m_json" title="Example 3-2. A résumé that references organizations by ID." class="w-full my-4" >}}

```json
{
    "user_id": 251,
    "first_name": "Barack",
    "last_name": "Obama",
    "positions": [
        {"start": 2009, "end": 2017, "job_title": "President", "org_id": 513},
        {"start": 2005, "end": 2008, "job_title": "US Senator (D-IL)", "org_id": 514}
    ],
    ...
}
```

{{< figure src="/fig/ddia_0304.png" id="fig_datamodels_many_to_many" caption="Figure 3-4. Many-to-many relationships in the document model: the data within each dotted box can be grouped into one document." class="w-full my-4" >}}
多对多关系常需双向查询：例如，查某人就职过的所有机构；或查某机构雇佣过的所有人。  
其一，可于双方皆存 ID 引用：即简历中存其所就职机构之 ID，机构文档中存提及该机构之所有简历 ID。此法属**反规范化**，因关系冗余存储于两处，易致不一致。  

其二，**规范化**表示仅存关系于一处，借由*二级索引*（参见[第 4 章](/zh-cn/ch4#ch_storage)）支持双向高效查询。在[图 3-3](/zh-cn/ch3#fig_datamodels_m2m_rel)所示关系模式中，须令数据库于 `positions` 表的 `user_id` 列与 `org_id` 列上分别建索引。  

在[例 3-2](/zh-cn/ch3#fig_datamodels_m2m_json) 所示文档模型中，数据库须对 `positions` 数组内各对象的 `org_id` 字段建立索引。多数文档数据库及支持 JSON 的关系型数据库，均能对此类嵌套文档内的值创建索引。
### 星与雪花：分析用数据模型 {#sec_datamodels_analytics}
数据仓库（参见【“数据仓库”】(/zh-cn/ch1#sec_introduction_dwh)）通常基于关系模型，其表结构存在若干广泛采用的约定：*星型模式*（star schema）、*雪花模式*（snowflake schema）、*维度建模*（dimensional modeling）[^12]，以及*宽表模式*（one big table, OBT）。此类结构专为业务分析师之分析需求而优化。ETL 流程负责将操作型系统中的原始数据转换至该结构。

[图 3-5](/zh-cn/ch3#fig_dwh_schema) 展示某连锁超市数据仓库中典型的星型模式示例。该模式以中心化的*事实表*（fact table）为核心（本例中名为 `fact_sales`）。事实表每行记录一个特定时间发生的业务事件（此处为顾客对某商品的一次购买行为）；若分析对象为网站流量，则每行可对应一次页面浏览或用户点击。
{{< figure src="/fig/ddia_0305.png" id="fig_dwh_schema" caption="Figure 3-5. Example of a star schema for use in a data warehouse." class="w-full my-4" >}}
通常，事实以单个事件形式捕获，以保后续分析之最大灵活性。然此亦致事实表极易膨胀。大型企业数据仓库中，交易历史常达数十拍字节（petabytes），主体即为事实表。

事实表中部分列为属性，如产品售出价格、向供应商采购成本（据此可算毛利率）；其余列则为外键，指向其他表——即所谓*维度表*。因事实表每行代表一事件，维度即刻画该事件之“何人、何物、何地、何时、何法、何因”。

例如，[图3-5](/zh-cn/ch3#fig_dwh_schema) 中，产品即为一维度。`dim_product` 表每行对应一种在售商品，含其库存单位（SKU）、描述、品牌、品类、脂肪含量、包装规格等；`fact_sales` 表每行则借外键指明该笔交易中所售具体产品。查询常需联结多个维度表。

日期与时间亦常以维度表表示，以便编码额外信息（如法定节假日），使查询可区分节假销售与平日销售。

[图3-5](/zh-cn/ch3#fig_dwh_schema) 展示一星型模式（star schema）。其名源于关系图示：事实表居中，诸维度表环列四周，连线如星芒放射。

此模式之变体称*雪花模式*（snowflake schema），即维度进一步分解为子维度。例如，品牌与产品品类可分设独立表；`dim_product` 表每行以两个外键分别引用品牌与品类，而非将二者字符串直接存于 `dim_product` 表中。雪花模式较星型模式更规范化，然星型模式常更受分析师青睐，盖因其结构简明、易用 [^12]。

典型数据仓库中，表宽常甚可观：事实表列数多逾百，甚或数百；维度表亦宽，因须容纳所有潜在分析所需元数据——例如，`dim_store` 表或含各门店所提供服务明细、是否设店内烘焙坊、建筑面积、初营日期、最近翻新日期、距最近高速公路之距离等。

星型或雪花模式主体由多对一关系构成（如：某产品、某门店可对应多笔销售），体现为事实表含维度表之外键，或维度表含子维度之外键。理论上虽可存在他类关系，但常予反规范化（denormalized），以简化查询。例如，客户单次购多品之交易，并不显式建模为一复合事务；而于事实表中为每件商品各立一行，诸行仅共享同一客户ID、门店ID与时间戳。

更有甚者，部分数据仓库架构将反规范化推向极致：索性省去维度表，将其全部字段直接冗余至事实表中（即预计算事实表与各维度表之联结）。此法谓之*一大表*（One Big Table, OBT）；虽增存储开销，然偶可提速查询 [^13]。

于分析场景下，此类反规范化并无碍：数据多为不可变历史日志（唯偶有勘误）；而OLTP系统中反规范化所致之数据一致性风险与写入开销，在分析系统中皆不紧迫。
### 何时选用何种模型 {#sec_datamodels_document_summary}
文档数据模型之优，在于模式灵活、局部性致性能较佳，且于若干应用中更契其对象模型。关系模型则以联结（join）、一对多及多对多关系之支持见长。今析其理如下：

若应用数据呈文档式结构——即一棵单向树状的一对多关系，且整棵树常被一次性加载——则宜用文档模型。关系模型中所谓“切片”（shredding）法，即将此类结构拆解为多张表（如[图3-1](/zh-cn/ch3#fig_obama_relational)中之 `positions`、`education` 与 `contact_info`），易致模式繁冗、应用代码徒增复杂。

文档模型有其限：无法直接引用文档内嵌项，而须迂回表述，如“用户251之职位列表中第二项”。若确需直引嵌项，则关系模型更优，盖可凭唯一ID直寻任意项。

若干应用允用户自定条目次序，例如待办清单或工单系统，用户可拖拽重排任务。文档模型于此甚便：条目本身或其ID可直存于JSON数组，顺序即隐含其中。关系数据库则无标准法表征可重排序列，实务中多用权宜之策：依整数列排序（中插须重编号）、以ID链表实现、或采分数索引（fractional indexing）[^14] [^15] [^16]。
#### 文档模型中的模式灵活性 {#sec_datamodels_schema_flexibility}
多数文档数据库，以及关系型数据库中的 JSON 支持，均不对文档数据施加任何模式约束。  
关系型数据库中的 XML 支持通常附带可选的模式校验（schema validation）。  
无模式（no schema）意味着：文档可任意添加键值对；读取时，客户端无法获知文档中必然包含哪些字段。

文档数据库常被称为“无模式”（*schemaless*），此称谓易致误解——因读取数据的应用代码通常隐含结构假设；换言之，**存在隐式模式（implicit schema），但数据库并不强制执行** [^17]。  
更准确的术语是 **“读时建模”（*schema-on-read*）**：数据结构隐含于语义，仅在读取时由应用解释；  
与之相对的是 **“写时建模”（*schema-on-write*）**：即关系型数据库的传统方式，模式显式定义，数据库在写入时确保数据严格符合该模式 [^18]。

“读时建模”类比编程语言中的动态（运行时）类型检查；  
“写时建模”则类比静态（编译时）类型检查。  
正如静态与动态类型支持者长期争论其优劣 [^19]，  
数据库中是否强制执行模式，亦属争议性议题；总体而言，**并无普适之对错**。

两类范式之差异，在应用需变更数据格式时尤为显著。  
例如：当前将用户全名存于单字段 `full_name`，现欲拆分为 `first_name` 与 `last_name` 两个独立字段 [^20]。  
在文档数据库中，只需开始写入含新字段的文档，并在应用代码中兼容旧文档的读取逻辑。例如：
```mongodb-json
if (user && user.name && !user.first_name) {
    // Documents written before Dec 8, 2023 don't have first_name
    user.first_name = user.name.split(" ")[0];
}
```
此法之弊，在于应用中所有读取数据库之处，今皆须兼容旧格式文档——彼等或系久远之前所写。  
反之，若用写时定模（schema-on-write）数据库，则通常需执行迁移（*migration*），其要略如下：
```sql
ALTER TABLE users ADD COLUMN first_name text DEFAULT NULL;
UPDATE users SET first_name = split_part(name, ' ', 1); -- PostgreSQL
UPDATE users SET first_name = substring_index(name, ' ', 1); -- MySQL
```
在多数关系型数据库中，为表添加带默认值的列，即便对大表而言，亦迅捷无碍。  
然执行 ``UPDATE`` 语句，于大表上则常迟滞——盖因须重写每一行；其余模式变更操作（如修改列的数据类型），亦多需全表拷贝。

已有多种工具，可于后台执行此类模式变更，实现零停机 [^21] [^22] [^23] [^24]；  
然于超大规模数据库上实施此类迁移，运维难度仍高。  
若仅新增 ``first_name`` 列，并设默认值为 ``NULL``（此操作迅捷），再于读取时按需填充，则可规避复杂迁移——其法类同文档数据库之用法。

读时建模（schema-on-read）之法，适用于集合中诸项结构本不统一之情形（即数据具异构性），例如：

* 对象类型繁多，分置各表实不可行；  
* 数据结构由外部系统决定，我方既无控制权，其变更亦不可预知。

此等情境下，强加模式反成桎梏，而无模式文档（schemaless document）反更契合作为数据模型。  
然若所有记录本应结构一致，则模式实为明示并约束该结构之有效机制。  
模式定义及其演进，详见[第五章](/zh-cn/ch5#ch_encoding)。
#### 读写数据局部性 {#sec_datamodels_document_locality}
文档通常以单个连续字符串形式存储，编码为 JSON、XML 或其二进制变体（如 MongoDB 的 BSON）。若应用常需读取整份文档（例如渲染网页），此 *存储局部性*（storage locality）可提升性能。相较之下，若数据分散于多张表中（如[图3-1](/zh-cn/ch3#fig_obama_relational)所示），则须执行多次索引查找，导致更多磁盘寻道，耗时更长。

然此局部性优势，仅当同时访问文档之大部时方显。数据库通常须加载整份文档；若仅需其中一小部分，此举徒耗资源。更新文档时，亦常需重写全文。故一般建议：文档宜小，且避免频繁施行细粒度更新。

然将关联数据聚存以提升局部性，并非文档模型所独有。例如，Google Spanner 在关系模型中亦提供同类局部性保障，允在模式中声明某表行应交错嵌套（interleaved）于父表之内 [^25]。Oracle 同具此能力，称为 *多表索引簇表*（multi-table index cluster tables）[^26]。Google Bigtable 所倡之 *宽列*（wide-column）模型（HBase、Accumulo 等亦采用），则以 *列族*（column families）实现相近的局部性管理目标 [^27]。
#### 文档查询语言 {#query-languages-for-documents}
关系型数据库与文档数据库的另一差异，在于所用查询语言或 API。  
多数关系型数据库以 SQL 查询；文档数据库则更为多样：  
- 有些仅支持按主键进行键值访问；  
- 有些另提供二级索引，以支持对文档内部字段的查询；  
- 尚有若干支持功能丰富的查询语言。

XML 数据库常以 XQuery 与 XPath 查询——二者专为复杂查询而设，可跨多份文档执行联结（join），且结果亦格式化为 XML [^28]。  
JSON Pointer [^29] 与 JSONPath [^30] 则为 JSON 提供了类 XPath 的路径定位能力。

MongoDB 的聚合管道（aggregation pipeline）即为面向 JSON 文档集合的查询语言之例；其中用于联结的 `$lookup` 操作符，前文 [“范式化、反范式化与联结”](/zh-cn/ch3#sec_datamodels_normalization) 已述。

再观一例，以体察此类语言之用——此例为聚合操作，尤适用于分析场景。  
设汝为海洋生物学家，每于海中目击动物，即向数据库写入一条观测记录。今欲生成一份报告，统计每月鲨鱼目击次数。在 PostgreSQL 中，该查询可表为：
```sql
SELECT date_trunc('month', observation_timestamp) AS observation_month, ❶ 
    sum(num_animals) AS total_animals
FROM observations
WHERE family = 'Sharks'
GROUP BY observation_month;
```
❶：``date_trunc('month', timestamp)`` 函数判定 ``timestamp`` 所属之公历月份，并返回表征该月月初时刻之时间戳。换言之，其将时间戳向下取整至最近之月始。

本查询先筛选观测记录，仅保留 ``Sharks`` 科之物种；继而按观测发生之公历月份分组；最终汇总该月所有观测中所见动物之总数。此查询亦可用 MongoDB 聚合管道表达如下：
```mongodb-json
db.observations.aggregate([
    { $match: { family: "Sharks" } },
    { $group: {
    _id: {
        year: { $year: "$observationTimestamp" },
        month: { $month: "$observationTimestamp" }
    },
    totalAnimals: { $sum: "$numAnimals" }
    } }
]);
```
聚合管道语言之表达力，约当 SQL 之子集；然其语法基于 JSON，异于 SQL 所用类英语句式。此差异，或纯属偏好使然。
#### 文档数据库与关系型数据库之趋同
文档数据库与关系型数据库，初为数据管理之迥异范式，然随时间推移，二者渐趋融合。

关系型数据库增补 JSON 类型及查询操作符，并支持对文档内属性建立索引；若干文档数据库（如 MongoDB、Couchbase 与 RethinkDB）则引入连接（joins）、二级索引及声明式查询语言。

此模型趋同之势，于应用开发者实为利好：盖因关系模型与文档模型各有所长，而二者共存于同一数据库时，方得其用之极。诸多文档数据库需以类关系方式引用他文档；诸多关系型数据库亦有场景，亟需模式灵活性。关系—文档混合架构，遂成强效组合。

> [!NOTE]  
> Codd 原初所构想之关系模型，[^3] 实已容许类似 JSON 之嵌套结构存于关系模式之中，谓之 *非简单域*（nonsimple domains）。其义谓：表中某列之值，未必限于数字、字符串等原始类型，亦可为一嵌套关系（即另一张表），故单个字段可承载任意深度之树状结构——此理念，与三十余年后 SQL 所增 JSON 或 XML 支持，实出一辙。
## 图状数据模型 {#sec_datamodels_graph}
此前已见，关系类型乃区分各类数据模型之关键特征。若应用中多为一对多关系（即树状结构数据），且记录间其余关系甚少，则文档模型最为适宜。

然若数据中多对多关系极为普遍，关系模型虽可处理简单情形，但当数据内部关联日趋复杂，以图模型建模便更为自然。

图由两类对象构成：*顶点*（亦称*节点*或*实体*）与*边*（亦称*关系*或*弧*）。多种数据皆可建模为图，典型示例如下：

社交图  
：顶点为人，边表征彼此相识关系。

网页图  
：顶点为网页，边表征 HTML 超链接。

道路或铁路网络  
：顶点为路口（或枢纽），边表征其间相连之道路或铁轨。

诸多著名算法可作用于此类图：例如，地图导航应用在路网中搜索两点间最短路径；PageRank 算法则用于网页图，以评估网页流行度，进而影响其在搜索引擎结果中的排序 [^32]。

图可有多种表示方式。在*邻接表*模型中，每个顶点存储与其直接相连（即相距一条边）的邻居顶点 ID；另可采用*邻接矩阵*，即二维数组，其行与列各对应一顶点，若行顶点与列顶点间无边，则对应值为零；若有边，则为一。邻接表利于图遍历，邻接矩阵则适用于机器学习（参见[“数据框、矩阵与数组”](/zh-cn/ch3#sec_datamodels_dataframes)）。

前述诸例中，图内所有顶点均表征同一类事物（分别为人、网页或路口）。然图模型不限于此类*同质*数据：其更强大之处，在于能以统一方式，在单一数据库中存储类型迥异之对象。例如：

* Facebook 维护一张大型图，含多种类型顶点与边：顶点涵盖用户、地理位置、事件、签到及用户评论；边则表征用户间好友关系、签到所属地点、评论所针对之帖文、用户所参加之活动等 [^33]。  
* 知识图谱被搜索引擎用于记录常出现在搜索查询中的实体事实，如组织、人物与地点 [^34]。此类信息源自对网站文本之爬取与分析；部分网站（如 Wikidata）亦以结构化形式发布图数据。

图数据之组织与查询，存在数种不同但相互关联的方式。本节将讨论*属性图*模型（由 Neo4j、Memgraph、KùzuDB [^35] 等实现 [^36]）与*三元组存储*模型（由 Datomic、AllegroGraph、Blazegraph 等实现）。二者在表达能力上颇为相近；部分图数据库（如 Amazon Neptune）更同时支持两种模型。

此外，还将考察四种图查询语言（Cypher、SPARQL、Datalog 与 GraphQL），以及 SQL 对图查询之支持。其他图查询语言（如 Gremlin [^37]）亦存在，然此四者已足具代表性。

为阐明上述语言与模型之异同，本节以[图 3-6](/zh-cn/ch3#fig_datamodels_graph)所示图为例贯穿始终。该图可源于社交网络或家谱数据库：显示二人——爱达荷州之露西（Lucy）与法国圣洛（Saint-Lô）之阿兰（Alain）；二人已婚，同居伦敦。每人、每地均为一顶点，其间关系（如“居住于”“出生于”“配偶为”）则以边表征。此例将凸显若干查询——于图数据库中易解，而于其他模型中则颇费周章。
{{< figure src="/fig/ddia_0306.png" id="fig_datamodels_graph" caption="Figure 3-6. Example of graph-structured data (boxes represent vertices, arrows represent edges)." class="w-full my-4" >}}

### 属性图 {#id56}
在*属性图*（亦称*带标签属性图*）模型中，每个顶点包含：

* 唯一标识符  
* 一个标签（字符串），用于表明该顶点所代表的对象类型  
* 一组出边  
* 一组入边  
* 一组属性（键值对）

每条边包含：

* 唯一标识符  
* 起始顶点（即*尾顶点*）  
* 终止顶点（即*头顶点*）  
* 一个标签，用于描述两端顶点之间的关系类型  
* 一组属性（键值对）

可将图数据库视作由两张关系表构成：一张存顶点，一张存边，如[示例 3-3](/zh-cn/ch3#fig_graph_sql_schema) 所示（该模式使用 PostgreSQL 的 `jsonb` 类型存储各顶点或边的属性）。每条边均显式存有其头顶点与尾顶点；若需获取某顶点的所有入边或出边，可分别对 `edges` 表按 `head_vertex` 或 `tail_vertex` 字段查询。
{{< figure id="fig_graph_sql_schema" title="Example 3-3. Representing a property graph using a relational schema" class="w-full my-4" >}}

```sql
CREATE TABLE vertices (
    vertex_id integer PRIMARY KEY,
    label text,
    properties jsonb
);

CREATE TABLE edges (
    edge_id integer PRIMARY KEY,
    tail_vertex integer REFERENCES vertices (vertex_id),
    head_vertex integer REFERENCES vertices (vertex_id),
    label text,
    properties jsonb
);

CREATE INDEX edges_tails ON edges (tail_vertex);
CREATE INDEX edges_heads ON edges (head_vertex);
```
该模型有如下要义：

其一、任意顶点可与任一其他顶点以边相连；无预设模式（schema）限制何种实体之间可或不可关联。

其二、对任一顶点，皆可高效查得其入边与出边，从而双向遍历图结构——即沿顶点链前向或反向行进。故[例 3-3](/zh-cn/ch3#fig_graph_sql_schema)中，``tail_vertex`` 与 ``head_vertex`` 两列均建有索引。

其三、通过为顶点与关系赋予不同标签（label），可在同一图中并存多种异构信息，而数据模型仍保持清晰。

边表（edges table）即[“一对多与多对多关系”](/zh-cn/ch3#sec_datamodels_many_to_many)中所见之多对多关联表（join table）之泛化：允许多种类型的关系共存于同一张表。此外，标签字段及属性字段亦可建索引，以支持按特定属性高效检索顶点或边。

> [!NOTE]  
> 图模型有一局限：一条边仅能关联两个顶点；而关系型连接表可通过单行含多个外键，表达三方乃至更高阶的关系。此类关系在图中可借两种方式建模：（1）为连接表的每一行引入一个新顶点，并连出入边；（2）采用*超图*（hypergraph）。

上述特性使图模型具备极强的数据建模灵活性，如[图 3-6](/zh-cn/ch3#fig_datamodels_graph)所示。图中呈现若干难以用传统关系模式表达的情形：各国行政区划体系各异（法国设 *départements* 与 *régions*，美国则为 *counties* 与 *states*）；历史特例如“国中之国”（暂不深究主权国家与民族之法理细节）；数据粒度不一（露西现居地精确至城市，出生地却仅标至州级）。

此图尚可延展，以容纳露西、阿兰及其他人物之更多事实。例如：为每种过敏原设一顶点，再以边连接人与过敏原，即可表示过敏关系；复设一组顶点描述各类食物所含成分，并以边关联之。由此可编写查询，判定每人可安全食用之物。

图模型尤擅演进：随应用功能扩展，其数据结构可自然延伸，无需重构全局模式。
### Cypher 查询语言 {#id57}
*Cypher* 是一种面向属性图（property graph）的查询语言，最初为 Neo4j 图数据库设计，后发展为开放标准 *openCypher* [^38]。除 Neo4j 外，Memgraph、KùzuDB [^35]、Amazon Neptune、Apache AGE（底层存储于 PostgreSQL）等系统亦支持 Cypher。其名取自电影《黑客帝国》（*The Matrix*）中一名角色，与密码学中的“cipher”（加密算法）无关 [^39]。

[例 3-4](/zh-cn/ch3#fig_cypher_create) 展示了向图数据库插入[图 3-6](/zh-cn/ch3#fig_datamodels_graph) 左半部分数据的 Cypher 查询语句；其余部分可依此法补全。各顶点被赋予符号名，如 `usa` 或 `idaho`；此类名称不存入数据库，仅在查询内部用于建立顶点间关系，语法采用箭头表示法：`(idaho) -[:WITHIN]-> (usa)` 表示创建一条标签为 `WITHIN` 的有向边，其中 `idaho` 为起点（tail node），`usa` 为终点（head node）。
{{< figure id="fig_cypher_create" title="Example 3-4. A subset of the data in [Figure 3-6](/zh-cn/ch3#fig_datamodels_graph), represented as a Cypher query" class="w-full my-4" >}}

```
CREATE
    (namerica :Location {name:'North America', type:'continent'}),
    (usa :Location {name:'United States', type:'country' }),
    (idaho :Location {name:'Idaho', type:'state' }),
    (lucy :Person {name:'Lucy' }),
    (idaho) -[:WITHIN ]-> (usa) -[:WITHIN]-> (namerica),
    (lucy) -[:BORN_IN]-> (idaho)
```
当图 3-6（见 `/en/ch3#fig_datamodels_graph`）中全部顶点与边均写入数据库后，即可提出若干有意义的问题：例如，*查出所有从美国移居至欧洲之人的姓名*。即：找出所有满足下述条件的顶点——其通过一条 ``BORN_IN`` 类型边指向一个位于美国境内的地点，且同时通过一条 ``LIVING_IN`` 类型边指向一个位于欧洲境内的地点；最终返回这些顶点的 ``name`` 属性值。

示例 3-5（见 `/en/ch3#fig_cypher_query`）展示了该查询在 Cypher 中的表达方式。其中，同一种箭头记号亦用于 ``MATCH`` 子句中，以匹配图中特定模式：``(person) -[:BORN_IN]-> ()`` 匹配任意两个由标签为 ``BORN_IN`` 的边所关联的顶点；该边的尾部顶点绑定至变量 ``person``，而头部顶点则不命名。
{{< figure id="fig_cypher_query" title="Example 3-5. Cypher query to find people who emigrated from the US to Europe" class="w-full my-4" >}}

```
MATCH
    (person) -[:BORN_IN]-> () -[:WITHIN*0..]-> (:Location {name:'United States'}),
    (person) -[:LIVES_IN]-> () -[:WITHIN*0..]-> (:Location {name:'Europe'})
RETURN person.name
```
该查询可释为：

> 求所有满足以下**双重路径条件**之顶点（记作 `person`）：
>
> 1. `person` 存在一条指向某顶点的出边（类型为 `BORN_IN`）；从此顶点出发，沿若干条连续出边（类型均为 `WITHIN`）可达一顶点，其类型为 `Location`，且其 `name` 属性值等于 `"United States"`。  
> 2. 同一 `person` 顶点另有一条出边（类型为 `LIVES_IN`）；沿此边及后续若干条连续出边（类型均为 `WITHIN`）可达一顶点，其类型为 `Location`，且其 `name` 属性值等于 `"Europe"`。  
>   
> 对每个满足条件的 `person` 顶点，返回其 `name` 属性。

执行此查询，路径不唯一。所述描述暗示一种**前向遍历策略**：  
先遍历全库中所有 `Person` 顶点，逐一检验其 `birthplace` 与 `residence` 关系链，筛选符合双路径约束者。

然亦可采**反向索引策略**，等价而高效：  
其一、若 `Location` 类型顶点（如 `Country`）之 `name` 属性（如 `name`）建有索引，则可快速定位 `US` 与 `Europe` 两顶点；  
其二、自该二顶点出发，沿全部入边（类型为 `WITHIN`，如 `locatedIn` 或 `partOf`）上溯，枚举其下辖全部地理实体（州、区、市等）；  
其三、对所得各地理顶点，查其入边（类型分别为 `BORN_IN` 与 `LIVES_IN`，如 `bornIn` 与 `livesIn`），收集聚合所有关联之 `Person` 顶点。

此反向法若辅以索引与选择性剪枝，常显著优于全量扫描，尤当 `Person` 数量远大于目标地理实体时。
### SQL 中的图查询 {#id58}
[示例 3-3](/zh-cn/ch3#fig_graph_sql_schema) 指出：图数据可存于关系型数据库。然若以关系结构存储图数据，能否亦用 SQL 查询之？

答曰：可，然颇费周章。图查询中每遍历一条边，即等效于对 `edges` 表执行一次连接（JOIN）。关系型数据库中，查询所涉连接通常预先已知；而图查询则不然——为定位目标顶点，或需遍历不定长度的路径，即连接次数无法事先确定。

此情形见于本例 Cypher 查询中的 `() -[:WITHIN*0..]-> ()` 模式。某人之 `LIVES_IN` 边可指向任意层级的位置节点：街道、城市、区、地区、州等；城市可 `WITHIN` 于地区，地区可 `WITHIN` 于州，州可 `WITHIN` 于国家，依此类推。该 `LIVES_IN` 边或直连所求位置节点，或需跨越多层位置层级方可达。

Cypher 中，`:WITHIN*0..` 即表此意，其义为“沿 `WITHIN` 边遍历零次或多次”，类比正则表达式中之 `*` 操作符。

自 SQL:1999 起，此类变长路径遍历可在查询中借 *递归公用表表达式*（recursive common table expressions，即 `WITH RECURSIVE` 语法）实现。  
[示例 3-6](/zh-cn/ch3#fig_graph_sql_query) 即以该技术，将同一查询——“查出由美国移居欧洲之人的姓名”——改写为 SQL。然其语法远较 Cypher 笨拙。
{{< figure id="fig_graph_sql_query" title="Example 3-6. The same query as [Example 3-5](/zh-cn/ch3#fig_cypher_query), written in SQL using recursive common table expressions" class="w-full my-4" >}}

```sql
WITH RECURSIVE

    -- in_usa is the set of vertex IDs of all locations within the United States
    in_usa(vertex_id) AS (
        SELECT vertex_id FROM vertices
            WHERE label = 'Location' AND properties->>'name' = 'United States' ❶ 
      UNION
        SELECT edges.tail_vertex FROM edges ❷
            JOIN in_usa ON edges.head_vertex = in_usa.vertex_id
            WHERE edges.label = 'within'
    ),
    
    -- in_europe is the set of vertex IDs of all locations within Europe
    in_europe(vertex_id) AS (
        SELECT vertex_id FROM vertices
            WHERE label = 'location' AND properties->>'name' = 'Europe' ❸
      UNION
        SELECT edges.tail_vertex FROM edges
            JOIN in_europe ON edges.head_vertex = in_europe.vertex_id
            WHERE edges.label = 'within'
    ),
    
    -- born_in_usa is the set of vertex IDs of all people born in the US
    born_in_usa(vertex_id) AS ( ❹
        SELECT edges.tail_vertex FROM edges
            JOIN in_usa ON edges.head_vertex = in_usa.vertex_id
            WHERE edges.label = 'born_in'
    ),
    
    -- lives_in_europe is the set of vertex IDs of all people living in Europe
    lives_in_europe(vertex_id) AS ( ❺
        SELECT edges.tail_vertex FROM edges
            JOIN in_europe ON edges.head_vertex = in_europe.vertex_id
            WHERE edges.label = 'lives_in'
    )
    
    SELECT vertices.properties->>'name'
    FROM vertices
    -- join to find those people who were both born in the US *and* live in Europe
    JOIN born_in_usa ON vertices.vertex_id = born_in_usa.vertex_id ❻
    JOIN lives_in_europe ON vertices.vertex_id = lives_in_europe.vertex_id;
```
❶：先找出其 `name` 属性值为 `"United States"` 的顶点，并将其设为顶点集 `in_usa` 的首元素。

❷：从集合 `in_usa` 中各顶点出发，沿所有入向 `within` 边递归遍历，将所达顶点加入同一集合，直至所有入向 `within` 边均已访问。

❸：同理，以 `name` 属性值为 `"Europe"` 的顶点为起点，构建顶点集 `in_europe`。

❹：对集合 `in_usa` 中每个顶点，沿入向 `born_in` 边追溯，找出出生地为美国境内某地的人员。

❺：同理，对集合 `in_europe` 中每个顶点，沿入向 `lives_in` 边追溯，找出现居欧洲的人员。

❻：最后，通过连接操作，求出“生于美国者”与“居于欧洲者”两集合之交集。

一则仅需 4 行的 Cypher 查询，若以 SQL 实现则需 31 行，足见数据模型与查询语言之择取，影响何其深远。此犹初阶；尚有诸多细节待究，例如环路处理、广度优先或深度优先遍历之取舍 [^40]。

Oracle 另有一套 SQL 扩展，专用于递归查询，名曰 *层次化*（hierarchical）[^41]。

然形势或趋改善：撰文之时，SQL 标准已拟纳入一种图查询语言，称 GQL [^42] [^43]，其语法融 Cypher、GSQL [^44] 与 PGQL [^45] 之长。
### 三元组存储与 SPARQL {#id59}
三元组存储模型与属性图模型大体等价，仅术语不同，所指概念一致。然仍值得专述，盖因三元组存储领域已有多种工具与语言，可为应用构建之利器。

三元组存储中，一切信息皆以极简之三元组形式存贮：（*主语*，*谓词*，*宾语*）。例如三元组（*Jim*，*likes*，*bananas*）中，*Jim* 为主语，*likes* 为谓词（动词），*bananas* 为宾语。

三元组之主语，等价于图中之顶点；宾语则有二类：

1. 原始数据类型之值，如字符串或数值。此时，该三元组之谓词与宾语，即等价于主语顶点上之属性键与属性值。  
   参见［图3-6］（/en/ch3#fig_datamodels_graph），三元组（*lucy*，*birthYear*，*1989*）相当于一顶点 `lucy`，其属性为 `{"birthYear": 1989}`。
2. 图中另一顶点。此时，谓词即为图中一条边，主语为边之尾顶点，宾语为边之头顶点。  
   例如三元组（*lucy*，*marriedTo*，*alain*）中，*lucy* 与 *alain* 均为顶点，谓词 *marriedTo* 即为其间边之标签。

> [!NOTE]  
> 严谨而言，提供类三元组数据模型之数据库，常需在每条三元组上附加若干元数据。  
> 例如，AWS Neptune 采用四元组（quad），即于三元组之上增补一图标识符（graph ID）[^46]；  
> Datomic 则采用五元组，于三元组中额外加入事务 ID 与一布尔值（标示是否删除）[^47]。  
> 鉴于此类数据库仍保留前述基本之 *subject-predicate-object* 结构，本书统称之为三元组存储（triple-store）。

［例3-7］（/en/ch3#fig_graph_n3_triples）以 *Turtle* 格式（*Notation3*（*N3*）之子集）[^48]，重写［例3-4］（/en/ch3#fig_cypher_create）中相同数据。
{{< figure id="fig_graph_n3_triples" title="Example 3-7. A subset of the data in [Figure 3-6](/zh-cn/ch3#fig_datamodels_graph), represented as Turtle triples" class="w-full my-4" >}}

```
@prefix : <urn:example:>.
_:lucy a :Person.
_:lucy :name "Lucy".
_:lucy :bornIn _:idaho.
_:idaho a :Location.
_:idaho :name "Idaho".
_:idaho :type "state".
_:idaho :within _:usa.
_:usa a :Location.
_:usa :name "United States".
_:usa :type "country".
_:usa :within _:namerica.
_:namerica a :Location.
_:namerica :name "North America".
_:namerica :type "continent".
```
本例中，图之顶点记为 ``_:someName``。此名仅于本文件内有效；设无此标识，则无法判定诸三元组所指是否为同一顶点。当谓词表征边时，宾语必为顶点，例如：  
`_:idaho :within _:usa`  
``. When the predicate is a property, the object is a string literal, as in `_:usa :name "United States"`  

反复书写同一主语，颇显冗赘；然 Turtle 允许以分号（`;`）续写同一主语之多项断言，故其格式清晰可读：参见[示例 3-8](/zh-cn/ch3#fig_graph_n3_shorthand)。
{{< figure id="fig_graph_n3_shorthand" title="Example 3-8. A more concise way of writing the data in [Example 3-7](/zh-cn/ch3#fig_graph_n3_triples)" class="w-full my-4" >}}

```
@prefix : <urn:example:>.
_:lucy a :Person; :name "Lucy"; :bornIn _:idaho.
_:idaho a :Location; :name "Idaho"; :type "state"; :within _:usa.
_:usa a :Location; :name "United States"; :type "country"; :within _:namerica.
_:namerica a :Location; :name "North America"; :type "continent".
```
> [!TIP] 语义网

三元组存储（triple store）的部分研发动因，源于本世纪初提出的*语义网*（Semantic Web）——该倡议旨在推动全网范围的数据互通：不仅以人类可读的网页形式发布数据，更须辅以标准化、机器可读的格式。尽管语义网之原始构想未能__全面实现__ __其初始目标__，  
其遗产仍存续于若干具体技术之中：*关联数据*（linked data）标准（如 JSON-LD __等序列化格式__）、生物医学领域所用*本体*（ontologies）__如 UMLS、SNOMED CT、GO__、Facebook 的开放图谱协议（Open Graph Protocol）__即网页元数据协议__（用于链接展开，link unfurling __即社交平台自动提取链接摘要__）、Wikidata 等知识图谱，以及由[__schema.org__](https://schema.org) __所维护__的结构化数据标准化词汇表。

三元组存储亦属语义网技术之一，然其应用已溢出原初场景：即便无意涉足语义网，三元组仍可作为应用程序内部优良的数据建模方式。
#### RDF 数据模型 {#the-rdf-data-model}
我们在[例3-8](/zh-cn/ch3#fig_graph_n3_shorthand)中所用之Turtle语言，实为*资源描述框架*（Resource Description Framework，RDF）之一种[^55]，此乃专为语义网（Semantic Web）所设计之数据模型。RDF数据亦可他法编码，例如以XML格式（更为冗长），如[例3-9](/zh-cn/ch3#fig_graph_rdf_xml)所示。Apache Jena等工具，可自动转换不同RDF编码格式。
{{< figure id="fig_graph_rdf_xml" title="Example 3-9. The data of [Example 3-8](/zh-cn/ch3#fig_graph_n3_shorthand), expressed using RDF/XML syntax" class="w-full my-4" >}}

```xml
<rdf:RDF xmlns="urn:example:"
         xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">

    <Location rdf:nodeID="idaho">
        <name>Idaho</name>
        <type>state</type>
        <within>
            <Location rdf:nodeID="usa">
                <name>United States</name>
                <type>country</type>
                <within>
                    <Location rdf:nodeID="namerica">
                        <name>North America</name>
                        <type>continent</type>
                    </Location>
                </within>
            </Location>
        </within>
    </Location>

    <Person rdf:nodeID="lucy">
        <name>Lucy</name>
        <bornIn rdf:nodeID="idaho"/>
    </Person>
</rdf:RDF>
```
RDF 因面向全球互联网数据交换而设，故有数端特异之处。  
其一，三元组之主语、谓语、宾语，多以 URI 表示。例如，谓语常为 ``<http://my-company.com/namespace#within>`` 或 ``<http://my-company.com/namespace#lives_in>`` 类 URI，而非简略之 ``WITHIN`` 或 ``LIVES_IN``。  
其二，此设计之本意，在于保障跨源数据可无冲突地融合：若他人对词项 ``within`` 或 ``lives_in`` 赋予不同语义，因其实际使用谓语为 ``<http://other.org/foo#within>`` 与 ``<http://other.org/foo#lives_in>``，故不致歧义或覆盖。  

URI 如 ``<http://my-company.com/namespace>``，未必须可解析——于 RDF 视角，其仅为命名空间标识，非必指向网络资源。  
为免与真实可访问之 ``http://`` URL 混淆，本节示例皆采用不可解析 URI，如 ``urn:example:within``。  
幸而该前缀仅需在文件首部声明一次， thereafter 可全篇简写，无需重复。
#### SPARQL 查询语言 {#the-sparql-query-language}
*SPARQL* 是一种面向三元组存储（triple-stores）的查询语言，基于 RDF 数据模型[^56]。  
（其全称为 *SPARQL Protocol and RDF Query Language*，读作“sparkle”。）  
它早于 Cypher；而 Cypher 的模式匹配语法正源于 SPARQL，故二者形态颇为相似。

此前所举之例——查询从美国移居欧洲之人——在 SPARQL 中亦如 Cypher 一般简洁（参见[示例 3-10](/zh-cn/ch3#fig_sparql_query)）。
{{< figure id="fig_sparql_query" title="Example 3-10. The same query as [Example 3-5](/zh-cn/ch3#fig_cypher_query), expressed in SPARQL" class="w-full my-4" >}}

```
PREFIX : <urn:example:>

SELECT ?personName WHERE {
 ?person :name ?personName.
 ?person :bornIn / :within* / :name "United States".
 ?person :livesIn / :within* / :name "Europe".
}
```
结构甚似。下述两式等价（SPARQL 中变量以问号 `?` 起始）：
```
(person) -[:BORN_IN]-> () -[:WITHIN*0..]-> (location) # Cypher

?person :bornIn / :within* ?location. # SPARQL
```
因 RDF 不区分属性与边，二者皆以谓词（predicate）表之，故属性匹配亦可用同一语法。  
下式中，变量 ``usa`` 绑定至任一顶点，该顶点具有名为 ``name`` 的属性，且其值为字符串 ``"United States"``：
```
(usa {name:'United States'}) # Cypher

?usa :name "United States". # SPARQL
```
SPARQL 为 Amazon Neptune、AllegroGraph、Blazegraph、OpenLink Virtuoso、Apache Jena 等多种三元组存储（triple store）所支持。
### Datalog：递归关系查询 {#id62}
Datalog 比 SPARQL 或 Cypher 问世更早：其源于 1980 年代之学术研究，[^57] [^58] [^59]。  
软件工程师对其知之甚少，主流数据库亦鲜有支持；然其表达力极强，尤擅复杂查询，故理应广为人知。  
若干小众数据库——如 Datomic、LogicBlox、CozoDB 及 LinkedIn 的 LIquid——[^60] 均以 Datalog 为查询语言。

Datalog 实际基于关系数据模型，而非图模型；然本书将其列于图数据库一节，盖因其递归查询能力在图结构上尤为突出。

Datalog 数据库之内容由 *事实*（facts）构成；每条事实对应关系表中之一行。  
例如，设有一张 *location* 表，存地点信息，含三列：*ID*、*name* 与 *type*；则“美国为一国家”这一事实可记作 `location(2, "United States", "country")`，其中 `2` 即美国之 ID。  
一般而言，语句 `table(val1, val2, …​)` 表明：关系 `table` 中存在一行，其首列为 `val1`，次列为 `val2`，依此类推。

[例 3-11](/zh-cn/ch3#fig_datalog_triples) 展示如何以 Datalog 表达 [图 3-6](/zh-cn/ch3#fig_datamodels_graph) 左侧之数据。  
图中各边（即 `within`、`born_in` 与 `lives_in`）以两列表连接表表示。  
例如，Lucy ID 为 100，Idaho ID 为 3，则“Lucy 出生于 Idaho”之关系记为 `born_in(100, 3)`。
{{< figure id="fig_datalog_triples" title="Example 3-11. A subset of the data in [Figure 3-6](/zh-cn/ch3#fig_datamodels_graph), represented as Datalog facts" class="w-full my-4" >}}

```
location(1, "North America", "continent").
location(2, "United States", "country").
location(3, "Idaho", "state").

within(2, 1). /* US is in North America */
within(3, 2). /* Idaho is in the US */

person(100, "Lucy").
born_in(100, 3). /* Lucy was born in Idaho */
```
既已定义数据，便可如前所述，写出相同查询，见[示例 3-12](/zh-cn/ch3#fig_datalog_query)。其语法略异于 Cypher 或 SPARQL，然勿以此为碍。Datalog 乃 Prolog 之子集；Prolog 为一逻辑编程语言，修习计算机科学者或曾识之。
{{< figure id="fig_datalog_query" title="Example 3-12. The same query as [Example 3-5](/zh-cn/ch3#fig_cypher_query), expressed in Datalog" class="w-full my-4" >}}

```sql
within_recursive(LocID, PlaceName) :- location(LocID, PlaceName, _). /* Rule 1 */

within_recursive(LocID, PlaceName) :- within(LocID, ViaID), /* Rule 2 */
 within_recursive(ViaID, PlaceName).

migrated(PName, BornIn, LivingIn) :- person(PersonID, PName), /* Rule 3 */
 born_in(PersonID, BornID),
 within_recursive(BornID, BornIn),
 lives_in(PersonID, LivingID),
 within_recursive(LivingID, LivingIn).

us_to_europe(Person) :- migrated(Person, "United States", "Europe"). /* Rule 4 */
/* us_to_europe contains the row "Lucy". */
```
Cypher 与 SPARQL 甫一登场，即以 `SELECT` 为原生查询范式；Datalog 则循序渐进，步步为营。  
吾辈定义 *规则*（rules），由底层事实推导出新的虚拟表。此类派生表，类同（虚拟）SQL 视图：不存于数据库中，然可如查询实表一般查询之。

在[例 3-12](/zh-cn/ch3#fig_datalog_query)中，吾辈定义三个派生表：`within_recursive`、`migrated` 与 `us_to_europe`。虚拟表之名及其列，由各条规则中 `:-` 符号之前所列者确定。例如，`migrated(PName, BornIn, LivingIn)` 为含三列之虚拟表：人名、出生地名、现居地名。

虚拟表之内容，则由规则中 `:-` 符号之后部分定义——此处旨在诸表中匹配特定模式之行。例如，`person(PersonID, PName)` 匹配行 `person(100, "Lucy")`，其中变量 `PersonID` 绑定至值 `100`，变量 `PName` 绑定至值 `"Lucy"`。若系统能在 `:-` 运算符右端找到 *全部* 模式的匹配，则该规则生效；一旦生效，即等效于将 `:-` 左端（变量已代换为其所匹配之值）插入数据库。

规则之一种应用方式如下（亦见于[图 3-7](/zh-cn/ch3#fig_datalog_naive)）：

1. `location(1, "North America", "continent")` 存于数据库，故规则 1 生效，生成 `within_recursive(1, "North America")`；  
2. `within(2, 1)` 存于数据库，且前步已生成 `within_recursive(1, "North America")`，故规则 2 生效，生成 `within_recursive(2, "North America")`；  
3. `within(3, 2)` 存于数据库，且前步已生成 `within_recursive(2, "North America")`，故规则 2 再次生效，生成 `within_recursive(3, "North America")`。  

藉规则 1 与规则 2 之反复应用，`within_recursive` 虚拟表即可枚举数据库中所有位于北美洲（或任一指定地域）之位置。
{{< figure link="#fig_datalog_query" src="/fig/ddia_0307.png" id="fig_datalog_naive" title="Figure 3-7. Determining that Idaho is in North America, using the Datalog rules from Example 3-12." class="w-full my-4" >}}
> 图 3-7：利用 [例 3-12](/zh-cn/ch3#fig_datalog_query) 中的 Datalog 规则，判定爱达荷州位于北美洲。

此时，规则 3 可找出在某地 `BornIn` 出生、又在某地 `LivingIn` 居住的人。  
规则 4 以 `BornIn = 'United States'` 和 `LivingIn = 'Europe'` 为参数调用规则 3，并仅返回匹配者之姓名。  
通过对虚拟 `us_to_europe` 表的内容发起查询，Datalog 系统最终得出与前述 Cypher 及 SPARQL 查询相同的结果。

Datalog 的思维方式，异于本章所论其余查询语言。其允许多层复杂查询逐条构建：一规则可引用他规则，类比程序中函数相互调用之结构。函数既可递归，Datalog 规则亦可自引用；如 [例 3-12](/zh-cn/ch3#fig_datalog_query) 中之规则 2，即藉此实现图遍历。
### GraphQL {#id63}
GraphQL 是一种查询语言，其设计本意即比本章所见其他查询语言更为严格。其目的在于：使运行于用户设备之上的客户端软件（如移动应用或基于 JavaScript 的 Web 前端）能够按需申领一份结构确定的 JSON 文档，其中仅含渲染用户界面所必需的字段。借助 GraphQL 接口，开发者可在客户端代码中快速调整查询逻辑，而无需同步修改服务端 API。

GraphQL 的灵活性亦伴生代价。采用 GraphQL 的组织，常需额外工具将 GraphQL 查询转译为对内部服务的调用——这些服务多基于 REST 或 gRPC（参见[第 5 章](/zh-cn/ch5#ch_encoding)）。授权控制、速率限制与性能优化，亦为不可忽视之挑战 [^61]。

GraphQL 查询语言本身亦受多重限制，盖因其查询源自不可信来源。该语言禁止任何可能引发高开销执行的操作；否则，攻击者可借大量昂贵查询实施拒绝服务（DoS）攻击。具体而言：  
- GraphQL 不支持递归查询（异于 Cypher、SPARQL、SQL 或 Datalog）；  
- 不支持任意组合的搜索条件（例如“查找出生地为美国、现居欧洲之人”），除非服务提供方显式开放对应搜索能力。

然则 GraphQL 仍具实用价值。[示例 3-13](/zh-cn/ch3#fig_graphql_query) 展示了如何以 GraphQL 实现类似 Discord 或 Slack 的群聊应用：该查询申领当前用户有权访问的所有频道，含频道名称及各频道最近 50 条消息；每条消息返回时间戳、正文内容、发送者姓名及其头像 URL；若该消息为回复，则一并申领被回复消息的发送者姓名与正文（可用于在回复上方以小号字体显示，以提供上下文）。
{{< figure id="fig_graphql_query" title="Example 3-13. Example GraphQL query for a group chat application" class="w-full my-4" >}}

```
query ChatApp {
    channels {
        name
        recentMessages(latest: 50) {
            timestamp
            content
        sender {
            fullName
            imageUrl
        }
    replyTo {
        content
        sender {
            fullName
        }
    }
    }
    }
}
```
[示例 3-14](/zh-cn/ch3#fig_graphql_response) 展示了对 [示例 3-13](/zh-cn/ch3#fig_graphql_query) 中查询的可能响应。该响应为一 JSON 文档，其结构与查询严格对应：仅包含客户端所请求的字段，不多不少。此设计之优，在于服务器无需预知客户端渲染界面所需字段；客户端可自主申明所需数据。例如，本查询未请求 `replyTo` 消息发送者的头像 URL；然若界面需新增该头像，则客户端仅须在查询中追加 `imageUrl` 字段，无须修改服务端逻辑。
{{< figure id="fig_graphql_response" title="Example 3-14. A possible response to the query in [Example 3-13](/zh-cn/ch3#fig_graphql_query)" class="w-full my-4" >}}

```json
{
"data": {
    "channels": [
        {
        "name": "#general",
        "recentMessages": [
        {
        "timestamp": 1693143014,
        "content": "Hey! How are y'all doing?",
        "sender": {"fullName": "Aaliyah", "imageUrl": "https://..."},
        "replyTo": null
        },
        {
            "timestamp": 1693143024,
            "content": "Great! And you?",
            "sender": {"fullName": "Caleb", "imageUrl": "https://..."},
            "replyTo": {
            "content": "Hey! How are y'all doing?",
            "sender": {"fullName": "Aaliyah"}
        }
},
...
```
在[例3-14](/zh-cn/ch3#fig_graphql_response)中，消息发送者的姓名与头像URL被直接嵌入消息对象内。若同一用户发送多条消息，则该信息将在每条消息中重复出现。理论上可消除此类冗余，但GraphQL刻意选择容忍响应体积增大，以换取客户端界面渲染逻辑之简明。

`replyTo` 字段同理：在[例3-14](/zh-cn/ch3#fig_graphql_response)中，第二条消息为对第一条的回复，其内容（“Hey!…”）及发送者Aaliyah亦被完整重复置于 `replyTo` 下。替代方案本可仅返回被回复消息的ID；然若该ID未落入客户端已获取的最近50条消息范围内，则客户端须另行发起请求以补全数据。重复携带内容，反使数据消费更为直接。

服务端数据库可采用更规范化的形式存储数据，并于查询执行时完成必要联结（join）。例如，消息记录可仅存发送者ID与所回复消息ID；收到前述查询时，服务端据此解析ID，查得对应实体。然客户端所能触发的联结操作，严格受限于GraphQL Schema中明确定义的字段与关系。

尽管GraphQL查询响应形似文档数据库输出，且名称含“graph”，其实现底层可适配任意数据库类型——关系型、文档型或图数据库皆可。
## 事件溯源与命令查询职责分离（CQRS）{#sec_datamodels_events}
迄今所论诸数据模型，其读取形式皆与写入形式一致——或为 JSON 文档，或为关系表之行，或为图之顶点与边。然于复杂应用中，常难觅一统之数据表示，以兼顾各类查询与呈现之需。此时，宜以一种形式写入数据，再从中派生若干种表示，各为其读取场景而优化。

此前已述此法，见于[“主数据系统与派生数据”](/zh-cn/ch1#sec_introduction_derived)；ETL（参见[“数据仓库”](/zh-cn/ch1#sec_introduction_dwh)）即为此类派生之典型。今更进一步：既须派生数据表示，则可分别选用专为写入优化、专为读取优化之不同表示。若仅求写入极致高效，全然不计查询性能，当如何建模？

最简、最快、最富表现力之写入方式，莫过*事件日志*（event log）：每欲写入数据，即编码为自包含字符串（如 JSON），附以时间戳，追加至事件序列末尾。日志中之事件皆*不可变*（immutable）：既不修改，亦不删除，唯可追加新事件（新事件或可覆盖旧事件语义）。事件可含任意属性。

[图 3-8](/zh-cn/ch3#fig_event_sourcing) 示一会议管理系统之例。会议业务本属复杂：参会者可 individually 注册并刷信用卡支付；企业则可批量预订席位、按发票付款，嗣后再将席位分配予具体人员；另有席位专 reserved 给讲者、赞助商、志愿者等；席位预订亦可取消；同时，主办方尚可因更换会场而动态调整总容量。凡此种种并发变更，仅计算当前可用席位数，已成棘手查询。
{{< figure src="/fig/ddia_0308.png" id="fig_event_sourcing" title="Figure 3-8. Using a log of immutable events as source of truth, and deriving materialized views from it." class="w-full my-4" >}}
在[图3-8](/zh-cn/ch3#fig_event_sourcing)中，会议（conference）状态的每一次变更——例如组织者开启注册、参会者提交或取消注册——均首先被记录为一个**事件**（event）。每当一个事件追加至日志，若干**物化视图**（materialized views，亦称*投影*（projections）或*读模型*（read models））亦同步更新，以反映该事件的影响。在会议示例中，此类视图或有三类：其一汇总各预订项的全部状态信息；其二为会议组织者的仪表盘生成统计图表；其三生成供打印参会者胸牌所用的文件。

以事件为唯一事实来源，并将一切状态变更显式表达为事件，此法谓之**事件溯源**（*event sourcing*）[^62] [^63]。  
维护写优化与读优化两类分离表示、且令读模型由写模型派生，此原则谓之**命令查询职责分离**（*command query responsibility segregation, CQRS*）[^64]。  
二者源出领域驱动设计（Domain-Driven Design, DDD）社区，然类似思想早有渊源，例如*状态机复制*（state machine replication）（参见[“使用共享日志”](/zh-cn/ch10#sec_consistency_smr)）。

用户请求抵达时，称为一条**命令**（command），须先经校验。仅当命令执行完毕并确认有效（例如：所申请预订尚有足够余座），方升格为既定事实，对应事件始得写入日志。故事件日志所载，唯有效事件；而基于该日志构建物化视图的消费者，不得拒收任一已存事件。

建模时若采事件溯源风格，宜以**过去时态**命名事件（如：“座位已被预订”），盖因事件乃对既往发生事实之客观记录。纵使用户嗣后修改或取消预订，其曾持有预订之事实依然成立；而变更或取消本身，则另为独立事件，迟后追加。

事件溯源与[“星型与雪花型：面向分析的数据模型”](/zh-cn/ch3#sec_datamodels_analytics)所述星型模式事实表（fact table）略有相似：二者皆为过往事件之集合。然事实表各行列结构恒定；事件溯源则允许多类事件并存，各类属性各异。更关键者，事实表为无序集合；事件溯源则严守时序：若预订先立后撤，颠倒处理顺序即致逻辑谬误。

事件溯源与CQRS具数项优势：

* 对系统开发者而言，事件更能阐明“何以至此”之本意。例如，“预订已被取消”远较“``bookings``表第4001行之``active``字段被设为``false``，关联该预订之三行数据自``seat_assignments``表删除，且一笔退款记录插入``payments``表”更易理解。此类行级操作或仍于物化视图处理取消事件时发生，但若由事件驱动，则更新动因昭然若揭。  
* 事件溯源之核心原则，在于物化视图须能以**可重现方式**自事件日志导出：恒可删除现有视图，复以相同代码、依原序重放全部事件，重建视图。若视图维护逻辑存有缺陷，仅需清空视图、以修正后代码重算即可。调试亦更便捷——可任意次数重放维护逻辑，细察其行为。  
* 可依应用所需查询，构建多个专用物化视图。其可与事件共存于同一数据库，亦可分置异库，视需求而定。数据模型不限，且可反规范化以加速读取。甚至可仅驻内存而不持久化，只要服务重启时允许自事件日志重算视图即可。  
* 若欲以新形式呈现既有信息，仅需基于现存事件日志新建物化视图，极为便利。系统演进亦更从容：新增事件类型、扩展现有事件属性（旧事件保持不变），或于既有事件上链式触发新行为（例如：参会者取消预订时，自动将其席位分配予候补名单首位）。  
* 若某事件误写入日志，可将其删除，再依修正后日志重建设视图。相较之下，在直接更新/删除数据的传统数据库中，此类错误难以彻底回溯与修复。
直接而言，已提交的事务往往难以回滚。事件溯源（Event Sourcing）因而可减少系统中不可逆操作的数量，提升可演化性（参见[“可演化性：让变更更简单”](/zh-cn/ch2#sec_introduction_evolvability)）。  
* 事件日志亦可作为系统全部操作的审计日志，在需满足强审计要求的受监管行业（如金融、医疗）中极具价值。

然事件溯源与CQRS亦存弊端：

* 若事件涉及外部信息，须审慎处理。例如：某事件含以某货币标示之价格，而某一读模型需将其换算为另一货币。因汇率持续波动，若于事件处理时实时调用外部汇率服务，则日后重建物化视图（materialized view）将得不同结果，致逻辑非确定。为保障事件处理之确定性，其一，须将当时适用之汇率内嵌于事件本身；其二，须能依据事件所带时间戳，精确查询对应时刻的历史汇率——且该查询对同一时间戳必返回相同结果。  
* 事件不可变之约束，与用户个人数据管理相冲突。依《通用数据保护条例》（GDPR）等法规，用户可主张删除其个人数据。若事件日志按用户隔离存储，尚可整删该用户日志；但若日志混存多用户事件，则此法失效。可行折中包括：将个人数据移出事件本体另行存储，或以密钥加密后存入事件——然密钥一旦销毁，即无法还原原始数据，亦使物化状态重计算变得困难。  
* 若事件重处理会引发对外可见副作用（如重复发送确认邮件），则须严加管控；重建物化视图时，此类副作用必须被抑制或幂等化。

事件溯源可构建于任意数据库之上；亦有专为此模式设计之系统，如 EventStoreDB、基于 PostgreSQL 的 MartenDB，以及 Axon Framework。亦可用消息中间件（如 Apache Kafka）持久化事件日志，并借流处理器（stream processor）实时维护物化视图；相关内容详见[“变更数据捕获 vs. 事件溯源”](/zh-cn/ch12#sec_stream_event_sourcing)。

唯一核心要求在于：事件存储系统须严格保证——所有物化视图所处理事件之顺序，与事件日志中原始顺序完全一致。如[第十章](/zh-cn/ch10#ch_consistency)所示，此一致性保障在分布式系统中并非易事。
## 数据框、矩阵与数组 {#sec_datamodels_dataframes}
本章迄今所见数据模型，多兼用于事务处理与分析任务（参见［“分析型系统与操作型系统”］(/zh-cn/ch1#sec_introduction_analytics)）。另有若干数据模型，常见于分析或科学计算场景，却罕用于 OLTP 系统：即**数据框（dataframe）**与**数值型多维数组（如矩阵）**。

数据框为 R 语言、Python 的 Pandas 库、Apache Spark、ArcticDB、Dask 等系统原生支持之数据模型。其为数据科学家准备机器学习训练数据之常用工具，亦广泛用于数据探索、统计分析、数据可视化等任务。

初观之，数据框形似关系数据库之表或电子表格。其支持类关系代数之批量操作：例如对全部行施加函数、依条件筛选行、按某列分组并聚合他列、依键将一数据框与另一数据框合并（关系数据库谓之 *join*，数据框中通常称 *merge*）。

数据框不依赖 SQL 等声明式查询，而以一系列命令式操作修改其结构与内容。此正契合数据科学家之典型工作流——渐进式“数据整理（wrangling）”，将原始数据逐步塑造成可回答具体问题之形态。此类操作通常在其私有数据副本上执行，常于本地机器完成；最终成果或可共享予他人。

数据框 API 所提供之运算远超关系数据库能力，其数据模型之用法亦常迥异于典型关系建模 [^65]。  
例如，数据框常被用于将类关系表示之数据，转换为矩阵或多维数组形式——此恰为多数机器学习算法所要求之输入格式。

[图 3-9](/zh-cn/ch3#fig_dataframe_to_matrix) 示一简例：左为用户对电影之评分关系表（1–5 分制），右为其转换所得矩阵，其中每列为一部电影，每行为一名用户（类同电子表格中之 *透视表*）。该矩阵为**稀疏矩阵（sparse matrix）**，即大量用户—电影组合无评分数据，此属正常。此类矩阵动辄数千列，难以适配关系数据库之范式设计；而数据框及支持稀疏数组之库（如 Python 的 NumPy）则可高效处理。
{{< figure src="/fig/ddia_0309.png" id="fig_dataframe_to_matrix" title="Figure 3-9. Transforming a relational database of movie ratings into a matrix representation." class="w-full my-4" >}}
矩阵仅可容纳数值；非数值数据须经多种技术转化为数值，方能纳入矩阵。例如：

* 日期（如[图3-9](/zh-cn/ch3#fig_dataframe_to_matrix)所示示例矩阵中已省略）可缩放为某一合适区间内的浮点数；
* 对取值有限且固定之列（如电影数据库中的“类型”字段），常用*独热编码（one-hot encoding）*：为每一可能取值设一列（如“喜剧”“剧情”“恐怖”等各一列）；对每部电影所在行，在其所属类型对应列填`1`，余者填`0`；此法亦自然支持多类型电影（即一行中可含多个`1`）。

数据一旦转为数值矩阵，即可施行线性代数运算——此乃诸多机器学习算法之基石。例如，[图3-9](/zh-cn/ch3#fig_dataframe_to_matrix)中数据或为用户电影推荐系统之一部分。数据框（DataFrame）兼具灵活性与可控性：既容许数据由关系型结构渐进演变为矩阵形式，又使数据科学家得以自主选择最契合分析目标或模型训练需求的表示方式。

另有专用于存储大规模多维数值数组之数据库，如 TileDB [^66]；此类系统称*数组数据库（array databases）*，多见于科学计算领域，典型应用场景包括：地理空间测量（规则网格上的栅格数据）、医学影像、天文望远镜观测数据 [^67]。  
金融行业亦广泛使用数据框表达*时间序列数据（time series data）*，例如资产价格与交易记录随时间变化之序列 [^68]。
## 概要 {#summary}
数据模型，范畴甚广。本章仅概览诸般模型，未及细述各型之精微；然愿此简要综述，已足激君探求之心，以择最契应用需求者。

*关系模型*虽逾半世纪，于今仍为诸多应用之基石——尤见于数据仓库与商业分析领域，星型模式（star schema）、雪花模式（snowflake schema）及 SQL 查询，几成标配。然亦有数种非关系模型，于他域蔚然成风：

* *文档模型*，适于数据以自包含 JSON 文档形式呈现、且文档间关联稀疏之场景。  
* *图数据模型*，取向相反：凡物皆可互连，查询常需跨多跳遍历（multi-hop traversal），以达目标数据；此类遍历可借 Cypher、SPARQL 或 Datalog 中之递归查询表达。  
* *数据框（DataFrame）*，将关系数据泛化至超宽列（large numbers of columns）情形，遂成数据库与机器学习、统计分析及科学计算所倚重之多维数组间的桥梁。

诸模型间，或可彼此模拟——例如图数据可存于关系数据库中——然常致笨拙，如 SQL 对递归查询之支持即为明证。

故而，各模型皆催生专用数据库：其查询语言与存储引擎，悉为该模型量身优化。然亦有融合之势：数据库渐扩边界，兼纳他模。例证如下：  
- 关系数据库增 JSON 列，以纳文档数据；  
- 文档数据库添类 SQL 的联接（join）能力；  
- SQL 对图数据之原生支持，亦稳步演进。

另有一模型，曰 *事件溯源（event sourcing）*：以只追加（append-only）、不可变之事件日志表征状态。此法尤宜建模复杂业务域中之活动流。只追加日志利于写入（详见[第四章](/zh-cn/ch4#ch_storage)）；为支撑高效读取，须藉 CQRS 模式，将事件日志转为读优化之物化视图（materialized view）。

非关系模型共通之处，在于通常不强制数据模式（schema）——此可助应用敏捷应变。然应用本身，仍隐含对数据结构之假设；所异者，唯在于该模式系显式（写入时强制）抑或隐式（读取时假定）耳。

纵已铺陈甚广，仍有若干模型未及论及。略举数例：

* 基因组研究者常需执行 *序列相似性搜索（sequence-similarity search）*：即以一极长字符串（代表 DNA 分子）为查询，在海量近似而非全等的字符串库中匹配。前述诸库，无一堪任此务；故学者专造 GenBank [^69] 等基因组数据库软件。  
* 多数金融系统以 *分类账（ledger）* 为基，采复式记账法（double-entry accounting）。此类数据虽可存于关系库，亦有 TigerBeetle 等专库为之优化。加密货币与区块链，则基于分布式账本（distributed ledger），其数据模型内建价值转移语义。  
* *全文检索（full-text search）*，实为一种高频辅佐数据库之数据模型。信息检索（information retrieval）乃专门学问，本书不拟深究；然将于[“全文检索”](/zh-cn/ch4#sec_storage_full_text)一节，略述检索索引与向量搜索（vector search）。

暂止于此。下章将析论：实现本章所述诸数据模型时，所涉之权衡取舍。
### 参考文献

[^1]: Jamie Brandon. [Unexplanations: query optimization works because sql is declarative](https://www.scattered-thoughts.net/writing/unexplanations-sql-declarative/). *scattered-thoughts.net*, February 2024. Archived at [perma.cc/P6W2-WMFZ](https://perma.cc/P6W2-WMFZ) 
[^2]: Joseph M. Hellerstein. [The Declarative Imperative: Experiences and Conjectures in Distributed Logic](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2010/EECS-2010-90.pdf). Tech report UCB/EECS-2010-90, Electrical Engineering and Computer Sciences, University of California at Berkeley, June 2010. Archived at [perma.cc/K56R-VVQM](https://perma.cc/K56R-VVQM) 
[^3]: Edgar F. Codd. [A Relational Model of Data for Large Shared Data Banks](https://www.seas.upenn.edu/~zives/03f/cis550/codd.pdf). *Communications of the ACM*, volume 13, issue 6, pages 377–387, June 1970. [doi:10.1145/362384.362685](https://doi.org/10.1145/362384.362685) 
[^4]: Michael Stonebraker and Joseph M. Hellerstein. [What Goes Around Comes Around](http://mitpress2.mit.edu/books/chapters/0262693143chapm1.pdf). In *Readings in Database Systems*, 4th edition, MIT Press, pages 2–41, 2005. ISBN: 9780262693141 
[^5]: Markus Winand. [Modern SQL: Beyond Relational](https://modern-sql.com/). *modern-sql.com*, 2015. Archived at [perma.cc/D63V-WAPN](https://perma.cc/D63V-WAPN) 
[^6]: Martin Fowler. [OrmHate](https://martinfowler.com/bliki/OrmHate.html). *martinfowler.com*, May 2012. Archived at [perma.cc/VCM8-PKNG](https://perma.cc/VCM8-PKNG) 
[^7]: Vlad Mihalcea. [N+1 query problem with JPA and Hibernate](https://vladmihalcea.com/n-plus-1-query-problem/). *vladmihalcea.com*, January 2023. Archived at [perma.cc/79EV-TZKB](https://perma.cc/79EV-TZKB) 
[^8]: Jens Schauder. [This is the Beginning of the End of the N+1 Problem: Introducing Single Query Loading](https://spring.io/blog/2023/08/31/this-is-the-beginning-of-the-end-of-the-n-1-problem-introducing-single-query). *spring.io*, August 2023. Archived at [perma.cc/6V96-R333](https://perma.cc/6V96-R333) 
[^9]: William Zola. [6 Rules of Thumb for MongoDB Schema Design](https://www.mongodb.com/blog/post/6-rules-of-thumb-for-mongodb-schema-design). *mongodb.com*, June 2014. Archived at [perma.cc/T2BZ-PPJB](https://perma.cc/T2BZ-PPJB) 
[^10]: Sidney Andrews and Christopher McClister. [Data modeling in Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/modeling-data). *learn.microsoft.com*, February 2023. Archived at [archive.org](https://web.archive.org/web/20230207193233/https%3A//learn.microsoft.com/en-us/azure/cosmos-db/nosql/modeling-data) 
[^11]: Raffi Krikorian. [Timelines at Scale](https://www.infoq.com/presentations/Twitter-Timeline-Scalability/). At *QCon San Francisco*, November 2012. Archived at [perma.cc/V9G5-KLYK](https://perma.cc/V9G5-KLYK) 
[^12]: Ralph Kimball and Margy Ross. [*The Data Warehouse Toolkit: The Definitive Guide to Dimensional Modeling*](https://learning.oreilly.com/library/view/the-data-warehouse/9781118530801/), 3rd edition. John Wiley & Sons, July 2013. ISBN: 9781118530801 
[^13]: Michael Kaminsky. [Data warehouse modeling: Star schema vs. OBT](https://www.fivetran.com/blog/star-schema-vs-obt). *fivetran.com*, August 2022. Archived at [perma.cc/2PZK-BFFP](https://perma.cc/2PZK-BFFP) 
[^14]: Joe Nelson. [User-defined Order in SQL](https://begriffs.com/posts/2018-03-20-user-defined-order.html). *begriffs.com*, March 2018. Archived at [perma.cc/GS3W-F7AD](https://perma.cc/GS3W-F7AD) 
[^15]: Evan Wallace. [Realtime Editing of Ordered Sequences](https://www.figma.com/blog/realtime-editing-of-ordered-sequences/). *figma.com*, March 2017. Archived at [perma.cc/K6ER-CQZW](https://perma.cc/K6ER-CQZW) 
[^16]: David Greenspan. [Implementing Fractional Indexing](https://observablehq.com/%40dgreensp/implementing-fractional-indexing). *observablehq.com*, October 2020. Archived at [perma.cc/5N4R-MREN](https://perma.cc/5N4R-MREN) 
[^17]: Martin Fowler. [Schemaless Data Structures](https://martinfowler.com/articles/schemaless/). *martinfowler.com*, January 2013. 
[^18]: Amr Awadallah. [Schema-on-Read vs. Schema-on-Write](https://www.slideshare.net/awadallah/schemaonread-vs-schemaonwrite). At *Berkeley EECS RAD Lab Retreat*, Santa Cruz, CA, May 2009. Archived at [perma.cc/DTB2-JCFR](https://perma.cc/DTB2-JCFR) 
[^19]: Martin Odersky. [The Trouble with Types](https://www.infoq.com/presentations/data-types-issues/). At *Strange Loop*, September 2013. Archived at [perma.cc/85QE-PVEP](https://perma.cc/85QE-PVEP) 
[^20]: Conrad Irwin. [MongoDB—Confessions of a PostgreSQL Lover](https://speakerdeck.com/conradirwin/mongodb-confessions-of-a-postgresql-lover). At *HTML5DevConf*, October 2013. Archived at [perma.cc/C2J6-3AL5](https://perma.cc/C2J6-3AL5) 
[^21]: [Percona Toolkit Documentation: pt-online-schema-change](https://docs.percona.com/percona-toolkit/pt-online-schema-change.html). *docs.percona.com*, 2023. Archived at [perma.cc/9K8R-E5UH](https://perma.cc/9K8R-E5UH) 
[^22]: Shlomi Noach. [gh-ost: GitHub’s Online Schema Migration Tool for MySQL](https://github.blog/2016-08-01-gh-ost-github-s-online-migration-tool-for-mysql/). *github.blog*, August 2016. Archived at [perma.cc/7XAG-XB72](https://perma.cc/7XAG-XB72) 
[^23]: Shayon Mukherjee. [pg-osc: Zero downtime schema changes in PostgreSQL](https://www.shayon.dev/post/2022/47/pg-osc-zero-downtime-schema-changes-in-postgresql/). *shayon.dev*, February 2022. Archived at [perma.cc/35WN-7WMY](https://perma.cc/35WN-7WMY) 
[^24]: Carlos Pérez-Aradros Herce. [Introducing pgroll: zero-downtime, reversible, schema migrations for Postgres](https://xata.io/blog/pgroll-schema-migrations-postgres). *xata.io*, October 2023. Archived at [archive.org](https://web.archive.org/web/20231008161750/https%3A//xata.io/blog/pgroll-schema-migrations-postgres) 
[^25]: James C. Corbett, Jeffrey Dean, Michael Epstein, Andrew Fikes, Christopher Frost, JJ Furman, Sanjay Ghemawat, Andrey Gubarev, Christopher Heiser, Peter Hochschild, Wilson Hsieh, Sebastian Kanthak, Eugene Kogan, Hongyi Li, Alexander Lloyd, Sergey Melnik, David Mwaura, David Nagle, Sean Quinlan, Rajesh Rao, Lindsay Rolig, Dale Woodford, Yasushi Saito, Christopher Taylor, Michal Szymaniak, and Ruth Wang. [Spanner: Google’s Globally-Distributed Database](https://research.google/pubs/pub39966/). At *10th USENIX Symposium on Operating System Design and Implementation* (OSDI), October 2012. 
[^26]: Donald K. Burleson. [Reduce I/O with Oracle Cluster Tables](http://www.dba-oracle.com/oracle_tip_hash_index_cluster_table.htm). *dba-oracle.com*. Archived at [perma.cc/7LBJ-9X2C](https://perma.cc/7LBJ-9X2C) 
[^27]: Fay Chang, Jeffrey Dean, Sanjay Ghemawat, Wilson C. Hsieh, Deborah A. Wallach, Mike Burrows, Tushar Chandra, Andrew Fikes, and Robert E. Gruber. [Bigtable: A Distributed Storage System for Structured Data](https://research.google/pubs/pub27898/). At *7th USENIX Symposium on Operating System Design and Implementation* (OSDI), November 2006. 
[^28]: Priscilla Walmsley. [*XQuery, 2nd Edition*](https://learning.oreilly.com/library/view/xquery-2nd-edition/9781491915080/). O’Reilly Media, December 2015. ISBN: 9781491915080 
[^29]: Paul C. Bryan, Kris Zyp, and Mark Nottingham. [JavaScript Object Notation (JSON) Pointer](https://www.rfc-editor.org/rfc/rfc6901). RFC 6901, IETF, April 2013. 
[^30]: Stefan Gössner, Glyn Normington, and Carsten Bormann. [JSONPath: Query Expressions for JSON](https://www.rfc-editor.org/rfc/rfc9535.html). RFC 9535, IETF, February 2024. 
[^31]: Michael Stonebraker and Andrew Pavlo. [What Goes Around Comes Around… And Around…](https://db.cs.cmu.edu/papers/2024/whatgoesaround-sigmodrec2024.pdf). *ACM SIGMOD Record*, volume 53, issue 2, pages 21–37. [doi:10.1145/3685980.3685984](https://doi.org/10.1145/3685980.3685984) 
[^32]: Lawrence Page, Sergey Brin, Rajeev Motwani, and Terry Winograd. [The PageRank Citation Ranking: Bringing Order to the Web](http://ilpubs.stanford.edu:8090/422/). Technical Report 1999-66, Stanford University InfoLab, November 1999. Archived at [perma.cc/UML9-UZHW](https://perma.cc/UML9-UZHW) 
[^33]: Nathan Bronson, Zach Amsden, George Cabrera, Prasad Chakka, Peter Dimov, Hui Ding, Jack Ferris, Anthony Giardullo, Sachin Kulkarni, Harry Li, Mark Marchukov, Dmitri Petrov, Lovro Puzar, Yee Jiun Song, and Venkat Venkataramani. [TAO: Facebook’s Distributed Data Store for the Social Graph](https://www.usenix.org/conference/atc13/technical-sessions/presentation/bronson). At *USENIX Annual Technical Conference* (ATC), June 2013. 
[^34]: Natasha Noy, Yuqing Gao, Anshu Jain, Anant Narayanan, Alan Patterson, and Jamie Taylor. [Industry-Scale Knowledge Graphs: Lessons and Challenges](https://cacm.acm.org/magazines/2019/8/238342-industry-scale-knowledge-graphs/fulltext). *Communications of the ACM*, volume 62, issue 8, pages 36–43, August 2019. [doi:10.1145/3331166](https://doi.org/10.1145/3331166) 
[^35]: Xiyang Feng, Guodong Jin, Ziyi Chen, Chang Liu, and Semih Salihoğlu. [KÙZU Graph Database Management System](https://www.cidrdb.org/cidr2023/papers/p48-jin.pdf). At *3th Annual Conference on Innovative Data Systems Research* (CIDR 2023), January 2023. 
[^36]: Maciej Besta, Emanuel Peter, Robert Gerstenberger, Marc Fischer, Michał Podstawski, Claude Barthels, Gustavo Alonso, Torsten Hoefler. [Demystifying Graph Databases: Analysis and Taxonomy of Data Organization, System Designs, and Graph Queries](https://arxiv.org/pdf/1910.09017.pdf). *arxiv.org*, October 2019. 
[^37]: [Apache TinkerPop 3.6.3 Documentation](https://tinkerpop.apache.org/docs/3.6.3/reference/). *tinkerpop.apache.org*, May 2023. Archived at [perma.cc/KM7W-7PAT](https://perma.cc/KM7W-7PAT) 
[^38]: Nadime Francis, Alastair Green, Paolo Guagliardo, Leonid Libkin, Tobias Lindaaker, Victor Marsault, Stefan Plantikow, Mats Rydberg, Petra Selmer, and Andrés Taylor. [Cypher: An Evolving Query Language for Property Graphs](https://core.ac.uk/download/pdf/158372754.pdf). At *International Conference on Management of Data* (SIGMOD), pages 1433–1445, May 2018. [doi:10.1145/3183713.3190657](https://doi.org/10.1145/3183713.3190657) 
[^39]: Emil Eifrem. [Twitter correspondence](https://twitter.com/emileifrem/status/419107961512804352), January 2014. Archived at [perma.cc/WM4S-BW64](https://perma.cc/WM4S-BW64) 
[^40]: Francesco Tisiot. [Explore the new SEARCH and CYCLE features in PostgreSQL® 14](https://aiven.io/blog/explore-the-new-search-and-cycle-features-in-postgresql-14). *aiven.io*, December 2021. Archived at [perma.cc/J6BT-83UZ](https://perma.cc/J6BT-83UZ) 
[^41]: Gaurav Goel. [Understanding Hierarchies in Oracle](https://towardsdatascience.com/understanding-hierarchies-in-oracle-43f85561f3d9). *towardsdatascience.com*, May 2020. Archived at [perma.cc/5ZLR-Q7EW](https://perma.cc/5ZLR-Q7EW) 
[^42]: Alin Deutsch, Nadime Francis, Alastair Green, Keith Hare, Bei Li, Leonid Libkin, Tobias Lindaaker, Victor Marsault, Wim Martens, Jan Michels, Filip Murlak, Stefan Plantikow, Petra Selmer, Oskar van Rest, Hannes Voigt, Domagoj Vrgoč, Mingxi Wu, and Fred Zemke. [Graph Pattern Matching in GQL and SQL/PGQ](https://arxiv.org/abs/2112.06217). At *International Conference on Management of Data* (SIGMOD), pages 2246–2258, June 2022. [doi:10.1145/3514221.3526057](https://doi.org/10.1145/3514221.3526057) 
[^43]: Alastair Green. [SQL... and now GQL](https://opencypher.org/articles/2019/09/12/SQL-and-now-GQL/). *opencypher.org*, September 2019. Archived at [perma.cc/AFB2-3SY7](https://perma.cc/AFB2-3SY7) 
[^44]: Alin Deutsch, Yu Xu, and Mingxi Wu. [Seamless Syntactic and Semantic Integration of Query Primitives over Relational and Graph Data in GSQL](https://cdn2.hubspot.net/hubfs/4114546/IntegrationQuery%20PrimitivesGSQL.pdf). *tigergraph.com*, November 2018. Archived at [perma.cc/JG7J-Y35X](https://perma.cc/JG7J-Y35X) 
[^45]: Oskar van Rest, Sungpack Hong, Jinha Kim, Xuming Meng, and Hassan Chafi. [PGQL: a property graph query language](https://event.cwi.nl/grades/2016/07-VanRest.pdf). At *4th International Workshop on Graph Data Management Experiences and Systems* (GRADES), June 2016. [doi:10.1145/2960414.2960421](https://doi.org/10.1145/2960414.2960421) 
[^46]: Amazon Web Services. [Neptune Graph Data Model](https://docs.aws.amazon.com/neptune/latest/userguide/feature-overview-data-model.html). Amazon Neptune User Guide, *docs.aws.amazon.com*. Archived at [perma.cc/CX3T-EZU9](https://perma.cc/CX3T-EZU9) 
[^47]: Cognitect. [Datomic Data Model](https://docs.datomic.com/cloud/whatis/data-model.html). Datomic Cloud Documentation, *docs.datomic.com*. Archived at [perma.cc/LGM9-LEUT](https://perma.cc/LGM9-LEUT) 
[^48]: David Beckett and Tim Berners-Lee. [Turtle – Terse RDF Triple Language](https://www.w3.org/TeamSubmission/turtle/). W3C Team Submission, March 2011. 
[^49]: Sinclair Target. [Whatever Happened to the Semantic Web?](https://twobithistory.org/2018/05/27/semantic-web.html) *twobithistory.org*, May 2018. Archived at [perma.cc/M8GL-9KHS](https://perma.cc/M8GL-9KHS) 
[^50]: Gavin Mendel-Gleason. [The Semantic Web is Dead – Long Live the Semantic Web!](https://terminusdb.com/blog/the-semantic-web-is-dead/) *terminusdb.com*, August 2022. Archived at [perma.cc/G2MZ-DSS3](https://perma.cc/G2MZ-DSS3) 
[^51]: Manu Sporny. [JSON-LD and Why I Hate the Semantic Web](http://manu.sporny.org/2014/json-ld-origins-2/). *manu.sporny.org*, January 2014. Archived at [perma.cc/7PT4-PJKF](https://perma.cc/7PT4-PJKF) 
[^52]: University of Michigan Library. [Biomedical Ontologies and Controlled Vocabularies](https://guides.lib.umich.edu/ontology), *guides.lib.umich.edu/ontology*. Archived at [perma.cc/Q5GA-F2N8](https://perma.cc/Q5GA-F2N8) 
[^53]: Facebook. [The Open Graph protocol](https://ogp.me/), *ogp.me*. Archived at [perma.cc/C49A-GUSY](https://perma.cc/C49A-GUSY) 
[^54]: Matt Haughey. [Everything you ever wanted to know about unfurling but were afraid to ask /or/ How to make your site previews look amazing in Slack](https://medium.com/slack-developer-blog/everything-you-ever-wanted-to-know-about-unfurling-but-were-afraid-to-ask-or-how-to-make-your-e64b4bb9254). *medium.com*, November 2015. Archived at [perma.cc/C7S8-4PZN](https://perma.cc/C7S8-4PZN) 
[^55]: W3C RDF Working Group. [Resource Description Framework (RDF)](https://www.w3.org/RDF/). *w3.org*, February 2004. 
[^56]: Steve Harris, Andy Seaborne, and Eric Prud’hommeaux. [SPARQL 1.1 Query Language](https://www.w3.org/TR/sparql11-query/). W3C Recommendation, March 2013. 
[^57]: Todd J. Green, Shan Shan Huang, Boon Thau Loo, and Wenchao Zhou. [Datalog and Recursive Query Processing](http://blogs.evergreen.edu/sosw/files/2014/04/Green-Vol5-DBS-017.pdf). *Foundations and Trends in Databases*, volume 5, issue 2, pages 105–195, November 2013. [doi:10.1561/1900000017](https://doi.org/10.1561/1900000017) 
[^58]: Stefano Ceri, Georg Gottlob, and Letizia Tanca. [What You Always Wanted to Know About Datalog (And Never Dared to Ask)](https://www.researchgate.net/profile/Letizia_Tanca/publication/3296132_What_you_always_wanted_to_know_about_Datalog_and_never_dared_to_ask/links/0fcfd50ca2d20473ca000000.pdf). *IEEE Transactions on Knowledge and Data Engineering*, volume 1, issue 1, pages 146–166, March 1989. [doi:10.1109/69.43410](https://doi.org/10.1109/69.43410) 
[^59]: Serge Abiteboul, Richard Hull, and Victor Vianu. [*Foundations of Databases*](http://webdam.inria.fr/Alice/). Addison-Wesley, 1995. ISBN: 9780201537710, available online at [*webdam.inria.fr/Alice*](http://webdam.inria.fr/Alice/) 
[^60]: Scott Meyer, Andrew Carter, and Andrew Rodriguez. [LIquid: The soul of a new graph database, Part 2](https://engineering.linkedin.com/blog/2020/liquid--the-soul-of-a-new-graph-database--part-2). *engineering.linkedin.com*, September 2020. Archived at [perma.cc/K9M4-PD6Q](https://perma.cc/K9M4-PD6Q) 
[^61]: Matt Bessey. [Why, after 6 years, I’m over GraphQL](https://bessey.dev/blog/2024/05/24/why-im-over-graphql/). *bessey.dev*, May 2024. Archived at [perma.cc/2PAU-JYRA](https://perma.cc/2PAU-JYRA) 
[^62]: Dominic Betts, Julián Domínguez, Grigori Melnik, Fernando Simonazzi, and Mani Subramanian. [*Exploring CQRS and Event Sourcing*](https://learn.microsoft.com/en-us/previous-versions/msp-n-p/jj554200%28v%3Dpandp.10%29). Microsoft Patterns & Practices, July 2012. ISBN: 1621140164, archived at [perma.cc/7A39-3NM8](https://perma.cc/7A39-3NM8) 
[^63]: Greg Young. [CQRS and Event Sourcing](https://www.youtube.com/watch?v=JHGkaShoyNs). At *Code on the Beach*, August 2014. 
[^64]: Greg Young. [CQRS Documents](https://cqrs.files.wordpress.com/2010/11/cqrs_documents.pdf). *cqrs.wordpress.com*, November 2010. Archived at [perma.cc/X5R6-R47F](https://perma.cc/X5R6-R47F) 
[^65]: Devin Petersohn, Stephen Macke, Doris Xin, William Ma, Doris Lee, Xiangxi Mo, Joseph E. Gonzalez, Joseph M. Hellerstein, Anthony D. Joseph, and Aditya Parameswaran. [Towards Scalable Dataframe Systems](https://www.vldb.org/pvldb/vol13/p2033-petersohn.pdf). *Proceedings of the VLDB Endowment*, volume 13, issue 11, pages 2033–2046. [doi:10.14778/3407790.3407807](https://doi.org/10.14778/3407790.3407807) 
[^66]: Stavros Papadopoulos, Kushal Datta, Samuel Madden, and Timothy Mattson. [The TileDB Array Data Storage Manager](https://www.vldb.org/pvldb/vol10/p349-papadopoulos.pdf). *Proceedings of the VLDB Endowment*, volume 10, issue 4, pages 349–360, November 2016. [doi:10.14778/3025111.3025117](https://doi.org/10.14778/3025111.3025117) 
[^67]: Florin Rusu. [Multidimensional Array Data Management](https://faculty.ucmerced.edu/frusu/Papers/Report/2022-09-fntdb-arrays.pdf). *Foundations and Trends in Databases*, volume 12, numbers 2–3, pages 69–220, February 2023. [doi:10.1561/1900000069](https://doi.org/10.1561/1900000069) 
[^68]: Ed Targett. [Bloomberg, Man Group team up to develop open source “ArcticDB” database](https://www.thestack.technology/bloomberg-man-group-arcticdb-database-dataframe/). *thestack.technology*, March 2023. Archived at [perma.cc/M5YD-QQYV](https://perma.cc/M5YD-QQYV) 
[^69]: Dennis A. Benson, Ilene Karsch-Mizrachi, David J. Lipman, James Ostell, and David L. Wheeler. [GenBank](https://academic.oup.com/nar/article/36/suppl_1/D25/2507746). *Nucleic Acids Research*, volume 36, database issue, pages D25–D30, December 2007. [doi:10.1093/nar/gkm929](https://doi.org/10.1093/nar/gkm929)
