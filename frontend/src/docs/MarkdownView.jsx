import React from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useNavigate } from "react-router-dom";
import { ExternalLink } from "lucide-react";
import { DOCS_RES, FILE_TO_SLUG, slugify } from "./docsData";

const nodeText = (children) => {
  if (children == null) return "";
  if (typeof children === "string" || typeof children === "number") return String(children);
  if (Array.isArray(children)) return children.map(nodeText).join("");
  if (children.props) return nodeText(children.props.children);
  return "";
};

const Heading = ({ level, children }) => {
  const id = slugify(nodeText(children));
  const Tag = `h${level}`;
  const sizes = {
    1: "text-3xl font-bold mt-2 mb-5 tracking-tight",
    2: "text-2xl font-semibold mt-10 mb-4 pb-2 border-b border-slate-200 tracking-tight",
    3: "text-xl font-semibold mt-8 mb-3",
    4: "text-lg font-semibold mt-6 mb-2",
    5: "text-base font-semibold mt-5 mb-2",
    6: "text-sm font-semibold mt-4 mb-2 text-slate-600",
  };
  return (
    <Tag id={id} className={`group scroll-mt-24 text-slate-900 font-['Space_Grotesk'] ${sizes[level]}`}>
      <a href={`#${id}`} className="no-underline">
        {children}
        <span className="ml-2 text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity">#</span>
      </a>
    </Tag>
  );
};

export const MarkdownView = ({ markdown }) => {
  const navigate = useNavigate();

  const DocLink = ({ href = "", children }) => {
    const isAnchor = href.startsWith("#");
    const isAbsolute = /^https?:\/\//i.test(href);
    const file = href.split("/").pop().split("#")[0];
    const hash = href.includes("#") ? "#" + href.split("#")[1] : "";
    const mdSlug = file && file.toLowerCase().endsWith(".md") ? FILE_TO_SLUG[file.toLowerCase()] : null;

    if (isAnchor) {
      return <a href={href} className="text-blue-600 hover:text-blue-700 underline underline-offset-2">{children}</a>;
    }
    if (mdSlug) {
      return (
        <a
          href={`/docs/${mdSlug}${hash}`}
          onClick={(e) => { e.preventDefault(); navigate(`/docs/${mdSlug}${hash}`); }}
          className="text-blue-600 hover:text-blue-700 underline underline-offset-2 cursor-pointer"
        >
          {children}
        </a>
      );
    }
    // Non-md relative file (e.g., openapi.yaml, postman_collection.json) → served resource.
    const target = isAbsolute ? href : `${DOCS_RES}/${href.replace(/^\.\//, "")}`;
    return (
      <a href={target} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-blue-600 hover:text-blue-700 underline underline-offset-2">
        {children}<ExternalLink className="h-3 w-3" />
      </a>
    );
  };

  return (
    <div className="text-[15px] leading-7 text-slate-700" data-testid="markdown-view">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <Heading level={1}>{children}</Heading>,
          h2: ({ children }) => <Heading level={2}>{children}</Heading>,
          h3: ({ children }) => <Heading level={3}>{children}</Heading>,
          h4: ({ children }) => <Heading level={4}>{children}</Heading>,
          h5: ({ children }) => <Heading level={5}>{children}</Heading>,
          h6: ({ children }) => <Heading level={6}>{children}</Heading>,
          a: DocLink,
          p: ({ children }) => <p className="my-4">{children}</p>,
          ul: ({ children }) => <ul className="my-4 ml-5 list-disc space-y-1.5 marker:text-slate-400">{children}</ul>,
          ol: ({ children }) => <ol className="my-4 ml-5 list-decimal space-y-1.5 marker:text-slate-400">{children}</ol>,
          li: ({ children }) => <li className="pl-1">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="my-4 border-l-4 border-blue-400 bg-blue-50/60 px-4 py-2 text-slate-700 rounded-r-lg">{children}</blockquote>
          ),
          hr: () => <hr className="my-8 border-slate-200" />,
          strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
          table: ({ children }) => (
            <div className="my-5 overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full text-sm border-collapse">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-slate-50">{children}</thead>,
          th: ({ children }) => <th className="text-left font-semibold text-slate-700 px-4 py-2.5 border-b border-slate-200">{children}</th>,
          td: ({ children }) => <td className="px-4 py-2.5 border-b border-slate-100 align-top">{children}</td>,
          pre: ({ children }) => (
            <pre className="my-5 overflow-x-auto rounded-xl bg-slate-950 border border-slate-800 p-4 text-[13px] leading-6 text-slate-100 font-mono">{children}</pre>
          ),
          code: ({ className, children }) => {
            const text = nodeText(children);
            const isBlock = /language-/.test(className || "") || text.includes("\n");
            if (isBlock) return <code className={`font-mono ${className || ""}`}>{children}</code>;
            return <code className="font-mono text-[13px] bg-slate-100 text-slate-800 rounded px-1.5 py-0.5">{children}</code>;
          },
          img: ({ src, alt }) => <img src={src} alt={alt} className="my-4 rounded-lg border border-slate-200 max-w-full" />,
        }}
      >
        {markdown}
      </Markdown>
    </div>
  );
};

// Extract headings (h2/h3) for the on-page TOC.
export const extractHeadings = (markdown) => {
  const lines = (markdown || "").split("\n");
  const out = [];
  let inFence = false;
  for (const line of lines) {
    if (/^```/.test(line.trim())) { inFence = !inFence; continue; }
    if (inFence) continue;
    const m = /^(#{2,3})\s+(.*)$/.exec(line);
    if (m) {
      const text = m[2].replace(/[#*`]/g, "").trim();
      out.push({ level: m[1].length, text, id: slugify(text) });
    }
  }
  return out;
};
