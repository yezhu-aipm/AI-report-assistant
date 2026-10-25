"""在独立进程里为一个批次生成全部 PDF 和预览图。

用法：python -m engine.run <job.json>
job.json: {analysis, content, names, outdir, workdir}
进度写入 <outdir>/progress.json，结果写入 <outdir>/result.json。
"""
import json, os, sys
from . import report

def main(path):
    job = json.load(open(path, encoding='utf-8'))
    out = job['outdir']; os.makedirs(out, exist_ok=True)
    prog = os.path.join(out, 'progress.json')
    def progress(i, n):
        json.dump({'done': i, 'total': n}, open(prog, 'w'))
    report.bind(job['analysis'], job['content'])
    names = job['names']
    keys = job.get('keys') or {n: k for k, n in enumerate(names)}
    pdfs = report.build(names, out, job['workdir'], progress, keys)
    import pymupdf as fitz
    previews = {}
    for n in names:
        k = keys[n]; doc = fitz.open(pdfs[n]); pics = []
        for p, page in enumerate(doc):
            pix = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6))
            fp = os.path.join(out, f'{k}-{p + 1}.jpg'); pix.save(fp, jpg_quality=86); pics.append(fp)
        previews[n] = pics
    json.dump({'pdfs': pdfs, 'previews': previews}, open(job.get('result_path') or os.path.join(out, 'result.json'), 'w'), ensure_ascii=False)

if __name__ == '__main__':
    main(sys.argv[1])
