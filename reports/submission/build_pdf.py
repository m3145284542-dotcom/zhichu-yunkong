"""Build the editorial report from its registered Markdown; preserve prior stages."""
from pathlib import Path
import re, json, hashlib, subprocess
import fitz

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=HERE/'technical_report.md'
EXPECTED='a48798b793185e9d4ef05d1b1d82c0d2d5896c5a7809c127649f405c88e18d0f'
assert hashlib.sha256(SOURCE.read_bytes().replace(b'\r\n', b'\n')).hexdigest()==EXPECTED
raw=SOURCE.read_text(encoding='utf-8')
qa=HERE/'qa'; qa.mkdir(exist_ok=True)
official=fitz.open(ROOT/'docs/competition_rules/2026-07_AI+能源技术报告参考大纲-科技创新组.pdf')
official[0].get_pixmap(matrix=fitz.Matrix(4,4),clip=fitz.Rect(79,30,115,49)).save(str(qa/'official_logo.png'))

def esc(t):
    return ''.join({'&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}','\\':r'\textbackslash{}'}.get(c,c) for c in t)

def inline(t):
    out=[]
    for i,p in enumerate(re.split(r'(\\\(.*?\\\)|`[^`]+`|\*\*.*?\*\*|\*[^*]+\*)',t)):
        if p.startswith(r'\('): out.append(p)
        elif p.startswith('`'):
            out.append((r'\texttt{'+esc(p[1:-1])+'}') if ' ' in p else (r'\nolinkurl{'+p[1:-1]+'}'))
        elif p.startswith('**'): out.append(r'\textbf{'+esc(p[2:-2])+'}')
        elif p.startswith('*'): out.append(r'\textit{'+esc(p[1:-1])+'}')
        else: out.append(esc(p))
    return ''.join(out)

