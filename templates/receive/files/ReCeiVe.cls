%% ReCeiVe.cls -- class for the ReCeiVe template (cv-templates/ReCeiVe.tex, original by Ged Lex).
%% The original class (LuaLaTeX only) was not included, so this is a compatible reimplementation written
%% for CV Creator. It compiles with pdfLaTeX, XeLaTeX and LuaLaTeX and keeps the template's interface:
%%   options leftPos/rightPos; \background \photo \name \address \mobile \email \github \linkedin
%%   \homepage \twitter \xing \stackoverflow \skype \reddit \extrainfo \position \headwords \quote
%%   \aboutMe \skillset \languages \hobbies \nonProfit \userSection \makecvheader \makecvsidebar
%%   \makecvfooter, colours highlight/darktext/text/graytext/lighttext.
%% Main-column content commands (the original kept them in cvSections/*.tex, also not included):
%%   \cvsection{title}  \cvevent{dates}{title}{organisation}{location}  \skillbar{name}{0..1}
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{ReCeiVe}[2026/10/30 v1.0 ReCeiVe-compatible CV class (CV Creator reimplementation)]

\newif\ifrcv@right
\DeclareOption{rightPos}{\rcv@righttrue}
\DeclareOption{leftPos}{\rcv@rightfalse}
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax
\LoadClass{article}

\RequirePackage{iftex}
\ifPDFTeX
  \RequirePackage[T1]{fontenc}
\fi
\RequirePackage[sfdefault]{roboto}
\RequirePackage[dvipsnames]{xcolor}
\RequirePackage{tikz}
\RequirePackage{fontawesome5}
\RequirePackage{graphicx}
\RequirePackage{etoolbox}
\RequirePackage{enumitem}
\RequirePackage{eso-pic}
\RequirePackage[absolute,overlay]{textpos}
\RequirePackage{fancyhdr}
\RequirePackage[hidelinks]{hyperref}

%% ------------------------------------------------------------------ colours
\providecolor{lightblue}{HTML}{5DA9E9}
\providecolor{concrete}{HTML}{95A5A6}
\definecolor{highlight}{HTML}{1F6E8C}
\definecolor{darktext}{HTML}{2B2B2B}
\definecolor{text}{HTML}{414141}
\definecolor{graytext}{HTML}{7A7A7A}
\definecolor{lighttext}{HTML}{D5D5D5}
\definecolor{sidebarbg}{HTML}{F1F3F4}

%% ------------------------------------------------------------------ geometry
\newlength{\rcv@sidebarwidth}
\setlength{\rcv@sidebarwidth}{6.2cm}
\newlength{\rcv@sidepad}
\setlength{\rcv@sidepad}{0.6cm}
\ifrcv@right
  \RequirePackage[left=1.4cm, right=\dimexpr\rcv@sidebarwidth+0.9cm\relax, top=1.4cm, bottom=1.8cm, footskip=0.9cm]{geometry}
\else
  \RequirePackage[left=\dimexpr\rcv@sidebarwidth+0.9cm\relax, right=1.4cm, top=1.4cm, bottom=1.8cm, footskip=0.9cm]{geometry}
\fi
\setlength{\parindent}{0pt}
\setlength{\TPHorizModule}{1cm}
\setlength{\TPVertModule}{1cm}
\AtBeginDocument{\color{text}\raggedright}

% Sidebar band on every page, background picture (if any) below it
\def\rcv@background{}
\newcommand{\background}[1]{\def\rcv@background{#1}}
\AddToShipoutPictureBG{%
  \ifx\rcv@background\@empty\else
    \IfFileExists{\rcv@background}{\AtPageLowerLeft{\includegraphics[width=\paperwidth,height=\paperheight]{\rcv@background}}}{}%
  \fi
  \AtPageLowerLeft{%
    \ifrcv@right\hspace*{\dimexpr\paperwidth-\rcv@sidebarwidth\relax}\fi
    {\color{sidebarbg}\rule{\rcv@sidebarwidth}{\paperheight}}}}

%% ------------------------------------------------------------------ personal data
\def\rcv@firstname{}\def\rcv@lastname{}
\def\rcv@position{}\def\rcv@headwords{}\def\rcv@quote{}
\def\rcv@photo{}\def\rcv@photosize{2.5cm}\def\rcv@photoopts{}
\def\rcv@contacts{}
\def\rcv@aboutme{}\def\rcv@skills{}\def\rcv@skilllabel{}\def\rcv@languages{}
\def\rcv@hobbies{}\def\rcv@nonprofit{}\def\rcv@usersections{}

\providecommand{\name}{}
\renewcommand{\name}[2]{\def\rcv@firstname{#1}\def\rcv@lastname{#2}}
\newcommand{\position}[1]{\def\rcv@position{#1}}
\newcommand{\headwords}[1]{\def\rcv@headwords{#1}}
\renewcommand{\quote}[1]{\def\rcv@quote{#1}}
\NewDocumentCommand{\photo}{O{circle} m m}{\def\rcv@photoopts{#1}\def\rcv@photosize{#2}\def\rcv@photo{#3}}

% icon, text, link (may be empty)
\newcommand{\rcv@contact}[3]{\appto\rcv@contacts{\rcv@contactline{#1}{#2}{#3}}}
\newcommand{\rcv@contactline}[3]{%
  \makebox[1.4em][l]{\color{highlight}#1}%
  \parbox[t]{\dimexpr\linewidth-1.4em\relax}{\raggedright\footnotesize\ifstrempty{#3}{#2}{\href{#3}{#2}}}\par\vspace{2pt}}
\newcommand{\address}[1]{\rcv@contact{\faMapMarker}{#1}{}}
\newcommand{\mobile}[1]{\rcv@contact{\faPhone}{#1}{}}
\newcommand{\email}[1]{\rcv@contact{\faEnvelope}{#1}{mailto:#1}}
\newcommand{\github}[1]{\rcv@contact{\faGithub}{#1}{https://github.com/#1}}
\newcommand{\linkedin}[1]{\rcv@contact{\faLinkedin}{#1}{https://www.linkedin.com/in/#1}}
\newcommand{\homepage}[1]{\rcv@contact{\faGlobe}{#1}{https://#1}}
\newcommand{\twitter}[1]{\rcv@contact{\faTwitter}{#1}{https://twitter.com/#1}}
\newcommand{\xing}[1]{\rcv@contact{\faXing}{#1}{}}
\newcommand{\stackoverflow}[2]{\rcv@contact{\faStackOverflow}{#2}{https://stackoverflow.com/users/#1/#2}}
\newcommand{\skype}[1]{\rcv@contact{\faSkype}{#1}{}}
\newcommand{\reddit}[1]{\rcv@contact{\faReddit}{#1}{https://www.reddit.com/user/#1}}
\newcommand{\extrainfo}[1]{\rcv@contact{\faInfoCircle}{#1}{}}
% generic contact line: \contactlink{icon}{text}{url}
\newcommand{\contactlink}[3]{\rcv@contact{#1}{#2}{#3}}

% Sidebar sections
\newcommand{\aboutmename}{About me}
\newcommand{\skillsname}{Skills}
\newcommand{\languagesname}{Languages}
\newcommand{\hobbiesname}{Hobbies}
\newcommand{\nonprofitname}{Non-profit}
\newcommand{\contactname}{Contact}
\newcommand{\aboutMe}[1]{\def\rcv@aboutme{#1}}
\def\rcv@parselabel label/#1\@nil{\def\rcv@skilllabel{#1}}
\NewDocumentCommand{\skillset}{o m}{\def\rcv@skills{#2}\IfValueT{#1}{\rcv@parselabel#1\@nil}}
\newcommand{\languages}[1]{\def\rcv@languages{#1}}
\newcommand{\hobbies}[1]{\def\rcv@hobbies{#1}}
\newcommand{\nonProfit}[1]{\def\rcv@nonprofit{#1}}
\NewDocumentCommand{\userSection}{O{} +m}{\appto\rcv@usersections{\rcv@sidesection{#1}#2\par\medskip}}

\newcommand{\rcv@sidesection}[1]{%
  \ifstrempty{#1}{}{{\color{highlight}\normalsize\bfseries\MakeUppercase{#1}}\par\vspace{1pt}%
  {\color{highlight}\rule{\linewidth}{0.6pt}}\par\vspace{3pt}}}

% \skillbar{name}{fraction 0..1}
\newcommand{\skillbar}[2]{%
  {\small #1}\par\vspace{1pt}%
  \begin{tikzpicture}
    \fill[lighttext] (0,0) rectangle (\linewidth,4pt);
    \fill[highlight] (0,0) rectangle (#2\linewidth,4pt);
  \end{tikzpicture}\par\vspace{3pt}}

\newcommand{\rcv@printphoto}{%
  \ifx\rcv@photo\@empty\else
    \IfFileExists{\rcv@photo}{\rcv@photobox}{%
      \IfFileExists{\rcv@photo.jpg}{\rcv@photobox}{%
        \IfFileExists{\rcv@photo.png}{\rcv@photobox}{\IfFileExists{\rcv@photo.pdf}{\rcv@photobox}{}}}}%
  \fi}
\newcommand{\rcv@hasopt}[1]{\edef\rcv@tmp{\noexpand\in@{#1}{\rcv@photoopts}}\rcv@tmp}
\newcommand{\rcv@photobox}{%
  {\centering
  \rcv@hasopt{circle}%
  \ifin@
    \rcv@hasopt{edge}%
    \ifin@
      \tikz\node[circle, draw=highlight, line width=1.5pt, inner sep=0pt, minimum size=\rcv@photosize,
        path picture={\node at (path picture bounding box.center)
          {\includegraphics[width=\rcv@photosize]{\rcv@photo}};}]{};%
    \else
      \tikz\node[circle, inner sep=0pt, minimum size=\rcv@photosize,
        path picture={\node at (path picture bounding box.center)
          {\includegraphics[width=\rcv@photosize]{\rcv@photo}};}]{};%
    \fi
  \else
    \includegraphics[width=\rcv@photosize]{\rcv@photo}%
  \fi
  \par}\vspace{8pt}}

\newlength{\rcv@sidex}
\newlength{\rcv@sideinner}
\NewDocumentCommand{\makecvsidebar}{o}{%
  \ifrcv@right
    \setlength{\rcv@sidex}{\dimexpr\paperwidth-\rcv@sidebarwidth+\rcv@sidepad\relax}%
  \else
    \setlength{\rcv@sidex}{\rcv@sidepad}%
  \fi
  \setlength{\rcv@sideinner}{\dimexpr\rcv@sidebarwidth-2\rcv@sidepad\relax}%
  \sbox\rcv@sidebox{\parbox[t]{\rcv@sideinner}{\rcv@sidecontent}}%
  \ifdim\dimexpr\ht\rcv@sidebox+\dp\rcv@sidebox\relax>\dimexpr\paperheight-2.4cm\relax
    \ClassWarningNoLine{ReCeiVe}{Sidebar content is taller than the page and is cut off.
      Move sections to the main column (cv.yaml meta.options.side_sections)}%
  \fi
  \begin{textblock*}{\rcv@sideinner}(\rcv@sidex, 1.2cm)
    \usebox\rcv@sidebox
  \end{textblock*}}

\newsavebox{\rcv@sidebox}
\newcommand{\rcv@sidecontent}{%
    \raggedright\color{text}
    \rcv@printphoto
    \ifx\rcv@contacts\@empty\else\rcv@sidesection{\contactname}\rcv@contacts\medskip\fi
    \ifx\rcv@aboutme\@empty\else\rcv@sidesection{\aboutmename}{\small\rcv@aboutme\par}\medskip\fi
    \ifx\rcv@skills\@empty\else
      \rcv@sidesection{\skillsname}%
      \foreach \rcv@n/\rcv@v in \rcv@skills {\skillbar{\rcv@n}{\rcv@v}}%
      \ifx\rcv@skilllabel\@empty\else{\scriptsize\color{graytext}\rcv@skilllabel\par}\fi
      \medskip
    \fi
    \ifx\rcv@languages\@empty\else
      \rcv@sidesection{\languagesname}%
      \foreach \rcv@l/\rcv@lv in \rcv@languages {{\small\textbf{\rcv@l}\hfill\rcv@lv\par}}%
      \medskip
    \fi
    \ifx\rcv@hobbies\@empty\else\rcv@sidesection{\hobbiesname}{\small\rcv@hobbies\par}\medskip\fi
    \ifx\rcv@nonprofit\@empty\else\rcv@sidesection{\nonprofitname}{\small\rcv@nonprofit\par}\medskip\fi
    \rcv@usersections}

%% ------------------------------------------------------------------ header and footer
\NewDocumentCommand{\makecvheader}{O{L}}{%
  \begingroup
  \ifstrequal{#1}{C}{\centering}{\ifstrequal{#1}{R}{\raggedleft}{\raggedright}}%
  {\color{darktext}\fontsize{26pt}{30pt}\selectfont \rcv@firstname\ \textbf{\rcv@lastname}\par}
  \ifx\rcv@position\@empty\else\vspace{4pt}{\color{highlight}\large\bfseries\rcv@position\par}\fi
  \ifx\rcv@headwords\@empty\else\vspace{2pt}{\color{graytext}\small\rcv@headwords\par}\fi
  \ifx\rcv@quote\@empty\else\vspace{6pt}{\color{graytext}\small\itshape\rcv@quote\par}\fi
  \endgroup
  \vspace{10pt}}

\newcommand{\makecvfooter}[3]{%
  \fancyhf{}%
  \renewcommand{\headrulewidth}{0pt}%
  \fancyfoot[L]{\footnotesize\color{graytext}#1}%
  \fancyfoot[C]{\footnotesize\color{graytext}#2}%
  \fancyfoot[R]{\footnotesize\color{graytext}#3}%
  \pagestyle{fancy}\thispagestyle{fancy}}
\pagestyle{empty}

%% ------------------------------------------------------------------ main column
\newcommand{\cvsection}[1]{%
  \par\addvspace{10pt}%
  {\color{highlight}\Large\bfseries #1}\par\vspace{1pt}%
  {\color{highlight}\rule{\linewidth}{1pt}}\par\vspace{4pt}}

% \cvevent{dates}{title}{organisation}{location}
\newcommand{\cvevent}[4]{%
  {\color{darktext}\bfseries #2}\hfill{\small\color{graytext}#1}\par
  \ifstrempty{#3#4}{}{{\color{highlight}#3}\hfill{\small\color{graytext}#4}\par}%
  \vspace{2pt}}

\setlist[itemize]{leftmargin=1.1em, topsep=2pt, itemsep=1pt, parsep=0pt, label={\color{highlight}\textbullet}}
\endinput
