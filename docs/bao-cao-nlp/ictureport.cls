% ==============================================================================
% LỚP TÀI LIỆU BÁO CÁO DỰ ÁN HỌC PHẦN XỬ LÝ NGÔN NGỮ TỰ NHIÊN - ICTU (giữ định dạng lớp báo cáo Học sâu)
% Mô phỏng định dạng tệp Word mẫu "BAO CAO DU AN _Hoc sau_NHOM 1"
%   - A4; lề trên 3 cm, dưới 3,5 cm, trái 3,5 cm, phải 2 cm; chân trang 2 cm
%   - Văn bản (0_TEXT_c1): Times New Roman 13, căn đều, thụt dòng 1,2 cm,
%     giãn dòng 1,5, cách đoạn 6 pt
%   - Chương (1_Chapter_c5): 16 pt, đậm, căn giữa, giãn 1,3, trước 6 pt, sau 18 pt
%   - Mục cấp 2 (2_1_Level2_c2): 14 pt đậm; cấp 3 (3_1_1_Level3_c3): 13 pt đậm
%   - Chú thích hình (4_Figures_c6) / bảng (5_Tables_c7): 13 pt nghiêng, căn giữa
%   - Số trang: Times New Roman 13, giữa chân trang
% Biên dịch: XeLaTeX + Biber
% ==============================================================================
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{ictureport}[2026/11/23 Bao cao du an Xu ly ngon ngu tu nhien - ICTU]

\LoadClass[a4paper,12pt,oneside,openany]{report}

% ------------------------------------------------------------------------------
% Phông chữ
% ------------------------------------------------------------------------------
\RequirePackage{amsmath}
\RequirePackage{amssymb}
\RequirePackage[varg]{newtxmath}
\RequirePackage{fontspec}
\setmainfont{Times New Roman}
\setsansfont{Times New Roman}
\setmonofont{Courier New}[Scale=0.95]

% Cỡ chữ (Word: dòng đơn TNR = 1,15 x cỡ chữ; giãn 1,5 = 1,725 x cỡ chữ)
\renewcommand{\normalsize}{\fontsize{13}{22.4}\selectfont
  \abovedisplayskip 6pt plus 2pt minus 2pt
  \belowdisplayskip 6pt plus 2pt minus 2pt
  \abovedisplayshortskip 3pt \belowdisplayshortskip 3pt}
\renewcommand{\small}{\fontsize{11}{14}\selectfont}
\renewcommand{\footnotesize}{\fontsize{10}{12.5}\selectfont}
\renewcommand{\scriptsize}{\fontsize{8}{10}\selectfont}
\renewcommand{\tiny}{\fontsize{6}{7.5}\selectfont}
\renewcommand{\large}{\fontsize{14}{18}\selectfont}
\renewcommand{\Large}{\fontsize{16}{21}\selectfont}
\normalsize

% ------------------------------------------------------------------------------
% Khổ giấy và lề
% ------------------------------------------------------------------------------
\RequirePackage[
    a4paper,
    top=30mm,
    bottom=35mm,
    left=35mm,
    right=20mm,
    headheight=14pt,
    headsep=6mm,
    footskip=15mm
]{geometry}

% ------------------------------------------------------------------------------
% Gói hỗ trợ
% ------------------------------------------------------------------------------
\RequirePackage{xcolor}
\definecolor{AccentBlue}{HTML}{1F4E79}
\definecolor{AccentLightBlue}{HTML}{DEEAF6}
\definecolor{AccentGray}{HTML}{A6A6A6}
\definecolor{AccentDarkGray}{HTML}{333333}
\definecolor{CodeBg}{HTML}{F7F7F7}
\definecolor{CodeBorder}{HTML}{808080}

\RequirePackage{graphicx}
\RequirePackage{fancyhdr}
\RequirePackage{titlesec}
\RequirePackage{titletoc}
\RequirePackage{array}
\RequirePackage{booktabs}
\RequirePackage{tabularx}
\RequirePackage{longtable}
\RequirePackage{multirow}
\RequirePackage{colortbl}
\RequirePackage{caption}
\RequirePackage{listings}
\RequirePackage{enumitem}
\RequirePackage{setspace}
\RequirePackage{etoolbox}
\RequirePackage{indentfirst}   % mẫu thụt dòng mọi đoạn, kể cả đoạn đầu sau tiêu đề

% ------------------------------------------------------------------------------
% Đoạn văn (0_TEXT_c1)
% ------------------------------------------------------------------------------
\setlength{\parindent}{1.2cm}
\setlength{\parskip}{6pt plus 1pt minus 1pt}
\setlength{\emergencystretch}{3em}
\hyphenpenalty=5000
\tolerance=2000
\renewcommand{\arraystretch}{1.25}

