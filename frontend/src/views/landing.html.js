export default `  <section class="lsec hero" id="hero">
    <div class="in">
      <div>
        <h1><span class="blur" data-split>上传三份材料，</span><br><span class="shiny">全班报告一次生成</span></h1>
        <p class="lead">试卷、逐题成绩表、出门测记录表交给它。分数怎么算、错在哪、下一步怎么补，它写成一份家长看得懂的三页 PDF，全班每人一份。</p>
        <div class="cta"><button class="lb hot lg" data-go="reg">免费开始使用</button><a class="lb lg" href="#dissect">看一份报告</a></div>
        <div class="facts"><div><b>3 份</b>老师上传的材料</div><div><b>5 步</b>从上传到下载</div><div><b>6 个</b>报告分析模块</div></div>
      </div>
      <div class="stage3" aria-hidden="true">
        <div class="halo"></div>
        <div class="tilt3" id="tilt3"><div class="hc" style="--i:0" id="hc1"></div><div class="hc" style="--i:1" id="hc2"></div><div class="hc" style="--i:2" id="hc3"></div></div>
      </div>
    </div>
  </section>

  <section class="lsec vsec veil" id="vs"><div class="in">
    <h2 class="sh2 rv">以前一晚上的活，现在三步</h2>
    <p class="shp rv" style="--d:.08s">期中考完，老师要给每位家长一份像样的反馈。以前全靠手工，现在交给系统，老师只做需要判断的事。</p>
    <div class="vs rv" id="vsBox" style="--d:.12s">
      <div class="gl col old"><h3>以前 · 老师手工</h3><p class="kick">每个班、每次考试都要重来一遍</p>
        <ol>
          <li style="--k:0"><i>1</i><span>对着成绩表一题一题算得分率</span></li>
          <li style="--k:1"><i>2</i><span>翻出门测记录，逐讲对照谁没听懂</span></li>
          <li style="--k:2"><i>3</i><span>判断每个孩子丢的分属于哪一类</span></li>
          <li style="--k:3"><i>4</i><span>给每个孩子写建议和寄语</span></li>
          <li style="--k:4"><i>5</i><span>做图、排版、导出成一份份报告</span></li>
          <li style="--k:5"><i>6</i><span>发出去之前再核一遍数字</span></li>
        </ol>
        <div class="tot"><b>6 件事</b>× 每位学生</div></div>
      <div class="mid"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg></div>
      <div class="gl col new glow"><h3>现在 · 交给学情报告助手</h3><p class="kick">计算、分析、写作和排版由系统完成</p>
        <ol>
          <li><i>1</i><div>上传三份材料<small>试卷、逐题成绩表、出门测记录表</small></div></li>
          <li><i>2</i><div>核对被标出来的几格<small>超满分、对不上的总分会先拦下来</small></div></li>
          <li><i>3</i><div>看一眼寄语，下载全班<small>每人一份三页 PDF，打包成 zip</small></div></li>
        </ol>
        <div class="tot"><b>3 步</b>× 整个班级</div></div>
    </div>
  </div></section>

  <section class="lsec flow veil" id="flow"><div class="in">
    <h2 class="sh2 rv">老师只做三件事</h2>
    <p class="shp rv" style="--d:.08s">上传、核对、确认。中间的计算和写作全部交给系统。</p>
    <div class="steps3">
      <div class="gl glow s3 rv" style="--d:.05s"><span class="k">第一步</span><h3>上传三份材料</h3><p>图片、PDF、Word、Excel 都可以。想在报告里推荐后续课程，就再传一份续报课程大纲。</p>
        <div class="vis"><div class="mf"><i>PDF</i>26秋期中测试卷.pdf<u></u></div><div class="mf"><i>XLSX</i>期中逐题成绩表.xlsx<u></u></div><div class="mf"><i>JPG</i>出门测登分表.jpg<u></u></div></div></div>
      <div class="gl glow s3 rv" style="--d:.15s"><span class="k">第二步</span><h3>只核对被标出来的地方</h3><p>系统先算一遍总分、查一遍满分、对一遍名单。有问题的格子标红，点一下就能改。</p>
        <div class="vis"><div class="mi r"><b>必须处理</b>吴语桐 · 第 18(1) 题 4 分，超过满分 3 分</div><div class="mi y"><b>提示</b>许嘉树 · 第 11 题识别没把握</div><div class="mi g"><b>已处理</b>改为 3 分，合计重新计算</div></div></div>
      <div class="gl glow s3 rv" style="--d:.25s"><span class="k">第三步</span><h3>预览、改寄语、下载</h3><p>数字由系统算好，老师只看一眼一句话总结和寄语，全班报告打包下载。</p>
        <div class="vis minis" id="minis"></div></div>
    </div>
  </div></section>

  <section class="lsec dsec veil" id="dissect"><div class="in">
    <h2 class="sh2 rv">一份报告，拆开看</h2>
    <p class="shp rv" style="--d:.08s">每位学生三页，六个模块，从“考得怎么样”一路讲到“下一步怎么做”。点一个模块，看它在报告里的哪个位置。</p>
    <div class="dis">
      <div class="gl dview rv" style="--d:.1s">
        <div class="dtop"><div class="seg" id="dStu" role="group" aria-label="切换示例学生"></div><span id="dPage">第 1 页 / 共 3 页</span></div>
        <div class="dpaper" id="dPaper"><div class="dmark" id="dMark"></div></div>
      </div>
      <ol class="dlist rv" id="dList" style="--d:.18s"></ol>
    </div>
  </div></section>

  <section class="lsec why veil" id="why"><div class="in">
    <h2 class="sh2 rv">数字由程序算，文字由大模型写</h2>
    <p class="shp rv" style="--d:.08s">报告里的每个数字都按固定规则计算，同样的成绩永远得到同样的报告。大模型只负责读懂材料，把结论写成家长听得懂的话。</p>
    <div class="bento">
      <div class="gl glow bt w4 rv"><h3>每个数字都能追溯</h3><p>班均、得分率、失分类型、提分潜力，全部按公开的规则计算。</p>
        <div class="bvis formula">班均 = 全班总分 ÷ 人数 = <em>83.1</em><br>第 13 题全班得分率 <em>40%</em> → 归为全班难题<br>提分潜力 = 个人漏洞 + 常规失分 + 全班难题 × 0.5 = <em>+9 分</em></div></div>
      <div class="gl glow bt w2 rv" style="--d:.08s"><h3>错数据进不了报告</h3><p>超满分、总分对不上、名单不一致，都会先拦下来。</p>
        <div class="bvis"><div class="mi r"><b>必须处理</b>第 18(1) 题 4 分 &gt; 满分 3 分</div></div></div>
      <div class="gl glow bt w3 rv"><h3>课堂和考试放在一起看</h3><p>出门测反映当堂听懂多少，期中检验一个多月后还记得多少。</p>
        <div class="bvis"><div class="drow">第 4 讲 出门测 <i class="n"></i><i class="n"></i><i class="n"></i><i></i> <s>→ 期中 80%</s><mark>已经补上</mark></div>
          <div class="drow">第 6 讲 出门测 <i></i><i></i><i></i><i></i> <s>→ 期中 50%</s><mark class="y">考试失分</mark></div></div></div>
      <div class="gl glow bt w3 rv" style="--d:.08s"><h3>课程规划按需出现</h3><p>上传续报课程大纲，报告就多一个模块，把孩子最需要补的那一讲和后续课程连起来。</p>
        <div class="bvis"><span class="tg"><span></span>已上传续报课程大纲 · 报告含课程规划</span></div></div>
    </div>
  </div></section>

  <section class="lsec final"><div class="in">
    <h2 class="rv">下次考完试，<span class="shiny">把反馈交给它</span></h2>
    <p class="rv" style="--d:.08s">注册账号就能用，第一版免费。</p>
    <div class="cta rv" style="--d:.16s"><button class="lb hot lg" data-go="reg">免费开始使用</button><button class="lb lg" data-go="login">我已有账号</button></div>
  </div></section>
  <footer class="lfoot"><div class="in"><span>学情报告助手 · 个人项目</span><span>界面原型：学生姓名与成绩均为示例数据</span></div></footer>`;
