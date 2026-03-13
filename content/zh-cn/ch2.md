---
title: "2. 非功能性需求的定义"
weight: 102
breadcrumbs: false
---

<a id="ch_nonfunctional"></a>
![](/map/ch01.png)

> *互联网构建得如此精良，以致多数人视其为太平洋般的天然资源，而非人造之物。上一次出现规模相当、 yet 几乎无错的技术，是在何时？*  
>   
> [艾伦·凯（Alan Kay）](https://www.drdobbs.com/architecture-and-design/interview-with-alan-kay/240003442)，  
> 《Dr Dobb’s Journal》访谈（2012）

若构建一应用，必依需求清单而行。清单之首，多为功能需求：即应用须提供何种界面、何类按钮，各操作应如何执行，方能达成软件之目的。此即所谓 *功能性需求（functional requirements）*。

此外，尚有若干 *非功能性需求（nonfunctional requirements）*：例如，应用须响应迅捷、运行可靠、保障安全、符合法规、易于维护。此类需求未必明文列出，盖因其看似不言自明；然其重要性，不亚于功能本身——若一应用迟滞难忍、故障频发，则形同虚设。

诸多非功能性需求（如安全性）超出本书范围。然有数项，本书将予详述；本章亦助你厘清并表述自身系统中如下关键要求：

- 如何定义与度量系统之 *性能（performance）*（参见［“性能的描述”］(/zh-cn/ch2#sec_introduction_percentiles)）；  
- 服务之 *可靠性（reliability）* 所指为何——即：纵遇异常，仍能持续正确运行（参见［“可靠性与容错”］(/zh-cn/ch2#sec_introduction_reliability)）；  
- 系统如何实现 *可扩展性（scalability）*——即：负载增长时，可通过高效扩充计算资源以维持效能（参见［“可扩展性”］(/zh-cn/ch2#sec_introduction_scalability)）；  
- 如何提升系统之 *可维护性（maintainability）*，以利长期演进与运维（参见［“可维护性”］(/zh-cn/ch2#sec_introduction_maintainability)）。

本章所立术语，亦将贯穿后续诸章，用以剖析数据密集型系统之实现细节。然抽象定义易流于枯燥；为使概念切实可感，本章将以社交网络服务为案例开篇，藉其实例阐释性能与可扩展性之要义。
## 案例研究：社交网络首页时间线 {#sec_introduction_twitter}
试拟一社交网络系统，效X（原Twitter）之制：用户可发帖、可关注他人。此仅为极简模型，[^1] [^2] [^3]，然足以揭示大规模系统中若干典型问题。

设用户日均发帖五亿条，即平均每秒五千七百条；  
偶有峰值，瞬时可达每秒十五万条 [^4]。  

又设人均关注二百人、被关注二百人（然实际分布极偏：多数用户仅数名粉丝，而极少数名人——如贝拉克·奥巴马——粉丝逾一亿）。
### 用户、帖子与关注关系的表示 {#id20}
试设所有数据悉存于关系型数据库，如[图2-1](/zh-cn/ch2#fig_twitter_relational)所示：  
用户存于 `users` 表，  
帖子存于 `posts` 表，  
关注关系存于 `follows` 表。
{{< figure src="/fig/ddia_0201.png" id="fig_twitter_relational" caption="Figure 2-1. Simple relational schema for a social network in which users can follow each other." class="w-full my-4" >}}
假设社交网络需支持的核心读操作为“首页时间线”（home timeline），即展示用户所关注之人近期发布的动态（为简化起见，暂忽略广告、非关注用户的推荐内容及其他扩展功能）。  
以下 SQL 查询可用于获取指定用户的首页时间线：
```sql
SELECT posts.*, users.* FROM posts
    JOIN follows ON posts.sender_id = follows.followee_id
    JOIN users ON posts.sender_id = users.id
    WHERE follows.follower_id = current_user
    ORDER BY posts.timestamp DESC
    LIMIT 1000
```
为执行此查询，数据库将使用 `follows` 表，查出 `current_user` 所关注之全部用户，继而检索这些用户的最新动态，并依时间戳排序，取其中最近之 1,000 条。

动态须具时效性：用户发帖后，其关注者应在 5 秒内可见。一种实现方式是——用户客户端在线期间，每 5 秒重复执行上述查询（此谓 *轮询，polling*）。若同时在线且已登录用户达一千万，则每秒需执行该查询二百万次。纵使延长轮询间隔，负载仍极高。

此外，该查询开销甚巨：若某用户关注 200 人，则需分别获取此 200 人之最新动态列表，再行归并。每秒二百万次时间线查询，即意味着数据库每秒须检索约四亿次“某发送者之最新动态”——规模惊人。此尚属平均情形；部分用户关注数以万计之账号，对该类用户，该查询不仅代价极高，且极难优化至低延迟。
### 实例化与更新时间线 {#sec_introduction_materializing}
如何改进？其一，宜弃轮询而用推送：服务器当主动向当前在线之关注者推送新帖；其二，宜预计算前述查询结果，使用户请求首页时间线（home timeline）时可直取缓存。

设想为每位用户维护一数据结构，专存其首页时间线——即其所关注用户之近期发帖。每当用户发帖，即查其全部关注者，并将此帖插入各关注者之首页时间线中，类如投信入箱。用户登录时，仅需返回该预计算完成之时间线即可。此外，若欲实时获知时间线中新帖通知，客户端唯需订阅该用户首页时间线之新增帖流。

然此法之弊，在于每次发帖均须执行更多计算：因首页时间线属派生数据，必随新帖同步更新。此流程见图 2-2（[Figure 2-2](/zh-cn/ch2#fig_twitter_timelines)）。当单次初始请求触发若干下游请求并发执行，吾辈以 *fan-out*（扇出）称之，其值即请求量之放大倍数。
{{< figure src="/fig/ddia_0202.png" id="fig_twitter_timelines" caption="Figure 2-2. Fan-out: delivering new posts to every follower of the user who made the post." class="w-full my-4" >}}
以每秒 5,700 篇发帖速率计，若平均每篇帖子触达 200 名关注者（即扇出因子为 200），则需完成略超每秒 100 万次首页时间线写入。此量虽巨，然较之原本所需每秒 4 亿次按发送者查帖之操作，已大幅节省。

若因特殊事件致发帖速率骤升，无需即时完成时间线投递；可将其入队缓存，容许帖子在关注者时间线中短暂延迟呈现。纵逢此类负载高峰，时间线加载仍迅捷，盖因仅需从缓存读取即可。

此类预先计算并持续更新查询结果之法，谓之**物化（materialization）**；时间线缓存即属一种**物化视图（materialized view）**（此概念详见[“维护物化视图”](/zh-cn/ch12#sec_stream_mat_view)）。物化视图加速读取，然代价在于写入开销增大。对多数用户，写入成本尚属可控；然社交网络尚须应对若干极端情形：

* 若一用户关注账号极多，且所关注者发帖频繁，则其物化时间线之写入速率将极高。然此时该用户实难遍览全部帖文，故可酌情丢弃部分写入，仅向其展示所关注账号之帖文抽样。  
  [^5]。

* 若一明星账号拥数百万关注者，其每发一帖，即须向百万级用户之首页时间线各插入一次。此等写入不可丢弃。解法之一，是将明星帖文与其他用户帖文分而治之：不将其写入各时间线，而单独存储；待读取时间线时，再与物化视图动态合并。纵有此类优化，支撑明星用户仍需庞杂基础设施。  
  [^6]。
## 描述性能 {#sec_introduction_percentiles}
软件性能之讨论，常以两类指标为要：

**响应时间**  
用户发起请求至收到所求结果之间所历之时长。计量单位为秒（或毫秒、微秒）。

**吞吐量**  
系统每秒所处理之请求数，或每秒所处理之数据量。在给定硬件资源配额下，系统存在一**最大吞吐量**。计量单位为“某物/秒”。

社交网络案例中，“每秒发帖数”与“每秒时间线写入数”属吞吐量指标；而“首页时间线加载耗时”及“帖子送达关注者所需时长”则属响应时间指标。

吞吐量与响应时间常有关联。图2-3（见 `/en/ch2#fig_throughput`）概示在线服务中二者之典型关系：低负载时响应时间较短；随负载上升，响应时间渐增。此乃因**排队效应**所致——当请求抵达高负载系统时，CPU 往往正处理先前请求，新到请求须待前序完成方得执行。当吞吐量趋近硬件所能承载之上限，排队延迟即急剧攀升。
{{< figure src="/fig/ddia_0203.png" id="fig_throughput" caption="Figure 2-3. As the throughput of a service approaches its capacity, the response time increases dramatically due to queueing." class="w-full my-4" >}}
无内容可译。
<a id="sidebar_metastable"></a>
> [!提示] 系统过载后无法自愈之时

若系统已近过载，吞吐量逼近极限，则或陷入恶性循环：效率持续下降，负载反进一步加剧。例如，当请求队列积压过长，响应时间大幅延长，致使客户端超时并重发请求，从而推高请求速率——此即“重试风暴”（*retry storm*）。即便原始负载回落，系统仍可能滞留于过载态，直至重启或人工干预复位。此现象谓之“亚稳态失效”（*metastable failure*），可致生产系统严重中断 [^7] [^8]。

为防重试加剧服务过载，客户端可采用指数退避（*exponential backoff* [^9] [^10]）策略：增大重试间隔，并施加随机化；亦可对近期返回错误或超时的服务临时熔断（*circuit breaker* [^11] [^12]），或以令牌桶（*token bucket* algorithm [^13]）限流。服务端则可主动监测过载迹象，提前拒绝新请求（*load shedding* [^14]），或向客户端返回降速指令（*backpressure* [^1] [^15]）。此外，队列调度与负载均衡算法之选，亦显著影响系统韧性 [^16]。

——

就性能指标而言，用户最关切者，常为响应时间；而吞吐量则决定所需算力资源（如服务器数量），进而影响特定工作负载之服务成本。若预估吞吐量将超出当前硬件承载能力，则须扩容；若系统可通过增加计算资源显著提升其最大吞吐量，则称其具备“可扩展性”（*scalable*）。

本节聚焦响应时间；吞吐量与可扩展性，将于[“可扩展性”](/zh-cn/ch2#sec_introduction_scalability)一节详述。
### 延迟与响应时间 {#id23}
“延迟”（latency）与“响应时间”（response time）偶被混用，然本书中二者含义有别（参见［图2-4］(/zh-cn/ch2#fig_response_time)）：

* *响应时间*，即客户端所感知之耗时；涵括系统内各环节所生一切延迟。  
* *服务时间*，即服务端实际处理用户请求所耗之时长。  
* *排队延迟*，可发生于流程多处：例如，请求抵达后，或需等待 CPU 空闲方得处理；又如，响应报文或需暂存缓冲区，待同机其他任务释放出站网络接口带宽后，方得发出。  
* *延迟*，泛指请求未被主动处理之全部时段，即其处于“潜伏”（latent）状态之时。尤须指出者：*网络延迟*（network latency）或*网络时延*（network delay），特指请求与响应在网络中传输所耗之时间。
{{< figure src="/fig/ddia_0204.png" id="fig_response_time" caption="Figure 2-4. Response time, service time, network latency, and queueing delay." class="w-full my-4" >}}
在[图2-4](/zh-cn/ch2#fig_response_time)中，时间自左向右流动；各通信节点以水平线表示；请求或响应消息则以粗斜箭头表示，自一节点指向另一节点。本书后续章节将屡见此类图示。

响应时间逐次波动甚大，纵使反复发出同一请求亦然。诸多因素可引入随机延迟：例如上下文切换至后台进程、网络包丢失及 TCP 重传、垃圾回收暂停（GC pause）、缺页中断致磁盘读取、机架内机械振动 [^17]，以及其他种种原因。此议题详见[“超时与无界延迟”](/zh-cn/ch9#sec_distributed_queueing)节。

排队延迟常构成响应时间变异性的主要来源。服务器并行处理能力有限（如受限于 CPU 核心数），故仅需少量慢请求，即可阻塞后续请求的处理——此即所谓*队首阻塞*（head-of-line blocking）。即便后续请求本身服务时间极短，客户端所观测之整体响应时间仍因等待前序请求完成而变长。须知：排队延迟不属于服务时间；正因如此，响应时间务必于客户端侧实测。
### 平均值、中位数与百分位数 {#id24}
因响应时间逐次而异，故不可视作单一数值，而应视为可测之**分布**。  
如[图 2-5](/zh-cn/ch2#fig_lognormal) 所示，每根灰色竖条代表一次服务请求，其高度表示该请求耗时。  
多数请求较快，然偶有**离群值**（outlier），耗时显著更长。  
网络延迟之变动，亦称**抖动**（jitter）。
{{< figure src="/fig/ddia_0205.png" id="fig_lognormal" caption="Figure 2-5. Illustrating mean and percentiles: response times for a sample of 100 requests to a service." class="w-full my-4" >}}
服务响应时间之统计，常以*平均值*（即算术平均数：诸响应时间之和除以请求数）为指标。此均值可用于估算吞吐量上限[^18]。  
然若欲知用户所历之“典型”延迟，则均值殊非良策——盖其不示若干用户实受此延时之苦。

通常宜用*百分位数*。将响应时间由快至慢排序，居中者即为*中位数*：例如中位数为 200 ms，即半数请求耗时短于 200 ms，另半数长于之。故中位数善表用户通常等待时长。中位数亦称*第 50 百分位数*，简作 *p50*。

欲察异常值之恶劣程度，可检视更高百分位：*第 95、99、99.9 百分位数*（简作 *p95*、*p99*、*p999*）最为常用。此即响应时间阈值，使 95%、99% 或 99.9% 请求快于该阈值。例如 p95 = 1.5 秒，即百次请求中九十五次耗时小于 1.5 秒，五次耗时大于或等于 1.5 秒。参见[图 2-5](/zh-cn/ch2#fig_lognormal)。

响应时间之高百分位（亦称*尾部延迟*），关乎用户体验至巨。例如 Amazon 对内部服务之响应时限，即依 *p999* 制定，虽仅影响千分之一请求。缘由在于：响应最慢之用户，往往账户数据最多（购货频密），恰为价值最高之客户[^19]。  
故须确保网站对其亦迅捷，以维系其满意度。

反之，优化 *p9999*（即万次请求中最慢之一）则被 Amazon 判为成本过高、收益过微。盖极高百分位之延迟极易受不可控随机事件扰动，且边际改善递减。

> [!TIP] 响应时间之用户影响  

直觉上，服务愈快，用户体验愈佳，似无疑义[^20]。  
然欲以可靠数据量化延迟对用户行为之影响，实出人意料地困难。

若干广引之统计，可信度存疑。2006 年 Google 报告称：搜索结果响应由 400 ms 延至 900 ms，致流量与营收下降 20%[^21]。  
然其 2009 年另一研究却称：延迟增 400 ms，仅致日均搜索量减 0.6%[^22]；  
同年 Bing 发现：页面加载延 2 秒，广告营收降 4.3%[^23]。  
此后诸公司新数据，未见公开。

Akamai 近年一研究[^24]称：响应时间增 100 ms，电商网站转化率至多降 7%；  
然细究之，该研究竟同时揭示：页面加载*极快*者，转化率亦偏低！此表面悖论，实因加载最快之页常为空页或无用内容（如 404 错误页）。然该研究未分离页面内容质量与加载时长之效应，故其结论恐难成立。

Yahoo 一项研究[^25]在控制搜索结果质量前提下，比对快、慢响应之点击率。结果显示：当快慢响应差达 1.25 秒或以上，快响应之点击率高出 20–30%。
### 响应时间指标之用 {#sec_introduction_slo_sla}
高百分位延迟，于后端服务尤须重视——此类服务常于单次终端用户请求中被多次调用。  
纵使并行发起调用，终端用户请求仍须等待最慢者完成。  
任一调用迟滞，即拖累整条请求链，如[图2-6](/zh-cn/ch2#fig_tail_amplification)所示。  
即便后端调用中仅小比例迟滞，一旦单次终端用户请求需发起多次后端调用，则遭遇至少一次迟滞调用的概率即升；  
终致更多终端用户请求整体变慢——此现象谓之*尾部延迟放大效应*（*tail latency amplification* [^26]）。
{{< figure src="/fig/ddia_0206.png" id="fig_tail_amplification" caption="Figure 2-6. When several backend calls are needed to serve a request, it takes just a single slow backend request to slow down the entire end-user request." class="w-full my-4" >}}
百分位数常用于*服务等级目标*（SLO）与*服务等级协议*（SLA），以界定服务之预期性能与可用性[^27]。  
例如，某SLO可规定：服务之中位响应时间须低于200毫秒，第99百分位响应时间须低于1秒，且至少99.9%之有效请求须返回非错误响应。SLA则为具法律约束力之契约，明定SLO未达成时之处置措施（如客户有权获退款）。此即基本要义；然实践中，为SLO与SLA选取恰当之可用性度量，殊非易事[^28] [^29]。
<a id="sidebar_percentiles"></a>
> [!提示] 计算百分位数

若需在服务监控看板中加入响应时间百分位数，须持续高效地计算之。例如，可维护一个滚动窗口，记录最近 10 分钟内所有请求的响应时间；每分钟，对窗口内数值计算中位数及若干百分位数，并将结果绘制成时序图。

最简实现：于窗口期内保存全部响应时间，每分钟排序后直接取值。若此法性能不足，可采用近似算法——以极低 CPU 与内存开销，输出高精度百分位数估计值。  
开源百分位数估计算法库包括：HdrHistogram、t-digest [^30] [^31]、OpenHistogram [^32]、DDSketch [^33]。

须警惕：对百分位数取平均（如为降低时间分辨率，或合并多机数据）在数学上无意义；响应时间数据的正确聚合方式，是直方图合并（histogram merging）[^34]。
## 可靠性与容错能力 {#sec_introduction_reliability}
人人皆有“可靠”与“不可靠”之直觉。软件之可靠性，常涵以下诸义：

* 应用依用户预期，正确执行其功能；  
* 可容用户误操作，或以未预期方式使用；  
* 在预期负载与数据规模下，性能足以满足用途；  
* 系统能阻断一切未授权访问及滥用行为。

若上述诸项合而谓之“正确运行”，则**可靠性**可概言为：“纵遇异常，仍持续正确运行”。  
为明“异常”之义，须析 **fault（缺陷）** 与 **failure（失效）** 二概念：

Fault  
: 系统之**局部组件**失常：如单块硬盘故障、单台机器宕机、或所依赖之外部服务中断。

Failure  
: 系统**整体**无法向用户提供所需服务，即未达服务等级目标（SLO）。

二者易混，实因同源而异层。例：一块硬盘停转，即该硬盘自身失效；若系统仅含此盘，则整系统亦失效。然若系统由多盘构成，则单盘失效仅为**对全局系统而言之缺陷**——此时，若数据另有副本存于他盘，全局系统即可容此缺陷，不致失效。
### 容错性 {#id27}
我们称一个系统为**容错系统**（fault-tolerant），当其在发生某些故障时，仍能持续向用户提供所需服务。若某部分一旦出错即导致整个系统失效，则该部分称为**单点故障**（single point of failure, SPOF）。

例如，在社交网络案例中，一种可能的故障是：在“扇出”（fan-out）过程中，参与更新物化时间线（materialized timelines）的某台机器崩溃或失联。为使该过程具备容错能力，须确保另一台机器可无缝接管任务，既不遗漏任何应投递的帖子，亦不重复投递。（此即所谓**恰好一次语义**（exactly-once semantics）；详见[《数据库的端到端论点》](/zh-cn/ch13#sec_future_end_to_end)。）

容错能力恒有边界：仅适用于特定类型、特定数量的故障。例如，某系统或可容忍最多两块硬盘同时损坏，或三节点集群中至多一个节点宕机。容忍任意数量的故障毫无意义——若全部节点均宕机，则无从恢复；若整颗地球（连同其上所有服务器）被黑洞吞噬，则容错需仰赖太空托管——此预算项获批之期，恐难预料。

反直觉的是，在此类容错系统中，**主动增加故障率**反而是合理策略：例如，随机、无预警地终止个别进程。此举谓之**故障注入**（fault injection）。许多关键缺陷实源于错误处理机制薄弱 [^38]；通过主动注入故障，可持续检验容错逻辑，从而提升对自然故障之应对信心。**混沌工程**（Chaos engineering）即以此为目标的工程学科：借由刻意注入故障等实验手段，验证并增强容错机制之可靠性 [^39]。

虽通常以容错优于防错，然亦有例外：防错胜于容错，盖因容错不可行也。安全领域即属此类——若攻击者已入侵系统并窃取敏感数据，该事件不可逆。然本书所论故障，多属可修复者，详述于后文各节。
### 硬件与软件故障 {#sec_introduction_hardware_faults}
当我们思考系统失效之成因，硬件故障首当其冲：

* 磁性硬盘年失效率约为 2–5% [^40] [^41]；故在含一万个磁盘的存储集群中，平均每日应发生一次磁盘失效。  
  近年数据显示，磁盘可靠性有所提升，但失效率仍具实际意义 [^42]。  

* 固态硬盘（SSD）年失效率约为 0.5–1% [^43]。少量位错误可由控制器自动纠正 [^44]；然不可纠正错误（uncorrectable errors）仍约每年每盘发生一次，即便在磨损极轻、服役较短之新盘上亦不例外；此错误率高于磁性硬盘 [^45]，[^46]。  

* 其他硬件组件——如电源、RAID 控制器、内存模组——亦会失效，唯频率低于磁盘 [^47] [^48]。  

* 约千分之一的服务器存在 CPU 核心偶发计算错误之现象，主因或为制造缺陷 [^49] [^50] [^51]。此类错误或致进程崩溃，或仅静默返回错误结果。  

* RAM 中数据亦可能损坏：或由宇宙射线等随机事件引发，或源于永久性物理缺陷。即便采用带错误校正码（ECC）之内存，逾 1% 的机器在一年内仍会遭遇至少一次不可纠正错误，通常导致整机宕机，且对应内存模组须更换 [^52]。  
  此外，特定病态内存访问模式可显著提高位翻转概率 [^53]。  

* 整个数据中心或陷于不可用状态（例如因断电或网络配置失误），甚或遭永久损毁（例如火灾、水灾、地震 [^54]）。  
  太阳风暴——即太阳抛射大量带电粒子，在长距离导线中感应强电流——可损毁电网及海底通信光缆 [^55]。  
  此类大规模失效虽罕见，若服务无法容忍单数据中心丢失，则其影响或致灾难性后果 [^56]。  

此类事件虽罕至，于小型系统中常可忽略，前提是故障硬件易于替换。然于大规模系统中，硬件故障频次已高至成为常态运行之固有组成部分。
#### 以冗余容硬件故障 {#tolerating-hardware-faults-through-redundancy}
我们应对硬件不可靠性的首要举措，通常是为单个硬件组件增设冗余，以降低系统整体失效率。例如：磁盘可配置为 RAID（将数据分散存储于同一台机器的多块磁盘上，单盘故障不致数据丢失）；服务器可配备双电源与热插拔 CPU；数据中心可部署蓄电池及柴油发电机作为备用电源。此类冗余设计，常可使单机持续运行数年而无中断。

冗余之效，以组件故障相互独立为前提——即一部件故障，不改变其余部件故障之概率。然实践表明，组件失效常具显著相关性：整机柜乃至整个数据中心之不可用，仍频发于预期之上。

硬件冗余可提升单机可用性；然如[“分布式系统 vs 单节点系统”](/zh-cn/ch1#sec_introduction_distributed)所述，分布式系统另有优势，譬如可容忍单个数据中心的全面宕机。故云服务系统往往弱化对单机可靠性的依赖，转而于软件层面容错，以保障服务高可用。云厂商以*可用区*（Availability Zone）标识物理同址资源；同区资源较异地资源更易同时失效。

本书所论容错技术，专为容忍整机、整机柜或整可用区之失效而设。其通用机制为：当某数据中心内机器故障或失联，由另一数据中心内机器接管服务。此类技术详见[第 6 章](/zh-cn/ch6#ch_replication)、[第 10 章](/zh-cn/ch10#ch_consistency)，及本书他处。

能容忍整机失效之系统，亦具运维优势：单机系统若需重启（如应用操作系统安全补丁），必致计划内停机；而多节点容错系统可逐台重启节点，全程不中断用户服务。此谓*滚动升级*（Rolling Upgrade），详见[第 5 章](/zh-cn/ch5#ch_encoding)。
#### 软件缺陷 {#software-faults}
虽硬件故障间相关性较弱，然大体独立：譬如一磁盘失效，同机其余磁盘仍可正常运行一段时日。  
反之，软件故障常高度相关，盖因多节点运行相同软件，故共享同一缺陷 [^59] [^60]。  
此类故障难于预见，所致系统失效远多于非相关之硬件故障 [^47]。例如：

* 某软件缺陷致所有节点于特定条件下同时失效。  
  例：2012年6月30日，闰秒触发 Linux 内核一缺陷，致使大量 Java 应用同步挂起，波及诸多互联网服务 [^61]；  
  因固件缺陷，某些型号 SSD 恰在运行满 32,768 小时（不足四年）后集体失效，所存数据不可恢复 [^62]。  
* 某失控进程耗尽共享且受限之资源，如 CPU 时间、内存、磁盘空间、网络带宽或线程 [^63]。  
  例：某进程处理大请求时内存占用过高，遭操作系统终止；客户端库存在缺陷，致请求数量远超预期 [^64]。  
* 系统所依赖之服务变慢、无响应，或开始返回损坏数据。  
* 多系统交互引发涌现行为，此行为在各系统孤立测试时均未显现 [^65]。  
* 级联故障：某组件异常致另一组件过载变慢，继而拖垮第三组件 [^66] [^67]。

引发此类软件故障之缺陷，常长期潜伏，直至遭遇异常组合条件方被触发。此时方显软件对其运行环境隐含某种假设——该假设通常成立，终因某因不再成立 [^68] [^69]。

软件系统性故障无速效解法。唯积小致巨：审慎辨析系统内假设与交互；充分测试；进程隔离；容许进程崩溃并重启；规避反馈环（如重试风暴，参见[“过载系统为何无法自愈”](/zh-cn/ch2#sidebar_metastable)）；于生产环境持续度量、监控与分析系统行为。
### 人与可靠性 {#id31}
人类设计并构建软件系统，而维系系统运行的运维人员亦为人类。  
机器唯循规则，人则长于创造与应变，此乃其优长；然此特性亦致行为难以预测，纵使尽心竭力，仍不免失误，终酿故障。  
例如，一项针对大型互联网服务的研究指出：运维人员所作配置变更，乃服务中断之首要成因；相较之下，硬件故障（服务器或网络设备）仅涉 10–25% 的中断事件<sup>①</sup>。

易将此类问题径称为“人为错误”，继而寄望借更严规程、更强合规以约束人性、根除此弊。  
然归咎于人，实为短视。所谓“人为错误”，非事故之因，实为社会技术系统（sociotechnical system）失谐之征——人在其中已竭尽所能履职<sup>②</sup>。  
复杂系统常具涌现行为（emergent behavior），组件间未预期之交互，亦可致故障<sup>③</sup>。

技术手段可缓释人为失误之影响：完备测试（含手工编写测试及面向大量随机输入的*属性测试*（property testing））<sup>④</sup>、配置变更后快速回滚机制、新代码渐进式发布（gradual roll-outs）、详明清晰之监控、用于诊断线上问题的可观测性工具（见[“分布式系统之困”](/zh-cn/ch1#sec_introduction_dist_sys_problems)），以及界面设计精当者——导人行正道，阻人蹈歧途。

然诸法皆需投入时力与资财。在日常商业之务实境况中，组织常重营收活动，轻容错建设。  
若须权衡“新增功能”与“加强测试”，多数组织择前者，情有可原。  
既作此取舍，则可预防之失误一旦发生，责罚执行者，于事无补；病根实系组织之优先级失当。

今愈多组织践行*无责复盘*（blameless postmortems）文化：事故发生后，涉事者可坦陈全过程，无所畏忌；惟如此，方能使全组织从中习得防范之道<sup>④</sup>。  
此过程或揭示：须调校业务优先级，须补足长期忽视之能力建设，须重构相关人员之激励机制，抑或暴露其他亟待管理层正视之系统性症结。

推而广之，事故调查之要，在戒简陋归因。  
“鲍勃部署变更时本该更审慎”，无益；  
“须以 Haskell 重写后端”，亦谬。  
管理之责，乃借机体察一线人员日日所用之社会技术系统实态，据其反馈，切实优化之<sup>⑤</sup>。
<a id="sidebar_reliability_importance"></a>
> [!TIP] 可靠性何其重要？

可靠性，非唯核电站、空管系统所独需；寻常商用软件，亦须可靠运行。业务系统若存缺陷，轻则致效率折损，重则因数据误报而引法律风险；电商网站若宕机，不仅营收锐减，更将严重损毁商誉。

诸多场景中，数分钟乃至数小时之短暂中断尚可容忍 [^74]，  
然数据永久丢失或损坏，则属灾难性后果。试想：一父母将其子女全部照片与视频悉数存于汝之影像应用 [^75]。若该数据库突遭损坏，彼等将作何感想？彼等可通晓如何自备份中恢复？

再观软件不可靠致人实害之例：英国邮政局“地平线”（Horizon）丑闻。1999 至 2019 年间，数百名英国土邮支局经理，因会计软件显示账目短缺，被控盗窃或欺诈而定罪。终查明：多数账目差额实由软件缺陷所致；迄今多起定罪已获推翻 [^76]。  
酿此恐为英国史上规模最大的司法不公之根源，在于英格兰法律预设计算机运行无误（故计算机生成之证据即具可靠性），除非反证确凿 [^77]。  
软件工程师或哂“软件永无缺陷”之说，然对那些因系统不可靠而蒙冤入狱、破产乃至自杀者而言，此笑毫无慰藉。

诚有情境，吾人或为压低开发成本而暂弃部分可靠性（如为未经验证之市场开发原型产品）；然此举须清醒自知——明辨取舍之时点，并审慎权衡潜在后果。
## 可扩展性 {#sec_introduction_scalability}
纵使系统今日运行稳健，亦不保来日必能如是。性能退化之常见缘由，首推负载增长：或因并发用户由一万人增至十万人，或因日处理数据量由百万级跃升至千万级。

*可扩展性（Scalability）*，即指系统应对负载增长之能力。

然论及可扩展性，常有言曰：“汝非谷歌，亦非亚马逊，毋庸忧于规模，径用关系型数据库可也。”此语是否适用，端视所构应用之性质而定。

若所建为初创产品，当前用户寥寥，则工程之首要目标，恒在保持系统至简至柔——以便依客户反馈迅疾调整功能、迭代设计 [^78]。  
于此情境，预忧未来虚设之规模，实为徒劳：上策不过白费心力、过早优化；下策则致架构僵化、反碍演进。

盖因可扩展性非单维标签：断言“X 可扩展”或“Y 不可扩展”，本无意义。  
论可扩展性，当究以下诸问：

* “若系统沿某方向增长，吾辈可择何策以应？”  
* “如何增补计算资源，以承新增负载？”  
* “据当前增长速率推算，何时将触现有架构之极限？”

若产品终获青睐，负载渐增，则性能瓶颈自现，扩缩维度亦明。至此，方为研习可扩展性技术之始。
### 描述负载 {#id33}
首先，须简明刻画系统当前负载；唯此，方能论及增长问题（如负载翻倍，将如何？）。负载常以吞吐量度量：例如服务每秒请求数、每日新增数据量（GB）、每小时购物车结算次数等。有时则须关注某变量之峰值，如[“案例研究：社交网络首页时间线”](/zh-cn/ch2#sec_introduction_twitter)中同时在线用户数。

负载尚有其他统计特征，亦影响访问模式，进而决定可扩展性需求。例如：数据库读写比、缓存命中率、每位用户关联的数据项数（如前述社交网络案例中的关注者数）。或以均值为关键，或瓶颈实由少数极端情形主导——悉依具体应用而定。

既已刻画负载，即可考察其增长之影响。视角有二：

* 若以特定方式增大负载，而系统资源（CPU、内存、网络带宽等）保持不变，则系统性能如何变化？  
* 若以特定方式增大负载，为维持原有性能，需增加多少资源？

通常目标为：在满足服务等级协议（SLA）性能要求（参见[“响应时间指标的使用”](/zh-cn/ch2#sec_introduction_slo_sla)）前提下，最小化系统运行成本。所需计算资源愈多，成本愈高；不同硬件类型之性价比或有差异，且随新型硬件问世而动态变化。

若负载加倍时，资源亦加倍，性能即得维持，则称该系统具*线性可扩展性*（linear scalability），此为理想情形。偶有例外：负载加倍而资源增幅不足一倍，盖因规模经济效应，或峰谷负载分布更优所致。  
然更常见者，成本增速超线性——低效成因甚多。例如：数据总量庞大时，单次写请求所涉计算量，或远超数据量较小时之同规格请求。
### 共享内存、共享磁盘与无共享架构 {#sec_introduction_shared_nothing}
提升服务硬件资源最简之法，乃迁其至更强之机器。单颗 CPU 核心之主频已难显著提升，然可购（或租用云实例）具更多核心、更大内存、更多磁盘空间之机器。此法谓之**垂直扩展**（*vertical scaling*）或**向上扩展**（*scaling up*）。

单机之内，可借多进程或多线程实现并行。同属一进程之诸线程共享同一片 RAM，故亦称**共享内存架构**（*shared-memory architecture*）。然其弊在于成本非线性增长：硬件资源翻倍之高端机器，其价常远超两倍；且受制于内存带宽、缓存一致性、锁争用等瓶颈，负载承载能力往往不足翻倍。

另有一法，曰**共享磁盘架构**（*shared-disk architecture*）：以多台独立 CPU 与内存之机器，共用一高速网络互联之磁盘阵列——即**网络附加存储**（*Network-Attached Storage*, NAS）或**存储区域网络**（*Storage Area Network*, SAN）。此架构素用于本地部署之数据仓库场景，然因节点间资源争用及锁开销，其可扩展性受限 [^81]。

相较之下，**无共享架构**（*shared-nothing architecture*）[^82]（亦称**水平扩展**（*horizontal scaling*）或**向外扩展**（*scaling out*））日益盛行。此架构以分布式系统为基，由多个节点组成，各节点独有 CPU、RAM 与磁盘；节点间协调悉赖软件层，经通用网络完成。

无共享架构之优，在于理论上线性可扩展、可择性价比最优之硬件（尤适云环境）、负载起伏时可弹性伸缩资源、且藉跨数据中心与地域部署，可获更高容错能力。其弊则有二：一须显式分片（参见[第 7 章](/zh-cn/ch7#ch_sharding)），二须直面分布式系统固有复杂性（参见[第 9 章](/zh-cn/ch9#ch_distributed)）。

若干云原生数据库系统，将存储与事务执行解耦为独立服务（参见[“存储与计算分离”](/zh-cn/ch1#sec_introduction_storage_compute)），允许多计算节点共享访问同一存储服务。此模型虽形似共享磁盘架构，却避开了旧式系统的可扩展性缺陷：存储服务不提供文件系统（NAS）或块设备（SAN）抽象，而专设面向数据库需求之定制化 API [^83]。
### 可扩展性原则 {#id35}
大规模系统之架构，恒因应用而异；  
**无通用可扩展架构**，所谓“万能伸缩秘方”（*magic scaling sauce*），实为虚妄。

例如：  
- 一系统每秒处理十万请求，每请求仅 1 kB；  
- 另一系统每分钟仅三请求，每请求却达 2 GB；  
二者吞吐量同为 100 MB/s，然其架构判若云泥。

复次，适配某负载量级之架构，十倍增载即难承其重。  
若服务增长迅疾，则每遇负载**数量级跃升**，皆须重审架构。  
应用需求本自演进，故前瞻规划，**至多覆盖一个数量级之变**；逾此则徒耗心力，反失实效。

 scalability 之要义有二：

**其一，分而治之。**  
将系统析为若干较小组件，使其尽可能独立运行。  
此即微服务（见［“微服务与无服务器”］(/zh-cn/ch1#sec_introduction_microservices)）、分片（［第七章］(/zh-cn/ch7#ch_sharding)）、流处理（［第十二章］(/zh-cn/ch12#ch_stream)）及无共享架构（*shared-nothing architecture*）之共通原理。  
然关键在**划界之准**：何者宜合，何者当分？  
微服务之设计准则，详于他书 [^84]；  
分片于无共享系统之实践，述于［第七章］(/zh-cn/ch7#ch_sharding)。

**其二，勿过求繁。**  
单机数据库足用，则远胜复杂分布式部署；  
自动扩缩容（*auto-scaling*）虽炫，然若负载可期，手动调优反少运维意外（见［“运维：自动或手动再均衡”］(/zh-cn/ch7#sec_sharding_operations)）；  
五服务之系统，必简于五十服务之系统。  
良构之架构，恒取务实折中之道，非执一术。
## 可维护性 {#sec_introduction_maintainability}
软件不磨损，亦无材料疲劳，故其失效方式迥异于机械物件。然应用之需求常变，运行环境亦迁（如依赖项与底层平台更迭），且固有缺陷待修。

业界共识：软件之成本，大半不在初始开发，而在持续维护——修缮缺陷、保障系统稳运、排查故障、适配新平台、因应新场景而改造、偿还技术债、增补新功能[^85] [^86]。

然维护实属不易。若系统久已稳定运行，则极可能倚赖过时技术（如大型机与 COBOL 代码），而今通晓者寡；其设计缘由与权衡取舍之机构记忆，或随人员离任而湮没；修复他人之误，亦在所难免。尤须注意：计算机系统常与所支撑之人类组织深度耦合，故此类*遗留系统*之维护，既是技术问题，亦是人事问题[^87]。

今日所建之系统，凡具足够价值而得以长存者，终将沦为遗留系统。为减轻后人维护之痛，吾辈当以可维护性为设计要务。虽无法尽料何等决策将致日后维护之困，本书仍聚焦若干普适原则：

**可运维性（Operability）**  
：使组织易于保障系统平稳运行。

**简洁性（Simplicity）**  
：借由成熟、一致之模式与结构实现系统，规避冗余复杂度，以利新工程师速识其全貌。

**可演化性（Evolvability）**  
：使工程师易于在未来依需变更系统——或适配未预见之场景，或延展其能力边界，以应需求之变。
### 可运维性：降低运维负担 {#id37}
此前论及云时代运维之职分（见《云时代之运维》一节），已明示：**人为流程之重要，不亚于软件工具**。诚如所言：“优良运维常可弥补拙劣（或不全）软件之缺憾；而优良软件若配以拙劣运维，则断难可靠运行。” [^60]。

于数千节点之大规模系统中，纯赖人工维护，成本必至不可承受之境，故自动化实为必需。然自动化亦具两面性：总存边缘情形（如罕见故障场景），须运维人员手动介入。而此类无法自动处置者，恰为最繁复之问题；故自动化愈深，则对运维团队之技能要求愈高 [^88]。

复次，若自动化系统自身失当，其排障之难，常甚于依赖人工执行部分操作之系统。是以，**自动化愈多，未必愈利可运维性**。然适度自动化不可或缺，其最优程度，须据具体应用与组织实情而定。

良善之可运维性，首在化常规任务为简易，使运维团队得以专注高价值事务。数据系统为此可施诸策，包括 [^89]：

* 支持监控工具采集关键指标，并兼容可观测性工具（参见《分布式系统之困》一节），以洞悉系统运行时行为；商用及开源工具皆可助此一臂之力 [^90]。  
* 避免单点机器依赖——容许个别机器下线维护，而系统整体持续无中断运行。  
* 提供完备文档与清晰易懂之运维模型（“若行 X，则生 Y”）。  
* 设定合理默认行为，同时赋予管理员按需覆写之权。  
* 在适当时机启用自愈机制，亦须保留管理员对系统状态之手动控制能力。  
* 行为须可预期，竭力减少意外。
### 简约：复杂性的管控 {#id38}
小型软件项目，代码常简洁而富表现力；然项目渐大，则往往趋于繁复难解。此等复杂性，拖慢所有系统维护者之进度，复使维护成本攀升。陷于复杂性之软件项目，时称“泥球”（*big ball of mud*）[^91]。

一旦复杂性妨害维护，则预算与工期常超支。在复杂软件中，变更更易引入缺陷：开发者若难以理解与推演系统行为，则隐含假设、非预期后果及意外交互，便更易被忽略 [^69]。  
反之，降低复杂性，可显著提升软件可维护性；故简洁性，当为系统构建之核心目标。

简明系统易于理解，故吾人宜以尽可能简之法解既定问题。惜乎知易行难。何谓“简”，常属主观之判，盖无客观之简洁标尺 [^92]。  
例如：一系统以简明接口封装复杂实现；另一系统则实现本身简易，却向用户暴露更多内部细节——二者孰简？

曾有尝试，将复杂性析为两类：*本质复杂性*（essential complexity）与*偶然复杂性*（accidental complexity）[^93]。  
其意谓：本质复杂性源于应用所处问题域本身；偶然复杂性则仅因工具局限而生。然此分野亦不牢靠：随工具演进，本质与偶然之界线随之迁移 [^94]。

管理复杂性之利器，首推*抽象*（abstraction）。良构之抽象，可于洁净、易懂之外观之下，隐去大量实现细节；且具广适性，可服务于多种不同场景。此类复用，不仅较重复实现更为高效，亦能提升整体软件品质——抽象组件之质量改进，惠及所有依赖者。

例如：高级编程语言，乃对机器码、CPU 寄存器与系统调用之抽象；SQL，则是对磁盘/内存中复杂数据结构、多客户端并发请求、崩溃后状态不一致等问题之抽象。诚然，使用高级语言编程时，底层仍运行机器码；唯吾人无需*直接*操持之，盖因语言抽象已代为屏蔽。

面向应用代码之抽象——旨在削减其复杂性者——可借*设计模式*（design patterns）[^95] 与*领域驱动设计*（Domain-Driven Design, DDD）[^96] 等方法构建。  
本书所论，非此类应用专属抽象，而是通用型抽象：数据库事务、索引、事件日志等，皆可为其基座。若欲采用 DDD 等技术，尽可建基于本书所述之基础架构之上。
### 可演化性：使变更易于实施 {#sec_introduction_evolvability}
系统需求恒久不变，实属极罕。  
其更常处于持续变动之中：新事实渐次浮现，未预见之用例悄然涌现，商业优先级更易，用户索求新功能，新平台迭代旧平台，法规与合规要求更新，系统规模扩张倒逼架构演进，等等。

组织流程层面，*敏捷（Agile）* 工作范式，为应变提供框架。  
敏捷社群亦发展出若干技术手段与实践，以支撑高频变更环境下的软件开发，如测试驱动开发（TDD）、重构（refactoring）等。  
本书所探者，非单体应用之敏捷，而是由多个异构应用或服务构成的数据系统整体之敏捷提升路径。

数据系统之可修改性、可适配性，与其简洁性及抽象程度密切相关：松耦合、简明之系统，通常较紧耦合、复杂者更易修改。  
此理至要，故另立专词以表数据系统层级之敏捷：*可演化性（evolvability）* [^97]。

大型系统中，致变更艰难之主因之一，在于某些操作不可逆，故须慎之又慎 [^98]。  
例如数据库迁移：若新库出错而无法回切至旧库，则风险陡增；若回切轻而易举，则容错空间大增。  
降低不可逆性，即提升灵活性。
## 概要 {#summary}
本章考察若干非功能性需求：性能、可靠性、可扩展性与可维护性。藉此亦引出全书后续章节所需之原理与术语。开篇以社交网络“首页时间线”实现为案例，揭示系统规模扩大时所面临之典型挑战。

性能之度量，常取响应时间百分位数；系统负载之刻画，多用吞吐量等指标；二者皆为服务等级协议（SLA）之核心依据。可扩展性与此密切相关：即负载增长时，性能仍能保持恒定。其通用原则有二：一曰任务分解，将大任务切分为可独立运行之小单元；二曰后续章节将详述各类可扩展性技术之实现细节。

可靠性之达成，赖于容错机制——即便组件（如磁盘、服务器或依赖服务）发生故障，系统仍可持续提供服务。硬件故障虽频发而模式相对确定；软件故障则更难应对，因其常具强相关性。此外，须增强对人为失误之韧性；“无责复盘”（blameless postmortem）即为此类事故中汲取经验之有效方法。

可维护性涵盖三端：支撑运维团队之日常操作、管控系统复杂度、以及支持应用功能之持续演进。此三者并无万全之策，然有一法可助益：以广为验证、语义清晰之构建模块（building blocks）搭建应用，借其抽象能力降低认知负荷。本书余下章节，即择要介绍若干经实践检验、确有价值之构建模块。
### 参考文献

[^1]: Mike Cvet. [How We Learned to Stop Worrying and Love Fan-In at Twitter](https://www.youtube.com/watch?v=WEgCjwyXvwc). At *QCon San Francisco*, December 2016. 
[^2]: Raffi Krikorian. [Timelines at Scale](https://www.infoq.com/presentations/Twitter-Timeline-Scalability/). At *QCon San Francisco*, November 2012. Archived at [perma.cc/V9G5-KLYK](https://perma.cc/V9G5-KLYK) 
[^3]: Twitter. [Twitter’s Recommendation Algorithm](https://blog.twitter.com/engineering/en_us/topics/open-source/2023/twitter-recommendation-algorithm). *blog.twitter.com*, March 2023. Archived at [perma.cc/L5GT-229T](https://perma.cc/L5GT-229T) 
[^4]: Raffi Krikorian. [New Tweets per second record, and how!](https://blog.twitter.com/engineering/en_us/a/2013/new-tweets-per-second-record-and-how) *blog.twitter.com*, August 2013. Archived at [perma.cc/6JZN-XJYN](https://perma.cc/6JZN-XJYN) 
[^5]: Jaz Volpert. [When Imperfect Systems are Good, Actually: Bluesky’s Lossy Timelines](https://jazco.dev/2025/02/19/imperfection/). *jazco.dev*, February 2025. Archived at [perma.cc/2PVE-L2MX](https://perma.cc/2PVE-L2MX) 
[^6]: Samuel Axon. [3% of Twitter’s Servers Dedicated to Justin Bieber](https://mashable.com/archive/justin-bieber-twitter). *mashable.com*, September 2010. Archived at [perma.cc/F35N-CGVX](https://perma.cc/F35N-CGVX) 
[^7]: Nathan Bronson, Abutalib Aghayev, Aleksey Charapko, and Timothy Zhu. [Metastable Failures in Distributed Systems](https://sigops.org/s/conferences/hotos/2021/papers/hotos21-s11-bronson.pdf). At *Workshop on Hot Topics in Operating Systems* (HotOS), May 2021. [doi:10.1145/3458336.3465286](https://doi.org/10.1145/3458336.3465286) 
[^8]: Marc Brooker. [Metastability and Distributed Systems](https://brooker.co.za/blog/2021/05/24/metastable.html). *brooker.co.za*, May 2021. Archived at [perma.cc/7FGJ-7XRK](https://perma.cc/7FGJ-7XRK) 
[^9]: Marc Brooker. [Exponential Backoff And Jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/). *aws.amazon.com*, March 2015. Archived at [perma.cc/R6MS-AZKH](https://perma.cc/R6MS-AZKH) 
[^10]: Marc Brooker. [What is Backoff For?](https://brooker.co.za/blog/2022/08/11/backoff.html) *brooker.co.za*, August 2022. Archived at [perma.cc/PW9N-55Q5](https://perma.cc/PW9N-55Q5) 
[^11]: Michael T. Nygard. [*Release It!*](https://learning.oreilly.com/library/view/release-it-2nd/9781680504552/), 2nd Edition. Pragmatic Bookshelf, January 2018. ISBN: 9781680502398 
[^12]: Frank Chen. [Slowing Down to Speed Up – Circuit Breakers for Slack’s CI/CD](https://slack.engineering/circuit-breakers/). *slack.engineering*, August 2022. Archived at [perma.cc/5FGS-ZPH3](https://perma.cc/5FGS-ZPH3) 
[^13]: Marc Brooker. [Fixing retries with token buckets and circuit breakers](https://brooker.co.za/blog/2022/02/28/retries.html). *brooker.co.za*, February 2022. Archived at [perma.cc/MD6N-GW26](https://perma.cc/MD6N-GW26) 
[^14]: David Yanacek. [Using load shedding to avoid overload](https://aws.amazon.com/builders-library/using-load-shedding-to-avoid-overload/). Amazon Builders’ Library, *aws.amazon.com*. Archived at [perma.cc/9SAW-68MP](https://perma.cc/9SAW-68MP) 
[^15]: Matthew Sackman. [Pushing Back](https://wellquite.org/posts/lshift/pushing_back/). *wellquite.org*, May 2016. Archived at [perma.cc/3KCZ-RUFY](https://perma.cc/3KCZ-RUFY) 
[^16]: Dmitry Kopytkov and Patrick Lee. [Meet Bandaid, the Dropbox service proxy](https://dropbox.tech/infrastructure/meet-bandaid-the-dropbox-service-proxy). *dropbox.tech*, March 2018. Archived at [perma.cc/KUU6-YG4S](https://perma.cc/KUU6-YG4S) 
[^17]: Haryadi S. Gunawi, Riza O. Suminto, Russell Sears, Casey Golliher, Swaminathan Sundararaman, Xing Lin, Tim Emami, Weiguang Sheng, Nematollah Bidokhti, Caitie McCaffrey, Gary Grider, Parks M. Fields, Kevin Harms, Robert B. Ross, Andree Jacobson, Robert Ricci, Kirk Webb, Peter Alvaro, H. Birali Runesha, Mingzhe Hao, and Huaicheng Li. [Fail-Slow at Scale: Evidence of Hardware Performance Faults in Large Production Systems](https://www.usenix.org/system/files/conference/fast18/fast18-gunawi.pdf). At *16th USENIX Conference on File and Storage Technologies*, February 2018. 
[^18]: Marc Brooker. [Is the Mean Really Useless?](https://brooker.co.za/blog/2017/12/28/mean.html) *brooker.co.za*, December 2017. Archived at [perma.cc/U5AE-CVEM](https://perma.cc/U5AE-CVEM) 
[^19]: Giuseppe DeCandia, Deniz Hastorun, Madan Jampani, Gunavardhan Kakulapati, Avinash Lakshman, Alex Pilchin, Swaminathan Sivasubramanian, Peter Vosshall, and Werner Vogels. [Dynamo: Amazon’s Highly Available Key-Value Store](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf). At *21st ACM Symposium on Operating Systems Principles* (SOSP), October 2007. [doi:10.1145/1294261.1294281](https://doi.org/10.1145/1294261.1294281) 
[^20]: Kathryn Whitenton. [The Need for Speed, 23 Years Later](https://www.nngroup.com/articles/the-need-for-speed/). *nngroup.com*, May 2020. Archived at [perma.cc/C4ER-LZYA](https://perma.cc/C4ER-LZYA) 
[^21]: Greg Linden. [Marissa Mayer at Web 2.0](https://glinden.blogspot.com/2006/11/marissa-mayer-at-web-20.html). *glinden.blogspot.com*, November 2005. Archived at [perma.cc/V7EA-3VXB](https://perma.cc/V7EA-3VXB) 
[^22]: Jake Brutlag. [Speed Matters for Google Web Search](https://services.google.com/fh/files/blogs/google_delayexp.pdf). *services.google.com*, June 2009. Archived at [perma.cc/BK7R-X7M2](https://perma.cc/BK7R-X7M2) 
[^23]: Eric Schurman and Jake Brutlag. [Performance Related Changes and their User Impact](https://www.youtube.com/watch?v=bQSE51-gr2s). Talk at *Velocity 2009*. 
[^24]: Akamai Technologies, Inc. [The State of Online Retail Performance](https://web.archive.org/web/20210729180749/https%3A//www.akamai.com/us/en/multimedia/documents/report/akamai-state-of-online-retail-performance-spring-2017.pdf). *akamai.com*, April 2017. Archived at [perma.cc/UEK2-HYCS](https://perma.cc/UEK2-HYCS) 
[^25]: Xiao Bai, Ioannis Arapakis, B. Barla Cambazoglu, and Ana Freire. [Understanding and Leveraging the Impact of Response Latency on User Behaviour in Web Search](https://iarapakis.github.io/papers/TOIS17.pdf). *ACM Transactions on Information Systems*, volume 36, issue 2, article 21, April 2018. [doi:10.1145/3106372](https://doi.org/10.1145/3106372) 
[^26]: Jeffrey Dean and Luiz André Barroso. [The Tail at Scale](https://cacm.acm.org/research/the-tail-at-scale/). *Communications of the ACM*, volume 56, issue 2, pages 74–80, February 2013. [doi:10.1145/2408776.2408794](https://doi.org/10.1145/2408776.2408794) 
[^27]: Alex Hidalgo. [*Implementing Service Level Objectives: A Practical Guide to SLIs, SLOs, and Error Budgets*](https://www.oreilly.com/library/view/implementing-service-level/9781492076803/). O’Reilly Media, September 2020. ISBN: 1492076813 
[^28]: Jeffrey C. Mogul and John Wilkes. [Nines are Not Enough: Meaningful Metrics for Clouds](https://research.google/pubs/pub48033/). At *17th Workshop on Hot Topics in Operating Systems* (HotOS), May 2019. [doi:10.1145/3317550.3321432](https://doi.org/10.1145/3317550.3321432) 
[^29]: Tamás Hauer, Philipp Hoffmann, John Lunney, Dan Ardelean, and Amer Diwan. [Meaningful Availability](https://www.usenix.org/conference/nsdi20/presentation/hauer). At *17th USENIX Symposium on Networked Systems Design and Implementation* (NSDI), February 2020. 
[^30]: Ted Dunning. [The t-digest: Efficient estimates of distributions](https://www.sciencedirect.com/science/article/pii/S2665963820300403). *Software Impacts*, volume 7, article 100049, February 2021. [doi:10.1016/j.simpa.2020.100049](https://doi.org/10.1016/j.simpa.2020.100049) 
[^31]: David Kohn. [How percentile approximation works (and why it’s more useful than averages)](https://www.timescale.com/blog/how-percentile-approximation-works-and-why-its-more-useful-than-averages/). *timescale.com*, September 2021. Archived at [perma.cc/3PDP-NR8B](https://perma.cc/3PDP-NR8B) 
[^32]: Heinrich Hartmann and Theo Schlossnagle. [Circllhist — A Log-Linear Histogram Data Structure for IT Infrastructure Monitoring](https://arxiv.org/pdf/2001.06561.pdf). *arxiv.org*, January 2020. 
[^33]: Charles Masson, Jee E. Rim, and Homin K. Lee. [DDSketch: A Fast and Fully-Mergeable Quantile Sketch with Relative-Error Guarantees](https://www.vldb.org/pvldb/vol12/p2195-masson.pdf). *Proceedings of the VLDB Endowment*, volume 12, issue 12, pages 2195–2205, August 2019. [doi:10.14778/3352063.3352135](https://doi.org/10.14778/3352063.3352135) 
[^34]: Baron Schwartz. [Why Percentiles Don’t Work the Way You Think](https://orangematter.solarwinds.com/2016/11/18/why-percentiles-dont-work-the-way-you-think/). *solarwinds.com*, November 2016. Archived at [perma.cc/469T-6UGB](https://perma.cc/469T-6UGB) 
[^35]: Walter L. Heimerdinger and Charles B. Weinstock. [A Conceptual Framework for System Fault Tolerance](https://resources.sei.cmu.edu/asset_files/TechnicalReport/1992_005_001_16112.pdf). Technical Report CMU/SEI-92-TR-033, Software Engineering Institute, Carnegie Mellon University, October 1992. Archived at [perma.cc/GD2V-DMJW](https://perma.cc/GD2V-DMJW) 
[^36]: Felix C. Gärtner. [Fundamentals of fault-tolerant distributed computing in asynchronous environments](https://dl.acm.org/doi/pdf/10.1145/311531.311532). *ACM Computing Surveys*, volume 31, issue 1, pages 1–26, March 1999. [doi:10.1145/311531.311532](https://doi.org/10.1145/311531.311532) 
[^37]: Algirdas Avižienis, Jean-Claude Laprie, Brian Randell, and Carl Landwehr. [Basic Concepts and Taxonomy of Dependable and Secure Computing](https://hdl.handle.net/1903/6459). *IEEE Transactions on Dependable and Secure Computing*, volume 1, issue 1, January 2004. [doi:10.1109/TDSC.2004.2](https://doi.org/10.1109/TDSC.2004.2) 
[^38]: Ding Yuan, Yu Luo, Xin Zhuang, Guilherme Renna Rodrigues, Xu Zhao, Yongle Zhang, Pranay U. Jain, and Michael Stumm. [Simple Testing Can Prevent Most Critical Failures: An Analysis of Production Failures in Distributed Data-Intensive Systems](https://www.usenix.org/system/files/conference/osdi14/osdi14-paper-yuan.pdf). At *11th USENIX Symposium on Operating Systems Design and Implementation* (OSDI), October 2014. 
[^39]: Casey Rosenthal and Nora Jones. [*Chaos Engineering*](https://learning.oreilly.com/library/view/chaos-engineering/9781492043850/). O’Reilly Media, April 2020. ISBN: 9781492043867 
[^40]: Eduardo Pinheiro, Wolf-Dietrich Weber, and Luiz Andre Barroso. [Failure Trends in a Large Disk Drive Population](https://www.usenix.org/legacy/events/fast07/tech/full_papers/pinheiro/pinheiro_old.pdf). At *5th USENIX Conference on File and Storage Technologies* (FAST), February 2007. 
[^41]: Bianca Schroeder and Garth A. Gibson. [Disk failures in the real world: What does an MTTF of 1,000,000 hours mean to you?](https://www.usenix.org/legacy/events/fast07/tech/schroeder/schroeder.pdf) At *5th USENIX Conference on File and Storage Technologies* (FAST), February 2007. 
[^42]: Andy Klein. [Backblaze Drive Stats for Q2 2021](https://www.backblaze.com/blog/backblaze-drive-stats-for-q2-2021/). *backblaze.com*, August 2021. Archived at [perma.cc/2943-UD5E](https://perma.cc/2943-UD5E) 
[^43]: Iyswarya Narayanan, Di Wang, Myeongjae Jeon, Bikash Sharma, Laura Caulfield, Anand Sivasubramaniam, Ben Cutler, Jie Liu, Badriddine Khessib, and Kushagra Vaid. [SSD Failures in Datacenters: What? When? and Why?](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/08/a7-narayanan.pdf) At *9th ACM International on Systems and Storage Conference* (SYSTOR), June 2016. [doi:10.1145/2928275.2928278](https://doi.org/10.1145/2928275.2928278) 
[^44]: Alibaba Cloud Storage Team. [Storage System Design Analysis: Factors Affecting NVMe SSD Performance (1)](https://www.alibabacloud.com/blog/594375). *alibabacloud.com*, January 2019. Archived at [archive.org](https://web.archive.org/web/20230522005034/https%3A//www.alibabacloud.com/blog/594375) 
[^45]: Bianca Schroeder, Raghav Lagisetty, and Arif Merchant. [Flash Reliability in Production: The Expected and the Unexpected](https://www.usenix.org/system/files/conference/fast16/fast16-papers-schroeder.pdf). At *14th USENIX Conference on File and Storage Technologies* (FAST), February 2016. 
[^46]: Jacob Alter, Ji Xue, Alma Dimnaku, and Evgenia Smirni. [SSD failures in the field: symptoms, causes, and prediction models](https://dl.acm.org/doi/pdf/10.1145/3295500.3356172). At *International Conference for High Performance Computing, Networking, Storage and Analysis* (SC), November 2019. [doi:10.1145/3295500.3356172](https://doi.org/10.1145/3295500.3356172) 
[^47]: Daniel Ford, François Labelle, Florentina I. Popovici, Murray Stokely, Van-Anh Truong, Luiz Barroso, Carrie Grimes, and Sean Quinlan. [Availability in Globally Distributed Storage Systems](https://www.usenix.org/legacy/event/osdi10/tech/full_papers/Ford.pdf). At *9th USENIX Symposium on Operating Systems Design and Implementation* (OSDI), October 2010. 
[^48]: Kashi Venkatesh Vishwanath and Nachiappan Nagappan. [Characterizing Cloud Computing Hardware Reliability](https://www.microsoft.com/en-us/research/wp-content/uploads/2010/06/socc088-vishwanath.pdf). At *1st ACM Symposium on Cloud Computing* (SoCC), June 2010. [doi:10.1145/1807128.1807161](https://doi.org/10.1145/1807128.1807161) 
[^49]: Peter H. Hochschild, Paul Turner, Jeffrey C. Mogul, Rama Govindaraju, Parthasarathy Ranganathan, David E. Culler, and Amin Vahdat. [Cores that don’t count](https://sigops.org/s/conferences/hotos/2021/papers/hotos21-s01-hochschild.pdf). At *Workshop on Hot Topics in Operating Systems* (HotOS), June 2021. [doi:10.1145/3458336.3465297](https://doi.org/10.1145/3458336.3465297) 
[^50]: Harish Dattatraya Dixit, Sneha Pendharkar, Matt Beadon, Chris Mason, Tejasvi Chakravarthy, Bharath Muthiah, and Sriram Sankar. [Silent Data Corruptions at Scale](https://arxiv.org/abs/2102.11245). *arXiv:2102.11245*, February 2021. 
[^51]: Diogo Behrens, Marco Serafini, Sergei Arnautov, Flavio P. Junqueira, and Christof Fetzer. [Scalable Error Isolation for Distributed Systems](https://www.usenix.org/conference/nsdi15/technical-sessions/presentation/behrens). At *12th USENIX Symposium on Networked Systems Design and Implementation* (NSDI), May 2015. 
[^52]: Bianca Schroeder, Eduardo Pinheiro, and Wolf-Dietrich Weber. [DRAM Errors in the Wild: A Large-Scale Field Study](https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/35162.pdf). At *11th International Joint Conference on Measurement and Modeling of Computer Systems* (SIGMETRICS), June 2009. [doi:10.1145/1555349.1555372](https://doi.org/10.1145/1555349.1555372) 
[^53]: Yoongu Kim, Ross Daly, Jeremie Kim, Chris Fallin, Ji Hye Lee, Donghyuk Lee, Chris Wilkerson, Konrad Lai, and Onur Mutlu. [Flipping Bits in Memory Without Accessing Them: An Experimental Study of DRAM Disturbance Errors](https://users.ece.cmu.edu/~yoonguk/papers/kim-isca14.pdf). At *41st Annual International Symposium on Computer Architecture* (ISCA), June 2014. [doi:10.5555/2665671.2665726](https://doi.org/10.5555/2665671.2665726) 
[^54]: Tim Bray. [Worst Case](https://www.tbray.org/ongoing/When/202x/2021/10/08/The-WOrst-Case). *tbray.org*, October 2021. Archived at [perma.cc/4QQM-RTHN](https://perma.cc/4QQM-RTHN) 
[^55]: Sangeetha Abdu Jyothi. [Solar Superstorms: Planning for an Internet Apocalypse](https://ics.uci.edu/~sabdujyo/papers/sigcomm21-cme.pdf). At *ACM SIGCOMM Conferene*, August 2021. [doi:10.1145/3452296.3472916](https://doi.org/10.1145/3452296.3472916) 
[^56]: Adrian Cockcroft. [Failure Modes and Continuous Resilience](https://adrianco.medium.com/failure-modes-and-continuous-resilience-6553078caad5). *adrianco.medium.com*, November 2019. Archived at [perma.cc/7SYS-BVJP](https://perma.cc/7SYS-BVJP) 
[^57]: Shujie Han, Patrick P. C. Lee, Fan Xu, Yi Liu, Cheng He, and Jiongzhou Liu. [An In-Depth Study of Correlated Failures in Production SSD-Based Data Centers](https://www.usenix.org/conference/fast21/presentation/han). At *19th USENIX Conference on File and Storage Technologies* (FAST), February 2021. 
[^58]: Edmund B. Nightingale, John R. Douceur, and Vince Orgovan. [Cycles, Cells and Platters: An Empirical Analysis of Hardware Failures on a Million Consumer PCs](https://eurosys2011.cs.uni-salzburg.at/pdf/eurosys2011-nightingale.pdf). At *6th European Conference on Computer Systems* (EuroSys), April 2011. [doi:10.1145/1966445.1966477](https://doi.org/10.1145/1966445.1966477) 
[^59]: Haryadi S. Gunawi, Mingzhe Hao, Tanakorn Leesatapornwongsa, Tiratat Patana-anake, Thanh Do, Jeffry Adityatama, Kurnia J. Eliazar, Agung Laksono, Jeffrey F. Lukman, Vincentius Martin, and Anang D. Satria. [What Bugs Live in the Cloud?](https://ucare.cs.uchicago.edu/pdf/socc14-cbs.pdf) At *5th ACM Symposium on Cloud Computing* (SoCC), November 2014. [doi:10.1145/2670979.2670986](https://doi.org/10.1145/2670979.2670986) 
[^60]: Jay Kreps. [Getting Real About Distributed System Reliability](https://blog.empathybox.com/post/19574936361/getting-real-about-distributed-system-reliability). *blog.empathybox.com*, March 2012. Archived at [perma.cc/9B5Q-AEBW](https://perma.cc/9B5Q-AEBW) 
[^61]: Nelson Minar. [Leap Second Crashes Half the Internet](https://www.somebits.com/weblog/tech/bad/leap-second-2012.html). *somebits.com*, July 2012. Archived at [perma.cc/2WB8-D6EU](https://perma.cc/2WB8-D6EU) 
[^62]: Hewlett Packard Enterprise. [Support Alerts – Customer Bulletin a00092491en\_us](https://support.hpe.com/hpesc/public/docDisplay?docId=emr_na-a00092491en_us). *support.hpe.com*, November 2019. Archived at [perma.cc/S5F6-7ZAC](https://perma.cc/S5F6-7ZAC) 
[^63]: Lorin Hochstein. [awesome limits](https://github.com/lorin/awesome-limits). *github.com*, November 2020. Archived at [perma.cc/3R5M-E5Q4](https://perma.cc/3R5M-E5Q4) 
[^64]: Caitie McCaffrey. [Clients Are Jerks: AKA How Halo 4 DoSed the Services at Launch & How We Survived](https://www.caitiem.com/2015/06/23/clients-are-jerks-aka-how-halo-4-dosed-the-services-at-launch-how-we-survived/). *caitiem.com*, June 2015. Archived at [perma.cc/MXX4-W373](https://perma.cc/MXX4-W373) 
[^65]: Lilia Tang, Chaitanya Bhandari, Yongle Zhang, Anna Karanika, Shuyang Ji, Indranil Gupta, and Tianyin Xu. [Fail through the Cracks: Cross-System Interaction Failures in Modern Cloud Systems](https://tianyin.github.io/pub/csi-failures.pdf). At *18th European Conference on Computer Systems* (EuroSys), May 2023. [doi:10.1145/3552326.3587448](https://doi.org/10.1145/3552326.3587448) 
[^66]: Mike Ulrich. [Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/). In Betsy Beyer, Jennifer Petoff, Chris Jones, and Niall Richard Murphy (ed). [*Site Reliability Engineering: How Google Runs Production Systems*](https://www.oreilly.com/library/view/site-reliability-engineering/9781491929117/). O’Reilly Media, 2016. ISBN: 9781491929124 
[^67]: Harri Faßbender. [Cascading failures in large-scale distributed systems](https://blog.mi.hdm-stuttgart.de/index.php/2022/03/03/cascading-failures-in-large-scale-distributed-systems/). *blog.mi.hdm-stuttgart.de*, March 2022. Archived at [perma.cc/K7VY-YJRX](https://perma.cc/K7VY-YJRX) 
[^68]: Richard I. Cook. [How Complex Systems Fail](https://www.adaptivecapacitylabs.com/HowComplexSystemsFail.pdf). Cognitive Technologies Laboratory, April 2000. Archived at [perma.cc/RDS6-2YVA](https://perma.cc/RDS6-2YVA) 
[^69]: David D. Woods. [STELLA: Report from the SNAFUcatchers Workshop on Coping With Complexity](https://snafucatchers.github.io/). *snafucatchers.github.io*, March 2017. Archived at [archive.org](https://web.archive.org/web/20230306130131/https%3A//snafucatchers.github.io/) 
[^70]: David Oppenheimer, Archana Ganapathi, and David A. Patterson. [Why Do Internet Services Fail, and What Can Be Done About It?](https://static.usenix.org/events/usits03/tech/full_papers/oppenheimer/oppenheimer.pdf) At *4th USENIX Symposium on Internet Technologies and Systems* (USITS), March 2003. 
[^71]: Sidney Dekker. [*The Field Guide to Understanding ‘Human Error’, 3rd Edition*](https://learning.oreilly.com/library/view/the-field-guide/9781317031833/). CRC Press, November 2017. ISBN: 9781472439055 
[^72]: Sidney Dekker. [*Drift into Failure: From Hunting Broken Components to Understanding Complex Systems*](https://www.taylorfrancis.com/books/mono/10.1201/9781315257396/drift-failure-sidney-dekker). CRC Press, 2011. ISBN: 9781315257396 
[^73]: John Allspaw. [Blameless PostMortems and a Just Culture](https://www.etsy.com/codeascraft/blameless-postmortems/). *etsy.com*, May 2012. Archived at [perma.cc/YMJ7-NTAP](https://perma.cc/YMJ7-NTAP) 
[^74]: Itzy Sabo. [Uptime Guarantees — A Pragmatic Perspective](https://world.hey.com/itzy/uptime-guarantees-a-pragmatic-perspective-736d7ea4). *world.hey.com*, March 2023. Archived at [perma.cc/F7TU-78JB](https://perma.cc/F7TU-78JB) 
[^75]: Michael Jurewitz. [The Human Impact of Bugs](http://jury.me/blog/2013/3/14/the-human-impact-of-bugs). *jury.me*, March 2013. Archived at [perma.cc/5KQ4-VDYL](https://perma.cc/5KQ4-VDYL) 
[^76]: Mark Halper. [How Software Bugs led to ‘One of the Greatest Miscarriages of Justice’ in British History](https://cacm.acm.org/news/how-software-bugs-led-to-one-of-the-greatest-miscarriages-of-justice-in-british-history/). *Communications of the ACM*, January 2025. [doi:10.1145/3703779](https://doi.org/10.1145/3703779) 
[^77]: Nicholas Bohm, James Christie, Peter Bernard Ladkin, Bev Littlewood, Paul Marshall, Stephen Mason, Martin Newby, Steven J. Murdoch, Harold Thimbleby, and Martyn Thomas. [The legal rule that computers are presumed to be operating correctly – unforeseen and unjust consequences](https://www.benthamsgaze.org/wp-content/uploads/2022/06/briefing-presumption-that-computers-are-reliable.pdf). Briefing note, *benthamsgaze.org*, June 2022. Archived at [perma.cc/WQ6X-TMW4](https://perma.cc/WQ6X-TMW4) 
[^78]: Dan McKinley. [Choose Boring Technology](https://mcfunley.com/choose-boring-technology). *mcfunley.com*, March 2015. Archived at [perma.cc/7QW7-J4YP](https://perma.cc/7QW7-J4YP) 
[^79]: Andy Warfield. [Building and operating a pretty big storage system called S3](https://www.allthingsdistributed.com/2023/07/building-and-operating-a-pretty-big-storage-system.html). *allthingsdistributed.com*, July 2023. Archived at [perma.cc/7LPK-TP7V](https://perma.cc/7LPK-TP7V) 
[^80]: Marc Brooker. [Surprising Scalability of Multitenancy](https://brooker.co.za/blog/2023/03/23/economics.html). *brooker.co.za*, March 2023. Archived at [perma.cc/ZZD9-VV8T](https://perma.cc/ZZD9-VV8T) 
[^81]: Ben Stopford. [Shared Nothing vs. Shared Disk Architectures: An Independent View](http://www.benstopford.com/2009/11/24/understanding-the-shared-nothing-architecture/). *benstopford.com*, November 2009. Archived at [perma.cc/7BXH-EDUR](https://perma.cc/7BXH-EDUR) 
[^82]: Michael Stonebraker. [The Case for Shared Nothing](https://dsf.berkeley.edu/papers/hpts85-nothing.pdf). *IEEE Database Engineering Bulletin*, volume 9, issue 1, pages 4–9, March 1986. 
[^83]: Panagiotis Antonopoulos, Alex Budovski, Cristian Diaconu, Alejandro Hernandez Saenz, Jack Hu, Hanuma Kodavalla, Donald Kossmann, Sandeep Lingam, Umar Farooq Minhas, Naveen Prakash, Vijendra Purohit, Hugh Qu, Chaitanya Sreenivas Ravella, Krystyna Reisteter, Sheetal Shrotri, Dixin Tang, and Vikram Wakade. [Socrates: The New SQL Server in the Cloud](https://www.microsoft.com/en-us/research/uploads/prod/2019/05/socrates.pdf). At *ACM International Conference on Management of Data* (SIGMOD), pages 1743–1756, June 2019. [doi:10.1145/3299869.3314047](https://doi.org/10.1145/3299869.3314047) 
[^84]: Sam Newman. [*Building Microservices*, second edition](https://www.oreilly.com/library/view/building-microservices-2nd/9781492034018/). O’Reilly Media, 2021. ISBN: 9781492034025 
[^85]: Nathan Ensmenger. [When Good Software Goes Bad: The Surprising Durability of an Ephemeral Technology](https://themaintainers.wpengine.com/wp-content/uploads/2021/04/ensmenger-maintainers-v2.pdf). At *The Maintainers Conference*, April 2016. Archived at [perma.cc/ZXT4-HGZB](https://perma.cc/ZXT4-HGZB) 
[^86]: Robert L. Glass. [*Facts and Fallacies of Software Engineering*](https://learning.oreilly.com/library/view/facts-and-fallacies/0321117425/). Addison-Wesley Professional, October 2002. ISBN: 9780321117427 
[^87]: Marianne Bellotti. [*Kill It with Fire*](https://learning.oreilly.com/library/view/kill-it-with/9781098128883/). No Starch Press, April 2021. ISBN: 9781718501188 
[^88]: Lisanne Bainbridge. [Ironies of automation](https://www.adaptivecapacitylabs.com/IroniesOfAutomation-Bainbridge83.pdf). *Automatica*, volume 19, issue 6, pages 775–779, November 1983. [doi:10.1016/0005-1098(83)90046-8](https://doi.org/10.1016/0005-1098%2883%2990046-8) 
[^89]: James Hamilton. [On Designing and Deploying Internet-Scale Services](https://www.usenix.org/legacy/events/lisa07/tech/full_papers/hamilton/hamilton.pdf). At *21st Large Installation System Administration Conference* (LISA), November 2007. 
[^90]: Dotan Horovits. [Open Source for Better Observability](https://horovits.medium.com/open-source-for-better-observability-8c65b5630561). *horovits.medium.com*, October 2021. Archived at [perma.cc/R2HD-U2ZT](https://perma.cc/R2HD-U2ZT) 
[^91]: Brian Foote and Joseph Yoder. [Big Ball of Mud](http://www.laputan.org/pub/foote/mud.pdf). At *4th Conference on Pattern Languages of Programs* (PLoP), September 1997. Archived at [perma.cc/4GUP-2PBV](https://perma.cc/4GUP-2PBV) 
[^92]: Marc Brooker. [What is a simple system?](https://brooker.co.za/blog/2022/05/03/simplicity.html) *brooker.co.za*, May 2022. Archived at [perma.cc/U72T-BFVE](https://perma.cc/U72T-BFVE) 
[^93]: Frederick P. Brooks. [No Silver Bullet – Essence and Accident in Software Engineering](https://worrydream.com/refs/Brooks_1986_-_No_Silver_Bullet.pdf). In [*The Mythical Man-Month*](https://www.oreilly.com/library/view/mythical-man-month-the/0201835959/), Anniversary edition, Addison-Wesley, 1995. ISBN: 9780201835953 
[^94]: Dan Luu. [Against essential and accidental complexity](https://danluu.com/essential-complexity/). *danluu.com*, December 2020. Archived at [perma.cc/H5ES-69KC](https://perma.cc/H5ES-69KC) 
[^95]: Erich Gamma, Richard Helm, Ralph Johnson, and John Vlissides. [*Design Patterns: Elements of Reusable Object-Oriented Software*](https://learning.oreilly.com/library/view/design-patterns-elements/0201633612/). Addison-Wesley Professional, October 1994. ISBN: 9780201633610 
[^96]: Eric Evans. [*Domain-Driven Design: Tackling Complexity in the Heart of Software*](https://learning.oreilly.com/library/view/domain-driven-design-tackling/0321125215/). Addison-Wesley Professional, August 2003. ISBN: 9780321125217 
[^97]: Hongyu Pei Breivold, Ivica Crnkovic, and Peter J. Eriksson. [Analyzing Software Evolvability](https://www.es.mdh.se/pdf_publications/1251.pdf). at *32nd Annual IEEE International Computer Software and Applications Conference* (COMPSAC), July 2008. [doi:10.1109/COMPSAC.2008.50](https://doi.org/10.1109/COMPSAC.2008.50) 
[^98]: Enrico Zaninotto. [From X programming to the X organisation](https://martinfowler.com/articles/zaninotto.pdf). At *XP Conference*, May 2002. Archived at [perma.cc/R9AR-QCKZ](https://perma.cc/R9AR-QCKZ)
