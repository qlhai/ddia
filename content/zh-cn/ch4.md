---
title: "4. 存储与检索"
weight: 104
breadcrumbs: false
---

<a id="ch_storage"></a>
![](/map/ch03.png)

> *人生之苦，常因命名略有偏差。命名若异，世间万物或更易解。计算机之要务，非算术运算，实乃文件系统。*
>
> [理查德·费曼](https://www.youtube.com/watch?v=EKWGGDXe5MA&t=296s)，
> *《独特思维》研讨会*（1985年）

数据库之根本，唯二事耳：存汝所予之数据，复还汝所求之数据。

[第三章](/zh-cn/ch3#ch_datamodels)论数据模型与查询语言，即汝予数据之格式，与复求数据之接口。本章则自数据库视角论之：数据库如何存储所予之数据，又如何寻回所求之数据。

应用开发者何以需知数据库内部之存储与检索？盖因虽不必自造存储引擎，然须从众引擎中择一合于应用者。欲使存储引擎适配汝之负载而高效运行，则需略知其内部运作。

尤须注意，为事务型负载（OLTP）优化之存储引擎，与为分析型负载优化者，差异甚大（此区别已于[“分析型与操作型系统”](/zh-cn/ch1#sec_introduction_analytics)中述及）。本章先论两类OLTP存储引擎：其一为*日志结构*存储引擎，写不可变数据文件；其二如*B树*，就地更新数据。此等结构既用于键值存储，亦用于次级索引。

后于[“分析型数据存储”](/zh-cn/ch4#sec_storage_analytics)将论为分析优化之存储引擎族，并于[“多维与全文索引”](/zh-cn/ch4#sec_storage_multidimensional)略述高级查询之索引，如文本检索。
## OLTP 存储与索引 {#sec_storage_oltp}
思及世间至简之数据库，以两 Bash 函数实现：
```bash
#!/bin/bash

db_set () {
  echo "$1,$2" >> database
}

db_get () {
  grep "^$1," database | sed -e "s/^$1,//" | tail -n 1
}
```
此二函数实现一键值存储。可调用 ``db_set key value``，将 ``key`` 与 ``value`` 存入数据库。键与值可为（几乎）任意内容——例如，值可为 JSON 文档。随后可调用 ``db_get key``，查找与该特定键关联之最新值并返回。

其功能有效：
```bash
$ db_set 12 '{"name":"London","attractions":["Big Ben","London Eye"]}'

$ db_set 42 '{"name":"San Francisco","attractions":["Golden Gate Bridge"]}'

$ db_get 42
{"name":"San Francisco","attractions":["Golden Gate Bridge"]}
```
存储格式甚简：文本文件，每行含一键值对，以逗号分隔（略似 CSV 文件，暂不计转义问题）。每次调用 ``db_set`` 皆向文件末尾追加。若多次更新同一键，旧值并不覆写——须于文件中查找该键之末次出现，方得最新值（此即 ``db_get`` 中 ``tail -n 1`` 之故）。
```bash
$ db_set 42 '{"name":"San Francisco","attractions":["Exploratorium"]}'

$ db_get 42
{"name":"San Francisco","attractions":["Exploratorium"]}

$ cat database
12,{"name":"London","attractions":["Big Ben","London Eye"]}
42,{"name":"San Francisco","attractions":["Golden Gate Bridge"]}
42,{"name":"San Francisco","attractions":["Exploratorium"]}

```
``db_set`` 函数虽极简，性能却颇佳，盖因追加写入文件通常效率甚高。此原理与 ``db_set`` 类同：诸多数据库内部皆使用*日志*，即一种仅追加写入的数据文件。真实数据库尚需处理更多问题（如并发写入、回收磁盘空间以防日志无限增长、崩溃恢复时处理部分写入的记录），然其基本原理无异。日志极为有用，本书后续将多次提及。

---------

> [!NOTE]
> *日志*一词常指应用日志，即应用程序输出描述运行状态的文本。本书中，*日志*取其更广义：磁盘上仅追加写入的记录序列。其不必为人可读，可为二进制格式，仅供数据库系统内部使用。

--------

反之，若数据库中记录数量庞大，``db_get`` 函数性能则极差。每次查找键时，``db_get`` 皆需从头至尾扫描整个数据库文件以搜寻该键。以算法术语论，查找成本为 *O*(*n*)：若数据库记录数 *n* 翻倍，则查找耗时亦翻倍。此非良策。

欲在数据库中高效查找特定键之值，需另寻数据结构：*索引*。本章将探讨一系列索引结构并比较其优劣；其核心思路乃以特定方式组织数据（例如按某键排序），以加速定位所需数据。若需以多种不同方式搜索同一数据，则可能需在数据的不同部分建立多个不同索引。

索引乃派生自主数据的*附加*结构。多数数据库允许增删索引，此操作不影响数据库内容，仅影响查询性能。维护附加结构会引入开销，尤以写入时为甚。就写入性能而言，单纯追加写入文件几无可能被超越，因其为最简单之写入操作。任何索引通常皆会拖慢写入，因每次写入数据时，索引亦需更新。

此乃存储系统之重要权衡：精心选择的索引可加速读取查询，然每个索引皆消耗额外磁盘空间并拖慢写入，有时影响甚巨 `[^1]`。是故，数据库通常不默认索引所有内容，而需由应用开发者或数据库管理员，依据对应用典型查询模式的了解，手动选择索引。如此，可择取为应用带来最大收益之索引，同时避免引入不必要的写入开销。
### 日志结构存储 {#sec_storage_log_structured}
首先，假设你希望继续将数据存储在由 `db_set` 写入的仅追加文件中，仅欲加速读取。  
一法可行：在内存中维护一个哈希映射，其中每个键映射至文件中可找到该键最新值的字节偏移量，如[图 4-1](/zh-cn/ch4#fig_storage_csv_hash_index)所示。
{{< figure src="/fig/ddia_0401.png" id="fig_storage_csv_hash_index" caption="Figure 4-1. Storing a log of key-value pairs in a CSV-like format, indexed with an in-memory hash map." class="w-full my-4" >}}
每当向文件追加新的键值对时，亦需更新哈希映射，以记录所写入数据的偏移量。欲查找某值时，先借哈希映射定位其在日志文件中的偏移，随即寻址至该处并读取数值。若该部分数据已存于文件系统缓存，则读取操作无需任何磁盘 I/O。

此法虽快，然仍存数弊：

* 已覆写之旧日志条目所占磁盘空间永不释放；若持续写入数据库，恐致磁盘耗尽。
* 哈希映射未持久化，故重启数据库时须重建之——例如，需扫描整个日志文件以寻各键之最新字节偏移。若数据量庞大，重启将甚缓。
* 哈希表须常驻内存。原则上，固可于磁盘维护哈希表，然磁盘哈希表性能难臻佳境。其需大量随机访问 I/O，满载时扩容成本高昂，且哈希冲突之处理逻辑繁复。
* 范围查询效率低下。例如，欲扫描 ``10000`` 至 ``19999`` 间所有键，殊为不易——须逐一于哈希映射中查找各键。
#### SSTable 文件格式 {#the-sstable-file-format}
实践中，哈希表较少用于数据库索引，更常见的是将数据存储在*按键排序*的结构中。

此类结构之一为*排序字符串表*，简称*SSTable*，如[图4-2](/zh-cn/ch4#fig_storage_sstable_index)所示。此文件格式亦存储键值对，但确保其按键排序，且每个键在文件中仅出现一次。
{{< figure src="/fig/ddia_0402.png" id="fig_storage_sstable_index" caption="Figure 4-2. An SSTable with a sparse index, allowing queries to jump to the right block." class="w-full my-4" >}}
今无需将所有键常驻内存：可将 SSTable 内的键值对分组为若干千字节大小的*块*，再将每块的首键存入索引。此类仅存储部分键的索引，谓之*稀疏索引*。该索引存于 SSTable 的独立区域，例如采用不可变 B 树、字典树或其他支持快速查询特定键 [^4] 的数据结构。

以[图 4-2](/zh-cn/ch4#fig_storage_sstable_index)为例，某块首键为 `handbag`，下一块首键为 `handsome`。今欲寻键 `handiwork`，其未现于稀疏索引。因键序已知，可断 `handiwork` 必位于 `handbag` 与 `handsome` 之间。故可定位至 `handbag` 的偏移量，自此扫描文件，直至寻得 `handiwork`（若键不在文件中则无果）。数千字节之块，扫描甚速。

另者，每记录块皆可压缩（如[图 4-2](/zh-cn/ch4#fig_storage_sstable_index)阴影区所示）。压缩既可节省磁盘空间，亦能降低 I/O 带宽占用，惟稍增 CPU 耗时耳。
#### 构建与合并 SSTable {#constructing-and-merging-sstables}
SSTable 文件格式于读取优于仅追加日志，然其令写入更为困难。不可仅于末尾追加，否则文件将失序（除非键值恰按升序写入）。若每次于中间某处插入键值皆须重写整个 SSTable，则写入成本将过高。

此问题可借*日志结构化*之法解决，此法乃仅追加日志与有序文件之混合：

1.  写入到来时，将其添入内存中有序映射数据结构，如红黑树、跳表或字典树。此类数据结构可任意顺序插入键值、高效查找，并按序读回。此内存数据结构称为*memtable*。
2.  当 memtable 大小超某阈值（通常为数兆字节），即将其按序写入磁盘为 SSTable 文件。此新 SSTable 文件称为数据库之最新*段*，与旧段并存为独立文件。每段有其内容之独立索引。新段写入磁盘时，数据库可继续写入新 memtable 实例，SSTable 写入完成后，旧 memtable 之内存即被释放。
3.  为读取某键值，先于 memtable 及最新磁盘段中查找。若无，则查次旧段，依此类推，直至找到键值或达最旧段。若键值未现于任何段中，则数据库中不存在。
4.  不时于后台运行合并与压缩进程，以合并段文件并丢弃被覆写或删除之值。

段合并运作类似*归并排序*算法。其过程示于[图 4-3](/zh-cn/ch4#fig_storage_sstable_merging)：并行读取输入文件，查看各文件之首键，将最低键（依排序顺序）复制至输出文件，重复此过程。若同一键值出现于多个输入文件，仅保留最新值。此生成新合并段文件，亦按键排序，每键一值，且因可逐键迭代 SSTables，故内存使用极低。
{{< figure src="/fig/ddia_0403.png" id="fig_storage_sstable_merging" caption="Figure 4-3. Merging several SSTable segments, retaining only the most recent value for each key." class="w-full my-4" >}}
为确保内存表（memtable）数据在数据库崩溃时不丢失，存储引擎会在磁盘上维护一个独立的日志，每次写入均立即追加至此日志。此日志不按键排序，然无妨，因其唯一用途乃在崩溃后恢复内存表。每当内存表被写入 SSTable（Sorted String Table，有序字符串表）后，日志对应部分即可丢弃。

若欲删除键及其关联值，须向数据文件追加一条特殊删除记录，称为 *tombstone*（墓碑标记）。当日志段合并时，墓碑标记告知合并进程丢弃该已删除键的所有先前值。一旦墓碑标记被合并至最旧段中，即可弃之。

此处所述算法，实为 RocksDB [^7]、Cassandra、Scylla 及 HBase [^8] 所用之核心，诸系统皆受 Google Bigtable 论文 [^9] 启发（该论文首提 *SSTable* 与 *memtable* 二词）。

此算法最初于 1996 年以 *Log-Structured Merge-Tree*（日志结构合并树）或 *LSM-Tree* [^10] 之名发表，其基础乃早期日志结构文件系统 [^11] 之研究。故基于合并与压缩有序文件原理之存储引擎，常被称为 *LSM 存储引擎*。

于 LSM 存储引擎中，段文件（segment file）一次性写入（或通过写出内存表，或通过合并现有段），此后即不可变。段之合并与压缩可在后台线程执行，期间仍可使用旧段文件服务读取请求。合并完成后，读取请求切换至使用新合并段，旧段文件即可删除。

段文件未必存储于本地磁盘：其亦适于写入对象存储。SlateDB 与 Delta Lake [^12] 即采此法。

段文件不可变亦简化崩溃恢复：若在写出内存表或合并段时发生崩溃，数据库仅需删除未完成之 SSTable 并重新开始。若写入记录中途崩溃或磁盘已满，持久化写入内存表之日志可能包含不完整记录；通常通过在日志中包含校验和以检测之，并丢弃损坏或不完整之日志条目。关于持久性与崩溃恢复之详述，见[第八章](/zh-cn/ch8#ch_transactions)。
<a id="sec_storage_bloom_filter"></a>

#### 布隆过滤器 {#bloom-filters}
采用 LSM 存储时，读取久未更新或不存在的键可能较慢，因存储引擎需检查多个段文件。为加速此类读取，LSM 存储引擎常在每个段中包含一个*布隆过滤器*（Bloom filter），其为检查特定键是否出现在特定 SSTable 提供快速但近似的方法。

[图 4-4](/zh-cn/ch4#fig_storage_bloom) 展示了一个包含两个键和 16 位的布隆过滤器示例（实际中会包含更多键和位）。对于 SSTable 中的每个键，我们计算一个哈希函数，生成一组数字，这些数字随后被解释为位数组的索引。我们将对应这些索引的位设为 1，其余位保持为 0。例如，键 ``handbag`` 哈希得到数字 (2, 9, 4)，因此我们将第 2、9、4 位设为 1。该位图随后与键的稀疏索引一同存储为 SSTable 的一部分。这占用少量额外空间，但布隆过滤器通常比 SSTable 的其余部分小得多。
{{< figure src="/fig/ddia_0404.png" id="fig_storage_bloom" caption="Figure 4-4. A Bloom filter provides a fast, probabilistic check whether a particular key exists in a particular SSTable." class="w-full my-4" >}}
欲知某键是否存于 SSTable 中，可先计算该键之哈希值（与前同法），再查验对应位。例如，[图 4-4](/zh-cn/ch4#fig_storage_bloom) 中查询键 ``handheld``，其哈希得 (6, 11, 2)。三者中仅第二位为 1，余二为 0。此查验可借 CPU 通用之位运算极速完成。

若至少一位为 0，则可断定该键必不在 SSTable 中。若查询位皆为 1，则键很可能在 SSTable 中，然亦可能因巧合，此诸位皆为他键所置。此看似键在而实不在之情形，谓之 *假阳性*。

假阳性之概率，取决于键数、每键所置位数及布隆过滤器总位数。可用在线计算工具，为应用 `[^15]` 求得合宜参数。经验而言，若欲得 1% 假阳性概率，需为 SSTable 中每键分配约 10 位布隆过滤器空间；每键增 5 位，则概率降十倍。

于 LSM 存储引擎中，假阳性并无大碍：

* 若布隆过滤器示键 *不在*，则可安全跳过该 SSTable，因确知其中无此键。
* 若布隆过滤器示键 *在*，则须查稀疏索引并解码键值对区块，以验键是否真在。若为假阳性，仅稍作无用之功，无害大局——续查次旧段即可。
#### 压缩策略 {#sec_storage_lsm_compaction}
LSM存储之关键，在于其如何择时进行压实（compaction），以及选取哪些SSTable参与压实。诸多基于LSM的存储系统允许配置压实策略，常见者有二：

**分层压实（Size-tiered compaction）**
: 新而小的SSTable逐次并入旧而大的SSTable。含旧数据的SSTable可变得极大，合并时需大量临时磁盘空间。此策略之利，在于能应对极高写入吞吐。

**层级压实（Leveled compaction）**
: 键范围被分割为较小的SSTable，旧数据移至独立的“层级”，使压实过程更渐进，且较分层压实占用更少磁盘空间。此策略对读取更高效，因存储引擎需检查的SSTable更少，以确认是否含有所寻键。

概言之，若写入为主、读取甚少，则分层压实性能更佳；若负载以读取为主，则层级压实更优。若频繁写入少量键，而极少写入大量键，则层级压实亦具优势。

纵有诸多精微之处，LSM树之基本理念——维护一系列在后台合并的SSTable——仍简明而有效。其性能特征，将于[“B树与LSM树之比较”](/zh-cn/ch4#sec_storage_btree_lsm_comparison)中详述。
<a id="sidebar_embedded"></a>
> [!TIP] 嵌入式存储引擎

诸多数据库以服务形式运行，通过网络接收查询。然亦有*嵌入式*数据库，不提供网络 API。此类数据库实为库文件，运行于应用进程之内，通常读写本地磁盘文件，通过常规函数调用与之交互。嵌入式存储引擎之例，包括 RocksDB、SQLite、LMDB、DuckDB 及 KùzuDB。

嵌入式数据库于移动应用中极为常见，用以存储本地用户数据。于后端场景，若数据规模可容于单机，且并发事务不多，亦属适宜之选。例如，在多租户系统中，若各租户规模甚小且彼此完全隔离（即无需执行跨租户数据之联合查询），则可考虑为每个租户配置独立之嵌入式数据库实例。

本章所述之存储与检索方法，于嵌入式及客户端-服务器数据库皆适用。于[第六章](/zh-cn/ch6#ch_replication)与[第七章](/zh-cn/ch7#ch_sharding)，吾等将探讨跨多机扩展数据库之技术。
### B 树 {#sec_storage_b_trees}
日志结构方法虽流行，然非键值存储唯一形态。按键读写数据库记录，应用最广之结构乃 *B 树*。

B 树于 1970 年问世，未及十年即被誉为“无处不在”，其经受时间考验，至今仍为几乎所有关系型数据库之标准索引实现，诸多非关系型数据库亦采用之。

与 SSTable 相似，B 树亦按键排序存储键值对，故能高效支持键值查找与范围查询。然相似之处仅止于此：B 树之设计理念迥异。

前文所述日志结构索引将数据库分解为可变大小之 *段*，通常为数兆字节或更大，段一经写入即不可变。反之，B 树将数据库分解为固定大小之 *块* 或 *页*，并可原地覆写页面。传统页面大小为 4 KiB，然 PostgreSQL 现用 8 KiB，MySQL 默认则为 16 KiB。

每页皆可通过页号标识，此机制允许一页引用另一页——类似指针，然位于磁盘而非内存。若所有页面存储于同一文件，将页号乘以页面大小，即可得该页在文件中之字节偏移。吾等可利用此类页面引用构建页面树，如[图 4-5](/zh-cn/ch4#fig_storage_b_tree)所示。
{{< figure src="/fig/ddia_0405.png" id="fig_storage_b_tree" caption="Figure 4-5. Looking up the key 251 using a B-tree index. From the root page we first follow the reference to the page for keys 200–300, then the page for keys 250–270." class="w-full my-4" >}}
一页被指定为 B 树的*根*；每当你想在索引中查找一个键时，便从此处开始。该页包含若干键及指向子页的引用。每个子页负责一个连续的键范围，引用之间的键则指示这些范围之间的边界所在。（此结构有时称为 B+ 树，但我们无需将其与其他 B 树变体区分。）

于[图 4-5](/zh-cn/ch4#fig_storage_b_tree) 示例中，我们正查找键 251，故知需遵循边界 200 与 300 之间的页引用。此将引至一个外观相似的页，该页进一步将 200–300 范围分解为子范围。最终，我们将抵达一个包含单个键的页（即*叶页*），该页或直接内联存储每个键的值，或包含指向可找到值的页的引用。

B 树中一页内指向子页的引用数量称为*分支因子*。例如，在[图 4-5](/zh-cn/ch4#fig_storage_b_tree) 中，分支因子为六。实践中，分支因子取决于存储页引用及范围边界所需的空间量，但通常为数百。

若欲更新 B 树中现有键的值，需查找包含该键的叶页，并在磁盘上以包含新值的版本覆写该页。若欲添加新键，需找到其范围涵盖新键的页，并将新键添加至该页。若页中无足够空闲空间容纳新键，则该页将被拆分为两个半满的页，并更新父页以反映键范围的新划分。
{{< figure src="/fig/ddia_0406.png" id="fig_storage_b_tree_split" caption="Figure 4-6. Growing a B-tree by splitting a page on the boundary key 337. The parent page is updated to reference both children." class="w-full my-4" >}}
于[图4-6](/zh-cn/ch4#fig_storage_b_tree_split)之例，欲插入键值334，然333–345范围之页已满。故将其拆分为两页：一页存333–337范围（含新键），另一页存337–344范围。亦须更新父页，使其包含对两子页之引用，并以337为界值分隔。若父页无足够空间容纳新引用，则亦需拆分，且拆分可逐级上溯，直至树根。根页拆分时，则于其上新建根页。删除键值（或需合并节点）则更为复杂。

此算法确保树恒持*平衡*：含*n*个键之B树，其深度恒为*O*(log *n*)。多数数据库可容纳于三至四层之B树，故寻页时无需遍历过多页引用。（以4 KiB页大小、分支因子500计，四层树可存储高达250 TB数据。）
#### 实现 B 树可靠性 {#sec_storage_btree_wal}
B 树的基本写入操作，乃以新数据覆写磁盘页面。其前提在于，覆写不改变页面位置；即覆写后，所有指向该页的引用仍保持有效。此与日志结构索引（如 LSM 树）截然不同：后者仅追加文件（最终删除废弃文件），从不就地修改文件。

一次性覆写多个页面（如页面分裂时）乃危险操作：若数据库在仅部分页面写入后崩溃，则树结构将损坏（例如，可能出现*孤儿*页面，即无父节点之子页）。若硬件无法原子性写入整个页面，亦可能导致*部分写入页面*（此即所谓*撕裂页*）。

为使数据库具备崩溃恢复能力，B 树实现通常会在磁盘上包含一额外数据结构：*预写日志*（WAL）。此为一仅追加文件，所有 B 树修改必须先写入此日志，方能应用于树之页面本身。数据库崩溃后重启时，即用此日志将 B 树恢复至一致状态。在文件系统中，等效机制称为*日志记录*。

为提升性能，B 树实现通常不立即将每个修改页面写入磁盘，而是先将 B 树页面在内存中缓冲一段时间。预写日志遂可确保数据在崩溃时不丢失：只要数据已写入 WAL，并通过 `fsync` 系统调用刷入磁盘，数据即具持久性，因数据库崩溃后仍能恢复之。
#### B-树变体 {#b-tree-variants}
B树问世已久，故多年间衍生诸多变体。略举数例：

* 部分数据库（如LMDB）采用写时复制方案，而非覆写页面并依赖WAL实现崩溃恢复。修改之页面写入新位置，并创建树中父页之新版本以指向新位置。此法亦有助于并发控制，详见[“快照隔离与可重复读”](/zh-cn/ch8#sec_transactions_snapshot_isolation)。

* 可通过不存储完整键值而仅保留其缩写以节省页面空间。尤以树内部页面为甚：键仅需提供足够信息以划定键值范围边界。单页容纳更多键可提升树之分支因子，从而减少层级。

* 为加速按序扫描键值范围，部分B树实现尝试将叶页按磁盘顺序连续排列，以减少磁盘寻道次数。然随树之生长，维持此顺序颇为困难。

* 树中添加额外指针。例如，各叶页可增设指向左右兄弟页之引用，从而实现顺序扫描键值而无需回溯至父页。
### B 树与 LSM 树之比较 {#sec_storage_btree_lsm_comparison}
经验而言，LSM 树更适用于写入密集的应用，而 B 树在读取方面通常更快。  
然基准测试常对工作负载细节敏感。欲作有效比较，需以特定负载测试系统。  
且 LSM 与 B 树并非严格二选一：存储引擎有时融合二者特性，例如以多个 B 树并以 LSM 风格合并之。  
本节将简述评估存储引擎性能时值得考虑的若干要点。
#### 读取性能 {#read-performance}
于 B 树中，键值查找需读取树每层之一页。因层数通常甚少，故 B 树读取一般迅速，性能可预测。于 LSM 存储引擎中，读取常须检查压缩不同阶段之多个 SSTable，然布隆过滤器可助减少实际磁盘 I/O 操作之数。二者皆可表现良好，孰快取决于存储引擎之细节与工作负载。

范围查询于 B 树简单且迅速，盖可利用树之有序结构。于 LSM 存储，范围查询亦可利用 SSTable 排序，然须并行扫描所有段并合并结果。布隆过滤器于范围查询无助（因需计算范围内所有可能键之哈希，此不切实际），故 LSM 方法中范围查询较点查询昂贵。

高写入吞吐若致内存表填满，可引发日志结构存储引擎之延迟尖峰。此发生于数据未能足够快写入磁盘时，或因压缩进程未能跟上写入之故。诸多存储引擎（含 RocksDB）于此情形实施*反压*：暂停所有读写，直至内存表写入磁盘。

至于读取吞吐，现代 SSD（尤以 NVMe 为甚）可并行执行多个独立读取请求。LSM 树与 B 树皆能提供高读取吞吐，然存储引擎须精心设计，方得利用此并行性。
#### 顺序写入与随机写入 {#sidebar_sequential}
使用 B 树时，若应用写入的键分散于整个键空间，则磁盘操作亦随之随机分散，因存储引擎需覆写的页可能位于磁盘任意位置。反之，日志结构存储引擎一次写入整个段文件（或写出内存表，或压缩现有段），其大小远大于 B 树中的单页。

此类分散的小规模写入模式（见于 B 树）称为**随机写入**，而较少的大规模写入模式（见于 LSM 树）称为**顺序写入**。磁盘的顺序写入吞吐量通常高于随机写入，故日志结构存储引擎在相同硬件上通常能处理更高的写入吞吐量。此差异在机械硬盘（HDD）上尤为显著；于现今多数数据库使用的固态硬盘（SSD）上，差异虽小，仍可察觉（参见[“SSD 上的顺序写入与随机写入”](/zh-cn/ch4#sidebar_sequential)）。

--------

> [!TIP] SSD 上的顺序写入与随机写入

于机械硬盘（HDD），顺序写入远快于随机写入：随机写入需机械移动磁头至新位置，并等待盘片正确部分转至磁头下方，耗时数毫秒——于计算时间尺度堪称永恒。然 SSD（固态硬盘，包括 NVMe，即连接至 PCI Express 总线的闪存）现已于多数用例超越 HDD，且不受此类机械限制所困。

尽管如此，SSD 的顺序写入吞吐量亦高于随机写入。其因在于，闪存可逐页（通常 4 KiB）读取或写入，但仅能逐块（通常 512 KiB）擦除。块中部分页或含有效数据，其余或含不再需要之数据。擦除块前，控制器须先将含有效数据之页移至他块；此过程称为**垃圾回收**（GC）。

顺序写入负载一次写入较大数据块，故整个 512 KiB 块很可能属于单一文件；当该文件后续被删除时，整个块可被擦除而无需执行任何 GC。反之，随机写入负载下，块更可能混杂有效与无效数据页，故 GC 在块可被擦除前须执行更多工作。

GC 消耗的写入带宽遂不可用于应用。此外，GC 执行的额外写入会加剧闪存磨损；故随机写入较顺序写入更快磨损驱动器。
#### 写入放大 {#write-amplification}
无论何种存储引擎，应用的一次写入请求都会转化为底层磁盘的多次 I/O 操作。对于 LSM 树，一个值首先被写入日志以确保持久性，随后在内存表写入磁盘时再次写入，并在每次键值对参与合并时再次写入。（若值远大于键，可将值与键分开存储，并仅对包含键及值引用的 SSTable 执行合并，以降低此开销。）

B 树索引则必须将每份数据至少写入两次：一次至预写日志，一次至树页面本身。此外，有时即使页面中仅少数字节发生更改，也需写出整个页面，以确保崩溃或断电后 B 树能正确恢复。

若以某工作负载下写入磁盘的总字节数，除以仅写入无索引的追加日志所需字节数，所得即为*写入放大*。（有时写入放大以 I/O 操作数而非字节数定义。）在写入密集型应用中，瓶颈可能在于数据库向磁盘写入的速率。此时，写入放大越高，在可用磁盘带宽内每秒能处理的写入操作越少。

写入放大在 LSM 树与 B 树中均存在。孰优孰劣取决于多种因素，如键与值的长度、覆盖现有键与插入新键的频率等。对于典型工作负载，LSM 树的写入放大往往较低，因其无需写入整个页面，且可压缩 SSTable 的数据块。此亦为 LSM 存储引擎更适配写入密集型工作负载的另一因素。

除影响吞吐量外，写入放大亦关乎 SSD 的磨损：写入放大较低的存储引擎对 SSD 的磨损更慢。

测量存储引擎的写入吞吐量时，须运行实验足够长时间，以使写入放大的影响显现。向空 LSM 树写入时，尚无合并操作，故全部磁盘带宽可用于新写入。随着数据库增长，新写入需与合并操作共享磁盘带宽。
#### 磁盘空间使用情况 {#disk-space-usage}
B树随时间推移可能产生*碎片*：例如，若大量键被删除，数据库文件可能包含许多不再被B树使用的页面。后续对B树的添加操作可使用这些空闲页面，但因它们位于文件中间，难以返还给操作系统，故仍占用文件系统空间。因此，数据库需后台进程移动页面以优化布局，如PostgreSQL中的vacuum进程。

碎片问题在LSM树中较轻，因压缩过程会定期重写数据文件，且SSTable无含未使用空间的页面。此外，键值对块在SSTable中更易压缩，故常比B树产生更小的磁盘文件。被覆写的键值在压缩移除前仍占用空间，但使用分层压缩时此开销较低。大小分层压缩（见[“压缩策略”](/zh-cn/ch4#sec_storage_lsm_compaction)）占用更多磁盘空间，尤其在压缩期间临时占用较多。

当需删除某些数据并确信其已删除时（如为遵守数据保护法规），磁盘上存在数据多副本亦成问题。例如，在多数LSM存储引擎中，已删除记录可能仍存在于较高层级，直至代表删除的墓碑标记通过所有压缩层级传播，此过程可能耗时较长。专用存储引擎设计可加速删除传播。

反之，若需在特定时间点获取数据库快照（如用于备份或创建测试副本），SSTable段文件的不可变性颇具优势：可写出内存表并记录该时间点存在的段文件。只要不删除快照所含文件，即无需实际复制。在页面可覆写的B树中，高效获取此类快照更为困难。
### 多列索引与二级索引 {#sec_storage_index_multicolumn}
迄今所论，皆为键值索引，其类于关系模型中之*主键*索引。主键可唯一标识关系表中一行、文档数据库中一文档，或图数据库中一顶点。库中其余记录，可借主键（或ID）引用该行/文档/顶点，索引即用以解析此类引用。

*二级索引*亦极常见。于关系数据库中，可借 `CREATE INDEX` 命令于同一表上创建多个二级索引，使能按主键外之列进行检索。例如，于[第三章](/zh-cn/ch3#ch_datamodels)之[图3-1](/zh-cn/ch3#fig_obama_relational)中，极可能于 `user_id` 列上建有二级索引，以便在各表中找出属于同一用户之所有行。

二级索引可轻易由键值索引构建而成。主要区别在于：二级索引中，被索引之值未必唯一；即同一索引条目下，或有多行（文档、顶点）。此问题可借两种方式解决：或将索引中每一值设为匹配行标识符之列表（如全文索引中之倒排列表），或通过附加行标识符使每一条目唯一。支持就地更新之存储引擎（如B树）与日志结构存储，皆可用于实现索引。
#### 在索引中存储值 {#sec_storage_index_heap}
索引之键，乃查询所据；其值则分三类：

* **聚簇索引**：若实际数据（行、文档、顶点）直接存于索引结构内，则称聚簇索引。  
  例：MySQL InnoDB 存储引擎中，表之主键恒为聚簇索引；SQL Server 中，每表可指定一聚簇索引。
* **引用索引**：值可为实际数据之引用：或为对应行之主键（InnoDB 之二级索引即如此），或为磁盘位置之直接指针。  
  后者中，行存储之处称为**堆文件**，数据存储无序（可仅追加，亦可记录已删行之位置以供后续覆写）。  
  例：Postgres 即采用堆文件方案。
* **覆盖索引**：此乃折中之策，亦称**含包含列之索引**。  
  除在堆文件或主键聚簇索引中存储整行外，索引内亦存表之**部分列**。  
  故某些查询可仅凭索引应答，无需解析主键或查找堆文件（此时谓索引**覆盖**查询）。  
  此举可加速部分查询，然数据重复致索引占用更多磁盘空间，且拖慢写入。

上述索引仅映射单键至单值。若需同时查询表之多列（或文档之多字段），参见[“多维与全文索引”](/zh-cn/ch4#sec_storage_multidimensional)。

**更新值而不改键时**，若新值不大于旧值，堆文件方案可原地覆写记录。  
若新值更大，则情形复杂：记录或需移至堆中新位置以获足够空间。  
此时，或需更新所有索引以指向记录之新堆位置，或在旧堆位置留**转发指针**。
### 内存存储 {#sec_storage_inmemory}
本章迄今所论之数据结构，皆旨在应对磁盘之局限。相较于主内存，磁盘处理颇为不便。无论磁盘或固态硬盘，若欲读写性能优良，数据布局须精心设计。然吾辈容忍此不便，盖因磁盘有二大优势：其一，持久性（断电后内容不丢失）；其二，每吉字节成本低于内存。

随着内存价格下降，成本优势渐被侵蚀。诸多数据集本非庞大，完全存于内存之中，或跨多机分布，皆属可行。此遂催生*内存数据库*之发展。

部分内存键值存储（如 Memcached）仅用于缓存，机器重启时数据丢失亦可接受。然其他内存数据库则追求持久性，其实现方式包括：采用特殊硬件（如电池供电内存）、将变更日志写入磁盘、定期写入快照至磁盘，或将内存状态复制至其他机器。

内存数据库重启时，需从磁盘或通过网络自副本重载状态（特殊硬件除外）。纵有磁盘写入，仍属内存数据库，盖因磁盘仅用作追加日志以保持久性，而读取则完全由内存响应。写入磁盘亦具运维优势：磁盘文件易于备份、检查，并可由外部工具分析。

诸如 VoltDB、SingleStore 及 Oracle TimesTen 等产品，皆为关系模型之内存数据库。厂商宣称，通过消除管理磁盘数据结构之开销，可显著提升性能 [^46] [^47]。RAMCloud 乃开源内存键值存储，具持久性（对内存及磁盘数据皆采用日志结构方法） [^48]。

Redis 与 Couchbase 通过异步写入磁盘，提供较弱之持久性。

反直觉之处在于，内存数据库之性能优势，非因无需从磁盘读取。即便基于磁盘之存储引擎，若内存充足，亦可能无需读盘，盖因操作系统自会将近期所用磁盘块缓存于内存。其所以更快，实因可避免将内存数据结构编码为可写入磁盘形式之开销 [^49]。

除性能外，内存数据库另一有趣领域，在于提供难以用基于磁盘之索引实现的数据模型。例如，Redis 为多种数据结构（如优先队列与集合）提供类数据库接口。因其将所有数据存于内存，实现相对简单。
## 数据分析之存储 {#sec_storage_analytics}
数据仓库之数据模型，多为关系型，盖因 SQL 适于分析查询。诸多图形化数据分析工具，皆可生成 SQL 查询、可视化结果，并供分析师探索数据（通过*下钻*、*切片与切块*等操作）。

观其表，数据仓库与关系型 OLTP 数据库似无二致，皆具 SQL 查询接口。然其内部机制迥异，盖因二者为迥异之查询模式而优化。今之数据库厂商，多专攻事务处理或分析负载，鲜有兼善者。

亦有数据库，如 Microsoft SQL Server、SAP HANA 与 SingleStore，于同一产品中兼支事务处理与数据仓库。然此类混合事务与分析处理（HTAP）数据库（见[“数据仓库”](/zh-cn/ch1#sec_introduction_dwh)），其存储与查询引擎渐趋分离，唯借共通之 SQL 接口 [^50] [^51] [^52] [^53] 以存取耳。
### 云数据仓库 {#sec_cloud_data_warehouses}
Teradata、Vertica、SAP HANA 等数据仓库供应商既销售商业许可的本地部署仓库，也提供基于云的解决方案。然随着众多客户迁移至云端，Google Cloud BigQuery、Amazon Redshift、Snowflake 等新型云数据仓库亦获广泛采用。与传统数据仓库不同，云数据仓库充分利用了可扩展的云基础设施，如对象存储与无服务器计算平台。

云数据仓库往往能更好地与其他云服务集成，且更具弹性。例如，诸多云仓库支持自动日志摄取，并能轻松与数据处理框架（如 Google Cloud Dataflow 或 Amazon Web Services Kinesis）集成。此类仓库亦因将查询计算与存储层解耦而更具弹性。数据持久化于对象存储而非本地磁盘，使得独立调整存储容量与查询计算资源变得简便，此前于[“云原生系统架构”](/zh-cn/ch1#sec_introduction_cloud_native)中已有述及。

Apache Hive、Trino、Apache Spark 等开源数据仓库亦随云演进。随着分析数据存储转向对象存储上的数据湖，开源仓库已开始解耦其架构。以下组件，先前集成于单一系统（如 Apache Hive）中，现常作为独立组件实现：

**查询引擎**
: 如 Trino、Apache DataFusion、Presto 等查询引擎解析 SQL 查询，将其优化为执行计划，并针对数据执行。执行通常需要并行、分布式的数据处理任务。部分查询引擎提供内置任务执行功能，其他则选择使用第三方执行框架，如 Apache Spark 或 Apache Flink。

**存储格式**
: 存储格式决定了表中行如何编码为文件中的字节，此类文件通常存储于对象存储或分布式文件系统中。查询引擎及其他使用数据湖的应用程序均可访问此数据。此类存储格式示例包括 Parquet、ORC、Lance 或 Nimble，后续章节将详述。

**表格式**
: 以 Apache Parquet 及类似存储格式写入的文件，一旦写入通常不可变。为支持行插入与删除，需使用表格式，如 Apache Iceberg 或 Databricks Delta 格式。表格式指定了文件格式，以定义哪些文件构成表及其模式。此类格式亦提供高级功能，如时间旅行（查询表在历史某时刻的状态）、垃圾回收，乃至事务支持。

**数据目录**
: 正如表格式定义构成表的文件，数据目录定义构成数据库的表。目录用于创建、重命名及删除表。与存储及表格式不同，如 Snowflake Polaris 与 Databricks Unity Catalog 等数据目录通常作为独立服务运行，可通过 REST 接口查询。Apache Iceberg 亦提供目录，可运行于客户端内或作为独立进程。查询引擎在读写表时使用目录信息。传统上，目录与查询引擎集成，然解耦二者使得数据发现与数据治理系统（见[“数据系统、法律与社会”](/zh-cn/ch1#sec_introduction_compliance)）亦能访问目录元数据。
### 列式存储 {#sec_storage_column}
如[《星型与雪花型：分析型数据模式》](/zh-cn/ch3#sec_datamodels_analytics)所述，数据仓库通常采用关系模式，其核心为包含维度表外键引用的大型事实表。若事实表数据达万亿行、PB级，高效存储与查询即成难题。维度表通常较小（百万行），故本节专论事实表存储。

事实表虽常逾百列，然典型数据仓库查询仅同时访问其中四五列（分析场景鲜需`SELECT *`查询）。以[例4-1](/zh-cn/ch4#fig_storage_analytics_query)之查询为例：其需扫描大量行（2024年所有购买水果或糖果记录），但仅需访问`fact_sales`表三列：`date_key`、`product_sk`、`quantity`。其余列皆被忽略。
{{< figure id="fig_storage_analytics_query" title="Example 4-1. Analyzing whether people are more inclined to buy fresh fruit or candy, depending on the day of the week" class="w-full my-4" >}}

```sql
SELECT
    dim_date.weekday, dim_product.category,
    SUM(fact_sales.quantity) AS quantity_sold
FROM fact_sales
    JOIN dim_date ON fact_sales.date_key = dim_date.date_key
    JOIN dim_product ON fact_sales.product_sk = dim_product.product_sk
WHERE
    dim_date.year = 2024 AND
    dim_product.category IN ('Fresh fruit', 'Candy')
GROUP BY
    dim_date.weekday, dim_product.category;
```
如何高效执行此查询？

多数 OLTP 数据库中，存储采用*行导向*布局：表中单行所有值相邻存储。文档数据库亦类似：整个文档通常存储为连续字节序列。此点可见于[图 4-1](/zh-cn/ch4#fig_storage_csv_hash_index) 的 CSV 示例。

处理如[示例 4-1](/zh-cn/ch4#fig_storage_analytics_query) 的查询时，或可在 `fact_sales.date_key` 与 `fact_sales.product_sk` 上建立索引，以指示存储引擎查找特定日期或特定产品的所有销售记录。然则，行导向存储引擎仍需从磁盘加载所有相关行（每行含逾百属性）至内存，解析后过滤不符合条件者。此过程耗时甚久。

*列导向*（或称*列式*）存储之原理甚简：不将单行所有值集中存储，而将每*列*所有值集中存储 [^56]。若每列独立存储，查询仅需读取并解析该查询所用之列，可省大量工作。[图 4-7](/zh-cn/ch4#fig_column_store) 以[图 3-5](/zh-cn/ch3#fig_dwh_schema) 事实表之扩展版演示此原理。

--------

> [!NOTE]
> 列存储于关系数据模型中最易理解，然其同样适用于非关系数据。例如，Parquet [^57] 为一种列式存储格式，支持文档数据模型，基于 Google 的 Dremel [^58]，采用称为*切分*或*条带化* [^59] 之技术。

--------
{{< figure src="/fig/ddia_0407.png" id="fig_column_store" caption="Figure 4-7. Storing relational data by column, rather than by row." class="w-full my-4" >}}
列式存储布局依赖于各列以相同顺序存储行数据。  
故若需重组整行，可取各列之第二十三项，合为表中第二十三行。

实则列式存储引擎并非将整列（或含万亿行）一次存储。  
其将表拆分为数千至数百万行之数据块，每块内各列数值分别存储。  
因多数查询限定时日范围，常使每块包含特定时间戳范围之行。  
查询时仅需加载所需列于符合日期范围之块中。

今时分析型数据库几皆用列式存储，  
自大规模云数据仓库如 Snowflake，  
至单节点嵌入式数据库如 DuckDB，  
及产品分析系统如 Pinot 与 Druid，皆然。  
其亦用于存储格式如 Parquet、ORC、Lance、Nimble，  
与内存分析格式如 Apache Arrow 及 Pandas/NumPy。  
部分时序数据库，如 InfluxDB IOx 与 TimescaleDB，亦基于列式存储。
#### 列压缩 {#sec_storage_column_compression}
除仅从磁盘加载查询所需列外，尚可通过压缩数据进一步降低磁盘吞吐与网络带宽之需求。幸而列式存储常与压缩相得益彰。

观[图 4-7](/zh-cn/ch4#fig_column_store)中各列数值序列：其模式常高度重复，此乃压缩之良兆。依列中数据之异，可采用不同压缩技术。数据仓库中尤有效者，乃*位图编码*，见[图 4-8](/zh-cn/ch4#fig_bitmap_index)所示。
{{< figure src="/fig/ddia_0408.png" id="fig_bitmap_index" caption="Figure 4-8. Compressed, bitmap-indexed storage of a single column." class="w-full my-4" >}}
通常，一列中不同值的数量远小于行数（例如，零售商可能有数十亿笔销售交易，但仅有十万种不同的商品）。由此，可将具有 *n* 个不同值的列转换为 *n* 个独立的位图：每个不同值对应一个位图，每行对应一个位。若该行具有该值，则位为 1；否则为 0。

一种方案是每行使用一个位来存储这些位图。然而，这些位图通常包含大量零（我们称其为*稀疏*位图）。此时，位图可进一步进行游程编码：计算连续零或一的个数并存储该数值，如[图 4-8](/zh-cn/ch4#fig_bitmap_index) 底部所示。诸如 *roaring bitmaps* 等技术会在两种位图表示之间切换，采用最紧凑者。这可使列的编码极为高效。

此类位图索引非常适合数据仓库中常见的查询类型。例如：

**按产品类别筛选**
: 加载 **产品类别** 为 **新鲜农产品**、**乳制品** 和 **肉类** 的三个位图，并计算三者的按位 *OR* 运算，此操作可高效完成。

**组合多列条件**
: 加载 **产品类别 = 新鲜农产品** 和 **商店编号 = 123** 的位图，并计算按位 *AND*。此方法有效，因为各列中的行序相同，故一列位图中的第 *k* 位与另一列位图中的第 *k* 位对应同一行。

位图亦可用于回答图查询，例如查找社交网络中所有被用户 *X* 关注且同时关注用户 *Y* 的用户。列式数据库亦有其他多种压缩方案，可于参考文献中查阅。

--------

> [!注意]
> 勿将列式数据库与*宽列*（亦称*列族*）数据模型混淆。在宽列模型中，一行可有数千列，且无需所有行具有相同的列。尽管名称相似，宽列数据库实为行式存储，因其将一行的所有值存储在一起。Google 的 Bigtable、Apache Accumulo 和 HBase 即为宽列模型的实例。

--------
#### 列式存储中的排序顺序 {#sort-order-in-column-storage}
于列式存储中，行序未必紧要。以插入顺序存储最为简便，因新增行仅需在各列末尾追加即可。然亦可择定排序，如前文 SSTables 之例，以此作为索引机制。

须注意，若各列独立排序，则无意义，因无法知悉各列中何项属同一行。行数据之重构，端赖知晓一列中第 *k* 项与另一列中第 *k* 项同属一行。

故数据虽按列存储，排序仍需以整行为单位。数据库管理员可依常用查询之经验，择定表应据何列排序。例如，若查询常针对日期范围（如最近一月），则令 `date_key` 为首排序键或为合理之选。如是，查询仅需扫描最近一月之行，较之扫描全部行，其速大增。

次列可决定首列值相同行之排序顺序。例如，若 `date_key` 为[图 4-7](/zh-cn/ch4#fig_column_store) 之首排序键，则令 `product_sk` 为次排序键或属合理，以使同日内同一产品之销售数据在存储中聚于一处。此有助于需在特定日期范围内按产品分组或筛选销售之查询。

排序之另一优势，在于有助于列压缩。若主排序列之相异值不多，排序后将出现长序列，其中同一值连续重复多次。采用简单游程编码（如[图 4-8](/zh-cn/ch4#fig_bitmap_index) 之位图所用），可将该列压缩至数千字节——即便表有数十亿行。

此压缩效果于首排序键最为显著。次、三排序键则较为混杂，故无如此长之重复值序列。排序优先级更低之列，其顺序近乎随机，因而压缩效果或不甚佳。然令前数列有序，整体仍属有利。
#### 写入列式存储 {#writing-to-column-oriented-storage}
观前文[《事务处理与分析之特性》](/zh-cn/ch1#sec_introduction_oltp)可知，数据仓库之读取，多为海量行聚合操作；列式存储、压缩与排序，皆可加速此类查询。数据仓库之写入，则常为批量数据导入，多经ETL流程。

若用列式存储，在已排序表之中间位置单行写入，效率极低。盖因自插入点起，所有压缩列皆需重写。然批量写入多行，则可摊薄重写之成本，使之高效。

常以日志结构之法，批量执行写入。所有写入先至内存中一行式、已排序之存储。待累积足够写入，即与磁盘上列编码文件合并，批量写入新文件。旧文件恒不变，新文件一次写入，故对象存储甚宜存此等文件。

查询需同时检视磁盘列数据与内存中新近写入，并合并二者。查询执行引擎对用户隐此区别。自分析师观之，经插入、更新或删除修改之数据，可即时反映于后续查询。Snowflake、Vertica、Apache Pinot、Apache Druid等众多系统，皆循此道。
### 查询执行：编译与向量化 {#sec_storage_vectorized}
复杂 SQL 分析查询被分解为由多个阶段组成的*查询计划*，这些阶段称为*运算符*，可分布于多台机器并行执行。查询规划器可通过选择使用哪些运算符、以何种顺序执行、在何处运行每个运算符，进行大量优化。

在每个运算符内部，查询引擎需对列中的值进行多种操作，例如查找值属于特定集合的所有行（可能作为连接的一部分），或检查值是否大于 15。同时，它还需查看同一行的多个列，例如查找产品为香蕉且商店为特定目标商店的所有销售交易。

对于需要扫描数百万行的数据仓库查询，我们不仅需关注从磁盘读取的数据量，还需关注执行复杂运算符所需的 CPU 时间。最简单的运算符类似于编程语言的解释器：在遍历每一行时，它检查代表查询的数据结构，以确定需对哪些列执行何种比较或计算。然此方法对多数分析用途而言过慢。遂有两条高效查询执行路径：

查询编译
: 查询引擎接收 SQL 查询并生成执行代码。该代码逐行遍历，查看目标列的值，执行所需的比较或计算，若满足条件则将必要值复制至输出缓冲区。查询引擎将生成的代码编译为机器码（常使用现有编译器如 LLVM），随后在已加载至内存的列编码数据上运行。此代码生成方法类似于 Java 虚拟机（JVM）及类似运行时中使用的即时（JIT）编译。

向量化处理
: 查询被解释而非编译，但通过批量处理列中的多个值（而非逐行迭代）实现加速。数据库内置一组固定的预定义运算符；可向其传递参数并获取批量结果。

 例如，可将 `product` 列与“香蕉”的 ID 传递给等值运算符，并获取位图（输入列中每个值对应一位，若为香蕉则置 1）；随后将 `store` 列与目标商店的 ID 传递给同一等值运算符，获取另一张位图；再将两张位图传递给“按位与”运算符，如[图 4-9](/zh-cn/ch4#fig_bitmap_and)所示。结果将是一张位图，其中特定商店的所有香蕉销售记录对应位均置 1。
{{< figure src="/fig/ddia_0409.png" id="fig_bitmap_and" caption="Figure 4-9. A bitwise AND between two bitmaps lends itself to vectorization." class="w-full my-4" >}}
两种方法在实现上差异显著，然于实践中皆有所用。二者皆可借现代 CPU 之特性，达致优异性能：

* 优先顺序内存访问，而非随机访问，以减少缓存未命中；
* 主要工作置于紧凑内循环中（即指令数少、无函数调用），以保持 CPU 指令处理流水线忙碌，避免分支预测失误；
* 利用并行性，如多线程与单指令多数据（SIMD）指令；及
* 直接操作压缩数据，无需解码为独立的内存表示，以节省内存分配与复制开销。
### 物化视图与数据立方体 {#sec_storage_materialized_views}
此前于[《物化与更新时间线》](/zh-cn/ch2#sec_introduction_materializing)中已提及**物化视图**：在关系数据模型中，其为类表对象，其内容为某查询之结果。其异在于，物化视图乃查询结果之实际副本，已写入磁盘；而虚拟视图仅为编写查询之快捷方式。读取虚拟视图时，SQL 引擎即时将其展开为视图所基于之底层查询，而后处理展开后之查询。

当底层数据变更时，物化视图需相应更新。部分数据库可自动执行此操作，亦有如 Materialize 等系统专精于物化视图维护 [^81]。执行此类更新意味着写入时需更多工作，然对于需重复执行相同查询之工作负载，物化视图可提升读取性能。

**物化聚合**乃物化视图之一种，于数据仓库中或有裨益。如前所述，数据仓库查询常涉及聚合函数，如 SQL 中之 `COUNT`、`SUM`、`AVG`、`MIN` 或 `MAX`。若众多不同查询皆使用相同聚合，每次皆处理原始数据则显浪费。何不缓存查询最常用之某些计数或总和？**数据立方体**或 **OLAP 立方体**即通过创建按不同维度分组之聚合网格实现此目的 [^82]。[图 4-10](/zh-cn/ch4#fig_data_cube) 展示一例。
{{< figure src="/fig/ddia_0410.png" id="fig_data_cube" caption="Figure 4-10. Two dimensions of a data cube, aggregating data by summing." class="w-full my-4" >}}
假设每个事实表仅外联两个维度表——如[图4-10](/zh-cn/ch4#fig_data_cube)所示，即`date_key`与`product_sk`。此时可绘制二维表格，一轴为日期，另一轴为产品。每单元格包含对应日期-产品组合下所有事实的某属性（如`net_price`）聚合值（如`SUM`）。继而可沿每行或每列施加相同聚合，获得降一维度的汇总（如忽略日期的产品销售额，或忽略产品的日期销售额）。

然事实表常具多维。如[图3-5](/zh-cn/ch3#fig_dwh_schema)即有五维：日期、产品、商店、促销、顾客。虽五维超立方体难以直观想象，其原理不变：每单元格存储特定日期-产品-商店-促销-顾客组合的销售额。此值可沿任一维度反复汇总。

物化数据立方体之利，在于特定查询因预计算而极速。例如，若需知昨日各店总销售额，仅需沿对应维度查看总计值，无需扫描数百万行。

其弊在于，数据立方体不如查询原始数据灵活。例如，无法计算售价超100美元商品所占销售比例，因价格非维度之一。故多数数据仓库力求保留尽可能多原始数据，仅将数据立方体等聚合结构用作特定查询之性能加速手段。
## 多维与全文索引 {#sec_storage_multidimensional}
本章前半部分所述之 B 树与 LSM 树，可支持基于单一属性的范围查询：例如，若键为用户名，则可将其用作索引，以高效查找所有以 L 开头的姓名。然单属性搜索，有时不足。

最常见的多列索引类型，称为*拼接索引*，其法乃将若干字段依次拼接为一键（索引定义中指定字段拼接顺序）。此犹旧式纸质电话簿，提供从（姓氏，名字）至电话号码之索引。因排序之故，此索引可用于查找所有具特定姓氏者，或所有具特定“姓氏-名字”组合者。然若欲查找所有具特定名字者，此索引则无用。

另一方面，*多维索引*允许多列同时查询。此于地理空间数据尤为重要。例如，餐厅搜索网站或有一数据库，内含各家餐厅之纬度与经度。当用户查看地图上之餐厅时，网站需搜索用户当前所视矩形地图区域内之所有餐厅。此需如下二维范围查询：
```sql
SELECT * FROM restaurants WHERE latitude > 51.4946 AND latitude < 51.5079
    AND longitude > -0.1162 AND longitude < -0.1004;
```
对经纬度列建立联合索引，无法高效处理此类查询：其可返回纬度区间内所有餐厅（但经度任意），或经度区间内所有餐厅（但纬度范围覆盖南北两极），然无法同时满足二者。

一法乃借空间填充曲线，将二维坐标转为单一数值，再以常规 B 树索引之。更常见者，则用 R 树或 Bkd 树等专用空间索引；此类索引划分空间，使邻近数据点归于同一子树。例如，PostGIS 即借 PostgreSQL 之通用搜索树索引功能，以 R 树实现地理空间索引。亦可用三角形、正方形或六边形之规则网格划分空间。

多维索引非仅用于地理位置。譬如，电商网站可于（*红*、*绿*、*蓝*）三维建索引，以搜索特定颜色区间之商品；气象观测数据库中，可于（*日期*、*温度*）二维建索引，以高效检索 2013 年内温度介于 25 至 30℃ 之所有观测记录。若用一维索引，则须扫描 2013 年全部记录（无论温度）再按温度过滤，或反之。二维索引则可同时按时间戳与温度缩小范围。
### 全文搜索 {#sec_storage_full_text}
全文检索，乃于文本集合（网页、商品描述等）中依关键词搜寻之法，该词可现于文本任意位置。

信息检索为一大而专之领域，常涉语言特异性处理：譬如若干东亚文字书写时词间无空格或标点，故须借模型判别何等字符序列构成一词。全文检索亦常需匹配形近而非全同之词（如拼写错误、词形变化）及同义词。诸般问题，已超本书所及。

然其核心，可视全文检索为一类多维查询：此处每一可能见于文本之词（即“项” *term*）皆为一维。含项 *x* 之文档，在 *x* 维取值为 1；不含者则为 0。检索“红苹果”之文档，即求 *red* 维与 *apples* 维同为 1 之文档。维度之数，因而甚巨。

诸多搜索引擎用以应答此类查询之数据结构，谓之“倒排索引”（*inverted index*）。此为一键值结构：键为项，值为所有含该项之文档 ID 列表（即“倒排列表” *postings list*）。若文档 ID 为连续整数，则倒排列表亦可表为稀疏位图（sparse bitmap），如[图 4-8](/zh-cn/ch4#fig_bitmap_index)所示：项 *x* 对应位图中第 *n* 位为 1，当且仅当 ID 为 *n* 之文档含 *x*。

今欲得同时含项 *x* 与 *y* 之全部文档，其法类于向量化数据仓库中对两条件联合筛选之行查询（[图 4-9](/zh-cn/ch4#fig_bitmap_and)）：载入 *x*、*y* 二项之位图，并作按位与（bitwise AND）运算。纵使位图经游程编码（run-length encoded），此操作仍极高效。

例如，Elasticsearch 与 Solr 所用之全文索引引擎 Lucene，即依此原理运作。其将项至倒排列表之映射存于类 SSTable 之有序文件中，并以后台方式依本章前文所述日志结构化（log-structured）策略予以归并。PostgreSQL 之 GIN 索引类型，亦以倒排列表支撑全文检索及 JSON 文档内字段之索引。

另有一法，不切分文本为词，而取所有长为 *n* 之子串，是谓“*n*-gram”。例如，字符串 `"hello"` 之三元组（*n* = 3）为 `"hel"`、`"ell"` 与 `"llo"`。若建全体三元组之倒排索引，则可检索任意长度不小于三之子串；三元组索引甚至可支持正则表达式查询；其弊则在于索引体积甚大。

为容文档或查询中之拼写错误，Lucene 可依编辑距离（edit distance）检索：距离为 1，即一字之增、删或替换。其实现，系将项集建为键字符之上之有限状态自动机（finite state automaton），类于“字典树”（*trie*），再转为“莱文斯坦自动机”（*Levenshtein automaton*），从而高效支持给定编辑距离内之词匹配。
### 向量嵌入 {#id92}
语义搜索不止于同义词与拼写纠错，更重在理解文档之概念及用户之意图。  
例如，若帮助文档中有一页面题为“取消您的订阅”，用户以“如何关闭我的账户”或“终止合同”为关键词搜索，亦应命中该页——虽用词迥异，然语义相近。

为解析文档语义（即其含义），语义搜索索引采用嵌入模型（embedding model），将文档映射为一浮点数向量，称作**向量嵌入**（vector embedding）。此向量表征高维空间中一点；各浮点数值，即该点沿某一维度轴之坐标。嵌入模型确保：语义相近之文档，其生成向量在该高维空间中彼此邻近。

> [!NOTE]  
> 前文[“查询执行：编译与向量化”](/zh-cn/ch4#sec_storage_vectorized)曾见术语 *vectorized processing*（向量化处理）。  
> 此处“向量”含义不同：向量化处理中，“向量”指一批可由专用优化代码并行处理的比特；而嵌入模型中，“向量”乃一浮点数序列，表征高维抽象空间中之位置。

例如，某农业主题维基百科页面之三维向量嵌入或为 `[0.1, 0.22, 0.11]`；蔬菜主题页面语义相近，其嵌入或为 `[0.13, 0.19, 0.24]`；星型模式（star schema）页面语义相远，嵌入或为 `[0.82, 0.39, -0.74]`。仅观数值，即可判前二者距离小于后者。

实际嵌入模型所用向量维数远高于三（常逾千维），然原理如一。吾人不究单个数值之义；其唯为嵌入模型标定抽象高维空间中位置之手段。搜索引擎藉距离函数（如余弦相似度、欧氏距离）度量向量间距：余弦相似度取两向量夹角之余弦值以判相近程度；欧氏距离则测两点间直线距离。

早期嵌入模型如 Word2Vec [^98]、BERT [^99]、GPT [^100]，多专用于文本。此类模型通常以神经网络实现。继而，研究者拓展至视频、音频、图像等模态之嵌入模型。近年，模型架构日趋**多模态**（multimodal）：单一模型可为文本、图像等多种模态生成向量嵌入。

语义搜索引擎于用户提交查询时，即调用嵌入模型生成查询之向量嵌入；查询文本及上下文（如用户地理位置）一并输入模型。嵌入生成后，引擎须借**向量索引**（vector index）检索语义相近之文档。

向量索引存储整批文档之向量嵌入。查询时，传入查询向量，索引即返回与其最邻近之文档向量。此前所述 R 树不适用于高维向量，故需专用向量索引，常见者有三：

**扁平索引（Flat index）**  
向量原样存入索引。每次查询须遍历全部向量，逐一计算其与查询向量之距离。精度确凿，然耗时甚巨。

**倒排文件索引（Inverted File, IVF）**  
将向量空间聚类为若干分区（称“质心”，centroids），以减少比对向量之数量。较扁平索引迅捷，然结果仅为近似：语义相近之查询与文档或因分属不同分区而漏检。IVF 查询先指定**探针数**（probes），即待查分区之数量。探针愈多，精度愈高，然耗时亦增。

**层级可导航小世界索引（Hierarchical Navigable Small World, HNSW）**  
HNSW 索引构建多层向量空间，如[图 4-11](/zh-cn/ch4#fig_vector_hnsw)所示。每层以图结构表示：节点为向量，边表征邻近关系。查询始于顶层（节点稀疏），定位最近向量；继而移至下一层同节点，在更稠密之图中循边搜索更近向量；逐层下行，直至底层。与 IVF 同，HNSW 结果亦为近似。
{{< figure src="/fig/ddia_0411.png" id="fig_vector_hnsw" caption="Figure 4-11. Searching for the database entry that is closest to a given query vector in a HNSW index." class="w-full my-4" >}}
诸多主流向量数据库均实现 IVF 与 HNSW 索引。Facebook 的 Faiss 库为此二者各提供多种变体 [^101]；PostgreSQL 的 pgvector 扩展亦同时支持二者 [^102]。  
IVF 与 HNSW 算法之完整细节，非本书所及；然其原始论文实为极佳参考 [^103] [^104]。
## 概要 {#summary}
本章探析数据库存储与检索之机理：数据入库之际，系统如何存之；日后查询之时，系统又如何取之。

【“分析型系统 vs. 运营型系统”】一节已明示事务处理（OLTP）与分析处理（OLAP）之分野。本章进而揭示：专为 OLTP 优化之存储引擎，与专为分析优化者，其设计迥异：

- OLTP 系统重在支撑高并发请求，每请求仅读写少量记录，且须低延迟响应。记录多经主键或二级索引定位；此类索引通常为有序映射（键 → 记录），兼支持范围查询。
- 数据仓库及同类分析系统，则面向复杂读取——常需扫描海量记录。故多采列式存储布局，辅以压缩，以最小化磁盘 I/O；并借查询即时编译（JIT compilation）或向量化执行（vectorization），压降 CPU 处理开销。

OLTP 存储引擎，大体分两派：

- 日志结构派（log-structured）：仅允许追加写入文件、删除过期文件，禁绝就地更新已写文件。SSTables、LSM-tree、RocksDB、Cassandra、HBase、Scylla、Lucene 等皆属此列。通例而言，此类引擎写吞吐量高。
- 就地更新派（update-in-place）：视磁盘为固定大小页之集合，允覆盖重写。B 树为此派典型，见于所有主流关系型 OLTP 数据库，亦广用于诸多非关系型系统。经验法则：B 树读性能更优，读吞吐更高、响应延迟更低。

继而论及多条件联合检索之索引：

- 多维索引，如 R 树，可同步依经纬度检索地理点；
- 全文索引，可检索同一文本中多个关键词之共现；
- 向量数据库，则专司语义搜索——对文本、图像等媒体提取高维向量，依向量相似度检索近似项。

身为应用开发者，若通晓存储引擎之内核机理，则能精准择器：何者适配当前场景？若需调优数据库参数，亦能推演参数升降之实效。

本章虽未授人以精调任一特定引擎之术，然已授以核心术语与基本范式，足助君通读所选数据库之官方文档。
### 参考文献

[^1]: Nikolay Samokhvalov. [How partial, covering, and multicolumn indexes may slow down UPDATEs in PostgreSQL](https://postgres.ai/blog/20211029-how-partial-and-covering-indexes-affect-update-performance-in-postgresql). *postgres.ai*, October 2021. Archived at [perma.cc/PBK3-F4G9](https://perma.cc/PBK3-F4G9) 
[^2]: Goetz Graefe. [Modern B-Tree Techniques](https://w6113.github.io/files/papers/btreesurvey-graefe.pdf). *Foundations and Trends in Databases*, volume 3, issue 4, pages 203–402, August 2011. [doi:10.1561/1900000028](https://doi.org/10.1561/1900000028) 
[^3]: Evan Jones. [Why databases use ordered indexes but programming uses hash tables](https://www.evanjones.ca/ordered-vs-unordered-indexes.html). *evanjones.ca*, December 2019. Archived at [perma.cc/NJX8-3ZZD](https://perma.cc/NJX8-3ZZD) 
[^4]: Branimir Lambov. [CEP-25: Trie-indexed SSTable format](https://cwiki.apache.org/confluence/display/CASSANDRA/CEP-25%3A%2BTrie-indexed%2BSSTable%2Bformat). *cwiki.apache.org*, November 2022. Archived at [perma.cc/HD7W-PW8U](https://perma.cc/HD7W-PW8U). Linked Google Doc archived at [perma.cc/UL6C-AAAE](https://perma.cc/UL6C-AAAE) 
[^5]: Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, and Clifford Stein: *Introduction to Algorithms*, 3rd edition. MIT Press, 2009. ISBN: 978-0-262-53305-8 
[^6]: Branimir Lambov. [Trie Memtables in Cassandra](https://www.vldb.org/pvldb/vol15/p3359-lambov.pdf). *Proceedings of the VLDB Endowment*, volume 15, issue 12, pages 3359–3371, August 2022. [doi:10.14778/3554821.3554828](https://doi.org/10.14778/3554821.3554828) 
[^7]: Dhruba Borthakur. [The History of RocksDB](https://rocksdb.blogspot.com/2013/11/the-history-of-rocksdb.html). *rocksdb.blogspot.com*, November 2013. Archived at [perma.cc/Z7C5-JPSP](https://perma.cc/Z7C5-JPSP) 
[^8]: Matteo Bertozzi. [Apache HBase I/O – HFile](https://blog.cloudera.com/apache-hbase-i-o-hfile/). *blog.cloudera.com*, June 2012. Archived at [perma.cc/U9XH-L2KL](https://perma.cc/U9XH-L2KL) 
[^9]: Fay Chang, Jeffrey Dean, Sanjay Ghemawat, Wilson C. Hsieh, Deborah A. Wallach, Mike Burrows, Tushar Chandra, Andrew Fikes, and Robert E. Gruber. [Bigtable: A Distributed Storage System for Structured Data](https://research.google/pubs/pub27898/). At *7th USENIX Symposium on Operating System Design and Implementation* (OSDI), November 2006. 
[^10]: Patrick O’Neil, Edward Cheng, Dieter Gawlick, and Elizabeth O’Neil. [The Log-Structured Merge-Tree (LSM-Tree)](https://www.cs.umb.edu/~poneil/lsmtree.pdf). *Acta Informatica*, volume 33, issue 4, pages 351–385, June 1996. [doi:10.1007/s002360050048](https://doi.org/10.1007/s002360050048) 
[^11]: Mendel Rosenblum and John K. Ousterhout. [The Design and Implementation of a Log-Structured File System](https://research.cs.wisc.edu/areas/os/Qual/papers/lfs.pdf). *ACM Transactions on Computer Systems*, volume 10, issue 1, pages 26–52, February 1992. [doi:10.1145/146941.146943](https://doi.org/10.1145/146941.146943) 
[^12]: Michael Armbrust, Tathagata Das, Liwen Sun, Burak Yavuz, Shixiong Zhu, Mukul Murthy, Joseph Torres, Herman van Hovell, Adrian Ionescu, Alicja Łuszczak, Michał Świtakowski, Michał Szafrański, Xiao Li, Takuya Ueshin, Mostafa Mokhtar, Peter Boncz, Ali Ghodsi, Sameer Paranjpye, Pieter Senster, Reynold Xin, and Matei Zaharia. [Delta Lake: High-Performance ACID Table Storage over Cloud Object Stores](https://vldb.org/pvldb/vol13/p3411-armbrust.pdf). *Proceedings of the VLDB Endowment*, volume 13, issue 12, pages 3411–3424, August 2020. [doi:10.14778/3415478.3415560](https://doi.org/10.14778/3415478.3415560) 
[^13]: Burton H. Bloom. [Space/Time Trade-offs in Hash Coding with Allowable Errors](https://people.cs.umass.edu/~emery/classes/cmpsci691st/readings/Misc/p422-bloom.pdf). *Communications of the ACM*, volume 13, issue 7, pages 422–426, July 1970. [doi:10.1145/362686.362692](https://doi.org/10.1145/362686.362692) 
[^14]: Adam Kirsch and Michael Mitzenmacher. [Less Hashing, Same Performance: Building a Better Bloom Filter](https://www.eecs.harvard.edu/~michaelm/postscripts/tr-02-05.pdf). *Random Structures & Algorithms*, volume 33, issue 2, pages 187–218, September 2008. [doi:10.1002/rsa.20208](https://doi.org/10.1002/rsa.20208) 
[^15]: Thomas Hurst. [Bloom Filter Calculator](https://hur.st/bloomfilter/). *hur.st*, September 2023. Archived at [perma.cc/L3AV-6VC2](https://perma.cc/L3AV-6VC2) 
[^16]: Chen Luo and Michael J. Carey. [LSM-based storage techniques: a survey](https://arxiv.org/abs/1812.07527). *The VLDB Journal*, volume 29, pages 393–418, July 2019. [doi:10.1007/s00778-019-00555-y](https://doi.org/10.1007/s00778-019-00555-y) 
[^17]: Subhadeep Sarkar and Manos Athanassoulis. [Dissecting, Designing, and Optimizing LSM-based Data Stores](https://www.youtube.com/watch?v=hkMkBZn2mGs). Tutorial at *ACM International Conference on Management of Data* (SIGMOD), June 2022. Slides archived at [perma.cc/93B3-E827](https://perma.cc/93B3-E827) 
[^18]: Mark Callaghan. [Name that compaction algorithm](https://smalldatum.blogspot.com/2018/08/name-that-compaction-algorithm.html). *smalldatum.blogspot.com*, August 2018. Archived at [perma.cc/CN4M-82DY](https://perma.cc/CN4M-82DY) 
[^19]: Prashanth Rao. [Embedded databases (1): The harmony of DuckDB, KùzuDB and LanceDB](https://thedataquarry.com/posts/embedded-db-1/). *thedataquarry.com*, August 2023. Archived at [perma.cc/PA28-2R35](https://perma.cc/PA28-2R35) 
[^20]: Hacker News discussion. [Bluesky migrates to single-tenant SQLite](https://news.ycombinator.com/item?id=38171322). *news.ycombinator.com*, October 2023. Archived at [perma.cc/69LM-5P6X](https://perma.cc/69LM-5P6X) 
[^21]: Rudolf Bayer and Edward M. McCreight. [Organization and Maintenance of Large Ordered Indices](https://dl.acm.org/doi/pdf/10.1145/1734663.1734671). Boeing Scientific Research Laboratories, Mathematical and Information Sciences Laboratory, report no. 20, July 1970. [doi:10.1145/1734663.1734671](https://doi.org/10.1145/1734663.1734671) 
[^22]: Douglas Comer. [The Ubiquitous B-Tree](https://web.archive.org/web/20170809145513id_/http%3A//sites.fas.harvard.edu/~cs165/papers/comer.pdf). *ACM Computing Surveys*, volume 11, issue 2, pages 121–137, June 1979. [doi:10.1145/356770.356776](https://doi.org/10.1145/356770.356776) 
[^23]: Alex Miller. [Torn Write Detection and Protection](https://transactional.blog/blog/2025-torn-writes). *transactional.blog*, April 2025. Archived at [perma.cc/G7EB-33EW](https://perma.cc/G7EB-33EW) 
[^24]: C. Mohan and Frank Levine. [ARIES/IM: An Efficient and High Concurrency Index Management Method Using Write-Ahead Logging](https://ics.uci.edu/~cs223/papers/p371-mohan.pdf). At *ACM International Conference on Management of Data* (SIGMOD), June 1992. [doi:10.1145/130283.130338](https://doi.org/10.1145/130283.130338) 
[^25]: Hironobu Suzuki. [The Internals of PostgreSQL](https://www.interdb.jp/pg/). *interdb.jp*, 2017. 
[^26]: Howard Chu. [LDAP at Lightning Speed](https://buildstuff14.sched.com/event/08a1a368e272eb599a52e08b4c3c779d). At *Build Stuff ’14*, November 2014. Archived at [perma.cc/GB6Z-P8YH](https://perma.cc/GB6Z-P8YH) 
[^27]: Manos Athanassoulis, Michael S. Kester, Lukas M. Maas, Radu Stoica, Stratos Idreos, Anastasia Ailamaki, and Mark Callaghan. [Designing Access Methods: The RUM Conjecture](https://openproceedings.org/2016/conf/edbt/paper-12.pdf). At *19th International Conference on Extending Database Technology* (EDBT), March 2016. [doi:10.5441/002/edbt.2016.42](https://doi.org/10.5441/002/edbt.2016.42) 
[^28]: Ben Stopford. [Log Structured Merge Trees](http://www.benstopford.com/2015/02/14/log-structured-merge-trees/). *benstopford.com*, February 2015. Archived at [perma.cc/E5BV-KUJ6](https://perma.cc/E5BV-KUJ6) 
[^29]: Mark Callaghan. [The Advantages of an LSM vs a B-Tree](https://smalldatum.blogspot.com/2016/01/summary-of-advantages-of-lsm-vs-b-tree.html). *smalldatum.blogspot.co.uk*, January 2016. Archived at [perma.cc/3TYZ-EFUD](https://perma.cc/3TYZ-EFUD) 
[^30]: Oana Balmau, Florin Dinu, Willy Zwaenepoel, Karan Gupta, Ravishankar Chandhiramoorthi, and Diego Didona. [SILK: Preventing Latency Spikes in Log-Structured Merge Key-Value Stores](https://www.usenix.org/conference/atc19/presentation/balmau). At *USENIX Annual Technical Conference*, July 2019. 
[^31]: Igor Canadi, Siying Dong, Mark Callaghan, et al. [RocksDB Tuning Guide](https://github.com/facebook/rocksdb/wiki/RocksDB-Tuning-Guide). *github.com*, 2023. Archived at [perma.cc/UNY4-MK6C](https://perma.cc/UNY4-MK6C) 
[^32]: Gabriel Haas and Viktor Leis. [What Modern NVMe Storage Can Do, and How to Exploit it: High-Performance I/O for High-Performance Storage Engines](https://www.vldb.org/pvldb/vol16/p2090-haas.pdf). *Proceedings of the VLDB Endowment*, volume 16, issue 9, pages 2090-2102. [doi:10.14778/3598581.3598584](https://doi.org/10.14778/3598581.3598584) 
[^33]: Emmanuel Goossaert. [Coding for SSDs](https://codecapsule.com/2014/02/12/coding-for-ssds-part-1-introduction-and-table-of-contents/). *codecapsule.com*, February 2014. 
[^34]: Jack Vanlightly. [Is sequential IO dead in the era of the NVMe drive?](https://jack-vanlightly.com/blog/2023/5/9/is-sequential-io-dead-in-the-era-of-the-nvme-drive) *jack-vanlightly.com*, May 2023. Archived at [perma.cc/7TMZ-TAPU](https://perma.cc/7TMZ-TAPU) 
[^35]: Alibaba Cloud Storage Team. [Storage System Design Analysis: Factors Affecting NVMe SSD Performance (2)](https://www.alibabacloud.com/blog/594376). *alibabacloud.com*, January 2019. Archived at [archive.org](https://web.archive.org/web/20230510065132/https%3A//www.alibabacloud.com/blog/594376) 
[^36]: Xiao-Yu Hu and Robert Haas. [The Fundamental Limit of Flash Random Write Performance: Understanding, Analysis and Performance Modelling](https://dominoweb.draco.res.ibm.com/reports/rz3771.pdf). *dominoweb.draco.res.ibm.com*, March 2010. Archived at [perma.cc/8JUL-4ZDS](https://perma.cc/8JUL-4ZDS) 
[^37]: Lanyue Lu, Thanumalayan Sankaranarayana Pillai, Andrea C. Arpaci-Dusseau, and Remzi H. Arpaci-Dusseau. [WiscKey: Separating Keys from Values in SSD-conscious Storage](https://www.usenix.org/system/files/conference/fast16/fast16-papers-lu.pdf). At *4th USENIX Conference on File and Storage Technologies* (FAST), February 2016. 
[^38]: Peter Zaitsev. [Innodb Double Write](https://www.percona.com/blog/innodb-double-write/). *percona.com*, August 2006. Archived at [perma.cc/NT4S-DK7T](https://perma.cc/NT4S-DK7T) 
[^39]: Tomas Vondra. [On the Impact of Full-Page Writes](https://www.2ndquadrant.com/en/blog/on-the-impact-of-full-page-writes/). *2ndquadrant.com*, November 2016. Archived at [perma.cc/7N6B-CVL3](https://perma.cc/7N6B-CVL3) 
[^40]: Mark Callaghan. [Read, write & space amplification - B-Tree vs LSM](https://smalldatum.blogspot.com/2015/11/read-write-space-amplification-b-tree.html). *smalldatum.blogspot.com*, November 2015. Archived at [perma.cc/S487-WK5P](https://perma.cc/S487-WK5P) 
[^41]: Mark Callaghan. [Choosing Between Efficiency and Performance with RocksDB](https://codemesh.io/codemesh2016/mark-callaghan). At *Code Mesh*, November 2016. Video at [youtube.com/watch?v=tgzkgZVXKB4](https://www.youtube.com/watch?v=tgzkgZVXKB4) 
[^42]: Subhadeep Sarkar, Tarikul Islam Papon, Dimitris Staratzis, Zichen Zhu, and Manos Athanassoulis. [Enabling Timely and Persistent Deletion in LSM-Engines](https://subhadeep.net/assets/fulltext/Enabling_Timely_and_Persistent_Deletion_in_LSM-Engines.pdf). *ACM Transactions on Database Systems*, volume 48, issue 3, article no. 8, August 2023. [doi:10.1145/3599724](https://doi.org/10.1145/3599724) 
[^43]: Lukas Fittl. [Postgres vs. SQL Server: B-Tree Index Differences & the Benefit of Deduplication](https://pganalyze.com/blog/postgresql-vs-sql-server-btree-index-deduplication). *pganalyze.com*, April 2025. Archived at [perma.cc/XY6T-LTPX](https://perma.cc/XY6T-LTPX) 
[^44]: Drew Silcock. [How Postgres stores data on disk – this one’s a page turner](https://drew.silcock.dev/blog/how-postgres-stores-data-on-disk/). *drew.silcock.dev*, August 2024. Archived at [perma.cc/8K7K-7VJ2](https://perma.cc/8K7K-7VJ2) 
[^45]: Joe Webb. [Using Covering Indexes to Improve Query Performance](https://www.red-gate.com/simple-talk/databases/sql-server/learn/using-covering-indexes-to-improve-query-performance/). *simple-talk.com*, September 2008. Archived at [perma.cc/6MEZ-R5VR](https://perma.cc/6MEZ-R5VR) 
[^46]: Michael Stonebraker, Samuel Madden, Daniel J. Abadi, Stavros Harizopoulos, Nabil Hachem, and Pat Helland. [The End of an Architectural Era (It’s Time for a Complete Rewrite)](https://vldb.org/conf/2007/papers/industrial/p1150-stonebraker.pdf). At *33rd International Conference on Very Large Data Bases* (VLDB), September 2007. 
[^47]: [VoltDB Technical Overview White Paper](https://www.voltactivedata.com/wp-content/uploads/2017/03/hv-white-paper-voltdb-technical-overview.pdf). VoltDB, 2017. Archived at [perma.cc/B9SF-SK5G](https://perma.cc/B9SF-SK5G) 
[^48]: Stephen M. Rumble, Ankita Kejriwal, and John K. Ousterhout. [Log-Structured Memory for DRAM-Based Storage](https://www.usenix.org/system/files/conference/fast14/fast14-paper_rumble.pdf). At *12th USENIX Conference on File and Storage Technologies* (FAST), February 2014. 
[^49]: Stavros Harizopoulos, Daniel J. Abadi, Samuel Madden, and Michael Stonebraker. [OLTP Through the Looking Glass, and What We Found There](https://hstore.cs.brown.edu/papers/hstore-lookingglass.pdf). At *ACM International Conference on Management of Data* (SIGMOD), June 2008. [doi:10.1145/1376616.1376713](https://doi.org/10.1145/1376616.1376713) 
[^50]: Per-Åke Larson, Cipri Clinciu, Campbell Fraser, Eric N. Hanson, Mostafa Mokhtar, Michal Nowakiewicz, Vassilis Papadimos, Susan L. Price, Srikumar Rangarajan, Remus Rusanu, and Mayukh Saubhasik. [Enhancements to SQL Server Column Stores](https://web.archive.org/web/20131203001153id_/http%3A//research.microsoft.com/pubs/193599/Apollo3%20-%20Sigmod%202013%20-%20final.pdf). At *ACM International Conference on Management of Data* (SIGMOD), June 2013. [doi:10.1145/2463676.2463708](https://doi.org/10.1145/2463676.2463708) 
[^51]: Franz Färber, Norman May, Wolfgang Lehner, Philipp Große, Ingo Müller, Hannes Rauhe, and Jonathan Dees. [The SAP HANA Database – An Architecture Overview](https://web.archive.org/web/20220208081111id_/http%3A//sites.computer.org/debull/A12mar/hana.pdf). *IEEE Data Engineering Bulletin*, volume 35, issue 1, pages 28–33, March 2012. 
[^52]: Michael Stonebraker. [The Traditional RDBMS Wisdom Is (Almost Certainly) All Wrong](https://slideshot.epfl.ch/talks/166). Presentation at *EPFL*, May 2013. 
[^53]: Adam Prout, Szu-Po Wang, Joseph Victor, Zhou Sun, Yongzhu Li, Jack Chen, Evan Bergeron, Eric Hanson, Robert Walzer, Rodrigo Gomes, and Nikita Shamgunov. [Cloud-Native Transactions and Analytics in SingleStore](https://dl.acm.org/doi/pdf/10.1145/3514221.3526055). At *ACM International Conference on Management of Data* (SIGMOD), June 2022. [doi:10.1145/3514221.3526055](https://doi.org/10.1145/3514221.3526055) 
[^54]: Tino Tereshko and Jordan Tigani. [BigQuery under the hood](https://cloud.google.com/blog/products/bigquery/bigquery-under-the-hood). *cloud.google.com*, January 2016. Archived at [perma.cc/WP2Y-FUCF](https://perma.cc/WP2Y-FUCF) 
[^55]: Wes McKinney. [The Road to Composable Data Systems: Thoughts on the Last 15 Years and the Future](https://wesmckinney.com/blog/looking-back-15-years/). *wesmckinney.com*, September 2023. Archived at [perma.cc/6L2M-GTJX](https://perma.cc/6L2M-GTJX) 
[^56]: Michael Stonebraker, Daniel J. Abadi, Adam Batkin, Xuedong Chen, Mitch Cherniack, Miguel Ferreira, Edmond Lau, Amerson Lin, Sam Madden, Elizabeth O’Neil, Pat O’Neil, Alex Rasin, Nga Tran, and Stan Zdonik. [C-Store: A Column-oriented DBMS](https://www.vldb.org/archives/website/2005/program/paper/thu/p553-stonebraker.pdf). At *31st International Conference on Very Large Data Bases* (VLDB), pages 553–564, September 2005. 
[^57]: Julien Le Dem. [Dremel Made Simple with Parquet](https://blog.twitter.com/engineering/en_us/a/2013/dremel-made-simple-with-parquet.html). *blog.twitter.com*, September 2013. 
[^58]: Sergey Melnik, Andrey Gubarev, Jing Jing Long, Geoffrey Romer, Shiva Shivakumar, Matt Tolton, and Theo Vassilakis. [Dremel: Interactive Analysis of Web-Scale Datasets](https://vldb.org/pvldb/vol3/R29.pdf). At *36th International Conference on Very Large Data Bases* (VLDB), pages 330–339, September 2010. [doi:10.14778/1920841.1920886](https://doi.org/10.14778/1920841.1920886) 
[^59]: Joe Kearney. [Understanding Record Shredding: storing nested data in columns](https://www.joekearney.co.uk/posts/understanding-record-shredding). *joekearney.co.uk*, December 2016. Archived at [perma.cc/ZD5N-AX5D](https://perma.cc/ZD5N-AX5D) 
[^60]: Jamie Brandon. [A shallow survey of OLAP and HTAP query engines](https://www.scattered-thoughts.net/writing/a-shallow-survey-of-olap-and-htap-query-engines). *scattered-thoughts.net*, September 2023. Archived at [perma.cc/L3KH-J4JF](https://perma.cc/L3KH-J4JF) 
[^61]: Benoit Dageville, Thierry Cruanes, Marcin Zukowski, Vadim Antonov, Artin Avanes, Jon Bock, Jonathan Claybaugh, Daniel Engovatov, Martin Hentschel, Jiansheng Huang, Allison W. Lee, Ashish Motivala, Abdul Q. Munir, Steven Pelley, Peter Povinec, Greg Rahn, Spyridon Triantafyllis, and Philipp Unterbrunner. [The Snowflake Elastic Data Warehouse](https://dl.acm.org/doi/pdf/10.1145/2882903.2903741). At *ACM International Conference on Management of Data* (SIGMOD), pages 215–226, June 2016. [doi:10.1145/2882903.2903741](https://doi.org/10.1145/2882903.2903741) 
[^62]: Mark Raasveldt and Hannes Mühleisen. [Data Management for Data Science Towards Embedded Analytics](https://duckdb.org/pdf/CIDR2020-raasveldt-muehleisen-duckdb.pdf). At *10th Conference on Innovative Data Systems Research* (CIDR), January 2020. 
[^63]: Jean-François Im, Kishore Gopalakrishna, Subbu Subramaniam, Mayank Shrivastava, Adwait Tumbde, Xiaotian Jiang, Jennifer Dai, Seunghyun Lee, Neha Pawar, Jialiang Li, and Ravi Aringunram. [Pinot: Realtime OLAP for 530 Million Users](https://cwiki.apache.org/confluence/download/attachments/103092375/Pinot.pdf). At *ACM International Conference on Management of Data* (SIGMOD), pages 583–594, May 2018. [doi:10.1145/3183713.3190661](https://doi.org/10.1145/3183713.3190661) 
[^64]: Fangjin Yang, Eric Tschetter, Xavier Léauté, Nelson Ray, Gian Merlino, and Deep Ganguli. [Druid: A Real-time Analytical Data Store](https://static.druid.io/docs/druid.pdf). At *ACM International Conference on Management of Data* (SIGMOD), June 2014. [doi:10.1145/2588555.2595631](https://doi.org/10.1145/2588555.2595631) 
[^65]: Chunwei Liu, Anna Pavlenko, Matteo Interlandi, and Brandon Haynes. [Deep Dive into Common Open Formats for Analytical DBMSs](https://www.vldb.org/pvldb/vol16/p3044-liu.pdf). *Proceedings of the VLDB Endowment*, volume 16, issue 11, pages 3044–3056, July 2023. [doi:10.14778/3611479.3611507](https://doi.org/10.14778/3611479.3611507) 
[^66]: Xinyu Zeng, Yulong Hui, Jiahong Shen, Andrew Pavlo, Wes McKinney, and Huanchen Zhang. [An Empirical Evaluation of Columnar Storage Formats](https://www.vldb.org/pvldb/vol17/p148-zeng.pdf). *Proceedings of the VLDB Endowment*, volume 17, issue 2, pages 148–161. [doi:10.14778/3626292.3626298](https://doi.org/10.14778/3626292.3626298) 
[^67]: Weston Pace. [Lance v2: A columnar container format for modern data](https://blog.lancedb.com/lance-v2/). *blog.lancedb.com*, April 2024. Archived at [perma.cc/ZK3Q-S9VJ](https://perma.cc/ZK3Q-S9VJ) 
[^68]: Yoav Helfman. [Nimble, A New Columnar File Format](https://www.youtube.com/watch?v=bISBNVtXZ6M). At *VeloxCon*, April 2024. 
[^69]: Wes McKinney. [Apache Arrow: High-Performance Columnar Data Framework](https://www.youtube.com/watch?v=YhF8YR0OEFk). At *CMU Database Group – Vaccination Database Tech Talks*, December 2021. 
[^70]: Wes McKinney. [Python for Data Analysis, 3rd Edition](https://learning.oreilly.com/library/view/python-for-data/9781098104023/). O’Reilly Media, August 2022. ISBN: 9781098104023 
[^71]: Paul Dix. [The Design of InfluxDB IOx: An In-Memory Columnar Database Written in Rust with Apache Arrow](https://www.youtube.com/watch?v=_zbwz-4RDXg). At *CMU Database Group – Vaccination Database Tech Talks*, May 2021. 
[^72]: Carlota Soto and Mike Freedman. [Building Columnar Compression for Large PostgreSQL Databases](https://www.timescale.com/blog/building-columnar-compression-in-a-row-oriented-database/). *timescale.com*, March 2024. Archived at [perma.cc/7KTF-V3EH](https://perma.cc/7KTF-V3EH) 
[^73]: Daniel Lemire, Gregory Ssi‐Yan‐Kai, and Owen Kaser. [Consistently faster and smaller compressed bitmaps with Roaring](https://arxiv.org/pdf/1603.06549). *Software: Practice and Experience*, volume 46, issue 11, pages 1547–1569, November 2016. [doi:10.1002/spe.2402](https://doi.org/10.1002/spe.2402) 
[^74]: Jaz Volpert. [An entire Social Network in 1.6GB (GraphD Part 2)](https://jazco.dev/2024/04/20/roaring-bitmaps/). *jazco.dev*, April 2024. Archived at [perma.cc/L27Z-QVMG](https://perma.cc/L27Z-QVMG) 
[^75]: Daniel J. Abadi, Peter Boncz, Stavros Harizopoulos, Stratos Idreos, and Samuel Madden. [The Design and Implementation of Modern Column-Oriented Database Systems](https://www.cs.umd.edu/~abadi/papers/abadi-column-stores.pdf). *Foundations and Trends in Databases*, volume 5, issue 3, pages 197–280, December 2013. [doi:10.1561/1900000024](https://doi.org/10.1561/1900000024) 
[^76]: Andrew Lamb, Matt Fuller, Ramakrishna Varadarajan, Nga Tran, Ben Vandiver, Lyric Doshi, and Chuck Bear. [The Vertica Analytic Database: C-Store 7 Years Later](https://vldb.org/pvldb/vol5/p1790_andrewlamb_vldb2012.pdf). *Proceedings of the VLDB Endowment*, volume 5, issue 12, pages 1790–1801, August 2012. [doi:10.14778/2367502.2367518](https://doi.org/10.14778/2367502.2367518) 
[^77]: Timo Kersten, Viktor Leis, Alfons Kemper, Thomas Neumann, Andrew Pavlo, and Peter Boncz. [Everything You Always Wanted to Know About Compiled and Vectorized Queries But Were Afraid to Ask](https://www.vldb.org/pvldb/vol11/p2209-kersten.pdf). *Proceedings of the VLDB Endowment*, volume 11, issue 13, pages 2209–2222, September 2018. [doi:10.14778/3275366.3284966](https://doi.org/10.14778/3275366.3284966) 
[^78]: Forrest Smith. [Memory Bandwidth Napkin Math](https://www.forrestthewoods.com/blog/memory-bandwidth-napkin-math/). *forrestthewoods.com*, February 2020. Archived at [perma.cc/Y8U4-PS7N](https://perma.cc/Y8U4-PS7N) 
[^79]: Peter Boncz, Marcin Zukowski, and Niels Nes. [MonetDB/X100: Hyper-Pipelining Query Execution](https://www.cidrdb.org/cidr2005/papers/P19.pdf). At *2nd Biennial Conference on Innovative Data Systems Research* (CIDR), January 2005. 
[^80]: Jingren Zhou and Kenneth A. Ross. [Implementing Database Operations Using SIMD Instructions](https://www1.cs.columbia.edu/~kar/pubsk/simd.pdf). At *ACM International Conference on Management of Data* (SIGMOD), pages 145–156, June 2002. [doi:10.1145/564691.564709](https://doi.org/10.1145/564691.564709) 
[^81]: Kevin Bartley. [OLTP Queries: Transfer Expensive Workloads to Materialize](https://materialize.com/blog/oltp-queries/). *materialize.com*, August 2024. Archived at [perma.cc/4TYM-TYD8](https://perma.cc/4TYM-TYD8) 
[^82]: Jim Gray, Surajit Chaudhuri, Adam Bosworth, Andrew Layman, Don Reichart, Murali Venkatrao, Frank Pellow, and Hamid Pirahesh. [Data Cube: A Relational Aggregation Operator Generalizing Group-By, Cross-Tab, and Sub-Totals](https://arxiv.org/pdf/cs/0701155). *Data Mining and Knowledge Discovery*, volume 1, issue 1, pages 29–53, March 2007. [doi:10.1023/A:1009726021843](https://doi.org/10.1023/A%3A1009726021843) 
[^83]: Frank Ramsak, Volker Markl, Robert Fenk, Martin Zirkel, Klaus Elhardt, and Rudolf Bayer. [Integrating the UB-Tree into a Database System Kernel](https://www.vldb.org/conf/2000/P263.pdf). At *26th International Conference on Very Large Data Bases* (VLDB), September 2000. 
[^84]: Octavian Procopiuc, Pankaj K. Agarwal, Lars Arge, and Jeffrey Scott Vitter. [Bkd-Tree: A Dynamic Scalable kd-Tree](https://users.cs.duke.edu/~pankaj/publications/papers/bkd-sstd.pdf). At *8th International Symposium on Spatial and Temporal Databases* (SSTD), pages 46–65, July 2003. [doi:10.1007/978-3-540-45072-6\_4](https://doi.org/10.1007/978-3-540-45072-6_4) 
[^85]: Joseph M. Hellerstein, Jeffrey F. Naughton, and Avi Pfeffer. [Generalized Search Trees for Database Systems](https://dsf.berkeley.edu/papers/vldb95-gist.pdf). At *21st International Conference on Very Large Data Bases* (VLDB), September 1995. 
[^86]: Isaac Brodsky. [H3: Uber’s Hexagonal Hierarchical Spatial Index](https://eng.uber.com/h3/). *eng.uber.com*, June 2018. Archived at [archive.org](https://web.archive.org/web/20240722003854/https%3A//www.uber.com/blog/h3/) 
[^87]: Robert Escriva, Bernard Wong, and Emin Gün Sirer. [HyperDex: A Distributed, Searchable Key-Value Store](https://www.cs.princeton.edu/courses/archive/fall13/cos518/papers/hyperdex.pdf). At *ACM SIGCOMM Conference*, August 2012. [doi:10.1145/2377677.2377681](https://doi.org/10.1145/2377677.2377681) 
[^88]: Christopher D. Manning, Prabhakar Raghavan, and Hinrich Schütze. [*Introduction to Information Retrieval*](https://nlp.stanford.edu/IR-book/). Cambridge University Press, 2008. ISBN: 978-0-521-86571-5, available online at [nlp.stanford.edu/IR-book](https://nlp.stanford.edu/IR-book/) 
[^89]: Jianguo Wang, Chunbin Lin, Yannis Papakonstantinou, and Steven Swanson. [An Experimental Study of Bitmap Compression vs. Inverted List Compression](https://cseweb.ucsd.edu/~swanson/papers/SIGMOD2017-ListCompression.pdf). At *ACM International Conference on Management of Data* (SIGMOD), pages 993–1008, May 2017. [doi:10.1145/3035918.3064007](https://doi.org/10.1145/3035918.3064007) 
[^90]: Adrien Grand. [What is in a Lucene Index?](https://speakerdeck.com/elasticsearch/what-is-in-a-lucene-index) At *Lucene/Solr Revolution*, November 2013. Archived at [perma.cc/Z7QN-GBYY](https://perma.cc/Z7QN-GBYY) 
[^91]: Michael McCandless. [Visualizing Lucene’s Segment Merges](https://blog.mikemccandless.com/2011/02/visualizing-lucenes-segment-merges.html). *blog.mikemccandless.com*, February 2011. Archived at [perma.cc/3ZV8-72W6](https://perma.cc/3ZV8-72W6) 
[^92]: Lukas Fittl. [Understanding Postgres GIN Indexes: The Good and the Bad](https://pganalyze.com/blog/gin-index). *pganalyze.com*, December 2021. Archived at [perma.cc/V3MW-26H6](https://perma.cc/V3MW-26H6) 
[^93]: Jimmy Angelakos. [The State of (Full) Text Search in PostgreSQL 12](https://www.youtube.com/watch?v=c8IrUHV70KQ). At *FOSDEM*, February 2020. Archived at [perma.cc/J6US-3WZS](https://perma.cc/J6US-3WZS) 
[^94]: Alexander Korotkov. [Index support for regular expression search](https://wiki.postgresql.org/images/6/6c/Index_support_for_regular_expression_search.pdf). At *PGConf.EU Prague*, October 2012. Archived at [perma.cc/5RFZ-ZKDQ](https://perma.cc/5RFZ-ZKDQ) 
[^95]: Michael McCandless. [Lucene’s FuzzyQuery Is 100 Times Faster in 4.0](https://blog.mikemccandless.com/2011/03/lucenes-fuzzyquery-is-100-times-faster.html). *blog.mikemccandless.com*, March 2011. Archived at [perma.cc/E2WC-GHTW](https://perma.cc/E2WC-GHTW) 
[^96]: Steffen Heinz, Justin Zobel, and Hugh E. Williams. [Burst Tries: A Fast, Efficient Data Structure for String Keys](https://web.archive.org/web/20130903070248id_/http%3A//ww2.cs.mu.oz.au%3A80/~jz/fulltext/acmtois02.pdf). *ACM Transactions on Information Systems*, volume 20, issue 2, pages 192–223, April 2002. [doi:10.1145/506309.506312](https://doi.org/10.1145/506309.506312) 
[^97]: Klaus U. Schulz and Stoyan Mihov. [Fast String Correction with Levenshtein Automata](https://dmice.ohsu.edu/bedricks/courses/cs655/pdf/readings/2002_Schulz.pdf). *International Journal on Document Analysis and Recognition*, volume 5, issue 1, pages 67–85, November 2002. [doi:10.1007/s10032-002-0082-8](https://doi.org/10.1007/s10032-002-0082-8) 
[^98]: Tomas Mikolov, Kai Chen, Greg Corrado, and Jeffrey Dean. [Efficient Estimation of Word Representations in Vector Space](https://arxiv.org/pdf/1301.3781). At *International Conference on Learning Representations* (ICLR), May 2013. [doi:10.48550/arXiv.1301.3781](https://doi.org/10.48550/arXiv.1301.3781) 
[^99]: Jacob Devlin, Ming-Wei Chang, Kenton Lee, and Kristina Toutanova. [BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding](https://arxiv.org/pdf/1810.04805). At *Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies*, volume 1, pages 4171–4186, June 2019. [doi:10.18653/v1/N19-1423](https://doi.org/10.18653/v1/N19-1423) 
[^100]: Alec Radford, Karthik Narasimhan, Tim Salimans, and Ilya Sutskever. [Improving Language Understanding by Generative Pre-Training](https://cdn.openai.com/research-covers/language-unsupervised/language_understanding_paper.pdf). *openai.com*, June 2018. Archived at [perma.cc/5N3C-DJ4C](https://perma.cc/5N3C-DJ4C) 
[^101]: Matthijs Douze, Maria Lomeli, and Lucas Hosseini. [Faiss indexes](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes). *github.com*, August 2024. Archived at [perma.cc/2EWG-FPBS](https://perma.cc/2EWG-FPBS) 
[^102]: Varik Matevosyan. [Understanding pgvector’s HNSW Index Storage in Postgres](https://lantern.dev/blog/pgvector-storage). *lantern.dev*, August 2024. Archived at [perma.cc/B2YB-JB59](https://perma.cc/B2YB-JB59) 
[^103]: Dmitry Baranchuk, Artem Babenko, and Yury Malkov. [Revisiting the Inverted Indices for Billion-Scale Approximate Nearest Neighbors](https://arxiv.org/pdf/1802.02422). At *European Conference on Computer Vision* (ECCV), pages 202–216, September 2018. [doi:10.1007/978-3-030-01258-8\_13](https://doi.org/10.1007/978-3-030-01258-8_13) 
[^104]: Yury A. Malkov and Dmitry A. Yashunin. [Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs](https://arxiv.org/pdf/1603.09320). *IEEE Transactions on Pattern Analysis and Machine Intelligence*, volume 42, issue 4, pages 824–836, April 2020. [doi:10.1109/TPAMI.2018.2889473](https://doi.org/10.1109/TPAMI.2018.2889473) 
