%% altacv.cls -- AltaCV-compatible CV class written for CV Creator.
%% AltaCV (LianTze Lim, LPPL 1.3c) is distributed through GitHub/Overleaf, not through CTAN or MiKTeX,
%% so this independent reimplementation provides the interface used by cv-templates/AltaCV_Template.tex:
%%   \name \tagline \photoR \photoL \personalinfo \email \phone \mailaddress \location \homepage \twitter
%%   \xtwitter \linkedin \github \orcid \printinfo \NewInfoField \makecvheader \cvsection \cvsubsection
%%   \cvevent \cvachievement \cvtag \cvskill \cvref \divider, the colour names and font hooks.
%% Not provided: \wheelchart and biblatex publication lists. To use the original class instead, place
%% its altacv.cls in templates/altacv/files/ (replacing this file).
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{altacv}[2026/10/30 v1.0 AltaCV-compatible CV class (CV Creator reimplementation)]

\newif\if@normalphoto
\DeclareOption{normalphoto}{\@normalphototrue}
\DeclareOption{withhyper}{}
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax
\LoadClass{article}

\RequirePackage{iftex}
\ifPDFTeX
  \RequirePackage[T1]{fontenc}
\else
  \RequirePackage{fontspec}
\fi
\RequirePackage{etoolbox}
\RequirePackage{geometry}
\RequirePackage[dvipsnames]{xcolor}
\RequirePackage{fontawesome5}
\RequirePackage{tikz}
\RequirePackage{dashrule}
\RequirePackage{multirow}
\RequirePackage{tabularx}
\RequirePackage{enumitem}
\RequirePackage{graphicx}
\RequirePackage{accsupp}
\RequirePackage[hidelinks]{hyperref}

\pagestyle{empty}
\setlength{\parindent}{0pt}
\raggedright

%% ------------------------------------------------------------------ colours and fonts
\colorlet{name}{black}
\colorlet{tagline}{black}
\colorlet{heading}{black}
\colorlet{headingrule}{black}
\colorlet{subheading}{black}
\colorlet{accent}{black}
\colorlet{emphasis}{black}
\colorlet{body}{black!80}
\AtBeginDocument{\color{body}}

\newcommand{\namefont}{\Huge\bfseries}
\newcommand{\taglinefont}{\large\bfseries}
\newcommand{\personalinfofont}{\footnotesize}
\newcommand{\cvsectionfont}{\LARGE\bfseries}
\newcommand{\cvsubsectionfont}{\large\bfseries}

\newcommand{\cvItemMarker}{\slash}
\newcommand{\cvRatingMarker}{\faCircle}
\newcommand{\cvDateMarker}{\faCalendar[regular]}
\newcommand{\cvLocationMarker}{\faMapMarker}
\newcommand{\locationname}{Location}
\newcommand{\datename}{Date}

\setlist{leftmargin=*,labelsep=0.5em,nosep,itemsep=0.25\baselineskip,after=\vspace{0.25\baselineskip}}
\setlist[itemize]{label=\cvItemMarker}

