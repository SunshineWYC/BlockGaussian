# BlockGaussian 网站维护

本目录用于在 Windows 本机维护论文项目页。网站是静态 HTML、CSS 和 JavaScript，无需 npm、前端构建或后端服务。

- 本地目录：`D:\documents\papers\BlockGaussian\project_page`，对应实际目录 `D:\BaiduSyncdisk\paper\BlockGaussian\project_page`。
- 仓库：[SunshineWYC/BlockGaussian](https://github.com/SunshineWYC/BlockGaussian)
- 分支：`project-page`，上游：`origin/project-page`
- 网站：[BlockGaussian](https://sunshinewyc.github.io/BlockGaussian/)
- 发布沿用 `project-page` 分支与既有 GitHub Pages 配置；实际发布状态以 GitHub 部署记录和线上页面为准。

## 本地预览

在 PowerShell 中执行：

~~~powershell
Set-Location 'D:\documents\papers\BlockGaussian\project_page'
python -m http.server 8000 --bind 127.0.0.1
~~~

打开 <http://127.0.0.1:8000/>。修改后刷新浏览器；保持终端运行，按 Ctrl+C 停止服务。端口被其他程序占用时改用 8001。不要重复启动已有的预览服务。

网页字体、图标和交互依赖均来自本地文件。Paper 和 arXiv 按钮仍指向公开预印本 2504.09048；本地最新版 PDF 不提供网页链接。

## 文件分工

| 内容 | 文件或目录 |
| --- | --- |
| 标题、作者、资源按钮、正文、图表引用、BibTeX | index.html |
| 页面布局与手机适配 | static/css/index.css |
| 场景选择、DICS 初始化、图片查看、引用复制 | static/js/index.js |
| 原版 DICS 图片比较组件 | static/js/dics.js、static/css/dics.css |
| 动态视频比较 | static/js/video_comparison.js |
| 论文插图、表格截图、视频预览帧 | static/images/updated/ |
| 原有比较图片与七段视频 | static/images/comparison/、static/videos/ |
| 用于数据核对的论文表格记录（页面不加载） | static/data/benchmarks.json |
| 从 charts 导出展示插图 | scripts/export_figures.py |
| 从论文页面截取表格和图 | scripts/export_paper_crops.py |
| 本地原稿和 charts，不发布 | materials/ |
| 检查报告、截图、渲染缓存，不发布 | .local-preview/ |

资源采用相对路径，文件名大小写保持一致，以兼容 GitHub Pages。保留模板署名、DICS 来源及现有许可说明。

## 最新展示调整（2026-10-04）

根据本轮反馈调整：

- 桌面标题统一字号并排成两行，不再单独放大 BlockGaussian；窄屏自然换行。
- 删除首屏版本说明、The idea、Efficiency, with evidence。
- Teaser 和 Overview 直接插图，不再提供点击放大或图注。
- 方法标题改为 “Balanced blocks. Efficient reconstruction.”。
- 伪视角说明整理为一段，增大字号，移除训练迭代数和权重调度细节。
- 效率主标题在桌面显示为一行。
- 当前展示表 I、III、VI 的论文原表截图，保留原始文字、数值、着色和表注；表 II 及高斯保留分析整节（含表 V）已从页面移除。
- 保留图 8，删除其下方的差异说明；图 10 只展示下半部分的两张梯度曲线，删除四联统计展开区。删除表 VI 下方的配置说明及图 9 漂浮物消融图。
- Rendering quality 及定性结果整体前置到效率章节之前，导航顺序同步调整；效率主标题上方增加 Efficiency 标签。局限第二段改为概念性说明，删除数值及具体方法对照。
- 定性结果继续通过具名标签切换，现有新视角视频和演示区保留。
- 图片比较复用原版 DICS，直接拖动画面分隔线；动态比较复用原版左右视频裁剪合成与鼠标跟随方式，恢复分隔线和双向箭头。两处均移除额外的 Comparison position 控件。
- 动态比较在进入视口时播放，支持暂停；隐藏或离屏后暂停并停止绘制。每个场景保留独立状态，未恢复原版重复 ID、克隆节点或全局比较位置。
- 键盘用户可聚焦画面中的分隔线，使用左右方向键、Home、End。系统设置减少动态效果时，不自动开始播放。
- 删除方法与定性结果图注中的稿件版本、图号及点击放大提示，保留简洁的图意说明与图片查看功能。
- Comparison protocol 移至 Efficiency 章节末尾；Teaser 定位句移至图片下方。
- 分块耗时图重新从论文第 12 页图表区域裁剪，不展示 “Fig. 8” 及论文图注，坐标、数值和场景名称完整保留；导出脚本同步更新裁剪范围。
- 动态比较删除拖动提示，播放后也不再恢复该提示；仍保留加载失败等必要状态反馈。
- 演示区删除关于旧演示与更新结果的介绍；全页文案避免稿件版本、修订过程和素材新旧关系等编辑背景表述。摘要使用 “We introduce”，梯度图查看标题直接描述图意；实验条件、数值来源、Paper / arXiv 入口及引用保留。

没有重新生成实验视频，没有新增期刊、年份或录用信息。BibTeX 仍使用公开 arXiv 引用。

## 字体层级与内容宽度

全页使用同一套本地系统字体 Segoe UI / Arial；BibTeX 使用等宽字体。字号统一在 `static/css/index.css` 顶部的 `--type-*` 变量中维护，不再给摘要、局限、方法卡片等单独设置字号。

| 用途 | 桌面 | 平板（≤800px） | 手机（≤540px） |
| --- | --- | --- | --- |
| 论文标题 | 36px（≤1100px 时 32px） | 32px | 28px |
| 章节标题 h2 | 32px | 30px | 26px |
| 子标题 h3 | 24px | 22px | 21px |
| 正文、章节介绍、方法细节 | 18px | 18px | 17px |
| 图注、比较说明、补充说明 | 15px | 15px | 14px |
| 按钮、场景标签、导航 | 14px | 14px | 13px |
| 章节小标签、步骤编号 | 12px | 12px | 12px |

正文行高统一为 1.75，标题为 1.3，图注为 1.65。首屏定位句使用 20px（≤800px 时 18px），论文标题行高为 1.35。

Abstract、Method、Results、Efficiency、Demos、Limitations、BibTeX 及页脚共用 `.container` 的左右边界：常规桌面最大 1080px，超宽屏最大 1120px；平板左右各 20px，手机左右各 16px。不再使用正文 850px、章节介绍 820px 等独立宽度上限。

已删除 “Challenges → method” 和 “Novel-view rendering” 两处标题文字。除桌面论文标题保留两行排版外，正文不插入强制换行；标题和首屏定位句均衡折行，正文尽量避免末行只剩一个词。浏览器不支持自动折行优化时使用正常换行。

## 论文与图表来源

来源为本地 18 页论文 `materials/BlockGaussian_IEEE_TIP_R2_supp.pdf` 及 `materials/charts/`。原始文件不改动、不上传，网页仅使用展示图片。

| 展示内容 | 来源 | static/images/updated/ 文件 |
| --- | --- | --- |
| Teaser 城市场景 | 图 1 上半部分，teaser.pdf | teaser-scene.webp |
| 方法总览 | 图 3，overview.pdf | overview.png |
| 伪视角示意 | 图 4，pseudo_loss.pdf | pseudo_loss.png |
| Mill19 / UrbanScene3D 定性结果 | 图 5 | result_comparison_us3d.webp |
| MatrixCity-Aerial 定性结果 | 图 6 | result_comparison_mc_aerial.webp |
| MatrixCity-Street 定性结果 | 图 7 | result_mc_street.webp |
| 质量表 I | 论文第 9 页原表 | table-i.png |
| 耗时和模型开销表 III | 论文第 11 页原表 | table-iii.png |
| 块间耗时分析图 8 | 论文第 12 页图表区域，不含论文图注 | figure-8.png |
| 完整消融表 VI | 论文第 14 页原表 | table-vi.png |
| 梯度行为 | 论文第 14 页图 10 下半部分 | training-gradients.png |
| 分块可视化（展开） | 图 11，partition_result.pdf | partition_result.png |
| 动态比较播放前预览 | 原有 MP4 的合成画面 | rubble-video-poster.webp、residence-video-poster.webp |
| 分享图 | 论文标题与 Teaser 场景组合 | social-preview.png |

表格截图包含表号、原表说明、单位、颜色标识及完整数据行。除 Teaser 和 Overview 外，宽图仍可点击查看高分辨率版本，方便手机阅读。下方图片延迟加载。

截图脚本按检查过的页面坐标裁剪；最长页边渲染为 6800px，保留高分辨率 PNG，正文加载最长边不超过 2200px 的预览。图 10 下半部分截图只包含位置和对数尺度梯度，不混入上半部分数量／显存图。

历史导出文件可能保留在 updated/ 中，但网页只加载 index.html 实际引用的素材。reconstruction-time.svg、training-resources.png、table-ii.png、table-v.png、training-full.png、result_airspace.webp 及其预览版本不再用于当前页面。移除展示不删除原始材料。原 HTML 表格生成器已移除；benchmarks.json 保留用于核对数值和计算口径。

## 数值口径与源文件冲突

- 单张消费级 GPU 指分块顺序训练能力；表 III 耗时测试平台是 8×RTX 5090，不与单卡耗时混用。
- 首页加速按表 III 的 VastGaussian 时间 / BlockGaussian 时间逐场景计算，一位小数为 Building 5.4×、Rubble 4.9×、Residence 6.6×、Sci-Art 4.8×、MatrixCity-Aerial 4.1×、MatrixCity-Street 3.8×，因此范围是 3.8–6.6×。
- 表 V 的保留比例定义为裁剪后高斯数 / 裁剪前高斯数；BlockGaussian 四场景为 76.9%、79.8%、77.6%、73.0%。不代表模型压缩率或渲染帧率。
- 图 10 只分析 MatrixCity-Aerial 的单个 block，不代表全场景显存。
- 表 VI 完整展示，包括灰色的未采用替代配置；图下的配置说明已删除。表 VI 写作 34 分钟，表 III 为 34.1 分钟，分别保留原值。
- 局限部分概念性说明渲染质量与几何精度的区别，以及对可靠场景初始化的依赖，不再展示几何 F1 数字或具体方法对照。
- PSNR／SSIM 越大越好，LPIPS 越小越好；保留论文截图原有排名颜色，不另行改写。

已知源文件差异的处理：

1. Teaser 下方将 VastGaussian 的 Residence / Sci-Art 时间标为 324 / 304 分钟，与表 III 的 230 / 215 不同；仍只使用 Teaser 上半部分。
2. 图 8 部分逐块耗时最大值与表 V 最慢块耗时不同。按后续反馈，图 8 原样展示且删除图下说明；差异仅记录在维护文档中。总体加速继续按表 III 计算，不从图 8 推导。
3. Challenges、mismatch 大图和表 VIII–X 不进入主页面。

## 更新素材

日常修改正文、样式或交互，直接编辑并刷新页面即可，不需要执行构建。

重新从论文截取表格／图 8／图 10 下半部分：

~~~powershell
python scripts/export_paper_crops.py --pdftoppm '实际路径\pdftoppm.exe'
~~~

依赖 Pillow 和 Poppler。源稿排版变化时必须检查并调整脚本中的 CROPS 坐标，逐图核对表号、列、图例和裁剪边缘。脚本验证 PDF 哈希未改变，记录于 .local-preview/paper-crops/manifest.json。

重新从 charts 导出其他插图：

~~~powershell
python scripts/export_figures.py --pdftoppm '实际路径\pdftoppm.exe'
~~~

该工具使用 Pillow、Matplotlib 和 Poppler；不再重绘耗时图。中间结果位于 .local-preview/figure-export/。替换原视频时需同步更新预览帧；PDF 导出工具不生成视频预览。

## 同步、提交与发布

固定流程：同步 → 修改 → 本地预览 → 检查差异 → 提交 → 发布验证。

~~~powershell
git status --short --branch
git branch --show-current
~~~

工作区干净且位于 project-page 时执行：

~~~powershell
git pull --ff-only origin project-page
~~~

有未提交修改时先保留和整理，不覆盖文件。需要临时收起改动，可使用 `git stash push -u -m "Before project-page sync"`，同步后 `git stash apply`，确认完整后再清理对应 stash。此操作不备份忽略的 materials，原始资料需单独保留。遇到分歧先查看双方历史，不丢弃式重置或强制推送。

修改完成检查：

~~~powershell
git diff --check
git diff --stat
git diff
git status --short
~~~

git diff 不显示未跟踪文件内容，新增素材需单独检查。普通内容更新仅停留在本地修改与预览；用户明确要求发布时才提交并推送。

发布前在 GitHub Settings → Pages 核实当前发布来源，沿用既有分支／Actions 配置及网站地址。逐项暂存本次实际改动，检查暂存差异后再提交和推送：

~~~powershell
git add -- index.html
git diff --cached --check
git diff --cached
git commit -m "Update project page"
git push origin project-page
~~~

以上仅是修改正文的示例；其他变更须逐项加入。materials/、.local-preview/ 已被 .gitignore 排除，不要强制加入。网站仅保存展示素材；原始实验视频和中间数据放在仓库之外。沿用本机 Git 身份和凭据，不修改全局配置。

推送后核对 Pages 部署与线上页面。撤销已发布普通提交时，使用 `git revert <提交哈希>` 生成撤销提交，预览后正常推送，保留历史。

## 验收记录

初始化基线为 6079c20a1e7162d437f56cfc2352e5fbb58cff74（2025-04-15，update）；独立克隆保留 project-page 的 16 次完整提交。以下为发布前各轮本地检查的历史记录。

前轮已核对 344 个数值与论文表 I、II、III、V、VI 一致，并检查七段视频可解码。报告在 .local-preview/updated-qa/。

前轮交互调整检查在 .local-preview/revision-qa/，包括：

- 指定小字和额外位置控件删除，桌面标题两行，效率主标题一行。
- 七处论文截图加载正常、裁剪完整；Teaser / Overview 没有点击入口或图注。
- 原版 DICS 四场景切换、画面分隔线拖动、键盘操作及触摸正常。
- 动态比较的左右画面像素与原视频对应区域一致，分隔线跟随鼠标；可暂停，离屏／隐藏后停止。
- 1440×1000、768×1024、390×844 下无页面级横向溢出。
- Chrome 检查无页面脚本错误或资源加载失败。未在 Safari / Firefox 实测。
- 原始 PDF 未变；本地材料未被 Git 跟踪。未提交、未推送，线上网站维持原版本。

本轮精简后，主展示顺序为：Abstract → Method → Rendering quality → Efficiency → Demos → Limitations → BibTeX。首页保留比例要点沿用表 V 来源文字，已移除指向被删除章节的跳转链接。页面结构和桌面／手机布局检查记录在 .local-preview/layout-trim-qa/。

字体与宽度统一后的检查记录在 `.local-preview/typography-qa/`：1440、768、390px 视口下，所有主章节左右边界一致；正文分别为 18、18、17px，同级标题字号一致，展开后的方法细节亦遵循正文规格。桌面论文标题仍为两行，效率主标题仍为一行。已逐模块检查截图，场景切换、比较滑块键盘操作、动态场景切换及图片查看正常，无页面横向溢出、脚本报错或资源加载失败。本次仅修改 HTML、CSS 和维护说明，未提交或发布。

图注精简及位置调整的检查记录在 `.local-preview/caption-cleanup-qa/`：桌面与 390px 手机布局正常；Comparison protocol 为 Efficiency 最后一项，Teaser 定位句位于图下。Rubble、Residence 动态比较均可播放和暂停，已删除的提示不会再次出现。分块耗时图的预览与放大版本均已去除论文图注，原始 PDF 哈希未变。本轮仍仅作本地更新。

## 部署前终检（2026-10-04）

已复核全页正文、展开内容、场景切换后的文案、图注、替代文本、分享信息与 BibTeX。页面没有稿件版本说明、编辑过程说明或占位链接；Paper / arXiv 继续使用公开预印本。

本次修正：

- 分享标题统一为完整论文标题，与浏览器标题及首屏一致。
- 分块细节明确逐个场景对应的块数，避免仅列数字产生歧义。
- 图 10 下半部分的标题改为训练梯度行为描述，与实际展示内容一致。
- 保留原版 DICS 外观和拖动方式，修复窗口连续缩放后图片比例错误，以及键盘操作后再拖动时分隔线和画面不同步的问题；场景切换等待图片解码后再更新尺寸。

核对结果：

- 重新核对表 I、II、III、V、VI 的 344 个记录值，首页加速和保留比例计算一致。13 个原始 PDF 的哈希未变；5 张论文截图的高分辨率版本与对应原页面裁剪像素一致。
- 检查 35 个本地资源引用、路径大小写和页内跳转；9 个外部链接均返回 HTTP 200。`materials/` 与 `.local-preview/` 均不在待提交文件中。
- Chrome 在 1440、768、390、320px 宽度下无页面横向溢出；各模块边界和同级文字规格一致。已检查桌面标题两行、效率标题一行，以及手机图像查看。
- 10 张高分辨率图像的查看、缩放与关闭正常；三组定性结果可切换；4 组图片比较通过鼠标、键盘、触摸模拟和连续缩放检查。
- 5 段场景视频与 2 段动态比较均可播放、暂停；动态比较左右画面与源视频对应区域一致，隐藏场景停止播放。BibTeX 已实际复制并核对剪贴板内容。
- 禁用 JavaScript 后仍能阅读定性结果和表格。检查期间无页面脚本异常或 HTTP 资源错误。

报告和截图位于 `.local-preview/release-qa/`。移动端使用 Chrome 视口及触摸模拟，未在实体手机或 Safari / Firefox 上实测。图 8 与表 V 的既有差异沿用前述处理决定，未改写原图数据，也未重新加入已要求删除的页面说明；总体加速只依据表 III。

终检阶段仅完成本地检查和修正。后续发布已获用户授权：提交当前确认的网页、实际引用的展示素材及维护文件，原始论文、检查缓存和未使用的导出图保留在本地；部署完成后检查线上资源与页面。

BibTeX 使用用户确认的 `@article{wu2025blockgaussian, ...}` 条目，保留其标题大小写、姓在前的作者格式、`journal={arXiv preprint arXiv:2504.09048}` 和 2025 年份。展示继续采用简洁的 BibTeX 标题及浅灰代码块，保留复制按钮和窄屏局部横向滚动；复制内容直接读取该条目。