preamble=r'''\documentclass[12pt,a4paper]{article}
\usepackage{fontspec,xeCJK,amsmath,amssymb,graphicx,geometry,tabularx,array,booktabs,fancyhdr,titlesec,needspace,xurl}
\usepackage[unicode,hidelinks,bookmarksnumbered=false]{hyperref}
\geometry{left=28mm,right=28mm,top=25mm,bottom=25mm,headheight=20pt,headsep=7mm}
\setmainfont{Times New Roman}
\setsansfont{Arial}
\setCJKmainfont{SimSun}[AutoFakeBold=2.0]
\setCJKsansfont{SimHei}[AutoFakeBold=1.5]
\setCJKmonofont{SimSun}
\setmonofont{Arial}
\hypersetup{pdftitle={智储云控——基于决策导向预测融合的建筑储能削峰优化系统},pdfauthor={},pdfsubject={AI+能源 科技创新组技术报告},pdfcreator={XeLaTeX}}
\pagestyle{fancy}\fancyhf{}
\fancyhead[L]{\includegraphics[width=10mm]{qa/official_logo.png}}
\fancyhead[R]{\fontsize{9}{11}\selectfont 第八届全球校园人工智能算法精英大赛·算法主题赛}
\fancyfoot[C]{—\quad\thepage\quad—}
\renewcommand{\headrulewidth}{0.4pt}
\setlength{\parindent}{2em}\setlength{\parskip}{2pt}
\linespread{1}\raggedbottom
\setcounter{secnumdepth}{0}\setcounter{tocdepth}{2}
\renewcommand{\contentsname}{目录}
\titleformat{\section}{\sffamily\large\bfseries}{}{0pt}{}
\titleformat{\subsection}{\sffamily\normalsize\bfseries}{}{0pt}{}
\titleformat{\subsubsection}{\normalsize\bfseries}{}{0pt}{}
\titlespacing*{\section}{0pt}{15pt}{8pt}
\titlespacing*{\subsection}{0pt}{12pt}{6pt}
\titlespacing*{\subsubsection}{0pt}{10pt}{5pt}
\widowpenalty=10000\clubpenalty=10000
\emergencystretch=2em
\hbadness=10000
\begin{document}
\thispagestyle{fancy}
\vspace*{7mm}
\begin{center}
{\sffamily\fontsize{22}{30}\selectfont 2026 年第八届\\全球校园人工智能算法精英大赛\par}
\vspace{20mm}
{\sffamily\fontsize{22}{30}\selectfont 算法主题赛\\AI+能源\\技术报告\par}
\vspace{33mm}
\begin{minipage}{125mm}
\noindent 作品名称：{\sffamily\fontsize{20}{26}\selectfont 智储云控}\par\vspace{3mm}
\noindent {\fontsize{12}{20}\selectfont ——基于决策导向预测融合的\\建筑储能削峰优化系统}\par\vspace{6mm}
\noindent 赛道组别：科技创新组\par\vspace{6mm}
\noindent 团队名称：电协\par\vspace{6mm}
\noindent 团队编号：AIC-2026-27833449
\end{minipage}
\vfill
{\fontsize{16}{20}\selectfont 日期：2026 年 9 月 5 日}\vspace{24mm}
\end{center}
\clearpage
'''
lines=raw.splitlines(); out=[preamble]; i=next(i for i,l in enumerate(lines) if l=='## 摘要'); mapping=[]
groups={1:'1. 项目背景与意义',2:'2. 技术方案与实现',7:'3. 实验结果与分析',8:'4. 创新点与应用前景',11:'5. 结论'}
group=0; sub=0; old=0; table_caption=''
while i<len(lines):
    l=lines[i]
    if not l.strip() or l.startswith('<!--'): i+=1; continue
    if l==r'\[':
        j=i+1
        while lines[j]!=r'\]': j+=1
        out.append('\n'.join(lines[i:j+1])); i=j+1;continue
    if l.startswith('## '):
        title=l[3:]
        if title=='总体架构设计':
            group=2;sub=1
            out.append(r'\section{2. 技术方案与实现}\subsection{2.1 总体架构设计}')
        elif title=='系统功能实现':
            sub+=1;out.append(r'\subsection{'+f'2.{sub} 系统功能实现'+'}')
        elif title=='摘要': out.append(r'\phantomsection\section*{摘要}\addcontentsline{toc}{section}{摘要}')
        elif re.match(r'\d+\.',title):
            n=int(title.split('.')[0]);old=n
            if n==1:out.append(r'\clearpage\tableofcontents\clearpage')
            if n in groups and n!=2:
                group+=1;sub=0
                out.append(r'\section{'+groups[n]+'}')
            sub+=1
            title2=f'{group}.{sub} '+re.sub(r'^\d+\.\s*','',title)
            if n not in [7,11]: out.append(r'\subsection{'+inline(title2)+'}')
            else: title2=groups[n]
            mapping.append({'source':title,'layout':title2,'template_group':groups[max(k for k in groups if k<=n)]})
        else:
            if title=='参考文献':out.append(r'\fontsize{10.5}{20}\selectfont')
            else:out.append(r'\normalsize')
            out.append(r'\section{'+inline(title)+'}')
        i+=1;continue
    if l.startswith('### '):
        title=l[4:]
        if title=='办公楼中的使用场景':
            out.append(r'\subsubsection{办公楼中的使用场景}')
            mapping.append({'source':title,'layout':title})
            i+=1;continue
        if title=='应用流程与部署条件':
            out.append(r'\subsubsection{4.2.1 应用流程与部署条件}');i+=1;continue
        child=title.split()[0].split('.')[-1]
        if old==7: child=str(int(child)+1)
        title2=(f'{group}.{child} ' if old==7 else f'{group}.{sub}.{child} ')+re.sub(r'^\d+\.\d+\s*','',title)
        out.append((r'\subsection{' if old==7 else r'\subsubsection{')+inline(title2)+'}');mapping.append({'source':title,'layout':title2});i+=1;continue
    if l.startswith('|'):
        rows=[]
        while i<len(lines) and lines[i].startswith('|'):
            if not re.match(r'^\|\s*:?-',lines[i]): rows.append([x.strip() for x in lines[i].strip('|').split('|')])
            i+=1
        n=len(rows[0]); spec=(r'>{\hsize=1.4\hsize\linewidth=\hsize\raggedright\arraybackslash}X'+(r'>{\hsize='+str((n-1.4)/(n-1))+r'\hsize\linewidth=\hsize\raggedright\arraybackslash}X')*(n-1)) if n>2 else r'>{\raggedright\arraybackslash}X>{\raggedright\arraybackslash}X'
        weights=None
        if rows[0][0]=='数据分区': weights=[0.55,1.10,1.55,0.80]
        elif rows[0][0]=='方法' and n==2: weights=[0.65,1.35]
        if weights:spec=''.join(r'>{\hsize='+str(w)+r'\hsize\linewidth=\hsize\raggedright\arraybackslash}X' for w in weights)
        out.append(r'\par\noindent\begin{minipage}{\linewidth}'+inline(table_caption)+r'\par\smallskip\renewcommand{\arraystretch}{1.2}\begin{tabularx}{\linewidth}{'+spec+r'}\toprule');table_caption=''
        for k,row in enumerate(rows):out.append(' & '.join(inline(x) for x in row)+r'\\'+(r'\midrule' if k==0 else ''))
        out.append(r'\bottomrule\end{tabularx}\end{minipage}\par');continue
    if l.startswith('!['):
        path=re.search(r'\]\((.*?)\)',l).group(1)
        img=(SOURCE.parent/path).resolve()
        import os
        imgpath=Path(os.path.relpath(img,HERE)).as_posix()
        if 'sci_04_' in img.name:imgpath='../phase13_6/assets/figure_04_layout.png'
        j=i+1
        while not lines[j].strip():j+=1
        assert lines[j].startswith('**图 ')
        out.append(r'\par\noindent\begin{minipage}{\linewidth}\centering\includegraphics[width=\linewidth]{'+imgpath+r'}\par\raggedright '+inline(lines[j])+r'\par\end{minipage}\par')
        i=j+1;continue
    if l.startswith('**表 '):table_caption=l;i+=1;continue
    out.append(inline(l)+r'\par')
    if l.startswith('关键词：'):out.append(r'\clearpage')
    i+=1
out.append(r'\end{document}')
(HERE/'technical_report_layout.tex').write_text('\n'.join(out),encoding='utf-8')
(qa/'heading_mapping.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),encoding='utf-8')
for _ in range(3):
    r=subprocess.run(['xelatex','-interaction=nonstopmode','-halt-on-error','-no-shell-escape','technical_report_layout.tex'],cwd=HERE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (qa/'compile_console.txt').write_bytes(r.stdout)
    if r.returncode: raise RuntimeError(r.stdout.decode(errors='replace')[-3000:])
pdf=fitz.open(HERE/'technical_report_layout.pdf')
pdf.save(HERE/'technical_report_submission.pdf',garbage=4,deflate=True)
print('Pages:',len(pdf))