%% ------------------------------------------------------------------ header
\def\@name{}
\def\@tagline{}
\def\@personalinfo{}
\def\@photos{}
\def\altacv@photoside{R}
\newlength{\altacv@photowidth}
\providecommand{\name}{}
\renewcommand{\name}[1]{\def\@name{#1}}
\newcommand{\tagline}[1]{\def\@tagline{#1}}
\newcommand{\personalinfo}[1]{\def\@personalinfo{#1}}
\newcommand{\photoR}[2]{\setlength{\altacv@photowidth}{#1}\def\altacv@photoside{R}\def\@photos{#2}}
\newcommand{\photoL}[2]{\setlength{\altacv@photowidth}{#1}\def\altacv@photoside{L}\def\@photos{#2}}
\newcommand{\photo}[2]{\photoR{#1}{#2}}

% symbol, text shown, link target (may be empty)
\newcommand{\altacv@info}[3]{%
  \mbox{\textcolor{accent}{\normalfont #1}~\ifstrempty{#3}{#2}{\href{#3}{#2}}}\hspace{2em}}
\NewDocumentCommand{\printinfo}{m m o}{%
  \IfNoValueTF{#3}{\altacv@info{#1}{#2}{}}{\altacv@info{#1}{#2}{#3#2}}}
\NewDocumentCommand{\NewInfoField}{s m m o}{%
  \IfBooleanTF{#1}
    {\expandafter\NewDocumentCommand\csname #2\endcsname{m m}{\altacv@info{#3}{##1}{##2}}}
    {\IfNoValueTF{#4}
      {\expandafter\NewDocumentCommand\csname #2\endcsname{m}{\altacv@info{#3}{##1}{}}}
      {\expandafter\NewDocumentCommand\csname #2\endcsname{m}{\altacv@info{#3}{##1}{#4##1}}}}}

\NewInfoField{email}{\faAt}[mailto:]
\NewInfoField{mailaddress}{\faEnvelope}
\NewInfoField{phone}{\faPhone}
\NewInfoField{homepage}{\faGlobe}[https://]
\NewInfoField{twitter}{\faTwitter}[https://twitter.com/]
\NewInfoField{xtwitter}{\faTwitter}[https://x.com/]
\NewInfoField{linkedin}{\faLinkedin}[https://www.linkedin.com/in/]
\NewInfoField{github}{\faGithub}[https://github.com/]
\NewInfoField{orcid}{\faOrcid}[https://orcid.org/]
\NewInfoField{location}{\faMapMarker}

\newcommand{\altacv@headertext}{%
  {\color{name}\namefont\@name\par}%
  \ifx\@tagline\@empty\else\medskip{\color{tagline}\taglinefont\@tagline\par}\fi
  \ifx\@personalinfo\@empty\else\medskip{\personalinfofont\@personalinfo\par}\fi}

\newcommand{\altacv@photo}{%
  \if@normalphoto
    \includegraphics[width=\altacv@photowidth]{\@photos}%
  \else
    \tikz\node[circle, inner sep=0pt, minimum size=\altacv@photowidth,
      path picture={\node at (path picture bounding box.center)
        {\includegraphics[width=\altacv@photowidth]{\@photos}};}]{};%
  \fi}

\newcommand{\makecvheader}{%
  \begingroup
  \ifx\@photos\@empty
    \altacv@headertext
  \else
    \ifdefstring{\altacv@photoside}{L}{%
      \begin{minipage}[c]{\altacv@photowidth}\altacv@photo\end{minipage}\hfill
      \begin{minipage}[c]{\dimexpr\linewidth-\altacv@photowidth-1.5em\relax}\altacv@headertext\end{minipage}}{%
      \begin{minipage}[c]{\dimexpr\linewidth-\altacv@photowidth-1.5em\relax}\altacv@headertext\end{minipage}\hfill
      \begin{minipage}[c]{\altacv@photowidth}\altacv@photo\end{minipage}}%
  \fi
  \par\endgroup
  \medskip}

%% ------------------------------------------------------------------ body elements
\NewDocumentCommand{\cvsection}{o m}{%
  \par\addvspace{\bigskipamount}%
  {\color{heading}\cvsectionfont\MakeUppercase{#2}}\\[-1ex]%
  {\color{headingrule}\rule{\linewidth}{2pt}\par}\medskip}

\newcommand{\cvsubsection}[1]{%
  \smallskip{\color{subheading}\cvsubsectionfont #1\par}\medskip}

\newcommand{\divider}{\textcolor{body!30}{\hdashrule{\linewidth}{0.6pt}{0.5ex}}\medskip}

% \cvevent{title}{organisation}{dates}{location}
\newcommand{\cvevent}[4]{%
  {\large\color{emphasis}#1\par}
  \smallskip\normalsize
  \ifstrempty{#2}{}{\textbf{\color{accent}#2}\par\smallskip}
  \ifstrempty{#3}{}{{\small\makebox[0.5\linewidth][l]{%
    \BeginAccSupp{method=pdfstringdef,ActualText={\datename:}}\cvDateMarker\EndAccSupp{}~#3}}}%
  \ifstrempty{#4}{}{{\small\makebox[0.5\linewidth][l]{%
    \BeginAccSupp{method=pdfstringdef,ActualText={\locationname:}}\cvLocationMarker\EndAccSupp{}~#4}}}%
  \par\medskip\normalsize}

% \cvachievement{icon}{title}{description}
\newcommand{\cvachievement}[3]{%
  \begin{tabularx}{\linewidth}{@{}p{2em} @{\hspace{1ex}} >{\raggedright\arraybackslash}X@{}}
    \multirow{2}{*}{\Large\color{accent}#1} & \bfseries\textcolor{emphasis}{#2}\\
    & #3
  \end{tabularx}%
  \smallskip}

\newcommand{\cvtag}[1]{%
  \tikz[baseline]\node[anchor=base, draw=body!30, rounded corners, inner xsep=1ex, inner ysep=0.75ex,
    text height=1.5ex, text depth=.25ex]{#1};}

% \cvskill{name}{rating 0-5, halves allowed}
\newcommand{\cvskill}[2]{%
  \textcolor{emphasis}{\textbf{#1}}\hfill
  \BeginAccSupp{method=plain,ActualText={#2/5}}%
  \foreach \x in {1,...,5}{%
    \pgfmathsetmacro{\altacv@diff}{#2-\x}%
    \ifdim\altacv@diff pt>-0.01pt \textcolor{accent}{\cvRatingMarker}%
    \else\ifdim\altacv@diff pt>-0.51pt \textcolor{accent!40}{\cvRatingMarker}%
    \else\textcolor{body!25}{\cvRatingMarker}\fi\fi\hspace{0.15em}}%
  \EndAccSupp{}\par}

% \cvref{name}{institution}{email}{address}
\newcommand{\cvref}[4]{%
  \textcolor{emphasis}{\textbf{#1}}\par\smallskip
  {\small\ifstrempty{#2}{}{#2\par}\ifstrempty{#3}{}{\href{mailto:#3}{#3}\par}\ifstrempty{#4}{}{#4\par}}%
  \medskip}
\endinput