% Danh sách: gạch đầu dòng "-" như trong mẫu, thụt theo đoạn văn
\setlist{itemsep=2pt,parsep=0pt,topsep=3pt}
\setlist[itemize,1]{label={-},leftmargin=*,labelindent=1.2cm}
\setlist[itemize,2]{label={+},leftmargin=*,labelindent=0.6cm}
\setlist[enumerate]{leftmargin=*,labelindent=1.2cm}

% ------------------------------------------------------------------------------
% Tên gọi tiếng Việt
% ------------------------------------------------------------------------------
\renewcommand{\chaptername}{CHƯƠNG}
\renewcommand{\appendixname}{PHỤ LỤC}
\renewcommand{\contentsname}{MỤC LỤC}
\renewcommand{\listfigurename}{DANH SÁCH CÁC HÌNH}
\renewcommand{\listtablename}{DANH SÁCH CÁC BẢNG}
\renewcommand{\figurename}{Hình}
\renewcommand{\tablename}{Bảng}
\renewcommand{\lstlistingname}{Đoạn mã}

% ------------------------------------------------------------------------------
% Chú thích hình / bảng (4_Figures_c6, 5_Tables_c7)
% "Hình 1.1. Nội dung" - nghiêng, căn giữa; hình: chú thích dưới; bảng: trên
% ------------------------------------------------------------------------------
\DeclareCaptionLabelSeparator{dotspace}{.\ }
\captionsetup{
    font={it},
    labelfont={it},
    labelsep=dotspace,
    justification=centering,
    singlelinecheck=true,
    skip=6pt
}
\captionsetup[table]{position=top}
\captionsetup[figure]{position=bottom}
\captionsetup[lstlisting]{font={it},labelsep=dotspace}

% Đánh số chú thích theo chương: 1.1, 1.2, ...
\renewcommand{\thefigure}{\thechapter.\arabic{figure}}
\renewcommand{\thetable}{\thechapter.\arabic{table}}
\renewcommand{\theequation}{\thechapter.\arabic{equation}}

% ------------------------------------------------------------------------------
% Tiêu đề chương (1_Chapter_c5): "CHƯƠNG 1. TÊN CHƯƠNG"
% ------------------------------------------------------------------------------
\titleformat{\chapter}[block]
  {\normalfont\Large\bfseries\filcenter\setstretch{1.1}}
  {\MakeUppercase{\@chapapp}~\thechapter.}
  {0.3em}
  {}% tiêu đề chương viết sẵn chữ hoa trong mã nguồn (giữ nguyên "CMAFuse")
\titlespacing*{\chapter}{0pt}{-14pt}{18pt}

\titleformat{name=\chapter,numberless}[block]
  {\normalfont\Large\bfseries\filcenter\setstretch{1.1}}
  {}
  {0pt}
  {\MakeUppercase}
\titlespacing*{name=\chapter,numberless}{0pt}{-14pt}{18pt}

% Mục cấp 2 (2_1_Level2_c2): "1.1. Tên mục" - 14 pt đậm
\titleformat{\section}
  {\normalfont\large\bfseries\setstretch{1.1}}
  {\thesection.}
  {0.4em}
  {}
\titlespacing*{\section}{0pt}{10pt plus 2pt minus 2pt}{4pt plus 1pt}

% Mục cấp 3 (3_1_1_Level3_c3): "1.1.1. Tên mục" - 13 pt đậm
\titleformat{\subsection}
  {\normalfont\normalsize\bfseries\setstretch{1.1}}
  {\thesubsection.}
  {0.4em}
  {}
\titlespacing*{\subsection}{0pt}{8pt plus 2pt minus 2pt}{3pt plus 1pt}

% Mục cấp 4 (mẫu không quy định): "a) Tên mục" - 13 pt đậm (không nghiêng), không vào mục lục
\setcounter{secnumdepth}{3}
\renewcommand{\thesubsubsection}{\alph{subsubsection})}
\titleformat{\subsubsection}
  {\normalfont\normalsize\bfseries}
  {\thesubsubsection}
  {0.4em}
  {}
\titlespacing*{\subsubsection}{0pt}{6pt plus 2pt minus 2pt}{2pt}

% Đoạn có nhãn chạy đầu dòng (run-in): chữ thường như văn bản, giữ thụt đầu dòng
\titleformat{\paragraph}[runin]
  {\normalfont\normalsize}
  {}
  {0pt}
  {\hspace*{\parindent}}
\titlespacing*{\paragraph}{0pt}{6pt plus 1pt minus 1pt}{0.5em}

