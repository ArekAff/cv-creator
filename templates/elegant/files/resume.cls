%% resume.cls -- class for the "Elegant resume template" (cv-templates/Elegant_resume_template.tex).
%% The template's own resume.cls was not included, so this is a compatible reimplementation written for
%% CV Creator, following the structure of Trey Hunner's resume.cls (MIT licence) that the template extends.
%% Interface: \name, \printPersonalInfo, \personalInfo, \tag, \info, \infoSeparator,
%%            rSection, rSubsection{1}{2}{3}{4}, rSubsectionNoBullet{1}{2}{3}{4}.
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{resume}[2026/10/30 v1.0 resume class (CV Creator reimplementation)]
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax
\LoadClass[11pt]{article}

\RequirePackage{iftex}
\ifPDFTeX
  \RequirePackage[T1]{fontenc}
  \RequirePackage{lmodern}
\fi
\RequirePackage[parfill]{parskip}
\RequirePackage{array}
\RequirePackage{xcolor}
\pagestyle{empty}

%----------------------------------------------------------------------------------------
%  Name and personal information
%----------------------------------------------------------------------------------------
\def\@name{}
\def\name#1{\def\@name{#1}}
\def\namesize{\huge}
\def\nameskip{\medskip}

\def\printname{%
  \begingroup
    \centering{\namesize\bfseries\@name}\par
  \endgroup
  \nameskip
}
\AddToHook{begindocument/end}{\ifx\@name\@empty\else\printname\fi}

\newcommand{\printPersonalInfo}[1]{%
  \begingroup\centering\small #1\par\endgroup
  \smallskip
}
\newcommand{\personalInfo}[1]{#1\par}
\providecommand{\tag}{}
\renewcommand{\tag}[1]{\textbf{#1:}~}
\newcommand{\info}[1]{#1}
\newcommand{\infoSeparator}{\quad$\diamond$\quad}

%----------------------------------------------------------------------------------------
%  Sections
%----------------------------------------------------------------------------------------
\colorlet{sectioncolor}{black}
\def\sectionskip{\medskip}
\def\sectionlineskip{\smallskip}

\newenvironment{rSection}[1]{%
  \sectionskip
  {\color{sectioncolor}\MakeUppercase{\textbf{#1}}}\par
  \sectionlineskip
  {\color{sectioncolor}\hrule}
  \begin{list}{}{\setlength{\leftmargin}{1.5em}\setlength{\topsep}{4pt}}
  \item[]
}{%
  \end{list}
}

% \begin{rSubsection}{left, bold}{right}{second line left, italic}{second line right, italic}
\newcommand{\rSubsectionHead}[4]{%
  {\bfseries #1}\hfill{#2}%
  \if\relax\detokenize{#3#4}\relax\else\\{\em #3}\hfill{\em #4}\fi
  \smallskip
}
\newenvironment{rSubsection}[4]{%
  \rSubsectionHead{#1}{#2}{#3}{#4}%
  \begin{list}{$\cdot$}{\leftmargin=0em}%
    \itemsep -0.5em \vspace{-0.5em}%
}{%
  \end{list}%
  \vspace{0.5em}%
}
\newenvironment{rSubsectionNoBullet}[4]{%
  \rSubsectionHead{#1}{#2}{#3}{#4}%
  \begin{list}{}{\leftmargin=0em\labelwidth=0em\labelsep=0em}%
    \itemsep -0.5em \vspace{-0.5em}%
}{%
  \end{list}%
  \vspace{0.5em}%
}
\endinput