% Tiêu đề không đánh số (dùng cho Mở đầu, Kết luận): 13 pt đậm
\newcommand{\plainheading}[1]{%
  \par\addvspace{8pt}{\noindent\normalfont\normalsize\bfseries #1\par}\nobreak\vspace{3pt}\nobreak}

% Chương không đánh số nhưng có mặt trong mục lục
\newcommand{\unnumberedchapter}[1]{%
  \chapter*{#1}%
  \addcontentsline{toc}{chapter}{\texorpdfstring{\MakeUppercase{#1}}{#1}}%
  \markboth{#1}{#1}}

% ------------------------------------------------------------------------------
% Mục lục (toc 1, toc 2, toc 3) và danh sách hình/bảng (toc 4, toc 5)
% ------------------------------------------------------------------------------
\setcounter{tocdepth}{2}
\contentsmargin{2em}
\titlecontents{chapter}[0pt]
  {\addvspace{6pt}\normalfont\bfseries}
  {\MakeUppercase{\chaptername}~\thecontentslabel.\ }
  {}
  {\titlerule*[0.5pc]{.}\contentspage}
\titlecontents{section}[1.9cm]
  {\addvspace{2pt}\normalfont}
  {\contentslabel[\thecontentslabel.]{0.9cm}}
  {}
  {\titlerule*[0.5pc]{.}\contentspage}
\titlecontents{subsection}[3.0cm]
  {\normalfont}
  {\contentslabel[\thecontentslabel.]{1.3cm}}
  {}
  {\titlerule*[0.5pc]{.}\contentspage}
\titlecontents{figure}[0pt]
  {\addvspace{2pt}\normalfont}
  {\figurename~\thecontentslabel.\ }
  {}
  {\titlerule*[0.5pc]{.}\contentspage}
\titlecontents{table}[0pt]
  {\addvspace{2pt}\normalfont}
  {\tablename~\thecontentslabel.\ }
  {}
  {\titlerule*[0.5pc]{.}\contentspage}
\titlecontents{lstlisting}[0pt]
  {\addvspace{2pt}\normalfont}
  {\lstlistingname~\thecontentslabel.\ }
  {}
  {\titlerule*[0.5pc]{.}\contentspage}

% Mục lục, danh sách bảng, danh sách hình đều có mặt trong mục lục (như mẫu)
\renewcommand{\tableofcontents}{%
  \chapter*{\contentsname}\addcontentsline{toc}{chapter}{\contentsname}%
  {\setstretch{1.15}\@starttoc{toc}}}
\renewcommand{\listoftables}{%
  \chapter*{\listtablename}\addcontentsline{toc}{chapter}{\listtablename}%
  {\setstretch{1.15}\@starttoc{lot}}}
\renewcommand{\listoffigures}{%
  \chapter*{\listfigurename}\addcontentsline{toc}{chapter}{\listfigurename}%
  {\setstretch{1.15}\@starttoc{lof}}}

% Không chèn khoảng trống theo chương vào danh sách hình/bảng
\makeatletter
\patchcmd{\@chapter}{\addtocontents{lof}{\protect\addvspace{10\p@}}}{}{}{}
\patchcmd{\@chapter}{\addtocontents{lot}{\protect\addvspace{10\p@}}}{}{}{}
\makeatother

% ------------------------------------------------------------------------------
% Đầu trang / chân trang: chỉ số trang ở giữa chân trang, TNR 13
% ------------------------------------------------------------------------------
\pagestyle{fancy}
\fancyhf{}
\fancyfoot[C]{\normalfont\normalsize\thepage}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}
\fancypagestyle{plain}{%
  \fancyhf{}%
  \fancyfoot[C]{\normalfont\normalsize\thepage}%
  \renewcommand{\headrulewidth}{0pt}%
  \renewcommand{\footrulewidth}{0pt}}

% ------------------------------------------------------------------------------
% Đoạn mã (mẫu không quy định): Courier New, đóng khung
% ------------------------------------------------------------------------------
\lstdefinestyle{ictulisting}{
    backgroundcolor=\color{CodeBg},
    commentstyle=\color{gray}\itshape,
    keywordstyle=\bfseries,
    numberstyle=\scriptsize\color{gray}\ttfamily,
    stringstyle=\color{AccentDarkGray},
    basicstyle=\fontsize{8.5}{10.5}\selectfont\ttfamily,
    breakatwhitespace=false,
    breaklines=true,
    captionpos=t,
    keepspaces=true,
    numbers=left,
    numbersep=6pt,
    showspaces=false,
    showstringspaces=false,
    showtabs=false,
    tabsize=4,
    frame=single,
    rulecolor=\color{CodeBorder},
    xleftmargin=14pt,
    framexleftmargin=4pt,
    extendedchars=true,
    inputencoding=utf8
}
\lstset{style=ictulisting}
\AtBeginDocument{\renewcommand{\thelstlisting}{\ifnum\value{chapter}>0 \thechapter.\fi\arabic{lstlisting}}}

% ------------------------------------------------------------------------------
% Bảng: kiểu "Table Grid" của Word (khung lưới đầy đủ)
% Các lệnh booktabs được quy về đường kẻ đơn
% ------------------------------------------------------------------------------
\setlength{\arrayrulewidth}{0.5pt}
\renewcommand{\toprule}{\hline}
\renewcommand{\midrule}{\hline}
\renewcommand{\bottomrule}{\hline}
\AtBeginEnvironment{table}{\setstretch{1.0}}
\AtBeginEnvironment{longtable}{\setstretch{1.0}}
\AtBeginEnvironment{figure}{\setstretch{1.0}}

% ------------------------------------------------------------------------------
% Trang bìa (theo bảng bìa trong mẫu Word, khung viền đôi 16 x 24 cm)
% ------------------------------------------------------------------------------
\RequirePackage{tikz}
\usetikzlibrary{calc}
\newcommand{\coverframe}{%
  \begin{tikzpicture}[remember picture,overlay]
    \coordinate (C) at ($(current page.south west)+(35mm,35mm)+(0.5\textwidth,0.5\textheight)$);
    \draw[line width=2.6pt] ($(C)+(-80mm,-120mm)$) rectangle ($(C)+(80mm,120mm)$);
    \draw[line width=0.8pt] ($(C)+(-78.3mm,-118.3mm)$) rectangle ($(C)+(78.3mm,118.3mm)$);
  \end{tikzpicture}}

% Mỗi hàng của bảng bìa trong mẫu có chiều cao cố định (đổi từ twip sang cm)
\newcommand{\coverrow}[3][c]{%
  \noindent\parbox[t][#2][#1]{\textwidth}{#3}\par\nointerlineskip}
\newcommand{\coverlabel}[2]{%
  \noindent\hspace*{2.4cm}\makebox[5.6cm][l]{#1}#2\par}

\newcommand{\makecoverpage}{%
  \begin{titlepage}
    \thispagestyle{empty}
    \coverframe
    \setlength{\parskip}{0pt}%
    \setlength{\parindent}{0pt}%
    \vspace*{-0.3cm}%
    \coverrow{0.2cm}{}%
    \coverrow[t]{1.4cm}{\centering\fontsize{13}{17}\selectfont
       TRƯỜNG ĐẠI HỌC CÔNG NGHỆ THÔNG TIN VÀ TRUYỀN THÔNG\par
       \textbf{KHOA CÔNG NGHỆ THÔNG TIN}\par\vspace{2pt}\rule{7cm}{0.5pt}\par}%
    \coverrow{0.6cm}{}%
    \coverrow{4.0cm}{\centering\includegraphics[width=4cm,height=4cm,keepaspectratio]{\logoPath}\par}%
    \coverrow{0.8cm}{}%
    \coverrow{2.5cm}{\centering
       {\fontsize{24}{30}\selectfont\bfseries BÁO CÁO DỰ ÁN\par}
       {\fontsize{19}{25}\selectfont\bfseries HỌC PHẦN XỬ LÝ NGÔN NGỮ TỰ NHIÊN\par}}%
    \coverrow{0.8cm}{}%
    \coverrow[t]{0.8cm}{\hspace*{1cm}\fontsize{13}{16}\selectfont\bfseries Đề tài:\par}%
    \coverrow{2.6cm}{\centering\fontsize{16}{24}\selectfont\bfseries \coverTitle\par}%
    \coverrow[t]{1.0cm}{\fontsize{14}{21}\selectfont\bfseries\coverlabel{Tên nhóm:}{\groupName}}%
    \coverrow[t]{3.2cm}{\fontsize{14}{21}\selectfont\bfseries
       \coverlabel{Sinh viên thực hiện:}{\memberOne}
       \coverlabel{}{\memberTwo}
       \coverlabel{}{\memberThree}
       \coverlabel{}{\memberFour}}%
    \coverrow[t]{1.0cm}{\fontsize{14}{21}\selectfont\bfseries\coverlabel{Giảng viên hướng dẫn:}{\instructorName}}%
    \vfill
    {\centering\fontsize{14}{17}\selectfont\bfseries THÁI NGUYÊN, NĂM \reportYear\par}
    \vspace*{0.3cm}
  \end{titlepage}}

\endinput
